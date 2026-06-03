"""로드맵 플래너 (LLM 계획 + 결정론 검증/repair) — agentic 코어.

결정론이 사실(후보 과목·갭)을 깔고, LLM은 RoadmapPlan만 생성한다. 검증기가 하드 제약을
재확인하고, 실패 시 1회 repair, 그래도 실패면 정직한 blocked(가짜 계획 금지). OPENAI 키가
없으면 status="not_generated"(리스크 강등 X). LLM엔 학번·이름·성적 미전달.
"""
from __future__ import annotations

import json
import os

from graduation_center.v2.catalog import (
    PREV_GPA_BONUS, SEASONAL_TERM_CAP, load_catalog, regular_term_cap,
)
from graduation_center.v2.models_v2 import (
    AuditResult, RequirementProfile, RoadmapPlan, RoadmapTerm, Source,
    StudentContext, ValidationError, ValidationReport, VerifiedTranscript,
)
from graduation_center.v2.text_norm import normalize_name

MAJOR_AREAS = {"전공"}  # 카탈로그(코드 보유)로 후보 가능한 영역


def _term_sem(term: str) -> str | None:
    # "2026-2" → "2"
    if term and "-" in term:
        return term.split("-")[-1]
    return None


def _term_key(term: str):
    try:
        y, s = term.split("-")
        order = {"1": 1, "S": 2, "2": 3, "W": 4}.get(s, 9)
        return (int(y), order)
    except Exception:
        return (9999, 9)


def _nth_regular_term(current_term: str | None, n: int) -> str | None:
    """current_term 다음의 n번째 정규학기(1/2학기) 라벨. n<=0이면 None."""
    if not current_term or n <= 0:
        return None
    try:
        y, s = current_term.split("-")
        y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
    except Exception:
        return None
    label = {1: "1", 3: "2"}
    count, steps = 0, 0
    while steps < 60:
        steps += 1
        so += 1
        if so > 4:
            so = 1; y += 1
        if so in (1, 3):                      # 정규학기만 카운트
            count += 1
            if count == n:
                return f"{y}-{label[so]}"
    return None


def project_overflow(audit: AuditResult, profile: RequirementProfile, context: StudentContext):
    """잔여 정규학기로 부족 학점을 못 채우면 초과학기 예상 시나리오 산출(결정론).

    capacity = 잔여학기 × 학기당 상한(+직전 3.75↑ 보너스 1회). shortfall(총 졸업학점 부족)이
    capacity를 넘으면, 필요한 총 정규학기 수와 초과학기 수·예상 졸업학기를 계산한다.
    """
    from graduation_center.v2.models_v2 import OverflowScenario
    shortfall = float(audit.total_gap)
    if shortfall <= 0:
        return None
    cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
    if cap <= 0:
        return None
    bonus = PREV_GPA_BONUS if context.prev_term_gpa_ge_375 else 0.0
    remaining = int(context.remaining_semesters)
    if shortfall <= remaining * cap + bonus:
        return None                            # 잔여 학기로 충분 → 시나리오 불필요
    # 필요한 최소 정규학기 수(첫 학기에만 보너스 1회)
    k = 1
    while k * cap + bonus < shortfall and k < 60:
        k += 1
    return OverflowScenario(
        shortfall_credits=round(shortfall, 1),
        per_term_credit_cap=cap,
        remaining_semesters=remaining,
        total_semesters_needed=k,
        extra_semesters=max(0, k - remaining),
        projected_graduation_term=_nth_regular_term(context.current_term, k),
        note=f"잔여 {remaining}학기·학기당 최대 {cap:.0f}학점으로는 부족 {shortfall:.0f}학점을 채울 수 없습니다. "
             f"최소 {k}학기(초과학기 {max(0, k - remaining)}학기)가 필요합니다.",
    )


