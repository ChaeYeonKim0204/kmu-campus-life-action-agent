"""Citation helpers for NotebookLM-style source references."""

from __future__ import annotations

import re


# KMU 사이트의 공통 네비게이션/레이아웃 텍스트. 크롤링 시 본문과 함께 추출돼 청크 text
# 앞부분을 채우므로, 화면에 보여줄 근거 텍스트에서는 걸러낸다(표시 전용 — 검색·청크 원문은 그대로).
_SITE_CHROME_LINES = frozenset(
    {
        "주메뉴 바로가기", "본문내용 바로가기", "푸터 바로가기", "홈으로", "통합검색",
        "대학소개", "입학안내", "대학ㆍ대학원", "산학ㆍ연구", "학사안내", "대학생활", "KMU 소식",
        "도전하는 국민", "한국 최고의 기업가 정신 대학", "고등교육의 새로운 표준을 제시하는 대학",
        "실천하는 교양인 · 소통하는 협력인 · 앞서가는 미래인 · 창의적인 전문인",
        "처리 중 입니다. 잠시만 기다려 주십시오.", "규정관리시스템", "국민대학교 규정관리시스템",
        "개정", "글자 축소", "글자 확대", "리스트", "캘린더", "목록", "TOP", "챗봇 콘텐츠 닫기",
        "자세히 보기", "교육과정", "전공/교과/교직", "수강신청", "성적/계절학기/현장실습",
        "등록/학적변동", "졸업", "장학", "국내대학 학점교환", "문화예술교육사", "전공자율선택제",
        "오메가교육시스템", "학사일정", "등록", "휴학/복학", "자퇴/재입학", "전부(과)", "*", "인",
    }
)


def clean_source_text(text: str) -> str:
    """Strip KMU site chrome and collapse whitespace for a readable source preview.

    Display-only: the underlying chunk text and the retrieval index are untouched.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    # 상단 글로벌 메뉴는 '통합검색'에서 끝난다 — 있으면 그 이전을 통째로 버린다.
    if "통합검색" in lines:
        lines = lines[lines.index("통합검색") + 1:]
    kept = [
        line
        for line in lines
        if line not in _SITE_CHROME_LINES
        and not line.endswith(":국민대학교")
        and not line.startswith("HOME >")
        and not re.fullmatch(r"[>\-·*∙\s]+", line)
    ]
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def build_citations(chunks: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """Assign stable S-style citation labels to retrieved chunks."""
    labels: dict[str, str] = {}
    citations: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue
        label = f"S{len(citations) + 1}"
        seen.add(chunk_id)
        labels[chunk_id] = label
        citations.append(
            {
                "id": label,
                "chunk_id": chunk_id,
                "title": chunk.get("title"),
                "url": chunk.get("url"),
                "source_type": chunk.get("source_type"),
                "source_tier": chunk.get("source_tier"),
                "department": chunk.get("department"),
                "published_at": chunk.get("published_at"),
                "fetched_from_network": chunk.get("fetched_from_network"),
                "used_fallback": chunk.get("used_fallback"),
                "fetch_status": chunk.get("fetch_status"),
                "http_status": chunk.get("http_status"),
                "text": clean_source_text(chunk.get("text") or ""),
            }
        )
    return labels, citations


def cite(chunk: dict | None, labels: dict[str, str]) -> str:
    """Return a citation marker for a chunk when available."""
    if not chunk:
        return ""
    label = labels.get(chunk.get("chunk_id", ""))
    return f"[{label}]" if label else ""
