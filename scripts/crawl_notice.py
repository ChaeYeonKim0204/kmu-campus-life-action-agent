"""Standalone Playwright crawler for KMU 학사공지.

Usage (with kmu-agent conda env activated):
    python scripts/crawl_notice.py                # default: 2026-01-01 cutoff
    python scripts/crawl_notice.py --since 2025-06-01
    python scripts/crawl_notice.py --max-pages 3  # safety cap

Behavior:
  - Walks list pages newest-first via ?currentPageNo=N
  - Collects general notices (not pinned) with date >= cutoff
  - For each, opens the view page and extracts body via .board_view
  - Writes/appends to data/processed/notices_crawled.jsonl (raw records)
  - Optional --merge flag merges into data/processed/chunks.jsonl as chunked entries

This is a probe-and-build step. We do NOT touch crawler/base.py yet;
once this proves stable on real data, we'll integrate properly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

# Make sibling package imports work when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestion.chunker import chunk_text


BASE = "https://www.kookmin.ac.kr"
LIST_URL = f"{BASE}/user/kmuNews/notice/4/index.do"
CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

OUT_RAW = Path("data/processed/notices_crawled.jsonl")
OUT_CHUNKS = Path("data/processed/chunks.jsonl")

MIN_DELAY = 8.0
MAX_DELAY = 18.0


@dataclass
class NoticeRow:
    """One notice as listed on the index page (pinned or general)."""
    title: str
    url: str
    posted_date: str        # "YYYY.MM.DD" — empty for pinned (no date shown in list)
    department: str = ""
    author: str = ""
    is_pinned: bool = False


@dataclass
class NoticeDoc:
    """One fully-fetched notice with body text and metadata."""
    doc_id: str
    title: str
    url: str
    posted_date: str
    department: str
    author: str
    contact_phone: str = ""
    body_text: str = ""
    attachments: list[dict] = field(default_factory=list)


def human_delay() -> None:
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"  [delay {delay:.1f}s]")
    time.sleep(delay)


def parse_date(s: str) -> date | None:
    """Parse 'YYYY.MM.DD' to date, or None on failure."""
    try:
        return datetime.strptime(s.strip(), "%Y.%m.%d").date()
    except ValueError:
        return None


def list_notices(page: Page, page_no: int) -> list[NoticeRow]:
    """Load list page N, return BOTH pinned and general notice rows.

    Pinned (li.notice) rows have no date/department/author in the list HTML —
    those fields are filled later from the view page.
    """
    url = f"{LIST_URL}?currentPageNo={page_no}"
    print(f"→ list page {page_no}: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("div.board_list", state="attached", timeout=15000)
    page.wait_for_timeout(1500)

    rows = page.evaluate("""
        () => {
            const out = [];
            const items = document.querySelectorAll('div.board_list ul li');
            for (const li of items) {
                const link = li.querySelector('a');
                const titleEl = li.querySelector('p.title');
                if (!link || !titleEl) continue;
                const isPinned = li.classList.contains('notice');
                const spans = li.querySelectorAll('div.board_etc span');
                out.push({
                    title: titleEl.innerText.trim(),
                    url: link.getAttribute('href'),
                    posted_date: (spans.length >= 1) ? spans[0].innerText.trim() : '',
                    department:  (spans.length >= 2) ? spans[1].innerText.trim() : '',
                    author:      (spans.length >= 3) ? spans[2].innerText.trim() : '',
                    is_pinned: isPinned,
                });
            }
            return out;
        }
    """)
    return [NoticeRow(**r) for r in rows]


# Matches a meta header line like:
#   "작성일 2026.05.11 담당부서 기후변화대응사업단 담당자 최석임 ☎ 02-910-5915 조회수 4214"
# All fields except phone are required; phone is optional.
META_RE = re.compile(
    r"작성일\s*(\S+)\s+담당부서\s*(.+?)\s+담당자\s*(\S+)"
    r"(?:\s*☎\s*([\d\-]+))?"
    r"(?:\s*조회수\s*\S+)?",
)


def fetch_notice_view(page: Page, row: NoticeRow) -> NoticeDoc | None:
    """Open one view.do page and extract body, attachments, meta."""
    url = row.url if row.url.startswith("http") else f"{BASE}{row.url}"
    print(f"  → view: {row.title[:60]}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector(".board_view", state="attached", timeout=10000)
    except Exception:
        print(f"    ⚠️ .board_view not found, skipping")
        return None
    page.wait_for_timeout(800)

    # .board_view structure:
    #   .view_top    → title + meta (작성일/담당부서/담당자/☎)
    #   .view_cont   → actual body (may be empty if notice is attachment-only)
    #   .view_bottom → prev/next navigation (must NOT be in body_text)

    view_top = page.locator(".board_view .view_top").first
    view_top_text = view_top.inner_text() if view_top.count() else ""

    view_cont = page.locator(".board_view .view_cont").first
    body_text = view_cont.inner_text().strip() if view_cont.count() else ""

    # Detect poster-style notices: count only TALL images (≥800px),
    # and only mark as poster when body text is also clearly short (<400 chars).
    # This avoids tagging normal notices that have a decorative banner.
    poster_image_count = 0
    poster_total_height = 0
    if view_cont.count():
        poster_info = view_cont.evaluate("""
            (root) => {
                const imgs = Array.from(root.querySelectorAll('img'));
                let count = 0;
                let totalH = 0;
                for (const im of imgs) {
                    let h = 0;
                    const styleH = im.style.height;
                    if (styleH && styleH.endsWith('px')) h = parseInt(styleH);
                    else if (im.height) h = im.height;
                    if (h >= 800) { count++; totalH += h; }
                }
                return { count, totalH };
            }
        """)
        poster_image_count = poster_info["count"]
        poster_total_height = poster_info["totalH"]

    if poster_image_count > 0 and len(body_text) < 400:
        notice_note = (
            f"※ 이 공지는 본문 텍스트가 짧고 포스터 이미지 {poster_image_count}장(총 {poster_total_height}px)으로 "
            f"안내됩니다. 자세한 내용은 게시글 원문({url}) 또는 첨부파일을 확인하세요."
        )
        body_text = (notice_note + "\n\n" + body_text).strip()

    # Title: prefer first non-empty line of view_top (the actual <h*> title in the page)
    top_lines = [ln.strip() for ln in view_top_text.splitlines() if ln.strip()]
    title = top_lines[0] if top_lines else row.title

    # Meta: extract date + phone from view_top
    # For pinned notices the list row has no date, so view_top is the only source.
    contact_phone = ""
    posted_date_from_view = ""
    m = META_RE.search(view_top_text)
    if m:
        posted_date_from_view = (m.group(1) or "").strip()
        contact_phone = m.group(4) or ""

    # Attachments — try .file a first, then broader file-download links
    attachments = []
    seen_urls: set[str] = set()
    for selector in [".file a", "a[href*='fileDefaultDownload']", "a[href*='/file']"]:
        links = page.locator(selector)
        for i in range(links.count()):
            a = links.nth(i)
            href = a.get_attribute("href") or ""
            text = a.inner_text().strip()
            if href and text and href not in seen_urls:
                attachments.append({"name": text, "url": href})
                seen_urls.add(href)

    # Doc ID from the URL path: .../4/{ID}/view.do
    m_id = re.search(r"/4/(\d+)/view\.do", url)
    notice_id = m_id.group(1) if m_id else hashlib.md5(url.encode()).hexdigest()[:8]
    doc_id = f"notice_{notice_id}"

    # Prefer list-row date when available; fall back to view-page date for pinned notices.
    posted_date = row.posted_date or posted_date_from_view

    return NoticeDoc(
        doc_id=doc_id,
        title=title,
        url=url,
        posted_date=posted_date,
        department=row.department,
        author=row.author,
        contact_phone=contact_phone,
        body_text=body_text,
        attachments=attachments,
    )


def crawl(since: date, max_pages: int, max_notices: int | None) -> list[NoticeDoc]:
    docs: list[NoticeDoc] = []
    seen_doc_ids: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=CHROME_UA, locale="ko-KR")
        list_page = context.new_page()
        view_page = context.new_page()

        for page_no in range(1, max_pages + 1):
            try:
                rows = list_notices(list_page, page_no)
            except Exception as exc:
                print(f"  ⚠️ failed to load list page {page_no}: {exc}")
                break
            if not rows:
                print(f"  no rows on page {page_no}, stopping")
                break

            # Page-end check uses only GENERAL notice dates (pinned have none).
            general_dates = [parse_date(r.posted_date) for r in rows if not r.is_pinned]
            general_dates = [d for d in general_dates if d]
            if general_dates and max(general_dates) < since:
                print(f"  all general notices on page {page_no} older than {since}, stopping")
                break

            for row in rows:
                # Pre-dedupe by URL-derived doc_id without fetching twice
                m_id = re.search(r"/4/(\d+)/view\.do", row.url)
                pre_doc_id = f"notice_{m_id.group(1)}" if m_id else None
                if pre_doc_id and pre_doc_id in seen_doc_ids:
                    print(f"    skip (already seen): {row.title[:60]}")
                    continue

                # General notice: filter by list-row date before fetching
                if not row.is_pinned:
                    d = parse_date(row.posted_date)
                    if d is None:
                        print(f"    skip (bad date): {row.title[:60]}")
                        continue
                    if d < since:
                        print(f"    skip (too old {d}): {row.title[:60]}")
                        continue

                human_delay()
                try:
                    doc = fetch_notice_view(view_page, row)
                except Exception as exc:
                    print(f"    ⚠️ view fetch failed: {exc}")
                    continue
                if not doc:
                    continue

                # Pinned: apply cutoff using view-page date
                if row.is_pinned:
                    vd = parse_date(doc.posted_date)
                    if vd and vd < since:
                        print(f"    skip pinned (too old {vd}): {row.title[:60]}")
                        continue

                if doc.doc_id in seen_doc_ids:
                    print(f"    skip (dup after fetch): {row.title[:60]}")
                    continue
                seen_doc_ids.add(doc.doc_id)
                docs.append(doc)
                pin_marker = "📌 " if row.is_pinned else ""
                body_note = f"{len(doc.body_text)} chars" if doc.body_text else "(empty body)"
                print(f"    ✓ {pin_marker}{body_note}, {len(doc.attachments)} files")
                if max_notices and len(docs) >= max_notices:
                    print(f"\nReached max_notices={max_notices}, stopping")
                    browser.close()
                    return docs

            human_delay()

        browser.close()
    return docs


def write_raw(docs: list[NoticeDoc]) -> None:
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RAW.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps({
                "doc_id": d.doc_id,
                "title": d.title,
                "url": d.url,
                "posted_date": d.posted_date,
                "department": d.department,
                "author": d.author,
                "contact_phone": d.contact_phone,
                "body_text": d.body_text,
                "attachments": d.attachments,
            }, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(docs)} notices → {OUT_RAW}")


def merge_into_chunks(docs: list[NoticeDoc]) -> None:
    """Append notice docs as chunks to data/processed/chunks.jsonl.

    Removes any existing chunks with the same doc_id first (idempotent re-runs).
    """
    existing: list[dict] = []
    if OUT_CHUNKS.exists():
        with OUT_CHUNKS.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.append(json.loads(line))

    new_doc_ids = {d.doc_id for d in docs}
    preserved = [c for c in existing if c.get("doc_id") not in new_doc_ids]

    new_chunks: list[dict] = []
    for d in docs:
        # If body is empty (e.g. attachment-only notice), still emit one
        # synthetic chunk so the notice is findable by title/attachment names.
        if not d.body_text.strip():
            synthetic = d.title
            if d.attachments:
                synthetic += "\n첨부파일: " + ", ".join(a["name"] for a in d.attachments)
            pieces = [synthetic]
        else:
            pieces = chunk_text(d.body_text, max_chars=700)
        body_hash = hashlib.sha256(
            (d.body_text or d.title).encode("utf-8")
        ).hexdigest()
        for i, piece in enumerate(pieces, start=1):
            new_chunks.append({
                "chunk_id": f"{d.doc_id}_{i:03d}",
                "doc_id": d.doc_id,
                "title": d.title,
                "url": d.url,
                "source_type": "notice",
                "source_tier": 5,
                "department": d.department,
                "text": piece,
                "content_hash": f"{body_hash}-{i}",
                "fetch_status": "success",
                "http_status": 200,
                "fetched_from_network": True,
                "used_fallback": False,
                "posted_date": d.posted_date,
                "contact_phone": d.contact_phone,
                "attachments": d.attachments,
            })

    with OUT_CHUNKS.open("w", encoding="utf-8") as f:
        for c in preserved + new_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Merged {len(new_chunks)} new chunks into {OUT_CHUNKS} "
          f"(preserved {len(preserved)} existing)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-01-01",
                        help="cutoff date YYYY-MM-DD (default: 2026-01-01)")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="max list pages to walk (safety cap, default: 5)")
    parser.add_argument("--max-notices", type=int, default=None,
                        help="hard cap on number of notices to fetch")
    parser.add_argument("--merge", action="store_true",
                        help="also merge results into chunks.jsonl")
    args = parser.parse_args()

    try:
        since = datetime.strptime(args.since, "%Y-%m-%d").date()
    except ValueError:
        print(f"Bad --since format, expected YYYY-MM-DD: {args.since}")
        sys.exit(1)

    print(f"Cutoff date: {since}, max_pages: {args.max_pages}, "
          f"max_notices: {args.max_notices}, merge: {args.merge}\n")

    docs = crawl(since=since, max_pages=args.max_pages,
                 max_notices=args.max_notices)
    print(f"\n=== Collected {len(docs)} notices ===")
    write_raw(docs)
    if args.merge:
        merge_into_chunks(docs)


if __name__ == "__main__":
    main()
