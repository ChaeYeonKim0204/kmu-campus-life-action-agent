"""로드맵 플래너 (LLM 계획 + 결정론 검증/repair) — agentic 코어.

결정론이 사실(후보 과목·갭)을 깔고, LLM은 RoadmapPlan만 생성한다. 검증기가 하드 제약을
재확인하고, 실패 시 1회 repair, 그래도 실패면 정직한 blocked(가짜 계획 금지). OPENAI 키가
없으면 status="not_generated"(리스크 강등 X). LLM엔 학번·이름·성적 미전달.
"""
from __future__ import annotations

import json
import os

from graduation_center.v2.catalog import (
    PREV_GPA_BONUS, SEASONAL_TERM_CAP, V2_DIR, load_catalog, regular_term_cap,
)
from graduation_center.v2.models_v2 import (
    AuditResult, RequirementProfile, RoadmapCourse, RoadmapPlan, RoadmapTerm, Source,
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
    # 더 채워야 하는 학점 = max(졸업최저 부족, 영역별 부족 합). 총학점은 충분해도 특정 영역
    # (예: 전공)이 부족하면 그만큼 추가 이수가 필요하므로 영역 갭 합도 본다.
    area_shortfall = round(sum(g.gap for g in audit.area_gaps if g.gap > 0), 1)
    shortfall = max(float(audit.total_gap), area_shortfall)
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


# ============ 결정론 통합 플래너 (codex 설계: 후보 정규화 → greedy 배치 → 검증) ============
def _ordered_terms(context: StudentContext, reg_cap: float) -> list[list]:
    """허용 학기를 시간순 [[label, cap]]로. 첫 정규학기 +직전3.75 보너스, 계절=6."""
    if not context.current_term:
        return []
    try:
        y, s = context.current_term.split("-"); y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
    except Exception:
        return []
    label = {1: "1", 2: "S", 3: "2", 4: "W"}
    out, reg, steps, first = [], 0, 0, True
    while reg < context.remaining_semesters and steps < 40:
        steps += 1; so += 1
        if so > 4:
            so = 1; y += 1
        lab = f"{y}-{label[so]}"
        if so in (1, 3):
            cap = reg_cap + (PREV_GPA_BONUS if (first and context.prev_term_gpa_ge_375) else 0.0)
            out.append([lab, cap]); reg += 1; first = False
        elif context.seasonal_semester_allowed:
            out.append([lab, SEASONAL_TERM_CAP])
    return out


def _required_meta(program_id: str, year: int | None) -> dict:
    """학번 요람 필수 과목의 학점·개설학기 메타 {정규화이름: {credits, terms}}."""
    import json
    p = V2_DIR / "required_names_by_year.json"
    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
    if not by_year:
        return {}
    avail = sorted(int(y) for y in by_year)
    pick = year if (year and str(year) in by_year) else (
        [y for y in avail if not year or y <= year][-1:] or [avail[-1]])[0]
    meta = {}
    for it in by_year.get(str(pick), []):
        if isinstance(it, dict):
            meta[normalize_name(it["name"])] = {"credits": float(it.get("credits", 3.0)),
                                                "terms": list(it.get("terms") or [])}
    return meta


def _slot_chunks(name: str, total: float, satisfies: str, size: float = 3.0) -> list[dict]:
    """교양 부족분을 학기당 배치 가능한 3학점 단위 슬롯으로 분할(단일 큰 슬롯 배치불가 방지)."""
    out, rem, i = [], round(float(total), 1), 0
    while rem > 0.01:
        c = min(size, rem); i += 1
        out.append({"name_ko": (name if total <= size else f"{name} #{i}"), "credits": round(c, 1),
                    "satisfies": satisfies, "confidence": "generic_slot", "manual": True})
        rem = round(rem - c, 1)
    return out


def build_unified_candidates(audit: AuditResult, profile: RequirementProfile,
                             verified: VerifiedTranscript) -> tuple[list[dict], list[dict]]:
    """남은 졸업 의무를 단일 후보 풀로 정규화(전공·필수·융합·교양). 반환 (선택후보, 요건요약)."""
    cat = load_catalog(profile.program_id)
    confirmed_norm = {normalize_name(c.name_ko) for c in verified.confirmed_courses}
    confirmed_pref = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
    reqs: list[dict] = []

    # 1) 미이수 필수(이름) — 전부 이수 필요. 학점·개설학기·코드·선수를 요람메타→카탈로그 순으로 보강.
    if audit.missing_required_names:
        rmeta = _required_meta(profile.program_id, profile.admission_year)
        items = []
        for n in audit.missing_required_names:
            m = rmeta.get(normalize_name(n), {})
            terms = list(m.get("terms") or [])
            credits = m.get("credits")
            cid, prereqs = "", []
            # 카탈로그 매칭으로 누락분 보강(특히 연도메타 없는 학과 — ai_bigdata 등)
            hit = cat["by_norm"].get(normalize_name(n)) if cat.get("by_norm") else None
            if hit:
                cc = cat["by_code"].get(hit[0])
                if cc:
                    cid = cc.course_id
                    if credits is None:
                        credits = cc.credits
                    if not terms:
                        terms = list(cc.offered_terms or [])
                    prereqs = list(cc.prerequisites or [])
            known = bool(terms)
            items.append({"name_ko": n, "course_id": cid, "credits": (credits if credits is not None else 3.0),
                          "satisfies": "필수지정", "offered_terms": terms or ["1", "2"], "prerequisites": prereqs,
                          "confidence": "catalog_verified" if known else "name_only", "manual": not known})
        reqs.append({"label": "필수지정 미이수", "area": "전공", "priority": 1, "need": None, "items": items})
    # 2) 연계융합 부족 — 총 또는 '그룹별 최저' 미충족 시. 부족 그룹 우선 미이수 융합과목
    for cc in audit.convergence_checks:
        group_gaps = {g["group"]: g["gap"] for g in cc.get("group_checks", []) if g["gap"] > 0}
        need = max(cc.get("gap", 0.0), round(sum(group_gaps.values()), 1))
        if need <= 0:
            continue
        short = set(group_gaps)
        untaken = sorted([c for c in cc.get("courses", []) if not c["taken"]],
                         key=lambda c: (c.get("group") not in short, -c.get("credits", 0)))
        reqs.append({"label": f"{cc['name']} 부족", "area": "융합전공", "priority": 2, "need": need,
                     "pool": [{"name_ko": c["name_ko"], "course_id": c.get("course_id", ""),
                               "credits": c["credits"], "assignment": "융합전공",
                               "satisfies": f"{cc['name']} {c.get('group', '')}".strip(),
                               "offered_terms": c.get("offered_terms") or ["1", "2"],
                               "prerequisites": c.get("prerequisites") or [],
                               "confidence": "catalog_verified" if c.get("offered_terms") else "name_only",
                               "manual": not c.get("offered_terms")} for c in untaken]})
    # 3) 전공 부족 — 제1전공 카탈로그 미이수. 미이수 '필수(전공)' 학점은 갭에서 제외(중복선택 방지)
    major_gap = next((g.gap for g in audit.area_gaps if g.area == "전공"), 0.0)
    req_major_credits = sum(it["credits"] for r in reqs if r.get("label") == "필수지정 미이수"
                            for it in r.get("items", []) if r.get("area") == "전공")
    major_gap_eff = max(0.0, round(major_gap - req_major_credits, 1))
    if major_gap_eff > 0:
        pool = [{"name_ko": c.name_ko, "course_id": c.course_id, "credits": c.credits, "satisfies": "전공 부족",
                 "offered_terms": c.offered_terms, "prerequisites": c.prerequisites, "confidence": "catalog_verified"}
                for c in cat["courses"]
                if not ((c.course_id and c.course_id[:5] in confirmed_pref) or normalize_name(c.name_ko) in confirmed_norm)]
        reqs.append({"label": "전공 부족", "area": "전공", "priority": 3, "need": major_gap_eff, "pool": pool})
    # 4) 기초교양 — 필수 미이수 과목명, 또는 영역 부족분을 학기 분할 슬롯으로
    missing_basic = [g for g in (audit.gen_basic_courses or []) if not g["taken"]]
    basic_gap = next((g.gap for g in audit.area_gaps if g.area == "기초교양"), 0.0)
    if missing_basic:
        reqs.append({"label": "기초교양 필수", "area": "기초교양", "priority": 4, "need": None,
                     "items": [{"name_ko": g["name_ko"], "credits": 3.0, "satisfies": "기초교양 필수",
                                "confidence": "name_only", "manual": True} for g in missing_basic]})
    elif basic_gap > 0:
        reqs.append({"label": "기초교양", "area": "기초교양", "priority": 4, "need": basic_gap,
                     "pool": _slot_chunks("기초교양 선택", basic_gap, "기초교양")})
    # 5) 핵심교양 영역별 부족 → 영역 슬롯(학기 분할)
    for g in audit.core_area_gaps:
        if g.gap > 0:
            reqs.append({"label": f"핵심교양 {g.area}", "area": "핵심교양", "priority": 4, "need": g.gap,
                         "pool": _slot_chunks(f"핵심교양 {g.area} 선택", g.gap, f"핵심교양-{g.area}")})
    # 6) 자유교양 부족 → 슬롯(학기 분할)
    free_gap = next((g.gap for g in audit.area_gaps if g.area == "자유교양"), 0.0)
    if free_gap > 0:
        reqs.append({"label": "자유교양", "area": "자유교양", "priority": 4, "need": free_gap,
                     "pool": _slot_chunks("자유교양 선택", free_gap, "자유교양")})
    # 7) 총학점(일반선택) 부족 — 영역 floor를 다 채워도 졸업최저에 모자란 잔여를 일반선택 슬롯으로.
    #    (이게 없으면 '영역 충족인데 총학점 부족'인 학생이 로드맵상 거짓 '충족'으로 표시됨)
    area_floor_gap = round(sum(g.gap for g in audit.area_gaps if g.gap > 0), 1)
    general_need = round(max(0.0, audit.total_gap - area_floor_gap), 1)
    if general_need > 0:
        reqs.append({"label": "총학점(일반선택)", "area": "일반선택", "priority": 5, "need": general_need,
                     "pool": _slot_chunks("일반선택 과목", general_need, "일반선택")})

    # 요건 → 후보 선택(quota 충족까지). 이름 중복 제거(필수지정이 전공부족 후보와 겹침 방지)
    selected: list[dict] = []
    seen: set[str] = set()
    for r in reqs:
        if r.get("items") is not None:
            for it in r["items"]:
                key = normalize_name(it["name_ko"])
                if key in seen:
                    continue
                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]})
        else:
            acc = 0.0
            for it in r["pool"]:
                if acc >= r["need"]:
                    break
                key = normalize_name(it["name_ko"])
                if key in seen:
                    continue
                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]}); acc += it["credits"]
    return selected, reqs


