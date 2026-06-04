"""Probe v5: confirm pagination via URL parameter works.

Run with kmu-agent conda env activated:
    python scripts/probe_notice_page.py
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright


BASE = "https://www.kookmin.ac.kr/user/kmuNews/notice/4/index.do"

CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def first_general_title_and_date(page) -> tuple[str, str]:
    """Grab the first general (non-pinned) notice on the current page."""
    # General items have no 'notice' class (also includes 'last' on the last row).
    # Use JS to find first <li> under board_list that lacks 'notice' class.
    result = page.evaluate("""
        () => {
            const items = document.querySelectorAll('div.board_list ul li');
            for (const li of items) {
                if (!li.classList.contains('notice')) {
                    const t = li.querySelector('p.title');
                    const d = li.querySelector('div.board_etc span');
                    return {
                        title: t ? t.innerText.trim() : null,
                        date: d ? d.innerText.trim() : null,
                    };
                }
            }
            return null;
        }
    """)
    if not result:
        return ("(none)", "(none)")
    return (result.get("title") or "(no title)", result.get("date") or "(no date)")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=CHROME_UA, locale="ko-KR")
        page = context.new_page()

        for page_no in [1, 2, 3]:
            url = f"{BASE}?currentPageNo={page_no}"
            print(f"\n=== Page {page_no}: {url} ===")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("div.board_list", state="attached", timeout=15000)
            page.wait_for_timeout(1500)

            title, date = first_general_title_and_date(page)
            print(f"  first general notice:")
            print(f"    title: {title}")
            print(f"    date : {date}")

            # Also count total general notices to confirm 10 per page
            n = page.evaluate("""
                () => {
                    const items = document.querySelectorAll('div.board_list ul li');
                    let count = 0;
                    for (const li of items) {
                        if (!li.classList.contains('notice')) count++;
                    }
                    return count;
                }
            """)
            print(f"    general notice count on this page: {n}")

        browser.close()


if __name__ == "__main__":
    main()
