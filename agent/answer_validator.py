"""Final answer contract validation."""

from __future__ import annotations

import re
from typing import Any


# Phase 5 follow-up: 일반 /ask 답변에도 졸업센터 sanitize 8 패턴과 동등한 출력 검증 적용.
# 졸업센터는 마스킹(replacement), 여기는 검증(detection) — 패턴은 동일/동등.
# 출처: graduation_center/service.py:SENSITIVE_PATTERNS + 기존 portal_password.
OUTPUT_PRIVACY_PATTERNS = {
    "student_id_value": re.compile(r"(?<!\d)20\d{6,8}(?!\d)"),
    "resident_number_value": re.compile(r"\d{6}-\d{7}"),
    "mobile_phone_value": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "portal_password_value": re.compile(
        r"(비밀번호|패스워드|password|pw)\s*(은|는|:|=)\s*[A-Za-z0-9!@#$%^&*._-]{4,}",
        re.IGNORECASE,
    ),
    # 졸업센터와 통일된 GPA/성적/이메일 패턴 (Phase 5 P3와 동등)
    "gpa_value_korean": re.compile(r"(GPA|평점평균)\s*[:：]?\s*\d+(?:\.\d+)?", re.IGNORECASE),
    "gpa_value_fraction": re.compile(r"\b\d\.\d{1,2}\s*/\s*4(?:\.\d+)?"),
    "gpa_value_decimal_nearby": re.compile(
        r"(?:학점|평점|성적)(?:이|은|는|이라|\s*[=:])?\s*[0-4]\.\d{1,2}"
    ),
    "email_value": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "grade_letter_nearby": re.compile(
        r"(?:성적|학점|grade|score)\s*[:=]?\s*[ABCDF][+\-0]?", re.IGNORECASE
    ),
}


def validate_answer_contract(answer: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate that answer citation markers resolve to returned citations."""
    citation_ids = {str(source.get("id")) for source in citations if source.get("id")}
    markers = re.findall(r"\[(S\d+)\]", answer or "")
    marker_ids = set(markers)
    flags: list[str] = []

    if "[None]" in (answer or ""):
        flags.append("citation_none_marker")
    if marker_ids - citation_ids:
        flags.append("unresolved_citation_marker")
    if citation_ids and "[근거]" not in (answer or ""):
        flags.append("missing_sources_section")
    if citations and not marker_ids:
        flags.append("missing_inline_citation_marker")

    return {
        "ok": not flags,
        "flags": flags,
        "markers": sorted(marker_ids),
        "citation_ids": sorted(citation_ids),
    }


def validate_output_privacy(answer: str) -> dict[str, Any]:
    """Detect sensitive concrete values in the final answer text."""
    flags = [name for name, pattern in OUTPUT_PRIVACY_PATTERNS.items() if pattern.search(answer or "")]
    return {
        "ok": not flags,
        "flags": flags,
    }
