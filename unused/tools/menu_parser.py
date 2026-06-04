"""Deterministic 학식(cafeteria) menu extraction from retrieved chunk text.

The crawler stores the 오늘의 메뉴 page as `campus_facility` chunks whose text mixes
navigation chrome with the real menu (코너 이름, [중식]/[석식] 태그, ￦가격). The main
answer builder otherwise only emits a generic campus_facility sentence, so this module
pulls the menu lines out of that noise into a structured, citation-friendly section.

No LLM is involved — extraction is regex-based and deterministic (평가기준: 결과의 정형성).
On failure it returns an empty result so the caller can fall back to the page link.
"""

from __future__ import annotations

import re

# 질문이 학식/식단/오늘의 메뉴를 묻는지 판단하는 키워드. campus_facility 분류와 AND로 게이트한다.
_MENU_QUERY_KEYWORDS = ("학식", "식단", "메뉴", "중식", "석식", "조식", "밥", "점심", "저녁", "끼니")

# 본문에서 코너 헤더 / 끼니 태그 / "메뉴명 ￦가격" 항목을 등장 순서대로 잡는 토큰 패턴.
# 메뉴명과 ￦가격은 같은 줄(왕만두￦1600)뿐 아니라 줄바꿈으로 분리(메뉴명\n￦1600)되는
# 경우가 대부분이라, 이름 줄 끝과 ￦ 사이에 줄바꿈 1개까지 허용한다(빈 줄은 넘지 않음).
_MEAL_TAGS = "조식|중식|중석식|석식|간식|야식"
_TOKEN_RE = re.compile(
    r"(?P<corner>\d+\s*코너[ \t]*[가-힣A-Za-z0-9&()]{0,16})"
    rf"|(?P<meal>\[(?:{_MEAL_TAGS})\])"
    r"|(?P<item>[가-힣A-Za-z][^￦\[\]\n]*[ \t]*\n?[ \t]*￦[ \t]*[\d,]+)"
)
_MEAL_TAG_RE = re.compile(rf"\[(?:{_MEAL_TAGS})\]")


def is_menu_query(query: str) -> bool:
    """True when the question is about the cafeteria menu (not other 시설 항목)."""
    text = query or ""
    return any(keyword in text for keyword in _MENU_QUERY_KEYWORDS)


def _looks_like_menu_chunk(chunk: dict) -> bool:
    text = chunk.get("text") or ""
    return bool(_MEAL_TAG_RE.search(text)) or "코너" in text


def is_menu_chunk(chunk: dict) -> bool:
    """Public check: does this retrieved chunk carry cafeteria-menu text?"""
    return _looks_like_menu_chunk(chunk)


def _split_item(raw: str) -> tuple[str, str] | None:
    """Split a "<메뉴명> ￦<가격>" fragment into (name, price-digits)."""
    name, _, price = raw.rpartition("￦")
    name = re.sub(r"\s+", " ", name).strip(" *-·/")
    digits = re.sub(r"[^\d]", "", price)
    if not name or not digits:
        return None
    return name, digits


def _extract_items(text: str) -> list[dict]:
    """Pull (corner, meal, name, price) items from one chunk's text in reading order."""
    items: list[dict] = []
    current_corner: str | None = None
    current_meal: str | None = None
    for match in _TOKEN_RE.finditer(text):
        if match.lastgroup == "corner":
            current_corner = re.sub(r"\s+", " ", match.group("corner")).strip()
            continue
        if match.lastgroup == "meal":
            current_meal = match.group("meal").strip("[]")
            continue
        parsed = _split_item(match.group("item"))
        if not parsed:
            continue
        name, price = parsed
        items.append({"corner": current_corner, "meal": current_meal, "name": name, "price": price})
    return items


def parse_menu(chunks: list[dict]) -> dict:
    """Extract structured menu items aggregated across all menu-bearing chunks.

    The 오늘의 메뉴 page is split across several chunks (nav fragment + per-코너 fragments),
    so items must be collected from every menu chunk, not just the first.

    Returns {"found": bool, "source_chunks": [dict], "items": [ ... ]} where each item is
    {"corner": str | None, "meal": str | None, "name": str, "price": str}.
    """
    items: list[dict] = []
    source_chunks: list[dict] = []
    seen: set[tuple] = set()

    for chunk in chunks:
        if not _looks_like_menu_chunk(chunk):
            continue
        chunk_items = _extract_items(chunk.get("text") or "")
        contributed = False
        for item in chunk_items:
            key = (item["corner"], item["meal"], item["name"], item["price"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            contributed = True
            if len(items) >= 80:  # 폭주 방지 상한
                break
        if contributed:
            source_chunks.append(chunk)
        if len(items) >= 80:
            break

    return {"found": bool(items), "source_chunks": source_chunks, "items": items}
