import asyncio, os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

async def debug():
    from playwright.async_api import async_playwright
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path, headless=True, args=["--no-sandbox"],
        )
        page = await ctx.new_page()
        await page.goto("https://www.threads.com/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # 1) a[href*="/post/"] 개수
        cnt = await page.evaluate("() => document.querySelectorAll('a[href*=\"/post/\"]').length")
        print(f"a[href*='/post/'] 개수: {cnt}")

        # 2) 첫번째 링크 href 확인
        first = await page.evaluate("""() => {
            const a = document.querySelector('a[href*="/post/"]');
            return a ? a.getAttribute('href') : 'none';
        }""")
        print(f"첫번째 링크: {first}")

        # 3) 모든 a 태그 href 샘플
        all_hrefs = await page.evaluate("""() => {
            const hrefs = [];
            document.querySelectorAll('a[href]').forEach(a => {
                hrefs.push(a.getAttribute('href'));
            });
            return hrefs.slice(0, 20);
        }""")
        print("\n전체 a href 샘플:")
        for h in all_hrefs:
            print(f"  {h}")

        # 4) span[dir=auto] 개수와 텍스트
        spans = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('span[dir="auto"]').forEach(span => {
                const t = (span.innerText || '').trim();
                if (t.length > 20) results.push(t.slice(0, 80));
            });
            return results.slice(0, 8);
        }""")
        print(f"\nspan[dir=auto] 텍스트:")
        for s in spans:
            try: print(f"  {s}")
            except: print(f"  [encoding error]")

        await ctx.close()

asyncio.run(debug())
