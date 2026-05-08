"""Threads 실제 DOM 구조 확인 - JavaScript 렌더링 후"""
import asyncio, os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

async def debug():
    from playwright.async_api import async_playwright
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-sandbox"],
        )
        page = await ctx.new_page()

        # threads.com 으로 수정
        await page.goto("https://www.threads.com/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)  # JS 렌더링 대기

        print("URL:", page.url)

        # JavaScript로 실제 렌더링된 DOM 탐색
        result = await page.evaluate("""() => {
            const info = {};

            // 텍스트 있는 요소 탐색
            const allText = [];
            document.querySelectorAll('span, p, div').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t.length > 30 && t.length < 400 && el.children.length === 0) {
                    allText.push(t.slice(0, 100));
                }
            });
            info.texts = allText.slice(0, 8);

            // 링크 탐색
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href');
                if (h && (h.includes('/post/') || h.includes('@'))) links.push(h);
            });
            info.links = links.slice(0, 10);

            // 부모 구조 (게시글 컨테이너 후보)
            const containers = [];
            ['article','[role=article]','[data-pressable-container]',
             'div[tabindex="0"]'].forEach(sel => {
                containers.push(sel + ': ' + document.querySelectorAll(sel).length);
            });
            info.containers = containers;

            return info;
        }""")

        print("\n게시글 텍스트 샘플:")
        for t in result.get("texts", []):
            print(f"  {t}")

        print("\n링크 샘플:")
        for l in result.get("links", []):
            print(f"  {l}")

        print("\n컨테이너 후보:")
        for c in result.get("containers", []):
            print(f"  {c}")

        # 렌더링 후 HTML 저장
        html = await page.content()
        with open("threads_debug2.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nHTML 저장: {len(html):,}자")

        input("확인 후 엔터...")
        await ctx.close()

asyncio.run(debug())