def build_planning_context(
    audit: AuditResult, profile: RequirementProfile, context: StudentContext,
    verified: VerifiedTranscript,
) -> dict:
    cat = load_catalog(context.program_id)
    confirmed_ids = {c.course_id for c in verified.confirmed_courses if c.course_id}
    unresolved_norms = {normalize_name(m.raw.course_name) for m in verified.unresolved}

    gap_areas = {g.area for g in audit.area_gaps if g.gap > 0}
    candidates, sources = [], []
    src_idx = {}

    def src_for(course):
        if course.course_id not in src_idx:
            sid = f"G{len(sources) + 1}"
            src_idx[course.course_id] = sid
            sources.append(Source(id=sid,
                                  doc=course.source.get("doc", "2025-2 교육과정 교과목코드 현황"),
                                  page=course.source.get("page"),
                                  source_type="catalog_course", ref=course.course_id))
        return src_idx[course.course_id]

    want_major = bool(gap_areas & MAJOR_AREAS) or bool(audit.missing_required_course_ids)
    for c in cat["courses"]:
        if c.course_id in confirmed_ids or normalize_name(c.name_ko) in unresolved_norms:
            continue
        is_missing_required = c.course_id in audit.missing_required_course_ids
        if (want_major and c.requirement_area in MAJOR_AREAS) or is_missing_required:
            candidates.append({
                "course_id": c.course_id, "name_ko": c.name_ko, "credits": c.credits,
                "requirement_area": c.requirement_area, "is_required": c.is_required,
                "prerequisites": c.prerequisites, "offered_terms": c.offered_terms,
                "source_id": src_for(c),
            })
    # 비-major(교양) 갭은 후보 카탈로그가 없어 자동계획 불가 → 별도 표기
    non_major_gap_areas = sorted(gap_areas - MAJOR_AREAS)
    # 학사규정 제32조: 정규학기 상한(사용자 override 우선), 계절 6학점, 직전 3.75↑ → 첫 학기 +3
    term_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
    caps = {
        "regular_term_credits": term_cap,
        "seasonal_term_credits": SEASONAL_TERM_CAP,
        "first_term_bonus": PREV_GPA_BONUS if context.prev_term_gpa_ge_375 else 0.0,
        "prev_term_gpa_ge_375": context.prev_term_gpa_ge_375,
    }
    return {
        "student_context": {
            "current_term": context.current_term, "remaining_semesters": context.remaining_semesters,
            "seasonal_semester_allowed": context.seasonal_semester_allowed,
            "max_credits_per_term": term_cap,
            "seasonal_credit_cap": SEASONAL_TERM_CAP,
            "first_regular_term_extra_credits": caps["first_term_bonus"],
            "preferences": context.preferences,
        },
        "caps": caps,
        "audit_result": {
            "total_gap": audit.total_gap,
            "gaps": [{"area": g.area, "gap": g.gap} for g in audit.area_gaps if g.gap > 0],
            "missing_required_course_ids": audit.missing_required_course_ids,
            "missing_required_names": audit.missing_required_names,
        },
        "completed_ids": sorted(confirmed_ids),
        "candidate_courses": candidates,
        "non_major_gap_areas": non_major_gap_areas,
        "sources": [s.model_dump() for s in sources],
    }


_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "feasible": {"type": "boolean"},
        "terms": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "term": {"type": "string"},
                "courses": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "course_id": {"type": "string"}, "name_ko": {"type": "string"},
                        "credits": {"type": "number"}, "satisfies": {"type": "string"},
                        "reason": {"type": "string"},
                        "source_ids": {"type": "array", "items": {"type": "string"}},
                    }, "required": ["course_id", "name_ko", "credits", "satisfies", "reason", "source_ids"]}},
                "term_credits": {"type": "number"},
                "term_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                "notes": {"type": "array", "items": {"type": "string"}},
            }, "required": ["term", "courses", "term_credits", "term_risk", "notes"]}},
        "why_this_plan": {"type": "string"},
        "blocked_reason": {"type": ["string", "null"]},
        "relaxation_hint": {"type": ["string", "null"]},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["feasible", "terms", "why_this_plan", "blocked_reason", "relaxation_hint", "assumptions"],
}

_SYS = ("너는 졸업 로드맵 플래너다. 제공된 candidate_courses와 사실만 사용해 남은 학기에 들을 "
        "과목을 배치한다. 새 과목·학점·요건을 지어내지 마라. 선수과목 순서·개설학기를 지키고, "
        "학기당 이수학점 상한(student_context.max_credits_per_term, 계절학기는 seasonal_credit_cap, "
        "첫 정규학기는 first_regular_term_extra_credits만큼 추가 허용)을 넘기지 마라. "
        "학생 선호를 반영한다. 출력은 스키마 JSON만.")


