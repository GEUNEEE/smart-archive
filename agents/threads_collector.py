"""
Threads 수집기 (Playwright)
로그인된 Chrome 프로필 세션을 재사용합니다.
첫 실행 전에 CHROME_PROFILE_PATH 경로의 Chrome에서 threads.net 로그인을 완료하세요.
"""
import asyncio
import os
import re
from datetime import datetime

from playwright.async_api import async_playwright


async def collect_threads(max_items: int = None) -> list[dict]:
    max_items = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    min_likes = int(os.getenv("MIN_LIKES", "500"))
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    items = []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        try:
            await page.goto("https://www.threads.net/", wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(3000)

            if "login" in page.url.lower() or await page.query_selector('input[type="password"]'):
                raise RuntimeError(
                    "Threads 로그인이 필요합니다.\n"
                    f"Chrome을 열어 threads.net에 로그인한 뒤 다시 실행하세요.\n"
                    f"프로필 경로: {profile_path}"
                )

            collected_urls: set[str] = set()
            scroll_round = 0

            while len(items) < max_items and scroll_round < 12:
                # 게시글 카드 (구조가 바뀌면 아래 셀렉터를 threads.net 소스에서 확인)
                posts = await page.query_selector_all("div[role='article'], article")

                for post in posts:
                    if len(items) >= max_items:
                        break
                    try:
                        # 본문 텍스트
                        text_el = await post.query_selector(
                            "div[dir='auto'] span, div[class*='x1iorvi4'] span"
                        )
                        text = (await text_el.inner_text()).strip() if text_el else ""
                        if len(text) < 20:
                            continue

                        # 퍼머링크
                        link_el = await post.query_selector("a[href*='/t/']")
                        url = ""
                        if link_el:
                            href = await link_el.get_attribute("href") or ""
                            url = (
                                f"https://www.threads.net{href}"
                                if href.startswith("/")
                                else href
                            )
                        if url in collected_urls:
                            continue
                        collected_urls.add(url)

                        # 좋아요 수 (aria-label 방식)
                        likes = 0
                        like_btn = await post.query_selector(
                            "button[aria-label*='like'], button[aria-label*='좋아요']"
                        )
                        if like_btn:
                            label = await like_btn.get_attribute("aria-label") or ""
                            nums = re.findall(r"[\d,]+", label)
                            if nums:
                                likes = int(nums[0].replace(",", ""))

                        if likes < min_likes:
                            continue

                        # 작성자
                        author_el = await post.query_selector("a[href*='/@'] span")
                        author = (await author_el.inner_text()).strip() if author_el else ""

                        items.append(
                            _make_item(
                                channel="스레드",
                                title=text[:80] + ("..." if len(text) > 80 else ""),
                                content=text,
                                author=author,
                                url=url,
                                likes=likes,
                            )
                        )
                    except Exception:
                        continue

                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await page.wait_for_timeout(2500)
                scroll_round += 1

        finally:
            await ctx.close()

    return items


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


# 구매/판매 키워드가 있으면 판매글로 자동 분류
_SALES_KEYWORDS = ["구매", "신청", "한정", "마감", "가격", "할인", "무료", "클릭", "링크"]


def _guess_type(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in _SALES_KEYWORDS):
        return "판매글"
    return "바이럴"


if __name__ == "__main__":
    results = asyncio.run(collect_threads())
    print(f"Threads 수집: {len(results)}개")
    for r in results[:3]:
        print(f"  [{r['likes']}좋아요] {r['title'][:50]}")
