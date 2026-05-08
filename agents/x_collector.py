"""
X (Twitter) 수집기 (Playwright)
로그인된 Chrome 프로필 세션을 재사용합니다.
X API는 2023년부터 유료화 — Playwright 브라우저 방식으로 대체합니다.
"""
import asyncio
import os
import re
from datetime import datetime

from playwright.async_api import async_playwright

from threads_collector import _make_item, _guess_type


async def collect_x(max_items: int = None) -> list[dict]:
    max_items = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    min_likes = int(os.getenv("MIN_LIKES", "500"))
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
            # 추천 탭 (For You) — 알고리즘 바이럴 피드
            await page.goto("https://x.com/home", wait_until="networkidle", timeout=30_000)
            await page.wait_for_timeout(3000)

            if "login" in page.url.lower() or await page.query_selector('input[name="text"]'):
                raise RuntimeError(
                    "X 로그인이 필요합니다.\n"
                    f"Chrome을 열어 x.com에 로그인한 뒤 다시 실행하세요.\n"
                    f"프로필 경로: {profile_path}"
                )

            collected_urls: set[str] = set()
            scroll_round = 0

            while len(items) < max_items and scroll_round < 12:
                # X 트윗 아티클 셀렉터 (2024 기준 — 바뀌면 x.com 소스 확인)
                tweets = await page.query_selector_all("article[data-testid='tweet']")

                for tweet in tweets:
                    if len(items) >= max_items:
                        break
                    try:
                        # 본문
                        text_el = await tweet.query_selector(
                            "div[data-testid='tweetText']"
                        )
                        text = (await text_el.inner_text()).strip() if text_el else ""
                        if len(text) < 20:
                            continue

                        # 퍼머링크
                        link_el = await tweet.query_selector(
                            "a[href*='/status/']"
                        )
                        url = ""
                        if link_el:
                            href = await link_el.get_attribute("href") or ""
                            url = (
                                f"https://x.com{href}"
                                if href.startswith("/")
                                else href
                            )
                        if url in collected_urls:
                            continue
                        collected_urls.add(url)

                        # 좋아요
                        likes = _parse_count(
                            await _get_aria(tweet, "[data-testid='like']")
                        )
                        if likes < min_likes:
                            continue

                        # 조회수 (Views)
                        views = _parse_count(
                            await _get_aria(tweet, "a[href*='/analytics']")
                        )

                        # 댓글
                        comments = _parse_count(
                            await _get_aria(tweet, "[data-testid='reply']")
                        )

                        # 작성자 핸들
                        user_el = await tweet.query_selector(
                            "div[data-testid='User-Name'] a"
                        )
                        author = ""
                        if user_el:
                            author = (await user_el.inner_text()).strip()

                        items.append(
                            _make_item(
                                channel="X",
                                title=text[:80] + ("..." if len(text) > 80 else ""),
                                content=text,
                                author=author,
                                url=url,
                                views=views,
                                likes=likes,
                                comments=comments,
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


async def _get_aria(el, selector: str) -> str:
    try:
        btn = await el.query_selector(selector)
        if btn:
            return await btn.get_attribute("aria-label") or ""
        return ""
    except Exception:
        return ""


def _parse_count(aria_label: str) -> int:
    """'1,234 Likes' 또는 '5만 좋아요' 형식에서 숫자 추출"""
    if not aria_label:
        return 0
    # 한국어 단위 처리
    aria_label = aria_label.replace("만", "0000").replace("천", "000")
    nums = re.findall(r"[\d,]+", aria_label.replace(",", ""))
    return int(nums[0]) if nums else 0


if __name__ == "__main__":
    results = asyncio.run(collect_x())
    print(f"X 수집: {len(results)}개")
    for r in results[:3]:
        print(f"  [{r['likes']}좋아요 | {r['views']}조회] {r['title'][:50]}")
