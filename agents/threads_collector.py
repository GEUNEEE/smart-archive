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

            # 홈피드 + 탐색(추천) 탭 두 곳 수집
            collect_pages = [
                ("홈피드", "https://www.threads.com/"),
                ("탐색",   "https://www.threads.com/explore/"),
            ]

            for page_name, page_url in collect_pages:
                if len(items) >= max_items:
                    break

                if page.url.rstrip("/") != page_url.rstrip("/"):
                    await page.goto(page_url, wait_until="load", timeout=30_000)
                    try:
                        await page.wait_for_selector('a[href*="/post/"]', timeout=10_000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(3000)

                scroll_round = 0

                while len(items) < max_items and scroll_round < 20:
                    posts = await page.evaluate(_EXTRACT_POSTS_JS)

                    for post in posts:
                        href = post.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        text = post.get("text", "").strip()
                        if len(text) < 20:
                            continue

                        likes = int(post.get("likes", 0))
                        if likes < min_likes:
                            continue

                        author = post.get("author", "")
                        url = f"https://www.threads.com{href}" if href.startswith("/") else href

                        items.append(_make_item(
                            channel="스레드",
                            title=text[:80] + ("..." if len(text) > 80 else ""),
                            content=text,
                            author=author,
                            url=url,
                            likes=likes,
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

        // 좋아요 — innerText 패턴
        let likes = 0;
        const containerText = (container.innerText || '');
        const likeMatch = containerText.match(/(\\d[\\d,]*)\\s*(?:like|좋아요)/i);
        if (likeMatch) likes = parseInt(likeMatch[1].replace(/,/g, ''));

        results.push({ href, text: text.slice(0, 500), author, likes });
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