def plan_greedy(selected: list[dict], terms: list[list],
                completed: set | None = None) -> tuple[list[RoadmapTerm], list[str], list[dict]]:
    """선택 후보를 학기에 배치. 우선순위·개설학기(아는 경우)·학점상한 + 선수과목 순서(위상).
    선수과목은 이미 이수(completed prefix)거나 '더 이른' 학기에 배치돼야 같은/이후 학기에 둔다.
    반환 (terms, assumptions, unplaced)."""
    completed = set(completed or set())                 # 이수 과목 코드 앞5자리
    items = sorted(selected, key=lambda c: (c["priority"], -c.get("credits", 0)))
    used = {lab: 0.0 for lab, _ in terms}
    bucket: dict[str, list] = {lab: [] for lab, _ in terms}
    placed_at: dict[str, int] = {}                      # course_id(앞5자리) → term index
    unplaced: list[dict] = []

    def _try_place(it):
        pres = [p[:5] for p in (it.get("prerequisites") or []) if p]
        # 선수 중 selected에 있는데 아직 미배치면 보류(나중 패스)
        sel_pref = {c.get("course_id", "")[:5] for c in items if c.get("course_id")}
        if any(p not in completed and p not in placed_at and p in sel_pref for p in pres):
            return None                                 # defer
        min_idx = 0                                     # 배치된 선수보다 뒤 학기여야
        for p in pres:
            if p in placed_at:
                min_idx = max(min_idx, placed_at[p] + 1)
        off = it.get("offered_terms")
        known = it.get("confidence") == "catalog_verified"
        for allow_seasonal in (False, True):
            for i, (lab, cap) in enumerate(terms):
                if i < min_idx:
                    continue
                sem = _term_sem(lab)
                if known and off and sem not in off:
                    continue
                if not known and sem in ("S", "W") and not allow_seasonal:
                    continue
                if used[lab] + it["credits"] <= cap + 0.01:
                    bucket[lab].append(it); used[lab] += it["credits"]
                    if it.get("course_id"):
                        placed_at[it["course_id"][:5]] = i
                    return True
        return False                                    # 배치 실패(용량/개설학기)

    pending = list(items)
    progress = True
    while pending and progress:
        progress = False
        still = []
        for it in pending:
            r = _try_place(it)
            if r is True:
                progress = True
            elif r is None:
                still.append(it)                        # 선수 미배치 → 다음 패스
            else:
                unplaced.append(it)
        pending = still
    unplaced.extend(pending)                            # 교착(순환/충족불가) → 미배치
    out = []
    for lab, cap in terms:
        if not bucket[lab]:
            continue
        courses = [RoadmapCourse(course_id=it.get("course_id", "") or "", name_ko=it["name_ko"],
                                 credits=it["credits"], satisfies=it.get("satisfies", ""),
                                 assignment=it.get("assignment", ""),
                                 offered_terms=(it.get("offered_terms") or []) if it.get("confidence") == "catalog_verified" else [],
                                 confidence=it.get("confidence", "catalog_verified"),
                                 manual_check=it.get("manual", False)) for it in bucket[lab]]
        out.append(RoadmapTerm(term=lab, courses=courses, term_credits=round(used[lab], 1),
                               term_risk="medium" if used[lab] > cap - 3 else "low"))
    assumptions = []
    if any(it.get("manual") for it in selected):
        assumptions.append("이름기준·교양 슬롯 과목은 개설학기·학점을 수강신청 전 확인하세요.")
    return out, assumptions, unplaced


