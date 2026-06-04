"""졸업 리스크 등급 (결정론 · 재현 가능).

grade = 충족 못 한 최악 트리거(D>C>B>A). score = clamp(100 - Σseverity).
planner 미가동(키 없음)은 강등 사유가 아니다. roadmap 실현불가(검증 실패)만 강등에 반영.
"""
from __future__ import annotations

from graduation_center.v2.models_v2 import (
    AuditResult, OverflowScenario, RiskAssessment, RiskReason, StudentContext,
)
from graduation_center.v2.catalog import PREV_GPA_BONUS, SEASONAL_TERM_CAP

GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
LABELS = {"A": "안전", "B": "주의", "C": "위험", "D": "졸업불가 가능성"}


def _worse(a: str, b: str) -> str:
    return a if GRADE_RANK[a] >= GRADE_RANK[b] else b


def compute_risk(
    audit: AuditResult, context: StudentContext, roadmap_feasible: bool | None = None,
    overflow: OverflowScenario | None = None,
) -> RiskAssessment:
    reasons: list[RiskReason] = []
    grade = "A"
    gap = audit.total_gap
    # 미이수 필수는 이름 기준(학번 요람) 경로·코드 경로 모두 names를 채우므로 names로 카운트
    missing = len(audit.missing_required_names)
    max_area_gap = max((g.gap for g in audit.area_gaps), default=0.0)
    core_missing = [g for g in audit.core_area_gaps if g.gap > 0]

    if gap > 15:
        grade = _worse(grade, "D")
        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족(15 초과)", severity=30))
    elif gap >= 7:
        grade = _worse(grade, "C")
        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=20))
    elif gap > 0:
        grade = _worse(grade, "B")
        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=10))

    if missing >= 2:
        grade = _worse(grade, "C")
        reasons.append(RiskReason(factor="전공필수", detail=f"필수지정 {missing}과목 미이수", severity=18))
    elif missing == 1:
        grade = _worse(grade, "B")
        reasons.append(RiskReason(factor="전공필수", detail="필수지정 1과목 미이수", severity=10))

    # 영역(이수구분) 갭 — 총학점과 무관하게 등급에 반영(worst trigger)
    if max_area_gap > 15:
        grade = _worse(grade, "D")
        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족(15 초과)", severity=20))
    elif max_area_gap >= 7:
        grade = _worse(grade, "C")
        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=14))
    elif max_area_gap > 0:
        grade = _worse(grade, "B")
        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=8))

    # 잔여학기 수용량(결정론): 학사규정 제32조 학기당 이수학점 상한 기반
    # 사용자 override는 법정 상한(졸업학점 기반) 이내로 클램프 (계절 6, 직전 3.75↑ +3 한 번)
    from graduation_center.v2.catalog import regular_term_cap
    legal = regular_term_cap(audit.total_required)
    term_cap = min(float(context.max_credits_per_term or legal), legal)
    capacity = context.remaining_semesters * term_cap
    if context.prev_term_gpa_ge_375:
        capacity += PREV_GPA_BONUS
    if context.seasonal_semester_allowed:
        # 플래너(_ordered_terms)와 동일 모델: 정규학기마다 계절학기 1개 — 1회(+6)만 더하면
        # 플래너 feasible인데 risk D가 뜨는 모순(라운드4 검증)
        capacity += context.remaining_semesters * SEASONAL_TERM_CAP
    if gap > 0 and capacity > 0 and gap > capacity:
        grade = _worse(grade, "D")
        reasons.append(RiskReason(factor="잔여학기",
                      detail=f"부족 {gap:.0f}학점 > 잔여 {context.remaining_semesters}학기 수용량(~{capacity:.0f})", severity=20))

    core_total_gap = next((g.gap for g in audit.area_gaps if g.area == "핵심교양"), 0.0)
    if core_missing and core_total_gap > 0:
        grade = _worse(grade, "B")
        areas = ", ".join(g.area for g in core_missing)
        reasons.append(RiskReason(factor="핵심교양", detail=f"영역 미충족: {areas}", severity=8))
    elif core_missing:
        # 총량은 충족 — 세부영역 미충족은 과목명 미매핑(attribution) 가능성 → 강등 없이 확인만
        reasons.append(RiskReason(factor="핵심교양", detail="영역별 분류 확인 필요(총량은 충족)", severity=0))

    for cc in audit.convergence_checks:
        group_short = [gc for gc in cc.get("group_checks", []) if gc["gap"] > 0]
        eff_gap = max(cc.get("gap", 0), *(gc["gap"] for gc in group_short)) if group_short else cc.get("gap", 0)
        if eff_gap > 0:
            grade = _worse(grade, "C" if eff_gap >= 9 else "B")
            detail = f"{cc['name']} 총 {cc['gap']:.0f}학점 부족" if cc["gap"] > 0 else f"{cc['name']}"
            if group_short:
                detail += " · 그룹 부족: " + ", ".join(f"{gc['group']} {gc['gap']:.0f}" for gc in group_short)
            reasons.append(RiskReason(factor="융합전공", detail=detail, severity=14 if eff_gap >= 9 else 8))

    if context.gpa_min_met == "no":
        # 졸업 평점(전학년 2.0) 미달은 확정적 졸업불가 → 최악 등급(D)
        grade = _worse(grade, "D")
        reasons.append(RiskReason(factor="평점", detail="졸업 평점 기준(2.0/4.5) 미달 — 졸업 불가", severity=30))
    elif context.gpa_min_met == "unknown":
        reasons.append(RiskReason(factor="평점", detail="평점 기준 충족 여부 확인 필요", severity=0))

    if roadmap_feasible is False:
        grade = _worse(grade, "C")
        # 초과학기 시나리오(overflow)가 있으면 '계획 없음' 대신 그것을 가리킨다 —
        # C등급에서도 '계획 없음' 문구와 초과학기 카드가 병치되는 모순 방지(시뮬레이션 검증)
        detail = (f"잔여 학기 내 전체 배치 불가 — 초과학기 약 {overflow.extra_semesters}학기 예상"
                  if overflow is not None else "잔여 학기 내 실현 가능한 계획 없음")
        reasons.append(RiskReason(factor="로드맵", detail=detail, severity=15))
    elif roadmap_feasible is True and grade == "D" and context.gpa_min_met != "no" \
            and gap <= capacity + 0.01:
        # 절대 학점차(gap>15 등)만으로 D였더라도, 실현 가능한 완성 로드맵이 있고 수용량 내면
        # '졸업불가 가능성'은 과장 — C로 완화('D 졸업불가 + feasible 로드맵' 동시표시 모순 방지)
        grade = "C"
        reasons.append(RiskReason(factor="로드맵", detail="실현 가능한 학기별 계획 존재 — 등급 완화(C)", severity=0))
    if grade == "D" and context.gpa_min_met != "no" and overflow is not None \
            and overflow.extra_semesters <= 1:
        # blocked라도 초과학기 1학기로 닫히는 구체적 졸업 경로(overflow 시나리오)가 있으면
        # 'D 졸업불가 가능성' 배지와 '초과학기 1학기 → 졸업' 카드의 무화해 병치 모순 — C로 완화.
        # 위 blocked 분기의 '실현 가능한 계획 없음' reason은 완화 문구와 모순 병치되므로
        # 한 문구로 치환(라운드5 검증 — severity 15는 blocked 패널티로 유지)
        grade = "C"
        reasons[:] = [r for r in reasons if r.factor != "로드맵"]
        reasons.append(RiskReason(
            factor="로드맵",
            detail=f"잔여 학기 내 전체 배치 불가 — 초과학기 {overflow.extra_semesters}학기로 "
                   f"졸업 경로 존재(등급 완화 C)", severity=15))

    if grade == "A" and not reasons:
        reasons.append(RiskReason(factor="종합", detail="확인된 부족·위험 항목 없음", severity=0))

    score = max(0, min(100, 100 - sum(r.severity for r in reasons)))
    return RiskAssessment(grade=grade, label=LABELS[grade], score=score, reasons=reasons)
