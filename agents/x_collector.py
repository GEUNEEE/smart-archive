"""
X (Twitter) 수집기 (Playwright)
- 홈피드 + 트렌딩 + 키워드 검색(Top) 수집
- 조회수 50만 이상 필터 (MIN_VIEWS_X)
- 로그인된 Chrome 프로필 세션 재사용
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from threads_collector import _make_item

load_dotenv(Path(__file__).parent / ".env")


async def collect_x(max_items: int = None) -> list[dict]:
    max_items   = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    min_views   = int(os.getenv("MIN_VIEWS_X", "500000"))
    min_likes   = int(os.getenv("MIN_LIKES", "1000"))   # views=0일 때 대체 기준
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    keywords = [
        k.strip()
        for k in os.getenv("SNS_KEYWORDS", "마케팅,퍼스널브랜딩").split(",")
        if k.strip()
    ]

    # 수집 페이지 목록: (이름, URL, 최대 스크롤 횟수)
    collect_pages = [
        ("홈피드",  "https://x.com/home",                    20),
        ("트렌딩",  "https://x.com/explore/tabs/trending",   15),
    ]
    for kw in keywords:
        collect_pages.append((
            f"검색:{kw}",
            f"https://x.com/search?q={quote(kw)}&src=typed_query&f=top",
            10,
        ))

    items: list[dict] = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = await ctx.new_page()

        try:
            # 로그인 확인
            await page.goto("https://x.com/home", wait_until="load", timeout=30_000)
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=15_000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)

            if "login" in page.url.lower() or await page.query_selector('input[name="text"]'):
                raise RuntimeError(
                    "X 로그인이 필요합니다.\n"
                    "run_login_chrome.bat 실행 후 x.com에 로그인하세요."
                )

            seen_urls: set[str] = set()

            for page_name, page_url, max_scroll in collect_pages:
                if len(items) >= max_items:
                    break

                if page.url.split("?")[0] != page_url.split("?")[0]:
                    await page.goto(page_url, wait_until="load", timeout=30_000)
                    try:
                        await page.wait_for_selector('article[data-testid="tweet"]', timeout=10_000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(2000)

                scroll_round = 0

                while len(items) < max_items and scroll_round < max_scroll:
                    posts = await page.evaluate(_EXTRACT_POSTS_JS)

                    for post in posts:
                        url = post.get("url", "")
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        text = post.get("text", "").strip()
                        if len(text) < 15:
                            continue

                        views  = int(post.get("views", 0))
                        likes  = int(post.get("likes", 0))

                        # 조회수 필터: views 있으면 50만 이상, 없으면 좋아요 기준
                        if views > 0:
                            if views < min_views:
                                continue
                        else:
                            if likes < min_likes:
                                continue

                        items.append(_make_item(
                            channel="X",
                            title=text[:80] + ("..." if len(text) > 80 else ""),
                            content=text,
                            author=post.get("author", ""),
                            url=url,
                            views=views,
                            likes=likes,
                            comments=int(post.get("comments", 0)),
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


_EXTRACT_POSTS_JS = """() => {
    const results = [];
    const seen = new Set();

    document.querySelectorAll('article[data-testid="tweet"]').forEach(article => {
        try {
            // 본문 텍스트
            const textEl = article.querySelector('div[data-testid="tweetText"]');
            const text = (textEl ? textEl.innerText : '').trim();
            if (!text || text.length < 15) return;

            // 퍼머링크
            const linkEl = article.querySelector('a[href*="/status/"]');
            const href = linkEl ? linkEl.getAttribute('href') : '';
            const url = href ? (href.startsWith('http') ? href : 'https://x.com' + href) : '';
            if (!url || seen.has(url)) return;
            seen.add(url);

            // 작성자
            const userEl = article.querySelector('div[data-testid="User-Name"] a');
            const author = userEl ? (userEl.innerText || '').trim() : '';

            // 통계 (aria-label 파싱)
            const parseCount = (testid) => {
                const btn = article.querySelector('[data-testid="' + testid + '"]');
                if (!btn) return 0;
                const lbl = btn.getAttribute('aria-label') || btn.innerText || '';
                const m = lbl.replace(/,/g,'').match(/\\d+/);
                return m ? parseInt(m[0]) : 0;
            };
            const likes    = parseCount('like');
            const comments = parseCount('reply');

            // 조회수 (analytics 링크)
            let views = 0;
            const analyticsEl = article.querySelector('a[href*="/analytics"]');
            if (analyticsEl) {
                const lbl = analyticsEl.getAttribute('aria-label') || analyticsEl.innerText || '';
                const m = lbl.replace(/,/g,'').match(/\\d+/);
                if (m) views = parseInt(m[0]);
            }

            results.push({ url, text: text.slice(0, 500), author, likes, comments, views });
        } catch(e) {}
    });

    return results;
}"""


if __name__ == "__main__":
    results = asyncio.run(collect_x())
    print(f"X 수집: {len(results)}개")
    for r in results[:5]:
        try:
            views_str = f"{r['views']:,}" if r['views'] else "N/A"
            print(f"  [{r['likes']:,}likes | {views_str}views] {r['title'][:60]}")
        except UnicodeEncodeError:
            print(f"  [{r['likes']}likes] (encoding error)")
