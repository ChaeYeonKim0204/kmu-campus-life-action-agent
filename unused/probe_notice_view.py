"""Probe v3: investigate notice 11798 (internship) — body got truncated.

We expect this notice to have a tables/images/long body, but .view_cont gave
only 344 chars starting at '※ 참고사항'. Look at what's INSIDE .view_cont
and what got missed.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright


URL = "https://www.kookmin.ac.kr/user/kmuNews/notice/4/11798/view.do?currentPageNo=1"

CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=CHROME_UA, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(".board_view", state="attached", timeout=10000)
        page.wait_for_timeout(2000)

        # 1. .view_cont's structure
        print("--- .view_cont children ---")
        kids = page.evaluate("""
            () => {
                const root = document.querySelector('.board_view .view_cont');
                if (!root) return null;
                return Array.from(root.children).map(c => ({
                    tag: c.tagName.toLowerCase(),
                    cls: c.className || '',
                    textLen: (c.innerText || '').length,
                    textPreview: (c.innerText || '').substring(0, 100),
                    hasImg: c.querySelector('img') ? true : false,
                    hasTable: c.querySelector('table') ? true : false,
                }));
            }
        """)
        if kids:
            for i, k in enumerate(kids):
                print(f"  [{i}] <{k['tag']} class={k['cls']!r}> "
                      f"textLen={k['textLen']} img={k['hasImg']} table={k['hasTable']}")
                print(f"      preview: {k['textPreview']!r}")
        else:
            print("  .view_cont not found!")

        # 2. raw HTML of .view_cont (first 2000 chars)
        print("\n--- .view_cont innerHTML (first 2500 chars) ---")
        html = page.evaluate("""
            () => {
                const root = document.querySelector('.board_view .view_cont');
                return root ? root.innerHTML : null;
            }
        """)
        if html:
            print(html[:2500])

        # 3. inner_text vs textContent vs full HTML length
        print("\n--- size comparisons ---")
        sizes = page.evaluate("""
            () => {
                const r = document.querySelector('.board_view .view_cont');
                if (!r) return null;
                return {
                    innerText: (r.innerText || '').length,
                    textContent: (r.textContent || '').length,
                    innerHTML: (r.innerHTML || '').length,
                };
            }
        """)
        print(f"  {sizes}")

        # 4. Is there an image-heavy body?
        print("\n--- Images in .view_cont ---")
        imgs = page.evaluate("""
            () => {
                const r = document.querySelector('.board_view .view_cont');
                if (!r) return null;
                const imgs = r.querySelectorAll('img');
                return Array.from(imgs).map(im => ({
                    src: im.src.substring(0, 100),
                    alt: im.alt,
                }));
            }
        """)
        if imgs:
            print(f"  Found {len(imgs)} images")
            for im in imgs[:5]:
                print(f"    src={im['src']!r} alt={im['alt']!r}")

        browser.close()


if __name__ == "__main__":
    main()
