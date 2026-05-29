"""Personalization helpers for non-sensitive student context."""

from __future__ import annotations


STATUS_ALIASES = {
    "new_student": ["신입생", "새내기", "1학년", "new_student"],
    "enrolled": ["재학생", "enrolled"],
    "returning": ["복학생", "복학", "returning"],
    "leave": ["휴학생", "휴학", "leave"],
    "graduating": ["졸업예정자", "막학기", "4학년", "graduating"],
}


STATUS_LABELS = {
    "new_student": "신입생",
    "enrolled": "재학생",
    "returning": "복학생",
    "leave": "휴학생",
    "graduating": "졸업예정자",
}


def normalize_student_context(raw_context: dict | None) -> dict:
    """Normalize optional, non-sensitive student context from the UI/API."""
    raw_context = raw_context or {}
    status = _normalize_status(str(raw_context.get("status", "")).strip())
    term = str(raw_context.get("term", "")).strip()
    concern = str(raw_context.get("concern", "")).strip()
    context = {
        "status": status,
        "status_label": STATUS_LABELS.get(status, "일반"),
        "term": term,
        "concern": concern,
    }
    return {key: value for key, value in context.items() if value}


def student_context_guidance(issue_type: str, raw_context: dict | None) -> dict | None:
    """Return student-status-specific tasks without using private records."""
    context = normalize_student_context(raw_context)
    status = context.get("status")
    if not status:
        return None

    tasks = list(_STATUS_BASE_TASKS.get(status, []))
    tasks.extend(_ISSUE_STATUS_TASKS.get((issue_type, status), []))

    concern = context.get("concern")
    if concern:
        tasks.append(f"관심 항목({concern})과 관련된 공지/학사일정을 우선 확인합니다.")

    term = context.get("term")
    if term:
        tasks.append(f"대상 학기({term}) 기준으로 신청기간과 개인 처리 상태를 나누어 확인합니다.")

    if not tasks:
        return None

    return {
        "label": context.get("status_label", "학생"),
        "tasks": _dedupe(tasks)[:5],
    }


def _normalize_status(value: str) -> str:
    lowered = value.lower()
    for status, aliases in STATUS_ALIASES.items():
        if any(alias.lower() == lowered for alias in aliases):
            return status
    return ""


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


_STATUS_BASE_TASKS = {
    "new_student": [
        "ON국민 사용자등록, eCampus 로그인, 모바일학생증 발급 가능 시점을 먼저 확인합니다.",
        "학과사무실/단과대학 공지처럼 신입생 대상 별도 안내가 있는지 확인합니다.",
    ],
    "enrolled": [
        "개인 신청 상태는 ON국민 포털에서 직접 확인하고, 공통 공지는 학사/행정/장학 공지로 나누어 봅니다.",
    ],
    "returning": [
        "복학 승인 상태, 수강신청 가능 상태, 등록금 고지서 반영 여부를 함께 확인합니다.",
        "휴학 중 변경된 교육과정이나 포털 접근 상태를 복학 전 점검합니다.",
    ],
    "leave": [
        "휴학 중 신청 가능한 절차와 재학생만 가능한 절차를 구분합니다.",
        "복학 예정 학기의 신청기간, 등록금 처리, 수강신청 가능 시점을 함께 확인합니다.",
    ],
    "graduating": [
        "졸업요건, 필수과목, 교양영역, 인증/논문/졸업작품 요건을 학과 기준으로 다시 확인합니다.",
        "증명서 발급 가능 시점과 졸업사정 결과 확인 일정을 함께 봅니다.",
    ],
}


_ISSUE_STATUS_TASKS = {
    ("portal_access", "new_student"): [
        "eCampus 강의가 안 보이면 수강신청 완료 여부와 강의 공개 시점을 먼저 확인합니다.",
    ],
    ("course_registration", "new_student"): [
        "신입생 수강신청은 일반 재학생 일정과 다른 안내가 있는지 학과/단과대학 공지를 확인합니다.",
    ],
    ("course_registration", "returning"): [
        "복학 승인 후 수강신청 자격이 열렸는지 ON국민에서 먼저 확인합니다.",
    ],
    ("registration_tuition", "returning"): [
        "복학 승인, 등록금 고지서 생성, 장학 반영 순서가 서로 다를 수 있으니 각각 확인합니다.",
    ],
    ("registration_tuition", "leave"): [
        "휴학자의 등록금 반환/이월 여부는 휴학 시점과 등록 상태에 따라 달라질 수 있습니다.",
    ],
    ("scholarship", "leave"): [
        "휴학 상태가 장학금 신청/수혜/이월에 영향을 주는지 학생지원팀 공지를 확인합니다.",
    ],
    ("graduation", "graduating"): [
        "마지막 학기에는 부족 학점뿐 아니라 필수 교과목, 졸업인증, 학과별 졸업요건을 같이 확인합니다.",
    ],
    ("schedule", "graduating"): [
        "졸업사정, 성적확정, 졸업예정증명서/졸업증명서 발급 가능 시점을 우선 확인합니다.",
    ],
    ("schedule", "returning"): [
        "복학 신청, 등록, 수강신청 일정이 서로 이어지는지 순서대로 확인합니다.",
    ],
}