def run_planner(
    audit: AuditResult, profile: RequirementProfile, context: StudentContext,
    verified: VerifiedTranscript, client=None,
) -> tuple[RoadmapPlan, ValidationReport, dict]:
    """결정론 통합 플래너: 남은 의무 → 단일 후보 풀 → greedy 학기배치 → 검증.
    (LLM 배치 미사용 — codex 권장. plan_roadmap 등 LLM 함수는 보존만.)"""
    overflow = project_overflow(audit, profile, context)
    selected, reqs = build_unified_candidates(audit, profile, verified)
    summary = [{"label": r["label"], "area": r["area"],
                "need": (r.get("need") if r.get("need") is not None else sum(i["credits"] for i in r.get("items", [])))}
               for r in reqs]
    ctx = {"sources": [], "requirements_summary": summary}

    if not selected:
        return (RoadmapPlan(status="generated", feasible=True, terms=[],
                            why_this_plan="졸업요건을 모두 충족했습니다. 추가 수강 계획이 필요 없습니다."),
                ValidationReport(ok=True), ctx)

    reg_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
    terms = _ordered_terms(context, reg_cap)
    if not terms:
        # 현재 학기 미상 → 학기 배치 불가. 무엇을 들어야 하는지만 안내.
        names = ", ".join(f"{it['name_ko']}({it['credits']:.0f})" for it in selected[:12])
        return (RoadmapPlan(status="generated", feasible=None, terms=[],
                            why_this_plan=f"현재 학기 미입력 — 학기 배치 생략. 추가 이수 권장: {names}",
                            assumptions=["현재 학기를 입력하면 학기별 배치를 제공합니다."], overflow=overflow),
                ValidationReport(ok=True), ctx)

    completed = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
    placed, assumptions, unplaced = plan_greedy(selected, terms, completed)

    # 결정론 검증: 학점상한 + 미배치(선수/개설/용량으로 못 넣음). 미배치 있으면 ok=False·blocked.
    errors = []
    for t in placed:
        cap = next((c for lab, c in terms if lab == t.term), reg_cap)
        if t.term_credits > cap + 0.01:
            errors.append(ValidationError(code="over_credit_cap", detail=f"{t.term} {t.term_credits:.0f}>{cap:.0f}"))
    for it in unplaced:
        errors.append(ValidationError(code="unplaced", detail=it["name_ko"], course_id=it.get("course_id") or None))
    report = ValidationReport(ok=not errors, errors=errors)

    parts = [s["label"] for s in summary]
    why = "남은 요건(" + ", ".join(parts) + ")을 잔여 학기에 개설학기·선수·학점상한을 지켜 배치했습니다." if parts else ""
    if unplaced:
        # 잔여 학기로 다 배치 못함 → 정직하게 blocked + 초과학기 시나리오(없으면 생성)
        un = ", ".join(f"{it['name_ko']}({it['credits']:.0f})" for it in unplaced)
        ov = overflow or project_overflow(audit, profile, context)
        hint = "잔여 학기를 늘리거나 계절학기를 활용하세요."
        if ov:
            hint = ov.note + " " + hint
        plan = RoadmapPlan(status="blocked", feasible=False, terms=placed, why_this_plan=why,
                           assumptions=assumptions, overflow=ov,
                           blocked_reason=f"잔여 학기에 다 배치하지 못한 과목: {un}", relaxation_hint=hint)
    else:
        # 전부 배치됨(feasible) → 초과학기 카드는 모순이므로 표시하지 않음(단일 용량 모델)
        plan = RoadmapPlan(status="generated", feasible=True, terms=placed,
                           why_this_plan=why, assumptions=assumptions, overflow=None)
    return plan, report, ctx
