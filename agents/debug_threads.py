"""Threads 페이지 구조 디버그 - 실제 셀렉터 확인용"""
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

async def debug():
    from playwright.async_api import async_playwright

    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,  # 화면 보이게
            args=["--no-sandbox"],
        )
        page = await ctx.new_page()
        await page.goto("https://www.threads.net/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)

        print(f"현재 URL: {page.url}")
        print(f"로그인 여부: {'login' not in page.url.lower()}")

        # 페이지에서 게시글처럼 보이는 요소 찾기
        candidates = [
            "article",
            "div[role='article']",
            "div[data-pressable-container]",
            "div[class*='x1yztbdb']",
        ]
        for sel in candidates:
            els = await page.query_selector_all(sel)
            print(f"  셀렉터 '{sel}': {len(els)}개")

        # 페이지 HTML 일부 저장 (구조 파악용)
        html = await page.content()
        with open("threads_debug.html", "w", encoding="utf-8") as f:
            f.write(html[:50000])
        print("\nthreads_debug.html 저장됨 (앞 50KB)")

        # 텍스트가 있는 div 샘플
        texts = await page.evaluate("""() => {
            const divs = document.querySelectorAll('div[dir="auto"]');
            const results = [];
            for (const d of divs) {
                const t = d.innerText.trim();
                if (t.length > 30 && t.length < 300) results.push(t.slice(0, 80));
                if (results.length >= 5) break;
            }
            return results;
        }""")
        print("\n게시글 텍스트 샘플:")
        for t in texts:
            print(f"  → {t}")

        await ctx.close()

asyncio.run(debug())
