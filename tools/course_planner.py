"""Course planning direction — operational output aligned with §15.4.

agent_product_planning.md §15.4 마지막 두 섹션 정렬:
- '다음 학기 수강계획에 반영할 항목' — 실제 학기 계획 행동
- '최종 판정은 학교 담당 부서 확인 필요' — 모든 항목 마지막 고정 문구
"""

from __future__ import annotations


def recommend_course_plan(interests: list[str], gaps: dict) -> list[str]:
    """Recommend course-plan items grounded in graduation gaps + interests.

    출력은 §15.4 '다음 학기 수강계획에 반영할 항목' 섹션 컨벤션:
    실행형 단문, 학사 절차 어휘, 마지막에 최종 확인 항목 고정.
    """
    items: list[str] = []
    major_gap = gaps.get("major_credit_gap", 0) or 0
    total_gap = gaps.get("total_credit_gap", 0) or 0

    if major_gap > 0:
        items.append(
            f"전공 부족 {major_gap}학점 보강: 전공선택·전공필수 개설 시간표를 "
            "학사조회에서 확인하고 학기별로 분산 수강."
        )
    if total_gap > 0:
        items.append(
            f"총 졸업학점 부족 {total_gap}학점 보강: 핵심교양·일반선택 영역을 "
            "우선 채워 구분별 요건을 동시에 맞추세요."
        )
    if interests:
        items.append(
            f"관심 분야({', '.join(interests)}) 강의계획서를 비교해 "
            "진로와 연결되는 과목으로 보강하세요."
        )
    if not items:
        items.append(
            "공식 요람과 학사조회 시간표를 기준으로 다음 학기 계획을 수립하세요."
        )

    # §15.4 마지막 섹션 정렬 — 모든 출력에 최종 확인 고정.
    items.append(
        "최종 졸업요건 충족 여부는 학과사무실·교무팀의 졸업사정 결과로 확정됩니다."
    )
    return items
