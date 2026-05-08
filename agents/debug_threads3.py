"""게시글 컨테이너 셀렉터 탐색"""
import asyncio, os, sys
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

async def debug():
    from playwright.async_api import async_playwright
    profile_path = os.getenv("CHROME_PROFILE_PATH", "C:/Chrome_Profile_Archive")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path, headless=True,
            args=["--no-sandbox"],
        )
        page = await ctx.new_page()
        await page.goto("https://www.threads.com/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        result = await page.evaluate("""() => {
            // 텍스트가 있는 span 하나를 골라서 부모 체인 확인
            let sample = null;
            for (const span of document.querySelectorAll('span')) {
                const t = (span.innerText||'').trim();
                if (t.length > 40 && t.length < 200 && span.children.length === 0) {
                    sample = span; break;
                }
            }
            if (!sample) return {error: 'no sample found'};

            // 부모 체인 (최대 10단계)
            const chain = [];
            let el = sample;
            for (let i = 0; i < 10; i++) {
                if (!el || el === document.body) break;
                const attrs = {};
                if (el.getAttribute('role')) attrs.role = el.getAttribute('role');
                if (el.getAttribute('data-testid')) attrs.testid = el.getAttribute('data-testid');
                if (el.getAttribute('tabindex')) attrs.tabindex = el.getAttribute('tabindex');
                const cls = el.className && typeof el.className === 'string'
                    ? el.className.slice(0, 80) : '';
                chain.push({
                    tag: el.tagName,
                    attrs: attrs,
                    cls: cls
                });
                el = el.parentElement;
            }

            // 링크 href 패턴
            const postLinks = [];
            document.querySelectorAll('a').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (h.includes('/post/') || (h.match(/^\/@[^/]+\//) )) postLinks.push(h);
            });

            // 좋아요 버튼
            const likeButtons = [];
            document.querySelectorAll('button, [role=button]').forEach(btn => {
                const lbl = btn.getAttribute('aria-label') || '';
                const txt = (btn.innerText || '').toLowerCase();
                if (lbl.toLowerCase().includes('like') || txt.includes('like') || lbl.includes('좋아요')) {
                    likeButtons.push({label: lbl, text: txt.slice(0,30)});
                }
            });

            return {
                sampleText: sample.innerText.slice(0, 80),
                chain: chain,
                postLinks: postLinks.slice(0, 5),
                likeButtons: likeButtons.slice(0, 5)
            };
        }""")

        out = []
        out.append(f"샘플 텍스트: {result.get('sampleText','')}")
        out.append("\n부모 체인:")
        for i, c in enumerate(result.get("chain", [])):
            out.append(f"  [{i}] {c['tag']} role={c['attrs'].get('role','')} testid={c['attrs'].get('testid','')} tabindex={c['attrs'].get('tabindex','')} class={c['cls'][:60]}")
        out.append("\n게시글 링크:")
        for l in result.get("postLinks", []):
            out.append(f"  {l}")
        out.append("\n좋아요 버튼:")
        for b in result.get("likeButtons", []):
            out.append(f"  label={b['label']} text={b['text']}")

        # ASCII 안전하게 출력
        for line in out:
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode('ascii', errors='replace').decode())

        await ctx.close()

asyncio.run(debug())
