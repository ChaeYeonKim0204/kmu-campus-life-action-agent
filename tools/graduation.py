"""Graduation requirement audit — operational quality output.

agent_product_planning.md §19.1 (정답성: source validity, citation correctness) +
§15.4 (졸업 응답 구조 분리) + §16 리스크 ("졸업 판정 오해 → 학생 피해 가능 →
최종 판정 학과/교무팀 확인 문구 유지"). README §15.2 + §16.
"""

from __future__ import annotations


DEFAULT_REQUIREMENTS = {"total_credits": 130, "major_credits": 60}

_OPERATIONAL_NOTE = (
    "본 진단은 사용자가 제공한 비식별 학점 요약 기준입니다. "
    "학과별 추가 요건(캡스톤·졸업인증·논문·학부별 인증 등)은 "
    "학과사무실·교무팀 확인이 필요합니다."
)


def audit_graduation_requirements(
    student_summary: dict,
    requirements: dict | None = None,
    *,
    chunks: list[dict] | None = None,
) -> dict:
    """Audit graduation requirements from a sanitized credit summary.

    `chunks` (keyword-only): 공식 졸업요건 chunk가 전달되면 그 출처를
    `requirements_source`에 명시하고 가능한 경우 chunk의 요건값으로 default를
    대체. `requirements` 인자가 명시되면 그 값이 최우선.
    """
    reqs, source = _resolve_requirements(requirements, chunks)
    total = _to_int(student_summary.get("total_credits"))
    major = _to_int(student_summary.get("major_credits"))
    total_gap = max(0, reqs["total_credits"] - total)
    major_gap = max(0, reqs["major_credits"] - major)

    next_actions_for_plan: list[str] = []
    if total_gap > 0:
        next_actions_for_plan.append(
            f"부족 총 {total_gap}학점을 학기별로 분산 수강하는 계획을 학사조회에서 작성하세요."
        )
    if major_gap > 0:
        next_actions_for_plan.append(
            f"전공 부족 {major_gap}학점은 전공필수·전공선택 개설 과목으로 우선 채우세요."
        )
    if not next_actions_for_plan:
        next_actions_for_plan.append(
            "남은 학점 요건은 충족된 것으로 보이지만 학과·교무팀 졸업심사를 별도 받아 최종 확인하세요."
        )

    confirm_with_department = [
        "학부·학과별 졸업인증(캡스톤·논문·프로젝트 등) 별도 요구 여부 확인",
        "본 진단 결과를 학과사무실에 제출해 사전 졸업사정 여부 확인",
        "성적포기·재이수·계절학기 등 추가 행정 절차 필요 여부 확인",
    ]

    return {
        "total_credit_gap": total_gap,
        "major_credit_gap": major_gap,
        "requirements_source": source,
        "next_actions_for_plan": next_actions_for_plan,
        "confirm_with_department": confirm_with_department,
        "note": _OPERATIONAL_NOTE,
    }


def _resolve_requirements(
    requirements: dict | None, chunks: list[dict] | None
) -> tuple[dict, str]:
    """priority: explicit requirements > chunk metadata > default 130/60."""
    if requirements is not None:
        return requirements, "caller_provided"
    if chunks:
        for chunk in chunks:
            req = chunk.get("graduation_requirements")
            if isinstance(req, dict) and "total_credits" in req:
                doc_id = chunk.get("doc_id") or chunk.get("chunk_id") or "?"
                return req, f"chunk:{doc_id}"
    return DEFAULT_REQUIREMENTS, "default(130/60) — 학과 요람 확인 필요"


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
