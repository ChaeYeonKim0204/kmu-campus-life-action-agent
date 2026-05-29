"""Deadline calculation tools."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re


KOREAN_DATE_RE = re.compile(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일")


def extract_event_date(text: str, default_year: int = 2026) -> str | None:
    """Extract a date from YYYY-MM-DD or Korean M월 D일 text."""
    iso = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text or "")
    if iso:
        return iso.group(0)
    korean = KOREAN_DATE_RE.search(text or "")
    if korean:
        year = int(korean.group(1) or default_year)
        month = int(korean.group(2))
        day = int(korean.group(3))
        return date(year, month, day).isoformat()
    return None


def calculate_deadline(event_date: str, rule_days: int) -> dict:
    """Calculate a submission deadline from an event date and rule-day offset."""
    try:
        base = datetime.strptime(event_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("event_date must be YYYY-MM-DD") from exc
    deadline = base + timedelta(days=int(rule_days))
    return {
        "event_date": base.isoformat(),
        "rule_days": int(rule_days),
        "deadline": deadline.isoformat(),
        "description": f"사유 발생일 {base.isoformat()} 기준 {rule_days}일 이내 제출 기한은 {deadline.isoformat()}입니다.",
    }

