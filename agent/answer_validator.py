"""Final answer contract validation."""

from __future__ import annotations

import re
from typing import Any


OUTPUT_PRIVACY_PATTERNS = {
    "student_id_value": re.compile(r"(?<!\d)20\d{6,8}(?!\d)"),
    "resident_number_value": re.compile(r"\d{6}-\d{7}"),
    "mobile_phone_value": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "portal_password_value": re.compile(
        r"(비밀번호|패스워드|password|pw)\s*(은|는|:|=)\s*[A-Za-z0-9!@#$%^&*._-]{4,}",
        re.IGNORECASE,
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