def _get_client():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception:
        return None


def plan_roadmap(planning_context: dict, client=None) -> RoadmapPlan:
    client = client or _get_client()
    if client is None:
        return RoadmapPlan(status="not_generated",
                           why_this_plan="LLM 미설정(OPENAI_API_KEY 없음) — 결정론 진단/리스크만 제공.")
    model = os.getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini")
    kwargs = {
        "model": model,
        "input": [{"role": "system", "content": _SYS},
                  {"role": "user", "content": json.dumps(planning_context, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "roadmap_plan",
                            "schema": _SCHEMA, "strict": True}},
    }
    if any(model.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")):
        kwargs["reasoning"] = {"effort": "minimal"}
    else:
        kwargs["temperature"] = 0.1
    resp = client.responses.create(**kwargs)
    text = getattr(resp, "output_text", "") or ""
    data = json.loads(text)
    return RoadmapPlan(
        status="generated",
        feasible=data.get("feasible"),
        terms=data.get("terms", []),
        why_this_plan=data.get("why_this_plan", ""),
        blocked_reason=data.get("blocked_reason"),
        relaxation_hint=data.get("relaxation_hint"),
        assumptions=data.get("assumptions", []),
    )


def _allowed_terms(context: StudentContext) -> set[str] | None:
    """current_term·잔여학기·계절학기로 허용 가능한 학기 라벨 집합 생성."""
    if not context.current_term:
        return None
    try:
        y, s = context.current_term.split("-")
        y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
    except Exception:
        return None
    label = {1: "1", 2: "S", 3: "2", 4: "W"}
    allowed, reg, steps = set(), 0, 0
    while reg < context.remaining_semesters and steps < 40:
        steps += 1
        so += 1
        if so > 4:
            so = 1; y += 1
        lab = f"{y}-{label[so]}"
        if so in (1, 3):           # 정규학기
            allowed.add(lab); reg += 1
        elif context.seasonal_semester_allowed:  # 계절학기(허용 시)
            allowed.add(lab)
    return allowed


def validate_roadmap(plan: RoadmapPlan, ctx: dict, context: StudentContext) -> ValidationReport:
    errors: list[ValidationError] = []
    cand = {c["course_id"]: c for c in ctx["candidate_courses"]}
    src_ids = {s["id"] for s in ctx["sources"]}
    completed = set(ctx.get("completed_ids", []))
    allowed = _allowed_terms(context)
    planned: set[str] = set()          # 전체 계획된 course_id
    prior_planned: set[str] = set()    # 앞 학기까지 계획된 course_id (선수 검사용)
    seen_terms: set[str] = set()
    planned_by_area: dict[str, float] = {}

    caps = ctx.get("caps", {})
    reg_cap = float(caps.get("regular_term_credits", 19.0))
    seasonal_cap = float(caps.get("seasonal_term_credits", SEASONAL_TERM_CAP))
    first_bonus = float(caps.get("first_term_bonus", 0.0))
    # 직전학기 3.75↑ 보너스는 첫 '정규학기'에만 — 계획상 가장 이른 정규학기 식별
    first_regular = None
    for t in sorted(plan.terms, key=lambda x: _term_key(x.term)):
        if _term_sem(t.term) in ("1", "2"):
            first_regular = t.term
            break

    # 잔여학기 상한은 '정규학기' 수 기준(계절학기는 _allowed_terms에서 별도 허용·6학점 cap)
    regular_count = sum(1 for t in plan.terms if _term_sem(t.term) in ("1", "2"))
    if regular_count > context.remaining_semesters:
        errors.append(ValidationError(code="too_many_terms",
                      detail=f"정규학기 수 {regular_count} > 잔여 {context.remaining_semesters}"))

    for t in plan.terms:
        sem = _term_sem(t.term)
        if t.term in seen_terms:
            errors.append(ValidationError(code="dup_term", detail=f"학기 라벨 중복: {t.term}"))
        seen_terms.add(t.term)
        if allowed is not None and t.term not in allowed:
            errors.append(ValidationError(code="term_out_of_range",
                          detail=f"{t.term}은 허용 학기({sorted(allowed)}) 밖"))
        # 학사규정 제32조 학기당 이수학점 상한(정규/계절 + 첫 정규학기 보너스)
        is_seasonal = sem in ("S", "W")
        term_cap = seasonal_cap if is_seasonal else (reg_cap + (first_bonus if t.term == first_regular else 0.0))
        term_credit_total = sum(float(c.credits) for c in t.courses)
        if term_credit_total > term_cap + 0.01:
            errors.append(ValidationError(code="over_credit_cap",
                          detail=f"{t.term} 이수학점 {term_credit_total:.0f} > 상한 {term_cap:.0f}"))
        if sem in ("S", "W") and not context.seasonal_semester_allowed:
            errors.append(ValidationError(code="seasonal_not_allowed", detail=f"{t.term} 계절학기 불가"))
        cur_term_ids = []
        catalog_credit_sum = 0.0
        for c in t.courses:
            if c.course_id not in cand:
                errors.append(ValidationError(code="unknown_course", detail=c.name_ko, course_id=c.course_id))
                continue
            cc = cand[c.course_id]
            if c.course_id in planned:
                errors.append(ValidationError(code="dup_course", detail=c.name_ko, course_id=c.course_id))
            planned.add(c.course_id)
            cur_term_ids.append(c.course_id)
            # 학점은 카탈로그 값이 진실 — LLM 값 위조 방지
            if abs(float(c.credits) - float(cc["credits"])) > 0.01:
                errors.append(ValidationError(code="credit_mismatch",
                              detail=f"{c.name_ko} 학점 {c.credits}≠카탈로그 {cc['credits']}", course_id=c.course_id))
            catalog_credit_sum += cc["credits"]
            # satisfies는 카탈로그 영역과 일치해야
            if cc["requirement_area"] not in (c.satisfies or "") and (c.satisfies or "") not in ("필수", "전공필수"):
                errors.append(ValidationError(code="bad_satisfies",
                              detail=f"{c.name_ko} satisfies={c.satisfies}≠{cc['requirement_area']}", course_id=c.course_id))
            if sem and sem not in cc["offered_terms"]:
                errors.append(ValidationError(code="not_offered", detail=f"{c.name_ko} {t.term} 미개설", course_id=c.course_id))
            # 선수과목: 이미 이수 or 앞 학기에 계획돼야 (같은 학기/뒤 학기 불가)
            for pre in cc.get("prerequisites", []):
                if pre not in completed and pre not in prior_planned:
                    errors.append(ValidationError(code="prereq_unmet",
                                  detail=f"{c.name_ko} 선수과목 미충족", course_id=c.course_id))
            if any(sid not in src_ids for sid in c.source_ids):
                errors.append(ValidationError(code="bad_source", detail=c.name_ko, course_id=c.course_id))
            planned_by_area[cc["requirement_area"]] = planned_by_area.get(cc["requirement_area"], 0.0) + cc["credits"]
        # term_credits는 카탈로그 학점 합과 일치해야
        if abs(round(catalog_credit_sum, 1) - float(t.term_credits)) > 0.01:
            errors.append(ValidationError(code="term_credits_mismatch", detail=f"{t.term} 학점합 불일치"))
        prior_planned |= set(cur_term_ids)

    for mid in ctx["audit_result"]["missing_required_course_ids"]:
        if mid not in planned:
            errors.append(ValidationError(code="required_not_planned", detail="필수지정 과목 미포함", course_id=mid))
    for g in ctx["audit_result"]["gaps"]:
        if g["area"] in MAJOR_AREAS and planned_by_area.get(g["area"], 0.0) < g["gap"]:
            errors.append(ValidationError(code="gap_not_closed",
                          detail=f"{g['area']} 계획 {planned_by_area.get(g['area'],0)}<부족 {g['gap']}"))
    return ValidationReport(ok=not errors, errors=errors)


def run_planner(
    audit: AuditResult, profile: RequirementProfile, context: StudentContext,
    verified: VerifiedTranscript, client=None,
) -> tuple[RoadmapPlan, ValidationReport, dict]:
    ctx = build_planning_context(audit, profile, context, verified)

    no_credit_gap = audit.total_gap <= 0 and not any(g["area"] in MAJOR_AREAS for g in ctx["audit_result"]["gaps"])
    # 잔여 정규학기로 부족 학점을 못 채우면 초과학기 예상 시나리오(결정론). 충족이면 None.
    overflow = project_overflow(audit, profile, context)

    # 학점·영역·필수 모두 충족 → 추가 계획 불필요
    if no_credit_gap and not audit.missing_required_course_ids and not audit.missing_required_names:
        plan = RoadmapPlan(status="generated", feasible=True, terms=[],
                           why_this_plan="졸업요건을 모두 충족했습니다. 추가 수강 계획이 필요 없습니다.")
        if ctx["non_major_gap_areas"]:
            plan.assumptions.append(f"교양 영역({', '.join(ctx['non_major_gap_areas'])})은 직접 확인 필요")
        return plan, ValidationReport(ok=True), ctx

    # 학점·영역은 충족인데 '이름 기준'(학번 요람) 필수지정만 미이수 → 코드가 없어 자동계획 불가
    # → 정직하게 직접 수강 안내(완전 충족으로 오판 금지). 학점 갭이 따로 있으면 아래 일반 경로로.
    if no_credit_gap and audit.missing_required_names and not ctx["candidate_courses"]:
        plan = RoadmapPlan(
            status="generated", feasible=True, terms=[],
            why_this_plan="졸업학점·영역 요건은 충족했으나 필수지정 과목 미이수: "
                          + ", ".join(audit.missing_required_names)
                          + ". 잔여 학기에 직접 수강 신청이 필요합니다.")
        if ctx["non_major_gap_areas"]:
            plan.assumptions.append(f"교양 영역({', '.join(ctx['non_major_gap_areas'])})은 직접 확인 필요")
        return plan, ValidationReport(ok=True), ctx

    # 자동계획 가능한 후보가 없는데 갭이 남음(예: 교양만 부족) → 정직한 partial/blocked
    if not ctx["candidate_courses"]:
        areas = ctx["non_major_gap_areas"] or [g["area"] for g in ctx["audit_result"]["gaps"]]
        hint = "교양 등 부족 영역은 직접 수강신청으로 채워야 합니다."
        if overflow:
            hint = overflow.note + " " + hint
        plan = RoadmapPlan(status="blocked", feasible=False,
                           blocked_reason=f"자동 계획 가능한 전공 후보가 없습니다(부족 영역: {', '.join(areas) or '미상'}).",
                           relaxation_hint=hint, overflow=overflow)
        return plan, ValidationReport(ok=True), ctx

    # LLM 계획 — 실패(예외·JSON·스키마)는 not_generated로 안전 폴백(500 방지)
    try:
        plan = plan_roadmap(ctx, client=client)
    except Exception as exc:
        return RoadmapPlan(status="not_generated", overflow=overflow,
                           why_this_plan=f"로드맵 생성 실패 — 결정론 진단/리스크만 제공 ({type(exc).__name__})."), \
            ValidationReport(ok=True), ctx
    if plan.status == "not_generated":
        plan.overflow = overflow
        return plan, ValidationReport(ok=True), ctx

    report = validate_roadmap(plan, ctx, context)
    repaired = False
    if not report.ok:
        # 1회 repair
        repaired = True
        ctx_with_errors = dict(ctx, validation_errors=[e.model_dump() for e in report.errors])
        try:
            plan = plan_roadmap(ctx_with_errors, client=client)
            report = validate_roadmap(plan, ctx, context)
        except Exception:
            pass
    report.repair_attempted = repaired
    if not report.ok:
        # 정직한 실패 (가짜 계획 금지)
        hint = "잔여 학기를 늘리거나 학기당 이수학점·계절학기를 조정해 보세요."
        if overflow:
            hint = overflow.note + " " + hint
        plan = RoadmapPlan(status="blocked", feasible=False,
                           blocked_reason="잔여 학기·제약 내 유효한 로드맵을 생성하지 못했습니다.",
                           relaxation_hint=hint)
    if ctx["non_major_gap_areas"]:
        plan.assumptions.append(f"교양 영역({', '.join(ctx['non_major_gap_areas'])}) 부족분은 직접 선택 필요")
    plan.overflow = overflow
    return plan, report, ctx
