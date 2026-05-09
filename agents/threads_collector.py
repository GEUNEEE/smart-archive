"""
Threads 수집기 (Playwright)
도메인: threads.com (2025년 변경)
로그인된 Chrome 프로필 세션 재사용
"""
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(Path(__file__).parent / ".env")


async def collect_threads(max_items: int = None) -> list[dict]:
    max_items = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    min_likes = 0  # Threads는 좋아요 수 미표시 — 필터 없음
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    items = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = await ctx.new_page()

        try:
            await page.goto("https://www.threads.com/", wait_until="load", timeout=30_000)
            try:
                await page.wait_for_selector('a[href*="/post/"]', timeout=10_000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)

            if "login" in page.url.lower():
                raise RuntimeError(
                    "Threads 로그인이 필요합니다.\n"
                    "run_login_chrome.bat 실행 후 threads.com에 로그인하세요."
                )

            seen_urls: set[str] = set()

            keywords = [
                k.strip()
                for k in os.getenv("SNS_KEYWORDS", "마케팅,퍼스널브랜딩").split(",")
                if k.strip()
            ]

            # 홈피드 + 탐색 + 키워드 검색
            collect_pages = [
                ("홈피드", "https://www.threads.com/",          20),
                ("탐색",   "https://www.threads.com/explore/",  15),
            ]
            for kw in keywords:
                collect_pages.append((
                    f"검색:{kw}",
                    f"https://www.threads.com/search/?q={quote(kw)}",
                    10,
                ))

            for page_name, page_url, max_scroll in collect_pages:
                if len(items) >= max_items:
                    break

                cur = page.url.split("?")[0].rstrip("/")
                tgt = page_url.split("?")[0].rstrip("/")
                if cur != tgt:
                    await page.goto(page_url, wait_until="load", timeout=30_000)
                    try:
                        await page.wait_for_selector('a[href*="/post/"]', timeout=10_000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)

                scroll_round = 0

                while len(items) < max_items and scroll_round < max_scroll:
                    posts = await page.evaluate(_EXTRACT_POSTS_JS)

                    for post in posts:
                        href = post.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        text = post.get("text", "").strip()
                        if len(text) < 20:
                            continue

                        likes    = int(post.get("likes", 0))
                        comments = int(post.get("comments", 0))

                        author = post.get("author", "")
                        url = f"https://www.threads.com{href}" if href.startswith("/") else href

                        items.append(_make_item(
                            channel="스레드",
                            title=text[:80] + ("..." if len(text) > 80 else ""),
                            content=text,
                            author=author,
                            url=url,
                            likes=likes,
                            comments=comments,
                        ))

                        if len(items) >= max_items:
                            break

                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    await page.wait_for_timeout(2000)
                    scroll_round += 1

                    if scroll_round % 10 == 0:
                        await page.wait_for_timeout(2000)

        finally:
            await ctx.close()

    return items


# 게시글 추출 JS — 텍스트 span 기반 (위로 탐색해 /post/ 링크 찾기)
_EXTRACT_POSTS_JS = """() => {
    const results = [];
    const seen = new Set();

    // span[dir=auto] 에서 시작해서 부모 중에 /post/ 링크가 있는 컨테이너 찾기
    document.querySelectorAll('span[dir="auto"]').forEach(span => {
        const text = (span.innerText || '').trim();
        // 너무 짧거나, URL처럼 보이거나, 사용자명처럼 보이는 것 제외
        if (text.length < 25 || text.startsWith('http') || text.startsWith('@')) return;

        // 위로 올라가며 /post/ 링크 찾기
        let container = span.parentElement;
        let postLink = null;
        for (let i = 0; i < 20; i++) {
            if (!container || container.tagName === 'BODY') break;
            const link = container.querySelector('a[href*="/post/"]');
            if (link) { postLink = link; break; }
            container = container.parentElement;
        }
        if (!postLink) return;

        const href = postLink.getAttribute('href');
        if (!href || seen.has(href)) return;
        seen.add(href);

        // 작성자: href 패턴 /@username/post/...
        const m = href.match(/^\\/?([@]?[^/]+)\\/post\\//);
        let author = '';
        if (m) {
            author = '@' + m[1].replace(/^@/, '');
        }
        // 또는 컨테이너 내 @계정명 링크
        if (!author) {
            const userLink = container.querySelector('a[href^="/@"]');
            if (userLink) author = (userLink.innerText || '').trim();
        }

        // 좋아요 / 댓글 — 다중 전략
        let likes = 0, comments = 0;

        // 전략 1: aria-label 에 숫자가 있는 버튼/역할 요소
        container.querySelectorAll('[role="button"], button, [aria-label]').forEach(el => {
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const m = aria.match(/(\\d[\\d,]+)/);
            const n = m ? parseInt(m[1].replace(/,/g,'')) : 0;
            if (n > 0) {
                if (/like|좋아요|heart/i.test(aria)) likes = Math.max(likes, n);
                if (/repl|comment|댓글|reply/i.test(aria)) comments = Math.max(comments, n);
            }
        });

        // 전략 2: innerText 패턴 (likes / 좋아요 / replies / 댓글)
        if (!likes || !comments) {
            const txt = container.innerText || '';
            if (!likes) {
                const m = txt.match(/(\\d[\\d,]*)\\s*(?:like|likes|좋아요)/i);
                if (m) likes = parseInt(m[1].replace(/,/g,''));
            }
            if (!comments) {
                const m = txt.match(/(\\d[\\d,]*)\\s*(?:repl|replies|comment|댓글)/i);
                if (m) comments = parseInt(m[1].replace(/,/g,''));
            }
        }

        // 전략 3: 숫자만 있는 작은 span — 하트 아이콘 옆
        if (!likes) {
            const svgs = container.querySelectorAll('svg');
            svgs.forEach(svg => {
                const ariaLabel = (svg.getAttribute('aria-label') || svg.closest('[aria-label]')?.getAttribute('aria-label') || '').toLowerCase();
                if (/like|heart|좋아요/.test(ariaLabel)) {
                    let el = svg.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (!el) break;
                        const numMatch = (el.innerText || '').match(/^(\\d[\\d,]*)$/);
                        if (numMatch) { likes = parseInt(numMatch[1].replace(/,/g,'')); break; }
                        const sib = el.nextElementSibling;
                        if (sib) { const nm = (sib.innerText || '').match(/^(\\d[\\d,]*)$/); if (nm) { likes = parseInt(nm[1].replace(/,/g,'')); break; } }
                        el = el.parentElement;
                    }
                }
            });
        }

        results.push({ href, text: text.slice(0, 500), author, likes, comments });
    });

    return results;
}"""


def _make_item(channel, title, content, author, url, views=0, likes=0, comments=0) -> dict:
    return {
        "channel": channel,
        "type": _guess_type(content),
        "title": title,
        "content": content,
        "author": author,
        "url": url,
        "views": views,
        "likes": likes,
        "comments": comments,
        "collectedAt": datetime.now().strftime("%Y-%m-%d"),
        "originalDate": datetime.now().strftime("%Y-%m-%d"),
        "tags": [],
        "aiSummary": "",
        "myMemo": "",
        "isBest": False,
        "isPublished": False,
        "publishedAt": None,
    }


_SALES_KEYWORDS = ["구매", "신청", "한정", "마감", "가격", "할인", "무료", "클릭", "링크"]


def _guess_type(text: str) -> str:
    if any(k in text for k in _SALES_KEYWORDS):
        return "판매글"
    return "바이럴"


if __name__ == "__main__":
    results = asyncio.run(collect_threads())
    print(f"Threads 수집: {len(results)}개")
    for r in results[:5]:
        try:
            print(f"  [{r['likes']}좋아요] {r['title'][:60]}")
        except UnicodeEncodeError:
            print(f"  [{r['likes']}likes] {r['title'][:60].encode('ascii','replace').decode()}")
