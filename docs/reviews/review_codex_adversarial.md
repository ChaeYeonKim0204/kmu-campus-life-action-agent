I’m going into review mode and will treat this as a correctness audit, not a cleanup pass. I’ll read the v2 backend, data rules, risk/privacy paths, and the React rendering, then rank findings by demo impact.
exec
/bin/bash -lc "sed -n '1,260p' graduation_center/v2/planner.py" in /home/carol/kmu_genai
exec
/bin/bash -lc "sed -n '1,320p' graduation_center/v2/audit_v2.py" in /home/carol/kmu_genai
 succeeded in 0ms:
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

 succeeded in 0ms:
"""졸업 진단 (결정론).

VerifiedTranscript(earned_by_area·core_area_earned) + RequirementProfile로 영역별 갭과
필수과목 누락을 계산한다. 카테고리 총계 요건은 graduation_requirements.json에서 온
RequirementProfile을 그대로 사용(= compute_structured_check와 동일 출처·동일 산식).

주의: '일반선택'은 hard floor가 아니라 총학점 충당용 잔여이므로 강제 갭에서 제외하고,
total_gap(졸업 최저합계 대비)을 전체 구속으로 본다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from graduation_center.v2.models_v2 import (
    AreaGap, AuditResult, RequirementProfile, VerifiedTranscript,
)
from graduation_center.v2.catalog import V2_DIR, load_catalog, load_gen_ed
from graduation_center.v2.text_norm import normalize_name

HARD_AREAS = ["전공", "기초교양", "핵심교양", "자유교양"]  # 일반선택 제외


@lru_cache(maxsize=1)
def _required_year_data() -> dict:
    """학번(입학연도)별 요람 필수 과목명. 코드 무관 — 이름 기준 체크용."""
    p = V2_DIR / "required_names_by_year.json"
    return json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}


def _required_names_for_year(program_id: str, year: int | None) -> list[str] | None:
    """해당 학번에 적용할 요람의 필수 과목명 + 실제 적용 연도. 없으면 (None, None)."""
    by_year = _required_year_data().get(program_id)
    if not by_year:
        return None, None
    avail = sorted(int(y) for y in by_year)
    if year is None:
        pick = avail[-1]
    elif str(year) in by_year:
        pick = year
    else:  # 입학연도 이하의 가장 가까운 요람(없으면 가장 이른 것)
        le = [y for y in avail if y <= year]
        pick = (le[-1] if le else avail[0])
    # 항목은 문자열 또는 {name,credits,terms} — 매칭은 이름만 사용
    names = [(it["name"] if isinstance(it, dict) else it) for it in by_year[str(pick)]]
    return names, pick


def _required_aliases(program_id: str) -> dict:
    """명칭 드리프트 동치(같은 교과목코드, 요람명↔수강내역명). 양방향 그룹으로 반환.

    데이터는 한 방향만 적어도(예: 미래모빌리티실험→모빌리티실험및실습) 양쪽 모두
    매칭되도록 정규화 키별로 동치 집합을 만든다.
    """
    p = V2_DIR / "required_names_by_year.json"
    raw = (json.loads(p.read_text(encoding="utf-8")).get("aliases", {}) if p.exists() else {}).get(program_id, {})
    groups: dict[str, set] = {}
    for k, vs in raw.items():
        members = {normalize_name(k)} | {normalize_name(v) for v in vs}
        for m in members:
            groups.setdefault(m, set()).update(members - {m})
    return {k: sorted(v) for k, v in groups.items()}


def _gen_basic_names(program_id: str, year: int | None) -> list[str]:
    """학번 요람의 기초교양 필수 과목명. 없으면 빈 리스트."""
    p = V2_DIR / "required_names_by_year.json"
    by_year = (json.loads(p.read_text(encoding="utf-8")).get("gen_basic", {}) if p.exists() else {}).get(program_id)
    if not by_year:
        return []
    avail = sorted(int(y) for y in by_year)
    if year is None:
        pick = avail[-1]
    elif str(year) in by_year:
        pick = year
    else:
        le = [y for y in avail if y <= year]
        pick = (le[-1] if le else avail[0])
    return by_year[str(pick)]


def _gen_basic_view(verified: VerifiedTranscript, program_id: str, year: int | None) -> list[dict]:
    """기초교양 필수 과목 이수/미이수 — 학생 기초교양 과목명에 부분일치(정규화)."""
    names = _gen_basic_names(program_id, year)
    if not names:
        return []
    taken_norm = [normalize_name(c.name_ko) for c in verified.confirmed_courses
                  if c.requirement_area == "기초교양"]
    out = []
    for nm in names:
        key = normalize_name(nm)
        taken = any(key in t for t in taken_norm)   # '택1'·접미사(ABEEK) 흡수 위해 부분일치
        out.append({"name_ko": nm, "taken": taken})
    return out


def _admission_year(profile: RequirementProfile, verified: VerifiedTranscript) -> int | None:
    """입학연도 — context.admission_year 우선, 없으면 수강내역 최초 학기 연도에서 추정."""
    if profile.admission_year:
        return int(profile.admission_year)
    years = [int(m.group(1)) for c in verified.confirmed_courses
             if (m := re.search(r"(20\d{2})", c.term_label or ""))]
    return min(years) if years else None


# TODO(동시배정 최적화 — 미구현): 겹침 과목을 제1전공/다전공 vs 융합전공 중 어디에 산입할지
# 최적 배정 + 이수구분정정 추천. 제약:
#   (1) 중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 0). 동시인정은 cap까지만.
#   (2) 그룹별 최저(다전공 12·부전공 6) + 총 최저(36·18) 모두 충족하도록 배정.
#   (3) **제1전공/다전공의 전공필수(is_required) 과목은 융합전공 전용으로 넘길 수 없음**
#       (필수는 해당 전공에 고정; 중복인정만 가능, 이동 불가).
# 현재는 "각 요건 독립 판정 + 중복인정 한도 표시"까지만 구현.
def _convergence_checks(verified: VerifiedTranscript, program_ids, tracks, primary_program_id,
                        primary_major_required: float = 0.0, primary_major_earned: float = 0.0) -> list[dict]:
    """연계·융합전공 졸업요건 + 학점 중복인정(학사규정 제77조). **교과목코드 기반.**

    이수구분 텍스트가 부정확할 수 있어, 과목 분류를 교과목코드 앞5자리로 판정:
      - 연계융합 designated = 학생 이수과목 중 앞5자리가 연계융합 카탈로그에 있는 것(교양 제외).
      - 그중 제1전공 카탈로그(앞5자리)에도 있으면 'shared'(중복인정 대상), 아니면 '융합전용'.
    - 최저: 다전공 36 / 부전공 18.  중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 불인정).
    - 인정 학점 = 융합전용 학점 + min(shared 학점, cap).  (shared 초과분은 제1전공에만 인정)
    """
    tracks = tracks or {}
    GYO = {"기초교양", "핵심교양", "자유교양"}
    # 프로그램별 코드 앞5자리 집합 (제1전공 + 선언한 모든 다전공)
    prog_prefixes: dict[str, set] = {}
    for ppid in [primary_program_id, *(program_ids or [])]:
        if ppid in prog_prefixes:
            continue
        try:
            prog_prefixes[ppid] = {c.course_id[:5] for c in load_catalog(ppid)["courses"] if c.course_id}
        except KeyError:
            prog_prefixes[ppid] = set()
    out = []
    for pid in program_ids or []:
        # 중복인정 겹침 = 제1전공 또는 '다른' 다전공의 전공과목과 동일(앞5자리) (학사규정 제77조)
        other_prefixes = set().union(*[pf for ppid, pf in prog_prefixes.items() if ppid != pid]) \
            if len(prog_prefixes) > 1 else prog_prefixes.get(primary_program_id, set())
        try:
            cat = load_catalog(pid)
        except KeyError:
            continue
        name = cat["department_name_ko"]
        is_yeonge = "연계전공" in name
        track = tracks.get(pid, "다전공")
        req = 36.0 if track == "다전공" else 18.0
        cap = 12.0 if track == "다전공" else (0.0 if is_yeonge else 6.0)
        prefix_to_group = {c.course_id[:5]: c.group for c in cat["courses"] if c.course_id}
        conv_prefixes = set(prefix_to_group)
        # 연계융합 designated 과목(교양 제외) — 코드 앞5자리 기준. 들은 건 전부 융합전공에 인정.
        designated = [c for c in verified.confirmed_courses
                      if c.course_id and c.course_id[:5] in conv_prefixes and c.requirement_area not in GYO]
        earned = round(sum(c.credits for c in designated), 1)
        gap = max(0.0, round(req - earned, 1))
        # 그룹별 최저(다전공 12 / 부전공 6) 체크
        rules = (cat.get("group_rules") or {}).get(track, {})
        per_group_min = float(rules.get("per_group_min", 12 if track == "다전공" else 6))
        all_groups = sorted({g for g in prefix_to_group.values() if g})
        group_earned = {g: 0.0 for g in all_groups}
        for c in designated:
            g = prefix_to_group.get(c.course_id[:5])
            if g:
                group_earned[g] = round(group_earned.get(g, 0) + c.credits, 1)
        group_checks = [{"group": g, "earned": group_earned[g], "required": per_group_min,
                         "gap": max(0.0, round(per_group_min - group_earned[g], 1))} for g in all_groups]
        # 그중 제1전공/다른 다전공과 겹치는 과목 = 중복인정 가능 후보(최대 cap까지 양쪽 동시 인정)
        overlap = sorted([c for c in designated if c.course_id[:5] in other_prefixes], key=lambda x: -x.credits)
        overlap_cr = round(sum(c.credits for c in overlap), 1)
        double_recognizable = round(min(overlap_cr, cap), 1)
        # 제1전공/다른 다전공의 '전공필수' 코드 앞5자리 — 중복인정 권장 우선순위
        required_prefixes: set = set()
        for ppid in prog_prefixes:
            if ppid == pid:
                continue
            try:
                required_prefixes |= {c.course_id[:5] for c in load_catalog(ppid)["courses"]
                                      if c.course_id and c.is_required}
            except KeyError:
                pass
        taken_prefixes = {c.course_id[:5] for c in designated}
        # 교육과정 전체 과목 + 이수 강조 + 겹침/이수 여부
        courses_view = []
        for cc in cat["courses"]:
            if not cc.course_id:
                continue
            pfx = cc.course_id[:5]
            courses_view.append({
                "name_ko": cc.name_ko, "group": cc.group or "", "credits": cc.credits,
                "taken": pfx in taken_prefixes, "overlap": pfx in other_prefixes,
                "primary_required": pfx in required_prefixes,
                "course_id": cc.course_id, "offered_terms": list(cc.offered_terms or []),
                "prerequisites": list(cc.prerequisites or []),
            })
        # 중복인정 '추천' = 들은 겹침과목 중 제1전공/다전공 '전공필수' 우선(없으면 학점순), 한도(cap)까지.
        # 한도를 넘는 겹침 과목은 '후보'일 뿐(실제 중복인정 X, 한쪽에만 산입).
        rec_pool = sorted([c for c in courses_view if c["taken"] and c["overlap"]],
                          key=lambda c: (not c["primary_required"], -c["credits"]))
        rec, rec_keys, acc = [], set(), 0.0
        for c in rec_pool:
            if acc >= cap:
                break
            rec.append(c["name_ko"]); rec_keys.add(id(c)); acc += c["credits"]
        # 이수구분 기본 라벨(표시용). 겹침(중복인정 가능) 과목은 프론트에서 3-way로 사용자 선택.
        for c in courses_view:
            if not c["taken"]:
                c["assignment"], c["selectable"] = "미이수", False
            elif not c["overlap"]:
                c["assignment"], c["selectable"] = "융합전용", False
            else:
                c["assignment"], c["selectable"] = "중복인정", True   # 기본 중복인정, 사용자 변경 가능
        # 고정분: 겹침을 제외한 나머지. 제1전공 non-overlap / 융합전용. 겹침은 전부 사용자 배정 풀.
        primary_base = round(primary_major_earned - overlap_cr, 1)    # 제1전공 non-overlap (예: 43)
        fusion_base = round(earned - overlap_cr, 1)                   # 융합전용 (예: 18)
        overlap_courses = [{"name_ko": c.name_ko, "credits": c.credits,
                            "group": prefix_to_group.get(c.course_id[:5]) or "",
                            "primary_required": c.course_id[:5] in required_prefixes}
                           for c in overlap]
        group_short = [gc for gc in group_checks if gc["gap"] > 0]
        note = (f"제1전공과 겹치는 {overlap_cr:.0f}학점은 중복인정(양쪽 동시) 최대 {cap:.0f}까지. "
                f"한도 초과·미선택분은 제1전공 또는 {('연계' if is_yeonge else '융합')}전공 한쪽에만 인정돼 양쪽 학점이 달라집니다.")
        out.append({
            "program_id": pid, "name": name, "track": track,
            "conv_type": "연계전공" if is_yeonge else "융합전공",
            "required": req, "double_cap": cap, "per_group_min": per_group_min,
            "earned": earned, "gap": gap, "group_checks": group_checks,
            "overlap_credits": overlap_cr, "double_recognizable": double_recognizable,
            "recommend_double_count": rec, "note": note, "courses": courses_view,
            # 동시배정: 제1전공 = primary_base + (중복인정+제1전공 선택분), 융합 = fusion_base + (중복인정+융합 선택분)
            "primary_base": primary_base, "fusion_base": fusion_base,
            "primary_required": primary_major_required, "overlap_courses": overlap_courses,
        })
    return out


def compute_audit(
    verified: VerifiedTranscript, profile: RequirementProfile,
    convergence_program_ids=(), convergence_tracks=None,
) -> AuditResult:
    earned = verified.earned_by_area
    # 핵심교양 영역별 최저(별표5 단과대 override 반영 — 예: 미래모빌리티 소통 5)
    gen = load_gen_ed().get("core_liberal", {})
    core_min = float(profile.core_area_min or 3)
    overrides = profile.core_area_min_overrides or {}
    gen_areas = gen.get("areas", [])
    # 핵심교양 총 요건 = 영역별 최저 합(소통 override 포함). 예: 미래모빌리티 5+3+3+3+3=17
    core_total_required = sum(float(overrides.get(a, core_min)) for a in gen_areas) or float(profile.area_min.get("핵심교양", 0))

    area_gaps: list[AreaGap] = []
    for area in HARD_AREAS:
        # 핵심교양은 영역별 최저 합을 요건으로(학번 요람 별표5 반영)
        req = core_total_required if area == "핵심교양" else float(profile.area_min.get(area, 0))
        got = float(earned.get(area, 0))
        if req <= 0:
            continue
        area_gaps.append(AreaGap(area=area, required=req, earned=got, gap=max(0.0, req - got)))

    core_gaps: list[AreaGap] = []
    for area in gen_areas:
        req = float(overrides.get(area, core_min))
        got = float(verified.core_area_earned.get(area, 0))
        core_gaps.append(AreaGap(area=area, required=req, earned=got, gap=max(0.0, req - got)))

    # 필수과목 누락 — 학번(입학연도) 요람 기준 '이름' 매칭(코드 무관 → 연도별 현황 엑셀 불필요).
    # 교육과정은 해마다 개편돼 명칭·코드가 바뀌므로, 학생 학번에 맞는 요람의 필수명과
    # 학생 수강내역 과목명을 정규화해 대조한다. 연도 데이터가 없으면 카탈로그 코드 prefix로 폴백.
    cat = load_catalog(profile.program_id)
    year = _admission_year(profile, verified)
    req_names, applied_year = _required_names_for_year(profile.program_id, year)
    if req_names:
        confirmed_norm = {normalize_name(c.name_ko) for c in verified.confirmed_courses}
        aliases = _required_aliases(profile.program_id)

        def _taken(rn: str) -> bool:
            nn = normalize_name(rn)
            if nn in confirmed_norm:
                return True
            return any(a in confirmed_norm for a in aliases.get(nn, []))  # 명칭 드리프트 동치
        missing_names = [rn for rn in req_names if not _taken(rn)]
        missing_ids = []                       # 이름 기준 — 코드 없음
        required_available = True
        if applied_year:
            profile.applied_yoram = f"{applied_year} 요람 (학번 {year} 기준)" if year else f"{applied_year} 요람"
    else:
        confirmed_prefixes = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
        missing_ids = [cid for cid in profile.required_course_ids if cid[:5] not in confirmed_prefixes]
        missing_names = [cat["by_code"][cid].name_ko for cid in missing_ids if cid in cat["by_code"]]
        required_available = bool(profile.required_course_ids)

    total_req = float(profile.total_credits_min or 0)
    total_earned = float(verified.total_earned)
    unresolved_credits = round(sum(m.raw.credits for m in verified.unresolved), 1)

    return AuditResult(
        total_required=total_req,
        total_earned=total_earned,
        total_gap=max(0.0, round(total_req - total_earned, 1)),
        area_gaps=area_gaps,
        core_area_gaps=core_gaps,
        missing_required_course_ids=missing_ids,
        missing_required_names=missing_names,
        required_check_available=required_available,
        gen_basic_courses=_gen_basic_view(verified, profile.program_id, year),
        convergence_checks=_convergence_checks(verified, convergence_program_ids, convergence_tracks,
                                               profile.program_id, float(profile.area_min.get("전공", 0)),
                                               float(earned.get("전공", 0))),
        unresolved_credits=unresolved_credits,
    )

exec
/bin/bash -lc "sed -n '1,260p' graduation_center/v2/catalog.py" in /home/carol/kmu_genai
 succeeded in 0ms:
"""v2 카탈로그·요건 로딩 + 과목 매칭 (결정론).

- 카탈로그/요건/교양은 data/graduation/v2/ 의 빌드 산출물에서 로드(캐시).
- match_course: 교과목코드 7자리 정확매칭 우선 → 이름 정규화 → 미스 시 unresolved.
- 카탈로그 밖(교양·타과)은 자동분류 금지: 이수구분 원문으로 집계영역만 부여(aggregate_only).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from graduation_center.v2.models_v2 import (
    Area, CatalogCourse, CourseMatch, RawLine, RequirementProfile, StudentContext,
)
from graduation_center.v2.text_norm import normalize_code, normalize_name

V2_DIR = Path("data/graduation/v2")
GRAD_REQ = Path("data/graduation/graduation_requirements.json")

# 이수구분 원문 → 집계 영역
_ISU_TO_AREA: dict[str, Area] = {
    "전공필수": "전공", "전공선택": "전공", "전공": "전공",
    "기초교양": "기초교양", "핵심교양": "핵심교양", "자유교양": "자유교양",
    "일반선택": "일반선택", "교직": "일반선택", "다전공": "일반선택",
}


def area_from_isugubun(isu: str | None) -> Area:
    s = str(isu or "").strip()
    for key, area in _ISU_TO_AREA.items():
        if key in s:
            return area
    return "일반선택"


@lru_cache(maxsize=1)
def load_programs() -> dict:
    p = V2_DIR / "programs.json"
    return json.loads(p.read_text(encoding="utf-8"))["programs"] if p.exists() else {}


# 학사규정 제32조(학기당 이수학점): 졸업 최저이수학점 → 정규학기 상한.
SEASONAL_TERM_CAP = 6.0          # 제32조 ④ 계절학기 6학점
PREV_GPA_BONUS = 3.0             # 제32조 ①-4 직전학기 평점평균 3.75 이상 → +3학점


def regular_term_cap(total_credits_min: float) -> float:
    """졸업 최저이수학점 → 학기당 정규 이수학점 상한(제32조 ①)."""
    t = float(total_credits_min or 0)
    if t >= 136:
        return 19.0
    if t >= 130:
        return 18.0
    if t >= 120:
        return 17.0
    return 18.0                   # 미상 시 보수적 기본값


def program_total_min(program_id: str) -> float | None:
    """프로그램의 졸업 최저이수학점(요건 데이터). 연계·융합전공(키 없음)은 None."""
    progs = load_programs()
    key = progs.get(program_id, {}).get("requirements_key")
    if not key:
        return None
    try:
        req = json.loads(GRAD_REQ.read_text(encoding="utf-8"))["departments"][key]
        return float(req.get("졸업_최저합계", 0)) or None
    except Exception:
        return None


@lru_cache(maxsize=1)
def load_gen_ed() -> dict:
    p = V2_DIR / "gen_ed_catalog.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@lru_cache(maxsize=8)
def load_catalog(program_id: str) -> dict:
    """프로그램 카탈로그 로드 → {by_code, by_norm, courses}."""
    progs = load_programs()
    if program_id not in progs:
        raise KeyError(f"unknown program_id: {program_id}")
    data = json.loads((V2_DIR / progs[program_id]["catalog_file"]).read_text(encoding="utf-8"))
    by_code: dict[str, CatalogCourse] = {}
    by_norm: dict[str, list[str]] = {}
    for c in data["courses"]:
        cc = CatalogCourse.model_validate(c)
        by_code[cc.course_id] = cc
        by_norm.setdefault(cc.name_norm, []).append(cc.course_id)
        for al in cc.aliases:
            by_norm.setdefault(normalize_name(al), []).append(cc.course_id)
    return {"by_code": by_code, "by_norm": by_norm, "courses": list(by_code.values()),
            "requirements_key": progs[program_id]["requirements_key"],
            "department_name_ko": progs[program_id]["name_ko"],
            "track_type": progs[program_id].get("track_type", "primary"),
            "convergence_required": progs[program_id].get("convergence_required"),
            "group_rules": data.get("group_rules")}


def _requirements_by_year(program_id: str, year: int | None) -> dict | None:
    """학번(입학연도) 요람 별표5 영역 최저학점. 없으면 None."""
    if not year:
        return None
    p = V2_DIR / "requirements_by_year.json"
    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
    if not by_year:
        return None
    # 정확 연도만 적용(기본값 graduation_requirements.json이 최신 요람 기준이므로 임의 근사 금지)
    return by_year.get(str(year))


def assemble_requirement_profile(context: StudentContext) -> RequirementProfile:
    """graduation_requirements.json(카테고리 총계) + 카탈로그 필수과목으로 요건 프로파일 구성.

    학번(입학연도) 요람 별표5(requirements_by_year.json)가 있으면 영역 최저학점은 그것을 우선.
    """
    cat = load_catalog(context.program_id)
    req = json.loads(GRAD_REQ.read_text(encoding="utf-8"))["departments"][cat["requirements_key"]]
    gyo = req.get("교양", {})
    yr = _requirements_by_year(context.program_id, context.admission_year)
    area_min = {
        "전공": float((yr or {}).get("전공", req.get("전공_최저", 0))),
        "기초교양": float((yr or {}).get("기초교양", gyo.get("기초교양", 0))),
        "핵심교양": float((yr or {}).get("핵심교양", gyo.get("핵심교양", 0))),
        "자유교양": float((yr or {}).get("자유교양", gyo.get("자유교양", 0))),
        "일반선택": float((yr or {}).get("일반선택", req.get("일반선택", 0))),
    }
    total_min = float((yr or {}).get("졸업_최저합계", req.get("졸업_최저합계", 0)))
    required_ids = [c.course_id for c in cat["courses"] if c.is_required]
    gen = load_gen_ed().get("core_liberal", {})
    applied = f"{context.admission_year} 요람 (학번 기준)" if (yr and context.admission_year) else "2025 요람"
    return RequirementProfile(
        program_id=context.program_id,
        department_name_ko=cat["department_name_ko"],
        admission_year=context.admission_year,
        total_credits_min=total_min,
        area_min=area_min,
        required_course_ids=required_ids,
        core_area_min=float(gen.get("area_min_credits", 3)),
        core_area_min_overrides={k: float(v) for k, v in (req.get("핵심교양_영역최저") or {}).items()},
        core_total_min=float(gen.get("total_min_credits", 15)),
        applied_yoram=applied,
    )


def match_course(raw: RawLine, program_id: str) -> CourseMatch:
    cat = load_catalog(program_id)
    gen = load_gen_ed().get("core_liberal", {})
    code = normalize_code(raw.course_code)
    area_raw = area_from_isugubun(raw.area_raw)
    core_area = None
    if area_raw == "핵심교양":
        core_area = (gen.get("name_norm_to_area") or {}).get(normalize_name(raw.course_name))

    # 1) 코드 정확매칭 (카탈로그 = 전공)
    if code and code in cat["by_code"]:
        cc = cat["by_code"][code]
        return CourseMatch(raw=raw, matched_course_id=code, match_by="code",
                           status="matched", requirement_area=cc.requirement_area)
    # 2) 이름 정규화 매칭 (유니크할 때만)
    hits = cat["by_norm"].get(normalize_name(raw.course_name), [])
    if len(hits) == 1:
        cc = cat["by_code"][hits[0]]
        return CourseMatch(raw=raw, matched_course_id=hits[0], match_by="name",
                           status="matched", requirement_area=cc.requirement_area)
    # 3) 카탈로그 밖 → 이수구분으로 집계영역만 (교양·타과·일반선택)
    if raw.area_raw:
        return CourseMatch(raw=raw, status="aggregate_only",
                           requirement_area=area_raw, core_area=core_area)
    # 4) 판단 불가
    return CourseMatch(raw=raw, status="unresolved")

I’ve already found a likely roadmap blocker: the v2 planner file starts with the older LLM-planning path, but the requested deterministic functions are lower in the file. I’m reading the rest now plus verification/models and the JSON rule data to validate the year and convergence assumptions.
exec
/bin/bash -lc "sed -n '1,320p' graduation_center/v2/verification.py" in /home/carol/kmu_genai
exec
/bin/bash -lc "sed -n '260,620p' graduation_center/v2/planner.py" in /home/carol/kmu_genai
 succeeded in 0ms:
"""사용자 검증(HITL) — 신뢰성 다리 (결정론).

수강내역엔 성적이 없으므로 F/재수강을 자동 판정하지 않는다. 동일 코드가 여러 학기
나오면(=재수강 가능) 첫 이수만 기본 포함, 나머지는 기본 제외(확인 필요)로 두고 사용자가
조정한다. 카탈로그 밖 과목은 aggregate_only로 집계영역에만 반영.
"""
from __future__ import annotations

import re

from graduation_center.v2.catalog import area_from_isugubun, match_course
from graduation_center.v2.models_v2 import (
    CourseMatch, RawLine, VerifiedCourse, VerifiedTranscript,
)


def _term_order(label: str) -> tuple[int, int]:
    """학기 라벨('2023학년도 1학기'/'하계'/'동계') → 정렬 키. 클수록 최신."""
    m = re.search(r"(\d{4})", label or "")
    year = int(m.group(1)) if m else 0
    if "1학기" in label:
        sem = 1
    elif "하계" in label:
        sem = 2
    elif "2학기" in label:
        sem = 3
    elif "동계" in label:
        sem = 4
    else:
        sem = 0
    return (year, sem)


def build_verification_table(
    lines: list[RawLine], program_id: str, retakes: list[dict],
) -> tuple[list[VerifiedCourse], list[CourseMatch], list[dict]]:
    """매칭 → 편집 가능한 검증 테이블 + unresolved + possible_retakes."""
    retake_codes = {r["course_code"] for r in retakes}
    # 재수강 코드의 '최신 이수' 학기 (가장 마지막 이수만 기본 포함)
    latest: dict[str, tuple[int, int]] = {}
    for ln in lines:
        if ln.course_code in retake_codes:
            o = _term_order(ln.term_label)
            if ln.course_code not in latest or o > latest[ln.course_code]:
                latest[ln.course_code] = o
    table: list[VerifiedCourse] = []
    unresolved: list[CourseMatch] = []
    used_latest: set[str] = set()
    for ln in lines:
        m = match_course(ln, program_id)
        if m.status == "unresolved":
            unresolved.append(m)
            continue
        area = m.requirement_area or area_from_isugubun(ln.area_raw)
        # 선택 전공의 교과목코드(현황)에도 이름에도 매칭 안 된 '전공선택'은 이 전공 과목이 아님
        # → 일반선택으로 재분류(학사규정: 타과·다전공 전공과목은 일반선택). 교양은 이수구분 유지.
        if m.status == "aggregate_only" and area == "전공":
            area = "일반선택"
        included, reason = True, None
        code = ln.course_code
        # 폐강 자동 제외
        if "폐강" in (ln.note or "") or "폐강" in (ln.area_raw or ""):
            included, reason = False, "폐강"
        elif code and code in retake_codes:
            # 최신 이수만 포함, 이전 이수는 제외(확인 필요)
            if _term_order(ln.term_label) == latest[code] and code not in used_latest:
                used_latest.add(code)
            else:
                included, reason = False, "재수강(이전 이수)"
        table.append(VerifiedCourse(
            # 실제 엑셀 교과목코드를 항상 보존(제1전공 카탈로그 밖 과목도 융합전공 코드매칭 가능하도록).
            course_id=ln.course_code or m.matched_course_id,
            name_ko=ln.course_name,
            credits=ln.credits,
            requirement_area=area,
            core_area=m.core_area,
            term_label=ln.term_label,
            included=included,
            exclude_reason=reason,
            aggregate_only=(m.status == "aggregate_only"),
        ))
    # 학기 오름차순(과거→최신) 정렬 — 화면 표시·검토 순서
    table.sort(key=lambda vc: _term_order(vc.term_label))
    return table, unresolved, retakes


def finalize_transcript(
    table: list[VerifiedCourse], unresolved: list[CourseMatch], retakes: list[dict],
) -> VerifiedTranscript:
    """확정 테이블(사용자 편집 반영) → 집계."""
    earned_by_area: dict[str, float] = {}
    core_area_earned: dict[str, float] = {}
    total = 0.0
    confirmed, excluded = [], []
    for vc in table:
        if vc.included:
            confirmed.append(vc)
            earned_by_area[vc.requirement_area] = earned_by_area.get(vc.requirement_area, 0.0) + vc.credits
            total += vc.credits
            if vc.requirement_area == "핵심교양" and vc.core_area:
                core_area_earned[vc.core_area] = core_area_earned.get(vc.core_area, 0.0) + vc.credits
        else:
            excluded.append(vc)
    return VerifiedTranscript(
        confirmed_courses=confirmed,
        excluded=excluded,
        unresolved=unresolved,
        possible_retakes=retakes,
        earned_by_area=earned_by_area,
        core_area_earned=core_area_earned,
        total_earned=round(total, 1),
    )

 succeeded in 0ms:
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


def build_unified_candidates(audit: AuditResult, profile: RequirementProfile,
                             verified: VerifiedTranscript) -> tuple[list[dict], list[dict]]:
    """남은 졸업 의무를 단일 후보 풀로 정규화(전공·필수·융합·교양). 반환 (선택후보, 요건요약)."""
    cat = load_catalog(profile.program_id)
    confirmed_norm = {normalize_name(c.name_ko) for c in verified.confirmed_courses}
    confirmed_pref = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
    reqs: list[dict] = []

    # 1) 미이수 필수(이름) — 전부 이수 필요. 요람 메타로 학점·개설학기 반영
    if audit.missing_required_names:
        rmeta = _required_meta(profile.program_id, profile.admission_year)
        items = []
        for n in audit.missing_required_names:
            m = rmeta.get(normalize_name(n), {})
            terms = m.get("terms") or []
            items.append({"name_ko": n, "credits": m.get("credits", 3.0), "satisfies": "필수지정",
                          "offered_terms": terms or ["1", "2"],
                          "confidence": "catalog_verified" if terms else "name_only",
                          "manual": not terms})
        reqs.append({"label": "필수지정 미이수", "area": "전공", "priority": 1, "need": None, "items": items})
    # 2) 연계융합 부족 — 부족 그룹 우선 미이수 융합과목
    for cc in audit.convergence_checks:
        if cc.get("gap", 0) > 0:
            short = {g["group"] for g in cc.get("group_checks", []) if g["gap"] > 0}
            untaken = sorted([c for c in cc.get("courses", []) if not c["taken"]],
                             key=lambda c: (c.get("group") not in short, -c.get("credits", 0)))
            reqs.append({"label": f"{cc['name']} 부족", "area": "융합전공", "priority": 2, "need": cc["gap"],
                         "pool": [{"name_ko": c["name_ko"], "course_id": c.get("course_id", ""),
                                   "credits": c["credits"], "assignment": "융합전공",
                                   "satisfies": f"{cc['name']} {c.get('group', '')}".strip(),
                                   "offered_terms": c.get("offered_terms") or ["1", "2"],
                                   # 융합 카탈로그는 현황 기반 → 개설학기 known(있으면 hard-check)
                                   "confidence": "catalog_verified" if c.get("offered_terms") else "name_only",
                                   "manual": not c.get("offered_terms")} for c in untaken]})
    # 3) 전공 부족 — 제1전공 카탈로그 미이수
    major_gap = next((g.gap for g in audit.area_gaps if g.area == "전공"), 0.0)
    if major_gap > 0:
        pool = [{"name_ko": c.name_ko, "course_id": c.course_id, "credits": c.credits, "satisfies": "전공 부족",
                 "offered_terms": c.offered_terms, "prerequisites": c.prerequisites, "confidence": "catalog_verified"}
                for c in cat["courses"]
                if not ((c.course_id and c.course_id[:5] in confirmed_pref) or normalize_name(c.name_ko) in confirmed_norm)]
        reqs.append({"label": "전공 부족", "area": "전공", "priority": 3, "need": major_gap, "pool": pool})
    # 4) 기초교양 — 필수 미이수 과목명이 있으면 그것을, 없으면 영역 부족분을 슬롯으로
    missing_basic = [g for g in (audit.gen_basic_courses or []) if not g["taken"]]
    basic_gap = next((g.gap for g in audit.area_gaps if g.area == "기초교양"), 0.0)
    if missing_basic:
        reqs.append({"label": "기초교양 필수", "area": "기초교양", "priority": 4, "need": None,
                     "items": [{"name_ko": g["name_ko"], "credits": 3.0, "satisfies": "기초교양 필수",
                                "confidence": "name_only", "manual": True} for g in missing_basic]})
    elif basic_gap > 0:
        reqs.append({"label": "기초교양", "area": "기초교양", "priority": 4, "need": basic_gap,
                     "pool": [{"name_ko": "기초교양 선택", "credits": basic_gap, "satisfies": "기초교양",
                               "confidence": "generic_slot", "manual": True}]})
    # 5) 핵심교양 영역별 부족 → 영역 슬롯
    for g in audit.core_area_gaps:
        if g.gap > 0:
            reqs.append({"label": f"핵심교양 {g.area}", "area": "핵심교양", "priority": 4, "need": g.gap,
                         "pool": [{"name_ko": f"핵심교양 {g.area} 선택", "credits": g.gap,
                                   "satisfies": f"핵심교양-{g.area}", "confidence": "generic_slot", "manual": True}]})
    # 6) 자유교양 부족 → 슬롯
    free_gap = next((g.gap for g in audit.area_gaps if g.area == "자유교양"), 0.0)
    if free_gap > 0:
        reqs.append({"label": "자유교양", "area": "자유교양", "priority": 4, "need": free_gap,
                     "pool": [{"name_ko": "자유교양 선택", "credits": free_gap, "satisfies": "자유교양",
                               "confidence": "generic_slot", "manual": True}]})

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


def plan_greedy(selected: list[dict], terms: list[list]) -> tuple[list[RoadmapTerm], list[str], list[dict]]:
    """선택 후보를 학기에 greedy 배치(우선순위·개설학기[아는 경우]·학점상한). 반환 (terms, assumptions, unplaced)."""
    items = sorted(selected, key=lambda c: (c["priority"], -c.get("credits", 0)))
    used = {lab: 0.0 for lab, _ in terms}
    bucket: dict[str, list] = {lab: [] for lab, _ in terms}
    unplaced = []
    for it in items:
        off = it.get("offered_terms")
        known = it.get("confidence") == "catalog_verified"
        placed = False
        # 1차: 개설학기 아는 과목은 해당 학기, 불확실 과목은 정규학기에만. 2차: 계절학기까지 허용
        for allow_seasonal in (False, True):
            for lab, cap in terms:
                sem = _term_sem(lab)
                if known and off and sem not in off:
                    continue
                if not known and sem in ("S", "W") and not allow_seasonal:
                    continue            # 개설학기 불확실 과목은 정규학기 우선
                if used[lab] + it["credits"] <= cap + 0.01:
                    bucket[lab].append(it); used[lab] += it["credits"]; placed = True; break
            if placed:
                break
        if not placed:
            unplaced.append(it)
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

    placed, assumptions, unplaced = plan_greedy(selected, terms)
    errors = []
    for t in placed:
        cap = next((c for lab, c in terms if lab == t.term), reg_cap)
        if t.term_credits > cap + 0.01:
            errors.append(ValidationError(code="over_credit_cap", detail=f"{t.term} {t.term_credits} > {cap}"))
    report = ValidationReport(ok=not errors, errors=errors)

    parts = [f"{s['label']}" for s in summary]
    why = "남은 요건(" + ", ".join(parts) + ")을 잔여 학기에 배치했습니다." if parts else ""
    plan = RoadmapPlan(status="generated", feasible=not unplaced, terms=placed,
                       why_this_plan=why, assumptions=assumptions, overflow=overflow)
    if unplaced:
        un = ", ".join(f"{it['name_ko']}({it['credits']:.0f})" for it in unplaced)
        hint = "잔여 학기를 늘리거나 계절학기를 활용하세요."
        if overflow:
            hint = overflow.note + " " + hint
        plan.feasible = False
        plan.blocked_reason = f"잔여 학기에 다 배치하지 못한 과목: {un}"
        plan.relaxation_hint = hint
    return plan, report, ctx

exec
/bin/bash -lc "sed -n '1,340p' graduation_center/v2/models_v2.py" in /home/carol/kmu_genai
 succeeded in 0ms:
"""졸업센터 v2 Pydantic 스키마 (Bounded Audit Agent).

데이터 계약: 결정론 노드가 사실(matching·audit·risk)을 채우고, LLM은 RoadmapPlan만
생성하며, 검증기가 RoadmapPlan을 재확인한다. AuditPipelineResponse가 JSON-first 응답.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 졸업요건 영역 (집계 카테고리). 융합전공은 연계·융합전공 카탈로그 과목 표시용.
Area = Literal["전공", "기초교양", "핵심교양", "자유교양", "일반선택", "융합전공"]
GpaMinStatus = Literal["yes", "no", "unknown"]


# ---------- 입력 컨텍스트 ----------
class StudentContext(BaseModel):
    program_id: str                                  # 예: ai_bigdata, mirae_mobility
    admission_year: int | None = None
    current_term: str | None = None                  # "2026-1" 등; None이면 로드맵 시작점 미상
    remaining_semesters: int = Field(default=2, ge=0, le=12)
    seasonal_semester_allowed: bool = False
    max_courses_per_term: int = Field(default=6, ge=1, le=12)
    max_credits_per_term: float | None = None        # 사용자 override; None이면 학사규정 제32조로 산출
    prev_term_gpa_ge_375: bool = False               # 직전학기 평점 3.75↑ → 첫 학기 +3학점(제32조)
    preferences: list[str] = Field(default_factory=list)
    gpa_min_met: GpaMinStatus = "unknown"            # 엑셀에 성적 없음 → 사용자 선언
    convergence_program_ids: list[str] = Field(default_factory=list)  # 연계·융합전공 — 사용자 입력
    convergence_tracks: dict[str, str] = Field(default_factory=dict)  # program_id → "다전공"|"부전공"
    masked_student_id: str | None = None             # 표시용(뒷자리 마스킹)


# ---------- 카탈로그 ----------
class CatalogCourse(BaseModel):
    course_id: str                                   # 교과목코드 7자리
    name_ko: str
    name_norm: str = ""
    aliases: list[str] = Field(default_factory=list)
    credits: float = 0.0
    requirement_area: Area = "전공"
    is_required: bool = False                        # 요람 비고 '필수지정'
    prerequisites: list[str] = Field(default_factory=list)        # course_id
    prereq_external: list[str] = Field(default_factory=list)      # 미해소 선수(이름) → 확인 필요
    grade_level: int | None = None
    offered_terms: list[str] = Field(default_factory=lambda: ["1", "2"])
    group: str | None = None                         # 연계융합전공 그룹(A그룹/B그룹) — 그룹별 최저 체크용
    source: dict = Field(default_factory=dict)


# ---------- 파싱/매칭 ----------
class RawLine(BaseModel):
    """수강내역 .xls 한 행."""
    course_code: str = ""
    course_name: str = ""
    area_raw: str = ""                               # 이수구분 원문(전공선택/기초교양...)
    credits: float = 0.0
    section: str = ""                                # 분반
    term_label: str = ""                             # 파일/헤더에서 온 학기 라벨
    professor: str = ""
    note: str = ""                                   # 비고


class CourseMatch(BaseModel):
    raw: RawLine
    matched_course_id: str | None = None
    match_by: Literal["code", "name", "none"] = "none"
    status: Literal["matched", "aggregate_only", "unresolved"] = "unresolved"
    requirement_area: Area | None = None             # 확정 영역(매칭/이수구분 유래)
    core_area: str | None = None                     # 핵심교양 세부영역(인문Ⅰ..)


# ---------- 검증 ----------
class VerifiedCourse(BaseModel):
    course_id: str | None = None
    name_ko: str
    credits: float
    requirement_area: Area
    core_area: str | None = None
    term_label: str = ""
    included: bool = True
    exclude_reason: str | None = None                # 폐강 / F / 재수강중복
    aggregate_only: bool = False                     # 카탈로그 밖(교양·타과) → 집계만


class VerifiedTranscript(BaseModel):
    confirmed_courses: list[VerifiedCourse] = Field(default_factory=list)
    excluded: list[VerifiedCourse] = Field(default_factory=list)
    unresolved: list[CourseMatch] = Field(default_factory=list)
    possible_retakes: list[dict] = Field(default_factory=list)    # {code, name, term_labels[]}
    earned_by_area: dict[str, float] = Field(default_factory=dict)
    core_area_earned: dict[str, float] = Field(default_factory=dict)
    total_earned: float = 0.0


# ---------- 요건 프로파일 ----------
class RequirementProfile(BaseModel):
    program_id: str
    department_name_ko: str = ""
    admission_year: int | None = None
    total_credits_min: float = 0.0
    area_min: dict[str, float] = Field(default_factory=dict)      # {전공,기초교양,핵심교양,자유교양,일반선택}
    required_course_ids: list[str] = Field(default_factory=list)
    core_area_min: float = 3.0
    core_area_min_overrides: dict[str, float] = Field(default_factory=dict)  # 별표5 영역별 override(예: 소통 5)
    core_total_min: float = 15.0
    applied_yoram: str = "2025 요람"


# ---------- 진단 ----------
class AreaGap(BaseModel):
    area: str
    required: float
    earned: float
    gap: float


class AuditResult(BaseModel):
    total_required: float
    total_earned: float
    total_gap: float
    area_gaps: list[AreaGap] = Field(default_factory=list)
    core_area_gaps: list[AreaGap] = Field(default_factory=list)   # 핵심교양 영역별
    missing_required_course_ids: list[str] = Field(default_factory=list)
    missing_required_names: list[str] = Field(default_factory=list)
    required_check_available: bool = True   # 요람 필수지정 데이터 구축 여부
    gen_basic_courses: list[dict] = Field(default_factory=list)   # 기초교양 필수 [{name_ko,taken}]
    convergence_checks: list[dict] = Field(default_factory=list)  # [{program_id,name,required,earned,gap,matched_courses}]
    unresolved_credits: float = 0.0


# ---------- 리스크 ----------
class RiskReason(BaseModel):
    factor: str
    detail: str
    severity: int = 0


class RiskAssessment(BaseModel):
    grade: Literal["A", "B", "C", "D"]
    label: str
    score: int = 0
    reasons: list[RiskReason] = Field(default_factory=list)


# ---------- 로드맵 ----------
class RoadmapCourse(BaseModel):
    course_id: str = ""                              # 슬롯/이름기준 후보는 빈 값
    name_ko: str = ""
    credits: float = 0.0
    satisfies: str = ""                              # 영역/필수 (예: 필수지정, 전공 부족, 융합 A그룹)
    reason: str = ""
    assignment: str = ""                             # 융합 과목 이수구분(중복인정/제1전공/융합전공) 등
    offered_terms: list[str] = Field(default_factory=list)   # 개설학기(아는 경우; 예: ["1"],["1","2"])
    confidence: Literal["catalog_verified", "name_only", "generic_slot"] = "catalog_verified"
    manual_check: bool = False                       # 개설학기·학점 확인 필요(이름기준/슬롯)
    source_ids: list[str] = Field(default_factory=list)


class RoadmapTerm(BaseModel):
    term: str
    courses: list[RoadmapCourse] = Field(default_factory=list)
    term_credits: float = 0.0
    term_risk: Literal["low", "medium", "high"] = "low"
    notes: list[str] = Field(default_factory=list)


class OverflowScenario(BaseModel):
    """잔여 학기로 졸업이 불가능할 때의 초과학기 예상(결정론 산출)."""
    shortfall_credits: float                          # 부족 학점(총 졸업학점 대비)
    per_term_credit_cap: float                        # 학기당 이수학점 상한(제32조)
    remaining_semesters: int                          # 현재 잔여 정규학기
    total_semesters_needed: int                       # 졸업까지 필요한 총 정규학기
    extra_semesters: int                              # 초과학기 수(= 필요 - 잔여)
    projected_graduation_term: str | None = None      # 예상 졸업 학기 라벨
    note: str = ""


class RoadmapPlan(BaseModel):
    status: Literal["generated", "not_generated", "blocked"] = "not_generated"
    feasible: bool | None = None
    terms: list[RoadmapTerm] = Field(default_factory=list)
    why_this_plan: str = ""
    blocked_reason: str | None = None
    relaxation_hint: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    overflow: OverflowScenario | None = None          # 잔여 학기 초과 시 예상 시나리오


class ValidationError(BaseModel):
    code: str
    detail: str
    course_id: str | None = None


class ValidationReport(BaseModel):
    ok: bool = True
    errors: list[ValidationError] = Field(default_factory=list)
    repair_attempted: bool = False


# ---------- 근거 / 응답 ----------
class Source(BaseModel):
    id: str                                          # G1, G2, ...
    doc: str = ""
    page: int | None = None
    source_type: Literal["requirement_rule", "catalog_course", "gen_ed"] = "requirement_rule"
    ref: str | None = None                           # rule area or course_id


class NodeTraceEvent(BaseModel):
    node: str
    status: Literal["ok", "warn", "skip", "fail"] = "ok"
    summary: str = ""
    kind: Literal["tool", "llm", "hitl", "validator", "branch"] = "tool"
    branch_taken: str | None = None      # 실행된 분기(예: 통과 / repair 1회 / blocked / 갭없음)


class AuditPipelineResponse(BaseModel):
    context: StudentContext
    verified_transcript: VerifiedTranscript
    audit: AuditResult
    risk: RiskAssessment
    roadmap: RoadmapPlan
    sources: list[Source] = Field(default_factory=list)
    node_trace: list[NodeTraceEvent] = Field(default_factory=list)
    report_markdown: str = ""

The deterministic planner does not call the full `validate_roadmap` function, only a local cap check, so several constraints are currently decorative rather than enforced. I’m checking whether tests or frontend compensate for that, and whether the data files encode the KMU year-specific rules consistently.
exec
/bin/bash -lc "sed -n '1,260p' data/graduation/v2/requirements_by_year.json" in /home/carol/kmu_genai
exec
/bin/bash -lc "sed -n '1,260p' graduation_center/v2/risk.py" in /home/carol/kmu_genai
 succeeded in 0ms:
"""졸업 리스크 등급 (결정론 · 재현 가능).

grade = 충족 못 한 최악 트리거(D>C>B>A). score = clamp(100 - Σseverity).
planner 미가동(키 없음)은 강등 사유가 아니다. roadmap 실현불가(검증 실패)만 강등에 반영.
"""
from __future__ import annotations

from graduation_center.v2.models_v2 import (
    AuditResult, RiskAssessment, RiskReason, StudentContext,
)
from graduation_center.v2.catalog import PREV_GPA_BONUS, SEASONAL_TERM_CAP

GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
LABELS = {"A": "안전", "B": "주의", "C": "위험", "D": "졸업불가 가능성"}


def _worse(a: str, b: str) -> str:
    return a if GRADE_RANK[a] >= GRADE_RANK[b] else b


def compute_risk(
    audit: AuditResult, context: StudentContext, roadmap_feasible: bool | None = None,
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
    # (계절학기 허용 시 6학점, 직전 3.75↑면 +3 한 번)
    term_cap = float(context.max_credits_per_term or 18)
    capacity = context.remaining_semesters * term_cap
    if context.prev_term_gpa_ge_375:
        capacity += PREV_GPA_BONUS
    if context.seasonal_semester_allowed:
        capacity += SEASONAL_TERM_CAP
    if gap > 0 and capacity > 0 and gap > capacity:
        grade = _worse(grade, "D")
        reasons.append(RiskReason(factor="잔여학기",
                      detail=f"부족 {gap:.0f}학점 > 잔여 {context.remaining_semesters}학기 수용량(~{capacity:.0f})", severity=20))

    if core_missing:
        grade = _worse(grade, "B")
        areas = ", ".join(g.area for g in core_missing)
        reasons.append(RiskReason(factor="핵심교양", detail=f"영역 미충족: {areas}", severity=8))

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
        grade = _worse(grade, "C")
        reasons.append(RiskReason(factor="평점", detail="졸업 평점 기준 미달", severity=20))
    elif context.gpa_min_met == "unknown":
        reasons.append(RiskReason(factor="평점", detail="평점 기준 충족 여부 확인 필요", severity=0))

    if roadmap_feasible is False:
        grade = _worse(grade, "C")
        reasons.append(RiskReason(factor="로드맵", detail="잔여 학기 내 실현 가능한 계획 없음", severity=15))

    if grade == "A" and not reasons:
        reasons.append(RiskReason(factor="종합", detail="확인된 부족·위험 항목 없음", severity=0))

    score = max(0, min(100, 100 - sum(r.severity for r in reasons)))
    return RiskAssessment(grade=grade, label=LABELS[grade], score=score, reasons=reasons)

 succeeded in 0ms:
{
  "_source": "학번(입학연도)별 요람 별표5 이수구분별 최저이수학점. 없으면 graduation_requirements.json 기본값.",
  "programs": {
    "mirae_mobility": {
      "2023": {
        "전공": 62,
        "기초교양": 8,
        "자유교양": 2,
        "일반선택": 47,
        "졸업_최저합계": 136
      }
    }
  }
}
exec
/bin/bash -lc "sed -n '1,320p' data/graduation/v2/required_names_by_year.json" in /home/carol/kmu_genai
 succeeded in 0ms:
{
  "_source": "학번(입학연도)별 요람 교과과정 비고 필수 — 이름 기준(코드 무관). 2023=2023요람 p739-740, 2025=2025요람 p772-773",
  "programs": {
    "mirae_mobility": {
      "2023": [
        {
          "name": "일반물리Ⅰ",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "일반물리실험Ⅰ",
          "credits": 1,
          "terms": [
            "1"
          ]
        },
        {
          "name": "S-TEAM Class",
          "credits": 1,
          "terms": [
            "1"
          ]
        },
        {
          "name": "공학기초수학",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "Python프로그래밍",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "미래모빌리티기초",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "공학수학Ⅰ",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "정역학",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "일반물리Ⅱ",
          "credits": 2,
          "terms": [
            "2"
          ]
        },
        {
          "name": "일반물리실험Ⅱ",
          "credits": 1,
          "terms": [
            "2"
          ]
        },
        {
          "name": "미래모빌리티AD",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "기초선형대수",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "회로이론",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "확률및통계",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "동역학",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "자료구조및알고리즘",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "전자회로",
          "credits": 3,
          "terms": [
            "2"
          ]
        },
        {
          "name": "미래모빌리티실험",
          "credits": 2,
          "terms": [
            "2"
          ]
        },
        {
          "name": "다학제간캡스톤디자인Ⅰ",
          "credits": 3,
          "terms": [
            "1"
          ]
        },
        {
          "name": "다학제간캡스톤디자인Ⅱ",
          "credits": 3,
          "terms": [
            "2"
          ]
        }
      ],
      "2025": [
        "S-TEAM Class",
        "일반물리Ⅰ",
        "일반물리실험Ⅰ",
        "공학기초수학",
        "Python프로그래밍",
        "자동차모빌리티기초",
        "일반물리Ⅱ",
        "일반물리실험Ⅱ",
        "공학수학Ⅰ",
        "정역학",
        "자동차모빌리티 Adventure Design",
        "기초선형대수",
        "회로이론",
        "확률및통계",
        "동역학",
        "전자회로",
        "자료구조및알고리즘",
        "모빌리티실험및실습",
        "다학제간캡스톤디자인"
      ]
    }
  },
  "aliases": {
    "mirae_mobility": {
      "미래모빌리티실험": [
        "모빌리티실험및실습"
      ]
    }
  },
  "_aliases_note": "요람 명칭↔수강내역 명칭 드리프트(동일 교과목코드). 요람엔 코드가 없어 이름 매칭 보정용.",
  "gen_basic": {
    "mirae_mobility": {
      "2023": [
        "College English",
        "글로벌영어",
        "English Conversation",
        "글쓰기"
      ],
      "2025": [
        "College English",
        "English Conversation",
        "글쓰기"
      ]
    }
  },
  "_gen_basic_note": "학번 요람 기초교양 필수 과목명(택1 포함). 학생 수강내역 기초교양 과목명과 부분일치로 이수 판정.",
  "_required_format": "값은 [문자열] 또는 [{name,credits,terms}] 모두 허용. terms=개설학기(['1'],['2'],['1','2'])."
}
exec
/bin/bash -lc "sed -n '1,360p' frontend/src/components/GraduationV2.jsx" in /home/carol/kmu_genai
 succeeded in 0ms:
import React from "react";

// 졸업센터 v2 — 수강내역 엑셀 → 검증(HITL) → 졸업사정 컨설팅 대시보드
const GRADE_COLOR = { A: "#10B981", B: "#F59E0B", C: "#EF4444", D: "#B91C1C" };
const C = {
  navy: "#0F3D7A", accent: "#1d6fe0", bg: "#eef2f7", card: "#ffffff",
  border: "#e3e8ef", text: "#1f2937", muted: "#6b7280", soft: "#f7f9fc",
  ok: "#10B981", warn: "#F59E0B", danger: "#EF4444",
};
const card = {
  background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
  padding: 18, marginBottom: 14, boxShadow: "0 1px 3px rgba(16,24,40,.06)",
};
const sectionTitle = { fontSize: 14, fontWeight: 700, margin: "0 0 12px", color: C.navy,
  display: "flex", alignItems: "center", gap: 7, letterSpacing: "-.01em" };
const inputStyle = { width: "100%", padding: "7px 9px", border: `1px solid ${C.border}`,
  borderRadius: 8, fontSize: 13, boxSizing: "border-box", marginTop: 4, background: "#fff" };
const labelStyle = { fontSize: 11.5, fontWeight: 600, color: C.muted };
const btnPrimary = (on = true) => ({ background: on ? C.navy : "#9aa6b8", color: "#fff",
  border: "none", borderRadius: 9, padding: "10px 20px", fontSize: 14, fontWeight: 600,
  cursor: on ? "pointer" : "default", boxShadow: on ? "0 1px 2px rgba(15,61,122,.3)" : "none" });
const btnGhost = { background: "#fff", color: C.navy, border: `1px solid ${C.border}`,
  borderRadius: 8, padding: "7px 14px", fontSize: 12.5, fontWeight: 600, cursor: "pointer" };

function Field({ label, children, hint }) {
  return (
    <label style={{ display: "block" }}>
      <span style={labelStyle}>{label}</span>
      {children}
      {hint && <span style={{ display: "block", fontSize: 10.5, color: "#94a3b8", marginTop: 3, lineHeight: 1.35 }}>{hint}</span>}
    </label>
  );
}

function Gauge({ label, earned, required, gap, sub }) {
  const pct = required > 0 ? Math.min(100, Math.round((earned / required) * 100)) : 100;
  const ok = gap <= 0;
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span style={{ fontWeight: 600, color: C.text }}>{label}{sub && <span style={{ color: C.muted, fontWeight: 400, marginLeft: 6, fontSize: 11.5 }}>{sub}</span>}</span>
        <span style={{ fontWeight: 600, color: ok ? C.ok : C.warn }}>
          {earned}/{required}
          <span style={{ marginLeft: 6, fontSize: 11.5 }}>{ok ? "충족" : `${gap} 부족`}</span>
        </span>
      </div>
      <div style={{ background: "#eef1f5", borderRadius: 6, height: 9, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: 9, borderRadius: 6, transition: "width .5s ease",
          background: ok ? "linear-gradient(90deg,#34d399,#10B981)" : "linear-gradient(90deg,#fbbf24,#f59e0b)" }} />
      </div>
    </div>
  );
}

const ASSIGN_STYLE = {
  "중복인정 추천": { bg: "#dbeafe", border: "#93c5fd", color: "#1d4ed8" },
  "중복인정": { bg: "#dbeafe", border: "#93c5fd", color: "#1d4ed8" },
  "융합 유지": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
  "융합전용": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
  "미이수": { bg: "#f3f4f6", border: "#e5e7eb", color: "#9aa6b8" },
};

function StatBox({ label, earned, required, C }) {
  const ok = earned >= required;
  return (
    <div style={{ flex: 1, minWidth: 140, border: `1px solid ${ok ? "#a7f3d0" : "#fecaca"}`, borderRadius: 10,
      padding: "10px 12px", background: ok ? "#f0fdf4" : "#fef2f2" }}>
      <div style={{ fontSize: 11.5, color: C.muted, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: ok ? "#047857" : "#dc2626" }}>
        {earned}<span style={{ fontSize: 12, color: C.muted, fontWeight: 500 }}> / {required}</span>
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: ok ? "#047857" : "#dc2626" }}>{ok ? "충족" : `${(required - earned).toFixed(0)}학점 부족`}</div>
    </div>
  );
}

const SEL3 = [["dup", "중복인정", "#1d4ed8", "#dbeafe", "#93c5fd"],
  ["primary", "제1전공", "#6d28d9", "#ede9fe", "#c4b5fd"],
  ["fusion", "융합전공", "#047857", "#ecfdf5", "#a7f3d0"]];

function ConvergenceBlock({ cc, C, first }) {
  const ov = cc.overlap_courses || [];
  const cap = cc.double_cap || 0;
  // 기본 선택: 전공필수 우선 중복인정(한도까지) → 제1전공 부족분 채움(제1전공) → 나머지 융합
  const defaultSel = React.useMemo(() => {
    const order = [...ov.keys()].sort((i, j) =>
      (ov[j].primary_required - ov[i].primary_required) || (ov[j].credits - ov[i].credits));
    const s = {}; let dup = 0;
    for (const i of order) { if (dup + ov[i].credits <= cap) { s[i] = "dup"; dup += ov[i].credits; } }
    let pneed = Math.max(0, (cc.primary_required || 0) - (cc.primary_base || 0) - dup);
    for (const i of order) {
      if (s[i]) continue;
      if (pneed > 0) { s[i] = "primary"; pneed -= ov[i].credits; } else s[i] = "fusion";
    }
    return s;
  }, [cc]);
  const [sel, setSel] = React.useState(defaultSel);
  React.useEffect(() => { setSel(defaultSel); }, [defaultSel]);

  const sum = (pred) => ov.reduce((s, f, i) => s + (pred(sel[i]) ? f.credits : 0), 0);
  const dupCr = sum((x) => x === "dup");
  const primaryCr = (cc.primary_base || 0) + sum((x) => x === "dup" || x === "primary");
  const fusionCr = (cc.fusion_base || 0) + sum((x) => x === "dup" || x === "fusion");
  const overCap = dupCr > cap;
  const fits = !overCap && primaryCr >= (cc.primary_required || 0) && fusionCr >= cc.required;

  // 미이수 시나리오: 융합 부족 시 안 들은 융합 과목 추천(부족 그룹 우선)
  const untaken = (cc.courses || []).filter((c) => !c.taken);
  const fusionGap = Math.max(0, cc.required - fusionCr);
  const shortGroups = new Set((cc.group_checks || []).filter((g) => g.gap > 0).map((g) => g.group));
  const suggest = [];
  if (fusionGap > 0) {
    const pool = [...untaken].sort((a, b) => (shortGroups.has(b.group) - shortGroups.has(a.group)));
    let acc = 0;
    for (const c of pool) { if (acc >= fusionGap) break; suggest.push(c); acc += c.credits; }
  }

  const groups = [...new Set((cc.courses || []).map((c) => c.group || "기타"))].sort();
  const taken = (cc.courses || []).filter((c) => c.taken).length;
  const selByName = {}; ov.forEach((f, i) => { selByName[f.name_ko] = sel[i]; });

  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 14, background: C.soft, marginTop: first ? 0 : 14 }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: C.navy, marginBottom: 8 }}>{cc.name} <span style={{ fontSize: 11.5, color: C.muted, fontWeight: 400 }}>{cc.track}·{cc.conv_type} · 이수 {taken}/{(cc.courses || []).length}과목 · 중복인정 한도 {cap}학점</span></div>

      <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
        <StatBox label="제1전공 전공 (배정 반영)" earned={primaryCr} required={cc.primary_required || 0} C={C} />
        <StatBox label={`${cc.conv_type} 이수 (배정 반영)`} earned={fusionCr} required={cc.required} C={C} />
      </div>
      {overCap && <div style={{ fontSize: 11.5, color: "#dc2626", marginBottom: 6 }}>⚠️ 중복인정 {dupCr}학점 &gt; 한도 {cap}학점 — 일부를 제1전공/융합으로 바꾸세요.</div>}
      <div style={{ fontSize: 11.5, color: fits ? "#047857" : "#b45309", marginBottom: 8 }}>
        {fits
          ? "✅ 현재 배정으로 제1전공·융합 둘 다 졸업요건 충족"
          : (primaryCr < (cc.primary_required || 0)
            ? `⚠️ 제1전공 ${((cc.primary_required || 0) - primaryCr).toFixed(0)}학점 부족 — 겹침과목을 제1전공으로 더 돌리거나 제1전공 과목 추가 이수`
            : `⚠️ ${cc.conv_type} ${fusionGap.toFixed(0)}학점 부족 — 아래 미이수 과목 추가 이수 필요`)}
      </div>

      {/* 미이수 시나리오 — 무엇을 더 들어 어떤 이수구분으로 빼면 졸업 가능 */}
      {suggest.length > 0 && (
        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: 10, marginBottom: 8 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "#b45309", marginBottom: 4 }}>📋 졸업 가능 시나리오 (미이수 과목 추가 이수)</div>
          <div style={{ fontSize: 11.5, color: "#7c4a12" }}>
            다음 {cc.conv_type} 과목을 추가 이수하면 충족: {suggest.map((c) => `${c.name_ko}(${c.credits}${c.group ? "·" + c.group : ""})`).join(", ")}
          </div>
        </div>
      )}

      {cc.recommend_double_count?.length > 0 && (
        <div style={{ fontSize: 11.5, color: C.accent, marginBottom: 8 }}>
          💡 중복인정(양쪽 동시) 권장 — 제1전공·다전공 전공필수 우선: <strong>{cc.recommend_double_count.join(", ")}</strong>
        </div>
      )}

      {/* 교육과정 전체 — 그룹별. 겹침(이수) 과목은 옆에서 3-way 이수구분 선택 */}
      <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden", background: "#fff" }}>
        {groups.map((g) => (
          <div key={g}>
            <div style={{ background: C.soft, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, color: C.navy, borderTop: `1px solid ${C.border}` }}>{g}</div>
            {(cc.courses || []).filter((c) => (c.group || "기타") === g).map((c, ci) => {
              const ovIdx = ov.findIndex((f) => f.name_ko === c.name_ko);
              const selectable = c.taken && c.overlap && ovIdx >= 0;
              return (
                <div key={ci} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", fontSize: 12,
                  borderTop: "1px solid #f1f4f8", opacity: c.taken ? 1 : 0.5, background: c.taken ? "#fafcff" : "#fff" }}>
                  <span style={{ width: 16 }}>{c.taken ? "✅" : "⬜"}</span>
                  <span style={{ flex: 1, fontWeight: c.taken ? 600 : 400 }}>
                    {c.name_ko}
                    {c.primary_required && <span style={{ marginLeft: 5, fontSize: 9.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 4, padding: "0 4px" }}>전공필수</span>}
                  </span>
                  <span style={{ width: 24, textAlign: "right", color: C.muted }}>{c.credits}</span>
                  {selectable ? (
                    <span style={{ display: "inline-flex", border: `1px solid ${C.border}`, borderRadius: 6, overflow: "hidden" }}>
                      {SEL3.map(([key, lbl, col, bg, bd]) => {
                        const on = sel[ovIdx] === key;
                        // 중복인정은 한도(cap) 초과하면 선택 불가
                        const wouldExceed = key === "dup" && !on && (dupCr + ov[ovIdx].credits > cap);
                        return (
                          <button key={key} disabled={wouldExceed}
                            onClick={() => !wouldExceed && setSel((s) => ({ ...s, [ovIdx]: key }))}
                            title={wouldExceed ? `중복인정 한도 ${cap}학점 초과` : ""}
                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 6px",
                              cursor: wouldExceed ? "not-allowed" : "pointer", border: "none",
                              borderLeft: key !== "dup" ? `1px solid ${C.border}` : "none",
                              background: on ? bg : "#fff", color: on ? col : (wouldExceed ? "#d1d5db" : "#9aa6b8") }}>{lbl}</button>
                        );
                      })}
                    </span>
                  ) : (
                    <span style={{ width: 70, textAlign: "center", fontSize: 10.5, fontWeight: 600,
                      color: c.taken ? "#047857" : "#9aa6b8", background: c.taken ? "#ecfdf5" : "#f3f4f6",
                      border: `1px solid ${c.taken ? "#a7f3d0" : "#e5e7eb"}`, borderRadius: 5, padding: "2px 0" }}>{c.taken ? "융합전용" : "미이수"}</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {cc.note && <div style={{ fontSize: 10.5, color: C.muted, marginTop: 6, lineHeight: 1.4 }}>※ {cc.note}</div>}
    </div>
  );
}

export default function GraduationV2({ apiBase }) {
  const [programs, setPrograms] = React.useState({});
  const [ctx, setCtx] = React.useState({
    student_id: "", program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
    seasonal_semester_allowed: true, gpa_min_met: "unknown",
    preferences: "", convergence_program_ids: [], convergence_tracks: {},
  });
  const [departments, setDepartments] = React.useState([]);   // 전체 학과(검색용)
  const [otherMajors, setOtherMajors] = React.useState([]);   // 데모 미지원 다전공/부전공(표시만)
  const [majorQuery, setMajorQuery] = React.useState("");
  const [files, setFiles] = React.useState([]);
  const [verify, setVerify] = React.useState(null);
  const [table, setTable] = React.useState([]);
  const [audit, setAudit] = React.useState(null);
  const [busy, setBusy] = React.useState("");
  const [error, setError] = React.useState("");
  const [showSources, setShowSources] = React.useState(false);

  React.useEffect(() => {
    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
      .then((d) => {
        const progs = d.programs || {};
        setPrograms(progs);
        setDepartments(d.departments || []);
        // 초기 주전공의 학사규정 상한을 기본값으로
        setCtx((c) => {
          const cap = progs[c.program_id]?.max_credits_per_term;
          return cap ? { ...c, max_credits_per_term: cap } : c;
        });
      }).catch(() => {});
  }, [apiBase]);

  const admissionYear = () => {
    const m = String(ctx.student_id || "").match(/(20\d{2})/);
    return m ? Number(m[1]) : null;
  };
  const contextPayload = () => ({
    ...ctx,
    remaining_semesters: Number(ctx.remaining_semesters),
    max_credits_per_term: Number(ctx.max_credits_per_term),
    admission_year: admissionYear(),
    masked_student_id: ctx.student_id ? ctx.student_id.slice(0, 4) + "XXXX" : null,
    preferences: ctx.preferences ? ctx.preferences.split(",").map((s) => s.trim()).filter(Boolean) : [],
  });

  // 주전공 변경 시 학사규정 제32조 학기당 상한을 기본값으로 자동 채움
  const onProgramChange = (id) => {
    const cap = programs[id]?.max_credits_per_term;
    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
  };

  // 다전공·부전공 검색 옵션: 연계융합(분석지원) + 전체 학과(데모 미지원)
  const majorOptions = () => {
    const convNames = new Set(convergencePrograms.map(([, p]) => p.name_ko));
    const conv = convergencePrograms.map(([id, p]) => ({ key: "c:" + id, id, label: p.name_ko, supported: true }));
    const depts = departments.filter((d) => !convNames.has(d.name))
      .map((d) => ({ key: "d:" + d.name, label: d.name, supported: false }));
    return [...conv, ...depts];
  };
  const pickMajor = (o) => {
    setMajorQuery("");
    if (o.supported) { if (!ctx.convergence_program_ids.includes(o.id)) toggleConv(o.id); }
    else { setOtherMajors((m) => (m.includes(o.label) ? m : [...m, o.label])); }
  };

  const primaryPrograms = Object.entries(programs).filter(([, p]) => (p.track_type || "primary") === "primary");
  const convergencePrograms = Object.entries(programs).filter(([, p]) => p.track_type === "convergence");
  const toggleConv = (id) => setCtx((c) => {
    const on = c.convergence_program_ids.includes(id);
    const ids = on ? c.convergence_program_ids.filter((x) => x !== id) : [...c.convergence_program_ids, id];
    const tracks = { ...c.convergence_tracks };
    if (on) delete tracks[id]; else tracks[id] = tracks[id] || "다전공";
    return { ...c, convergence_program_ids: ids, convergence_tracks: tracks };
  });
  const setConvTrack = (id, track) => setCtx((c) => ({ ...c, convergence_tracks: { ...c.convergence_tracks, [id]: track } }));

  const runVerify = async () => {
    if (!files.length) { setError("수강내역 엑셀(.xls/.xlsx)을 업로드하세요."); return; }
    setBusy("verify"); setError(""); setAudit(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      form.append("context", JSON.stringify(contextPayload()));
      const r = await fetch(`${apiBase}/graduation/v2/verify`, { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const d = await r.json();
      setVerify(d); setTable(d.verification_table);
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  const toggleRow = (i) => setTable((t) => t.map((row, idx) => {
    if (idx !== i) return row;
    const included = !row.included;
    // 제외로 바꾸는데 사유가 없으면 기본값, 포함으로 되돌리면 사유 비움
    return { ...row, included, exclude_reason: included ? null : (row.exclude_reason || "F·재이수") };
  }));
  const setReason = (i, reason) => setTable((t) => t.map((row, idx) =>
    idx === i ? { ...row, exclude_reason: reason, included: false } : row));
  const EXCLUDE_REASONS = ["재수강(이전 이수)", "F·재이수", "드랍·철회", "폐강", "기타"];
  const retakeCount = table.filter((r) => (r.exclude_reason || "").includes("재수강")).length;

  const runAudit = async () => {
    setBusy("audit"); setError("");
    try {
      const payload = { context: verify.context, verification_table: table,
        unresolved: verify.unresolved, possible_retakes: verify.possible_retakes };
      const r = await fetch(`${apiBase}/graduation/v2/audit`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const result = await r.json();
      setAudit(result);
      // 워크플로우 전용 페이지(#workflow)가 읽도록 trace 저장
      try {
        localStorage.setItem("v2_workflow_trace",
          JSON.stringify([...(verify?.node_trace || []), ...(result.node_trace || [])]));
      } catch { /* storage 불가 무시 */ }
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  const stepActive = (n) => (n === 1 ? !!files.length : n === 2 ? !!verify : !!audit);

  return (
    <div style={{ background: C.bg, height: "100vh", overflowY: "auto", padding: "0 0 60px",
      fontFamily: "'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif", color: C.text }}>
      {/* 헤더 배너 */}
      <div style={{ background: `linear-gradient(120deg,${C.navy},#143e8c 60%,#1d6fe0)`, color: "#fff",
        padding: "22px 26px 20px" }}>
        <div style={{ maxWidth: 940, margin: "0 auto" }}>
          <div style={{ fontSize: 12, letterSpacing: ".08em", opacity: .85, fontWeight: 600 }}>KOOKMIN UNIV · 졸업센터</div>
          <h1 style={{ margin: "4px 0 6px", fontSize: 23, fontWeight: 800, letterSpacing: "-.02em" }}>졸업사정 컨설팅</h1>
          <p style={{ margin: 0, fontSize: 13, opacity: .9, lineHeight: 1.5 }}>
            내 수강내역 × 내 요람으로 졸업 가능 여부를 진단하고 남은 학기 로드맵을 설계합니다.
            결정론적 사실 위에서 LLM이 로드맵만 계획하고 검증기가 재확인합니다.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 940, margin: "0 auto", padding: "18px 20px 0" }}>
        {/* 스텝 인디케이터 */}
        <div style={{ display: "flex", gap: 8, marginBottom: 14, fontSize: 12.5 }}>
          {[[1, "수강내역 업로드"], [2, "검증 (HITL)"], [3, "졸업사정 리포트"]].map(([n, t]) => (
            <div key={n} style={{ flex: 1, padding: "8px 10px", borderRadius: 9, textAlign: "center", fontWeight: 600,
              background: stepActive(n) ? C.navy : "#fff", color: stepActive(n) ? "#fff" : C.muted,
              border: `1px solid ${stepActive(n) ? C.navy : C.border}` }}>
              <span style={{ opacity: .7, marginRight: 5 }}>{n}</span>{t}
            </div>
          ))}
        </div>

        {/* 1) 학생 정보 + 업로드 */}
        <div style={card}>
          <div style={sectionTitle}>🎓 학생 정보 & 수강내역</div>


The year-specific requirements file only contains a 2023 override for `mirae_mobility`; everything else falls back to a generic/latest profile. That matters because several functions claim “학번 요람 기준” but only some requirements actually have year-aware data. I’m now reading the rest of the component and route wiring so findings can point to the exact broken surface.
exec
/bin/bash -lc "sed -n '360,760p' frontend/src/components/GraduationV2.jsx" in /home/carol/kmu_genai
 succeeded in 0ms:

          {/* ① 학적 정보 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "2px 0 8px" }}>① 학적 정보</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="입학연도 (학번 앞 4자리)" hint={admissionYear() ? `→ ${admissionYear()} 요람 적용` : "입학연도 기준 요람 적용"}>
              <input style={inputStyle} placeholder="예: 2025" value={ctx.student_id} onChange={(e) => setCtx({ ...ctx, student_id: e.target.value })} /></Field>
            <Field label="주전공">
              <select style={inputStyle} value={ctx.program_id} onChange={(e) => onProgramChange(e.target.value)}>
                {primaryPrograms.map(([id, p]) => <option key={id} value={id}>{p.name_ko}</option>)}
                {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
              </select>
            </Field>
          </div>

          {/* 다전공·부전공 (연계융합 포함, 검색) */}
          <div style={{ marginTop: 12 }}>
            <span style={labelStyle}>다전공 · 부전공 (연계·융합전공 포함, 검색)</span>
            <div style={{ position: "relative", marginTop: 4 }}>
              <input style={inputStyle} placeholder="학과/전공 검색 후 선택 (데모 분석: 데이터사이언스융합·모빌리티데이터분석)"
                value={majorQuery} onChange={(e) => setMajorQuery(e.target.value)} />
              {majorQuery.trim() && (
                <div style={{ position: "absolute", zIndex: 5, left: 0, right: 0, top: "100%", maxHeight: 190, overflow: "auto",
                  background: "#fff", border: `1px solid ${C.border}`, borderRadius: 8, marginTop: 2, boxShadow: "0 4px 12px rgba(16,24,40,.1)" }}>
                  {majorOptions().filter((o) => o.label.includes(majorQuery.trim())).slice(0, 30).map((o) => (
                    <div key={o.key} onClick={() => pickMajor(o)}
                      style={{ padding: "6px 10px", fontSize: 12.5, cursor: "pointer", borderBottom: "1px solid #f1f4f8",
                        color: o.supported ? C.text : "#9aa6b8" }}>
                      {o.label}{o.supported ? <span style={{ color: C.accent, fontSize: 10.5, marginLeft: 6 }}>분석지원</span>
                        : <span style={{ fontSize: 10.5, marginLeft: 6 }}>(데모 미지원)</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* 선택된 추가전공 칩 */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {convergencePrograms.filter(([id]) => ctx.convergence_program_ids.includes(id)).map(([id, p]) => (
                <div key={id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
                  border: `1px solid ${C.accent}`, background: "#eef5ff", fontSize: 12.5 }}>
                  <span style={{ fontWeight: 600 }}>{p.name_ko}</span>
                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
                    style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px" }}>
                    <option value="다전공">다전공 · 36/중복12</option>
                    <option value="부전공">부전공 · 18/중복6</option>
                  </select>
                  <span onClick={() => toggleConv(id)} style={{ cursor: "pointer", color: C.muted }}>✕</span>
                </div>
              ))}
              {otherMajors.map((nm, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
                  border: `1px solid ${C.border}`, background: "#f3f4f6", fontSize: 12.5, color: "#9aa6b8" }}>
                  {nm} (데모 미지원)
                  <span onClick={() => setOtherMajors((o) => o.filter((x) => x !== nm))} style={{ cursor: "pointer" }}>✕</span>
                </div>
              ))}
            </div>
            {ctx.convergence_program_ids.length === 0 && otherMajors.length === 0 && (
              <div style={{ fontSize: 11.5, color: "#b45309", marginTop: 8, background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: "7px 10px" }}>
                ※ 다전공·부전공을 모두 이수하지 않는 경우 <strong>심화전공(심화과정)</strong>을 이수해야 합니다 (학사규정 제33조).
              </div>
            )}
          </div>

          {/* ② 학기 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "16px 0 8px" }}>② 학기</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="현재 학기" hint="형식: 연도-학기 (1=1학기, 2=2학기). 예: 2026-1">
              <input style={inputStyle} placeholder="예: 2026-1" value={ctx.current_term} onChange={(e) => setCtx({ ...ctx, current_term: e.target.value })} /></Field>
            <Field label="남은 학기" hint="현재 학기 다음부터 들을 정규학기 수 (현재 학기는 수강내역에 포함 → 제외)">
              <input style={inputStyle} type="number" value={ctx.remaining_semesters} onChange={(e) => setCtx({ ...ctx, remaining_semesters: e.target.value })} /></Field>
          </div>

          {/* ③ 수강 제약 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "16px 0 8px" }}>③ 수강 제약</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="한 학기 최대 수강 학점" hint="학사규정 제32조: 졸업학점 따라 17/18/19 자동 (수정 가능)">
              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
            <Field label="졸업 최소 평점 충족" hint="졸업 요건: 전학년 평점평균 2.0/4.5 이상 (학사규정 제95조)">
              <select style={inputStyle} value={ctx.gpa_min_met} onChange={(e) => setCtx({ ...ctx, gpa_min_met: e.target.value })}>
                <option value="unknown">모름</option><option value="yes">충족 (2.0↑)</option><option value="no">미달 (2.0 미만)</option>
              </select>
            </Field>
            <label style={{ gridColumn: "1 / 3", display: "flex", alignItems: "center", gap: 7, fontSize: 12.5 }}>
              <input type="checkbox" checked={ctx.prev_term_gpa_ge_375} onChange={(e) => setCtx({ ...ctx, prev_term_gpa_ge_375: e.target.checked })} />
              직전학기 성적우수 (평점평균 3.75↑) — 다음 학기 +3학점 추가 수강 (학사규정 제32조)
            </label>
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 8 }}>※ 계절학기(6학점)는 기본 포함해 시나리오를 짭니다. 리포트 후 계절학기 불가 시 알려주시면 다시 계산합니다.</div>

          <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <label style={{ ...btnGhost, display: "inline-flex", alignItems: "center", gap: 6 }}>
              📂 엑셀 선택
              <input type="file" multiple accept=".xls,.xlsx" style={{ display: "none" }} onChange={(e) => setFiles([...e.target.files])} />
            </label>
            <span style={{ fontSize: 12.5, color: C.muted }}>
              {files.length ? `${files.length}개 학기 파일 선택됨` : "ON국민 수강내역(.xls)을 학기별로 모두 선택"}
            </span>
            <button style={{ ...btnPrimary(busy !== "verify"), marginLeft: "auto" }} onClick={runVerify} disabled={busy === "verify"}>
              {busy === "verify" ? "검증 중…" : "① 검증 실행"}
            </button>
          </div>
          <p style={{ fontSize: 11.5, color: C.muted, margin: "10px 0 0" }}>※ 데모는 본인 또는 더미 수강내역을 사용하세요.</p>
        </div>

        {error && <div style={{ ...card, borderColor: "#fecaca", background: "#fef2f2", color: C.danger, fontSize: 13 }}>⚠️ {error}</div>}

        {/* 2) 검증 테이블 */}
        {verify && (
          <div style={card}>
            <div style={sectionTitle}>🔍 수강내역 검증 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>({table.length}행 · 학기 오름차순)</span></div>
            <p style={{ fontSize: 12, color: C.muted, margin: "0 0 10px", lineHeight: 1.5 }}>
              성적 정보가 없는 수강내역입니다. <strong style={{ color: C.text }}>F·드랍한 과목은 체크를 해제</strong>하고 비고에서 사유를 고르세요.
              재수강 의심 과목은 최신 이수만 자동 포함했습니다.
            </p>
            {retakeCount > 0 && (
              <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 9, padding: "9px 12px",
                fontSize: 12.5, color: "#b45309", marginBottom: 10 }}>
                ⚠️ <strong>재수강 의심 {retakeCount}건</strong> — 동일 교과목코드가 여러 학기에 있어 최신 이수만 포함했습니다.
                아래 강조된 행의 비고를 확인하세요. (사제동행세미나 등 반복수강 과목은 제외됨)
              </div>
            )}
            <div style={{ maxHeight: 260, overflow: "auto", border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                <thead><tr style={{ background: C.soft, position: "sticky", top: 0 }}>
                  {["포함", "과목명", "이수구분", "학점", "학기", "비고/제외사유"].map((h) => (
                    <th key={h} style={{ padding: "7px 8px", textAlign: "left", color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {table.map((row, i) => {
                    const isRetake = (row.exclude_reason || "").includes("재수강");
                    return (
                      <tr key={i} style={{ opacity: row.included ? 1 : 0.55, borderBottom: "1px solid #f1f4f8",
                        background: isRetake ? "#fffaf2" : undefined, borderLeft: isRetake ? "3px solid #f59e0b" : "3px solid transparent" }}>
                        <td style={{ textAlign: "center", padding: "5px 8px" }}><input type="checkbox" checked={row.included} onChange={() => toggleRow(i)} /></td>
                        <td style={{ padding: "5px 8px" }}>{row.name_ko}
                          {!row.course_id && <span style={{ marginLeft: 5, fontSize: 10.5, color: C.muted, background: "#eef1f5", borderRadius: 4, padding: "1px 5px" }}>집계</span>}</td>
                        <td style={{ padding: "5px 8px", color: C.muted }}>{row.requirement_area}{row.core_area ? `·${row.core_area}` : ""}</td>
                        <td style={{ textAlign: "center", padding: "5px 8px" }}>{row.credits}</td>
                        <td style={{ padding: "5px 8px", color: C.muted }}>{row.term_label}</td>
                        <td style={{ padding: "4px 8px" }}>
                          {row.included
                            ? <span style={{ color: "#9aa6b8" }}>정상 포함</span>
                            : (
                              <select value={EXCLUDE_REASONS.includes(row.exclude_reason) ? row.exclude_reason : "기타"}
                                onChange={(e) => setReason(i, e.target.value)}
                                style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px", color: "#b45309" }}>
                                {EXCLUDE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                              </select>
                            )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
              {verify.unresolved?.length > 0 && <span style={{ fontSize: 12, color: "#b45309" }}>미해소(확인 필요): {verify.unresolved.length}건</span>}
              <button style={{ ...btnPrimary(busy !== "audit"), marginLeft: "auto" }} onClick={runAudit} disabled={busy === "audit"}>
                {busy === "audit" ? "사정 중…" : "② 졸업사정 실행"}
              </button>
            </div>
          </div>
        )}

        {/* 3) 리포트 */}
        {audit && (
          <>
            {/* 종합 판정 히어로 */}
            <div style={{ ...card, padding: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "stretch" }}>
                <div style={{ width: 120, background: GRADE_COLOR[audit.risk.grade], color: "#fff",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "20px 0" }}>
                  <div style={{ fontSize: 46, fontWeight: 800, lineHeight: 1 }}>{audit.risk.grade}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{audit.risk.label}</div>
                </div>
                <div style={{ flex: 1, padding: "16px 18px" }}>
                  <div style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>종합 판정</div>
                  <div style={{ fontSize: 15, fontWeight: 700, margin: "3px 0 10px" }}>
                    총 {audit.audit.total_earned} / {audit.audit.total_required} 학점
                  </div>
                  <div style={{ background: "#eef1f5", borderRadius: 6, height: 9, overflow: "hidden", marginBottom: 10 }}>
                    <div style={{ width: `${Math.min(100, Math.round(audit.audit.total_earned / audit.audit.total_required * 100))}%`,
                      height: 9, background: GRADE_COLOR[audit.risk.grade] }} />
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {audit.risk.reasons.length === 0 && <span style={{ fontSize: 12, color: C.ok }}>리스크 요인 없음 — 졸업요건 충족</span>}
                    {audit.risk.reasons.map((r, i) => (
                      <span key={i} style={{ fontSize: 11.5, background: "#fff5ed", color: "#b45309",
                        border: "1px solid #fed7aa", borderRadius: 14, padding: "3px 9px" }}>{r.detail}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 졸업 최소 평점 주의 (충족이 아닐 때) */}
            {audit.context?.gpa_min_met !== "yes" && (
              <div style={{ ...card, background: audit.context?.gpa_min_met === "no" ? "#fef2f2" : "#fff7ed",
                border: `1px solid ${audit.context?.gpa_min_met === "no" ? "#fecaca" : "#fed7aa"}`,
                color: audit.context?.gpa_min_met === "no" ? C.danger : "#b45309", fontSize: 13 }}>
                ⚠️ {audit.context?.gpa_min_met === "no"
                  ? "졸업 최소 평점(전학년 평점평균 2.0/4.5) 미달 — 졸업요건을 충족하지 못합니다. 평점 관리가 필요합니다."
                  : "졸업 최소 평점(2.0/4.5) 충족 여부가 확인되지 않았습니다 — 성적표로 직접 확인하세요. (미달 시 졸업 불가)"}
              </div>
            )}

            {/* 영역별 현황 */}
            <div style={card}>
              <div style={sectionTitle}>📊 영역별 이수 현황</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {audit.audit.area_gaps.map((g, i) => <Gauge key={i} label={g.area} earned={g.earned} required={g.required} gap={g.gap} />)}
              </div>
              {audit.audit.core_area_gaps?.length > 0 && (
                <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.navy, marginBottom: 8 }}>핵심교양 영역별 (각 최저 학점 · 소통은 단과대 규정 반영)</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {audit.audit.core_area_gaps.map((g, i) => {
                      const ok = g.gap <= 0;
                      const pct = g.required > 0 ? Math.min(100, Math.round((g.earned / g.required) * 100)) : 100;
                      return (
                        <div key={i} style={{ flex: "1 1 90px", minWidth: 90, border: `1px solid ${ok ? "#a7f3d0" : "#fed7aa"}`,
                          borderRadius: 9, padding: "7px 9px", background: ok ? "#f0fdf4" : "#fff7ed" }}>
                          <div style={{ fontSize: 11.5, fontWeight: 600, color: "#334155" }}>{g.area}</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: ok ? C.ok : "#b45309" }}>{g.earned}<span style={{ fontSize: 11, color: C.muted, fontWeight: 400 }}>/{g.required}</span></div>
                          <div style={{ background: "#eef1f5", borderRadius: 5, height: 6, overflow: "hidden", marginTop: 3 }}>
                            <div style={{ width: `${pct}%`, height: 6, background: ok ? "#10B981" : "#f59e0b" }} />
                          </div>
                          <div style={{ fontSize: 10, color: ok ? C.ok : "#b45309", marginTop: 2 }}>{ok ? "충족" : `${g.gap} 부족`}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {audit.audit.gen_basic_courses?.length > 0 && (
                <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.navy, marginBottom: 6 }}>기초교양 필수 과목</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {audit.audit.gen_basic_courses.map((c, i) => (
                      <span key={i} style={{ fontSize: 12, padding: "3px 9px", borderRadius: 14,
                        background: c.taken ? "#f0fdf4" : "#fff7ed", border: `1px solid ${c.taken ? "#a7f3d0" : "#fed7aa"}`,
                        color: c.taken ? "#047857" : "#b45309" }}>{c.taken ? "✅" : "⬜"} {c.name_ko}</span>
                    ))}
                  </div>
                </div>
              )}
              {audit.audit.missing_required_names.length > 0 && (
                <p style={{ color: C.danger, fontSize: 13, margin: "8px 0 0" }}>미이수 필수지정: {audit.audit.missing_required_names.join(", ")}</p>
              )}
              {audit.audit.required_check_available === false && (
                <p style={{ fontSize: 11.5, color: C.muted, margin: "8px 0 0" }}>※ 이 학과는 요람 필수지정 과목 데이터가 아직 없어 필수과목 체크가 제외됐습니다(확인 필요).</p>
              )}
            </div>

            {/* 연계·융합전공 — 교육과정 전체 + 이수 강조 + 이수구분 배정 */}
            {audit.audit.convergence_checks?.length > 0 && (
              <div style={card}>
                <div style={sectionTitle}>🔗 연계·융합전공 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>(학점 중복인정 반영)</span></div>
                {audit.audit.convergence_checks.map((cc, i) => (
                  <ConvergenceBlock key={i} cc={cc} C={C} first={i === 0} />
                ))}
              </div>
            )}

            {/* 로드맵 */}
            <div style={card}>
              <div style={sectionTitle}>🗺️ 추천 학기별 로드맵</div>
              {audit.roadmap.status === "not_generated" && <p style={{ color: C.muted, fontSize: 13 }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
              {audit.roadmap.status === "blocked" && <p style={{ color: C.danger, fontSize: 13 }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
              {audit.roadmap.status === "generated" && audit.roadmap.terms.length === 0 && (
                <div style={{ padding: "14px 16px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 10, color: "#047857", fontSize: 13.5, fontWeight: 600 }}>
                  ✅ {audit.roadmap.why_this_plan}
                </div>
              )}
              {/* 남은 요건 요약 */}
              {(() => {
                const rem = [];
                const mg = audit.audit.area_gaps.find((g) => g.area === "전공");
                if (audit.audit.missing_required_names?.length) rem.push(`필수지정 ${audit.audit.missing_required_names.length}과목`);
                if (mg && mg.gap > 0) rem.push(`전공 ${mg.gap}학점`);
                (audit.audit.convergence_checks || []).forEach((cc) => { if (cc.gap > 0) rem.push(`${cc.name} ${cc.gap}학점`); });
                (audit.audit.core_area_gaps || []).filter((g) => g.gap > 0).forEach((g) => rem.push(`핵심교양 ${g.area} ${g.gap}학점`));
                ["기초교양", "자유교양"].forEach((a) => { const g = audit.audit.area_gaps.find((x) => x.area === a); if (g && g.gap > 0) rem.push(`${a} ${g.gap}학점`); });
                return rem.length > 0 && audit.roadmap.terms.length > 0 ? (
                  <div style={{ fontSize: 12, marginBottom: 10 }}>
                    <span style={{ color: C.muted, fontWeight: 600 }}>남은 요건: </span>
                    {rem.map((r, i) => <span key={i} style={{ display: "inline-block", background: "#fff7ed", border: "1px solid #fed7aa", color: "#b45309", borderRadius: 12, padding: "2px 8px", marginRight: 5, marginBottom: 4 }}>{r}</span>)}
                  </div>
                ) : null;
              })()}
              {audit.roadmap.terms.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {audit.roadmap.terms.map((t, i) => (
                    <div key={i} style={{ display: "flex", gap: 12 }}>
                      <div style={{ minWidth: 64, fontWeight: 700, color: C.navy, fontSize: 13.5, paddingTop: 2 }}>{t.term}<div style={{ fontSize: 10.5, color: C.muted, fontWeight: 400 }}>{t.term_credits}학점</div></div>
                      <div style={{ flex: 1, borderLeft: `3px solid ${C.accent}`, paddingLeft: 12, display: "flex", flexDirection: "column", gap: 5 }}>
                        {t.courses.map((c, ci) => {
                          const offered = (c.offered_terms || []).length ? `${c.offered_terms.map((x) => (x === "1" ? "1학기" : x === "2" ? "2학기" : x)).join("·")} 개설` : null;
                          return (
                            <div key={ci} style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", fontSize: 12.5 }}>
                              <span style={{ fontWeight: 600 }}>{c.name_ko}</span>
                              <span style={{ color: C.muted }}>{c.credits}학점</span>
                              {c.satisfies && <span style={{ fontSize: 10.5, background: "#eef5ff", color: C.accent, border: "1px solid #cfe1fb", borderRadius: 5, padding: "1px 6px" }}>{c.satisfies}</span>}
                              {c.assignment && <span style={{ fontSize: 10.5, background: "#ede9fe", color: "#6d28d9", border: "1px solid #c4b5fd", borderRadius: 5, padding: "1px 6px" }}>{c.assignment}</span>}
                              {offered && <span style={{ fontSize: 10.5, color: "#047857" }}>· {offered}</span>}
                              {c.manual_check && <span style={{ fontSize: 10.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 5, padding: "1px 6px" }}>개설학기 확인필요</span>}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {audit.roadmap.feasible === false && audit.roadmap.blocked_reason && (
                <div style={{ fontSize: 12.5, color: "#b45309", margin: "10px 0 0", padding: "10px 12px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8 }}>
                  ⚠️ {audit.roadmap.blocked_reason}{audit.roadmap.relaxation_hint ? ` · ${audit.roadmap.relaxation_hint}` : ""}
                </div>
              )}
              {audit.roadmap.why_this_plan && audit.roadmap.terms.length > 0 && (
                <p style={{ fontSize: 12.5, color: C.text, margin: "12px 0 0", padding: "10px 12px", background: C.soft, borderRadius: 8 }}>
                  <strong style={{ color: C.navy }}>왜 이 계획:</strong> {audit.roadmap.why_this_plan}</p>
              )}
              {audit.roadmap.assumptions?.length > 0 && <p style={{ fontSize: 11, color: C.muted, margin: "8px 0 0" }}>가정: {audit.roadmap.assumptions.join(" / ")}</p>}

              {audit.roadmap.overflow && (
                <div style={{ marginTop: 12, padding: 14, borderRadius: 10, background: "#fff7ed", border: "1px solid #fed7aa" }}>
                  <div style={{ fontWeight: 700, color: "#b45309", fontSize: 13.5, marginBottom: 8 }}>⏳ 초과학기 예상 시나리오</div>
                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 8 }}>
                    {[["부족 학점", `${audit.roadmap.overflow.shortfall_credits}학점`],
                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
                      ["필요 총학기", `${audit.roadmap.overflow.total_semesters_needed}학기`],
                      ["초과학기", `${audit.roadmap.overflow.extra_semesters}학기`],
                      ["예상 졸업", audit.roadmap.overflow.projected_graduation_term || "—"]].map(([k, v]) => (
                      <div key={k}>
                        <div style={{ fontSize: 11, color: C.muted }}>{k}</div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: "#b45309" }}>{v}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{audit.roadmap.overflow.note}</div>
                </div>
              )}
            </div>

            {/* 워크플로우 그래프 — 별도 페이지로 분리 */}
            <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: C.navy }}>🔀 워크플로우 실행 그래프</div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>
                  업무 노드 분절·실행 순서·분기를 별도 화면에서 시각화합니다 (방금 실행 결과 반영).
                </div>
              </div>
              <button onClick={() => window.open(`${window.location.pathname}#workflow`, "_blank")}
                style={{ ...btnGhost, whiteSpace: "nowrap" }}>워크플로우 그래프 열기 ↗</button>
            </div>

            {/* 근거 */}
            <div style={{ ...card, marginBottom: 0 }}>
              <button style={btnGhost} onClick={() => setShowSources((s) => !s)}>
                {showSources ? "근거 숨기기 ▲" : "근거 보기 ▼"}
              </button>
              {showSources && (
                <ul style={{ fontSize: 12, color: C.muted, margin: "10px 0 0", paddingLeft: 18 }}>
                  {audit.sources.map((s) => <li key={s.id} style={{ marginBottom: 3 }}>[{s.id}] {s.doc} {s.page ? `p.${s.page}` : ""} <span style={{ opacity: .7 }}>({s.source_type})</span></li>)}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

exec
/bin/bash -lc 'rg -n "convergence|융합|roadmap|planner|risk|mirae_mobility|required_names" tests graduation_center frontend/src -S' in /home/carol/kmu_genai
 succeeded in 0ms:
tests/test_v2_pipeline.py:15:from graduation_center.v2 import pipeline, planner
tests/test_v2_pipeline.py:16:from graduation_center.v2.models_v2 import RoadmapPlan
tests/test_v2_pipeline.py:57:    monkeypatch.setattr(planner, "_get_client", lambda: None)
tests/test_v2_pipeline.py:65:    assert resp.risk.grade in {"B", "C", "D"}
tests/test_v2_pipeline.py:67:    assert resp.roadmap.status == "generated"
tests/test_v2_pipeline.py:68:    assert resp.roadmap.terms == []  # current_term 없어 배치 생략
tests/test_v2_pipeline.py:71:def test_planner_fake_client_generates_valid_roadmap():
tests/test_v2_pipeline.py:97:    pctx = planner.build_planning_context(au, prof, ctx, vt)
tests/test_v2_pipeline.py:111:                "term_credits": acc, "term_risk": "low", "notes": []}]}
tests/test_v2_pipeline.py:122:    assert resp.roadmap.status == "generated"
tests/test_v2_pipeline.py:123:    assert resp.roadmap.feasible is True
tests/test_v2_pipeline.py:132:    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
tests/test_v2_pipeline.py:135:        "term_credits": 3, "term_risk": "low", "notes": []}])
tests/test_v2_pipeline.py:136:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
tests/test_v2_pipeline.py:150:    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
tests/test_v2_pipeline.py:153:        "term_credits": 48, "term_risk": "low", "notes": []}])
tests/test_v2_pipeline.py:154:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
tests/test_v2_pipeline.py:169:    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
tests/test_v2_pipeline.py:172:        "term_credits": 3, "term_risk": "low", "notes": []}])
tests/test_v2_pipeline.py:173:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
tests/test_v2_pipeline.py:177:def test_convergence_overlay(monkeypatch):
tests/test_v2_pipeline.py:178:    # 주전공 ai_bigdata + 융합전공 dsci_convergence — 융합전공 과목 이수분이 별도 집계됨
tests/test_v2_pipeline.py:179:    monkeypatch.setattr(planner, "_get_client", lambda: None)
tests/test_v2_pipeline.py:180:    rows = _major("경영통계", "수리통계", "빅데이터처리와시각화")  # dsci 융합전공에도 속한 과목들
tests/test_v2_pipeline.py:182:                            "remaining_semesters": 4, "convergence_program_ids": ["dsci_convergence"]})
tests/test_v2_pipeline.py:186:    cc = resp.audit.convergence_checks
tests/test_v2_pipeline.py:187:    assert len(cc) == 1 and cc[0]["program_id"] == "dsci_convergence"
tests/test_v2_pipeline.py:189:    assert cc[0]["earned"] > 0          # 융합전공 과목 이수분 집계
tests/test_v2_pipeline.py:193:def test_convergence_duplicate_credit_cap_and_exclusion():
tests/test_v2_pipeline.py:194:    # 학사규정 제77조: 제1전공 전공과목(앞5자리 동일)만 중복인정, 다전공 12 / 부전공 융합 6,
tests/test_v2_pipeline.py:196:    from graduation_center.v2.audit_v2 import _convergence_checks
tests/test_v2_pipeline.py:198:    cat = json.loads(Path("data/graduation/v2/catalog_dsci_convergence.json").read_text(encoding="utf-8"))["courses"]
tests/test_v2_pipeline.py:210:    # primary=dsci_convergence → 모든 designated가 제1전공과 겹침 → cap(double_recognizable) 검증
tests/test_v2_pipeline.py:211:    da = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "다전공"}, "dsci_convergence")[0]
tests/test_v2_pipeline.py:212:    assert da["required"] == 36 and da["double_cap"] == 12 and da["conv_type"] == "융합전공"
tests/test_v2_pipeline.py:213:    # 융합전공 인정 = 들은 융합 과목 전부(교양 gyo 제외) — cap이 깎지 않음
tests/test_v2_pipeline.py:216:    bu = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "부전공"}, "dsci_convergence")[0]
tests/test_v2_pipeline.py:232:    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
graduation_center/v2/catalog.py:61:    """프로그램의 졸업 최저이수학점(요건 데이터). 연계·융합전공(키 없음)은 None."""
graduation_center/v2/catalog.py:98:            "convergence_required": progs[program_id].get("convergence_required"),
graduation_center/v2/risk.py:4:planner 미가동(키 없음)은 강등 사유가 아니다. roadmap 실현불가(검증 실패)만 강등에 반영.
graduation_center/v2/risk.py:9:    AuditResult, RiskAssessment, RiskReason, StudentContext,
graduation_center/v2/risk.py:21:def compute_risk(
graduation_center/v2/risk.py:22:    audit: AuditResult, context: StudentContext, roadmap_feasible: bool | None = None,
graduation_center/v2/risk.py:23:) -> RiskAssessment:
graduation_center/v2/risk.py:24:    reasons: list[RiskReason] = []
graduation_center/v2/risk.py:28:    missing = len(audit.missing_required_names)
graduation_center/v2/risk.py:34:        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족(15 초과)", severity=30))
graduation_center/v2/risk.py:37:        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=20))
graduation_center/v2/risk.py:40:        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=10))
graduation_center/v2/risk.py:44:        reasons.append(RiskReason(factor="전공필수", detail=f"필수지정 {missing}과목 미이수", severity=18))
graduation_center/v2/risk.py:47:        reasons.append(RiskReason(factor="전공필수", detail="필수지정 1과목 미이수", severity=10))
graduation_center/v2/risk.py:52:        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족(15 초과)", severity=20))
graduation_center/v2/risk.py:55:        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=14))
graduation_center/v2/risk.py:58:        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=8))
graduation_center/v2/risk.py:70:        reasons.append(RiskReason(factor="잔여학기",
graduation_center/v2/risk.py:76:        reasons.append(RiskReason(factor="핵심교양", detail=f"영역 미충족: {areas}", severity=8))
graduation_center/v2/risk.py:78:    for cc in audit.convergence_checks:
graduation_center/v2/risk.py:86:            reasons.append(RiskReason(factor="융합전공", detail=detail, severity=14 if eff_gap >= 9 else 8))
graduation_center/v2/risk.py:90:        reasons.append(RiskReason(factor="평점", detail="졸업 평점 기준 미달", severity=20))
graduation_center/v2/risk.py:92:        reasons.append(RiskReason(factor="평점", detail="평점 기준 충족 여부 확인 필요", severity=0))
graduation_center/v2/risk.py:94:    if roadmap_feasible is False:
graduation_center/v2/risk.py:96:        reasons.append(RiskReason(factor="로드맵", detail="잔여 학기 내 실현 가능한 계획 없음", severity=15))
graduation_center/v2/risk.py:99:        reasons.append(RiskReason(factor="종합", detail="확인된 부족·위험 항목 없음", severity=0))
graduation_center/v2/risk.py:102:    return RiskAssessment(grade=grade, label=LABELS[grade], score=score, reasons=reasons)
tests/test_student_playbook.py:2:from agent.planner import suggest_actions
graduation_center/v2/audit_v2.py:28:    p = V2_DIR / "required_names_by_year.json"
graduation_center/v2/audit_v2.py:32:def _required_names_for_year(program_id: str, year: int | None) -> list[str] | None:
graduation_center/v2/audit_v2.py:56:    p = V2_DIR / "required_names_by_year.json"
graduation_center/v2/audit_v2.py:68:    p = V2_DIR / "required_names_by_year.json"
graduation_center/v2/audit_v2.py:107:# TODO(동시배정 최적화 — 미구현): 겹침 과목을 제1전공/다전공 vs 융합전공 중 어디에 산입할지
graduation_center/v2/audit_v2.py:109:#   (1) 중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 0). 동시인정은 cap까지만.
graduation_center/v2/audit_v2.py:111:#   (3) **제1전공/다전공의 전공필수(is_required) 과목은 융합전공 전용으로 넘길 수 없음**
graduation_center/v2/audit_v2.py:114:def _convergence_checks(verified: VerifiedTranscript, program_ids, tracks, primary_program_id,
graduation_center/v2/audit_v2.py:116:    """연계·융합전공 졸업요건 + 학점 중복인정(학사규정 제77조). **교과목코드 기반.**
graduation_center/v2/audit_v2.py:119:      - 연계융합 designated = 학생 이수과목 중 앞5자리가 연계융합 카탈로그에 있는 것(교양 제외).
graduation_center/v2/audit_v2.py:120:      - 그중 제1전공 카탈로그(앞5자리)에도 있으면 'shared'(중복인정 대상), 아니면 '융합전용'.
graduation_center/v2/audit_v2.py:121:    - 최저: 다전공 36 / 부전공 18.  중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 불인정).
graduation_center/v2/audit_v2.py:122:    - 인정 학점 = 융합전용 학점 + min(shared 학점, cap).  (shared 초과분은 제1전공에만 인정)
graduation_center/v2/audit_v2.py:151:        # 연계융합 designated 과목(교양 제외) — 코드 앞5자리 기준. 들은 건 전부 융합전공에 인정.
graduation_center/v2/audit_v2.py:209:                c["assignment"], c["selectable"] = "융합전용", False
graduation_center/v2/audit_v2.py:212:        # 고정분: 겹침을 제외한 나머지. 제1전공 non-overlap / 융합전용. 겹침은 전부 사용자 배정 풀.
graduation_center/v2/audit_v2.py:214:        fusion_base = round(earned - overlap_cr, 1)                   # 융합전용 (예: 18)
graduation_center/v2/audit_v2.py:221:                f"한도 초과·미선택분은 제1전공 또는 {('연계' if is_yeonge else '융합')}전공 한쪽에만 인정돼 양쪽 학점이 달라집니다.")
graduation_center/v2/audit_v2.py:224:            "conv_type": "연계전공" if is_yeonge else "융합전공",
graduation_center/v2/audit_v2.py:229:            # 동시배정: 제1전공 = primary_base + (중복인정+제1전공 선택분), 융합 = fusion_base + (중복인정+융합 선택분)
graduation_center/v2/audit_v2.py:238:    convergence_program_ids=(), convergence_tracks=None,
graduation_center/v2/audit_v2.py:269:    req_names, applied_year = _required_names_for_year(profile.program_id, year)
graduation_center/v2/audit_v2.py:301:        missing_required_names=missing_names,
graduation_center/v2/audit_v2.py:304:        convergence_checks=_convergence_checks(verified, convergence_program_ids, convergence_tracks,
tests/test_actions.py:111:def test_course_planner_action_output_ends_with_final_confirmation():
graduation_center/v2/planner.py:3:결정론이 사실(후보 과목·갭)을 깔고, LLM은 RoadmapPlan만 생성한다. 검증기가 하드 제약을
graduation_center/v2/planner.py:16:    AuditResult, RequirementProfile, RoadmapCourse, RoadmapPlan, RoadmapTerm, Source,
graduation_center/v2/planner.py:157:            "missing_required_names": audit.missing_required_names,
graduation_center/v2/planner.py:183:                "term_risk": {"type": "string", "enum": ["low", "medium", "high"]},
graduation_center/v2/planner.py:185:            }, "required": ["term", "courses", "term_credits", "term_risk", "notes"]}},
graduation_center/v2/planner.py:211:def plan_roadmap(planning_context: dict, client=None) -> RoadmapPlan:
graduation_center/v2/planner.py:214:        return RoadmapPlan(status="not_generated",
graduation_center/v2/planner.py:221:        "text": {"format": {"type": "json_schema", "name": "roadmap_plan",
graduation_center/v2/planner.py:231:    return RoadmapPlan(
graduation_center/v2/planner.py:266:def validate_roadmap(plan: RoadmapPlan, ctx: dict, context: StudentContext) -> ValidationReport:
graduation_center/v2/planner.py:383:    p = V2_DIR / "required_names_by_year.json"
graduation_center/v2/planner.py:400:    """남은 졸업 의무를 단일 후보 풀로 정규화(전공·필수·융합·교양). 반환 (선택후보, 요건요약)."""
graduation_center/v2/planner.py:407:    if audit.missing_required_names:
graduation_center/v2/planner.py:410:        for n in audit.missing_required_names:
graduation_center/v2/planner.py:418:    # 2) 연계융합 부족 — 부족 그룹 우선 미이수 융합과목
graduation_center/v2/planner.py:419:    for cc in audit.convergence_checks:
graduation_center/v2/planner.py:424:            reqs.append({"label": f"{cc['name']} 부족", "area": "융합전공", "priority": 2, "need": cc["gap"],
graduation_center/v2/planner.py:426:                                   "credits": c["credits"], "assignment": "융합전공",
graduation_center/v2/planner.py:429:                                   # 융합 카탈로그는 현황 기반 → 개설학기 known(있으면 hard-check)
graduation_center/v2/planner.py:486:def plan_greedy(selected: list[dict], terms: list[list]) -> tuple[list[RoadmapTerm], list[str], list[dict]]:
graduation_center/v2/planner.py:514:        courses = [RoadmapCourse(course_id=it.get("course_id", "") or "", name_ko=it["name_ko"],
graduation_center/v2/planner.py:520:        out.append(RoadmapTerm(term=lab, courses=courses, term_credits=round(used[lab], 1),
graduation_center/v2/planner.py:521:                               term_risk="medium" if used[lab] > cap - 3 else "low"))
graduation_center/v2/planner.py:528:def run_planner(
graduation_center/v2/planner.py:531:) -> tuple[RoadmapPlan, ValidationReport, dict]:
graduation_center/v2/planner.py:533:    (LLM 배치 미사용 — codex 권장. plan_roadmap 등 LLM 함수는 보존만.)"""
graduation_center/v2/planner.py:542:        return (RoadmapPlan(status="generated", feasible=True, terms=[],
graduation_center/v2/planner.py:551:        return (RoadmapPlan(status="generated", feasible=None, terms=[],
graduation_center/v2/planner.py:566:    plan = RoadmapPlan(status="generated", feasible=not unplaced, terms=placed,
graduation_center/v2/verification.py:71:            # 실제 엑셀 교과목코드를 항상 보존(제1전공 카탈로그 밖 과목도 융합전공 코드매칭 가능하도록).
graduation_center/v2/models_v2.py:3:데이터 계약: 결정론 노드가 사실(matching·audit·risk)을 채우고, LLM은 RoadmapPlan만
graduation_center/v2/models_v2.py:4:생성하며, 검증기가 RoadmapPlan을 재확인한다. AuditPipelineResponse가 JSON-first 응답.
graduation_center/v2/models_v2.py:12:# 졸업요건 영역 (집계 카테고리). 융합전공은 연계·융합전공 카탈로그 과목 표시용.
graduation_center/v2/models_v2.py:13:Area = Literal["전공", "기초교양", "핵심교양", "자유교양", "일반선택", "융합전공"]
graduation_center/v2/models_v2.py:19:    program_id: str                                  # 예: ai_bigdata, mirae_mobility
graduation_center/v2/models_v2.py:29:    convergence_program_ids: list[str] = Field(default_factory=list)  # 연계·융합전공 — 사용자 입력
graduation_center/v2/models_v2.py:30:    convergence_tracks: dict[str, str] = Field(default_factory=dict)  # program_id → "다전공"|"부전공"
graduation_center/v2/models_v2.py:47:    group: str | None = None                         # 연계융합전공 그룹(A그룹/B그룹) — 그룹별 최저 체크용
graduation_center/v2/models_v2.py:125:    missing_required_names: list[str] = Field(default_factory=list)
graduation_center/v2/models_v2.py:128:    convergence_checks: list[dict] = Field(default_factory=list)  # [{program_id,name,required,earned,gap,matched_courses}]
graduation_center/v2/models_v2.py:133:class RiskReason(BaseModel):
graduation_center/v2/models_v2.py:139:class RiskAssessment(BaseModel):
graduation_center/v2/models_v2.py:143:    reasons: list[RiskReason] = Field(default_factory=list)
graduation_center/v2/models_v2.py:147:class RoadmapCourse(BaseModel):
graduation_center/v2/models_v2.py:151:    satisfies: str = ""                              # 영역/필수 (예: 필수지정, 전공 부족, 융합 A그룹)
graduation_center/v2/models_v2.py:153:    assignment: str = ""                             # 융합 과목 이수구분(중복인정/제1전공/융합전공) 등
graduation_center/v2/models_v2.py:160:class RoadmapTerm(BaseModel):
graduation_center/v2/models_v2.py:162:    courses: list[RoadmapCourse] = Field(default_factory=list)
graduation_center/v2/models_v2.py:164:    term_risk: Literal["low", "medium", "high"] = "low"
graduation_center/v2/models_v2.py:179:class RoadmapPlan(BaseModel):
graduation_center/v2/models_v2.py:182:    terms: list[RoadmapTerm] = Field(default_factory=list)
graduation_center/v2/models_v2.py:223:    risk: RiskAssessment
graduation_center/v2/models_v2.py:224:    roadmap: RoadmapPlan
graduation_center/v2/pipeline.py:15:from graduation_center.v2.planner import run_planner
graduation_center/v2/pipeline.py:16:from graduation_center.v2.risk import compute_risk
graduation_center/v2/pipeline.py:51:    audit = compute_audit(verified, profile, convergence_program_ids=ctx.convergence_program_ids,
graduation_center/v2/pipeline.py:52:                          convergence_tracks=ctx.convergence_tracks)
graduation_center/v2/pipeline.py:53:    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
graduation_center/v2/pipeline.py:55:    risk = compute_risk(audit, ctx, roadmap_feasible=feasible)
graduation_center/v2/pipeline.py:58:    conv_n = len(audit.convergence_checks)
graduation_center/v2/pipeline.py:67:                       summary=f"총 부족 {audit.total_gap} · 필수누락 {len(audit.missing_required_names)} · 연계융합 {conv_n}건",
graduation_center/v2/pipeline.py:68:                       branch_taken=(f"연계융합 {conv_n}개 검사" if conv_n else ("부족 있음" if audit.total_gap > 0 else "충족"))),
graduation_center/v2/pipeline.py:79:                       summary=f"{risk.grade} {risk.label} ({risk.score})", branch_taken=f"{risk.grade} {risk.label}"),
graduation_center/v2/pipeline.py:81:    md = _markdown(ctx, profile, audit, risk, plan)
graduation_center/v2/pipeline.py:83:        context=ctx, verified_transcript=verified, audit=audit, risk=risk,
graduation_center/v2/pipeline.py:84:        roadmap=plan, sources=sources, node_trace=trace, report_markdown=md,
graduation_center/v2/pipeline.py:88:def _markdown(ctx, profile, audit, risk, plan) -> str:
graduation_center/v2/pipeline.py:90:         f"**종합 판정: {risk.grade} {risk.label}**  ·  총 {audit.total_earned:.0f}/{audit.total_required:.0f}학점"
graduation_center/v2/pipeline.py:95:    if audit.convergence_checks:
graduation_center/v2/pipeline.py:96:        L += ["", "## 연계·융합전공 (학점 중복인정 반영)"]
graduation_center/v2/pipeline.py:97:        for cc in audit.convergence_checks:
graduation_center/v2/pipeline.py:110:    if audit.missing_required_names:
graduation_center/v2/pipeline.py:111:        L += ["", "## 미이수 필수지정"] + [f"- {n}" for n in audit.missing_required_names]
frontend/src/components/GraduationV2.jsx:58:  "융합 유지": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
frontend/src/components/GraduationV2.jsx:59:  "융합전용": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
frontend/src/components/GraduationV2.jsx:79:  ["fusion", "융합전공", "#047857", "#ecfdf5", "#a7f3d0"]];
frontend/src/components/GraduationV2.jsx:81:function ConvergenceBlock({ cc, C, first }) {
frontend/src/components/GraduationV2.jsx:84:  // 기본 선택: 전공필수 우선 중복인정(한도까지) → 제1전공 부족분 채움(제1전공) → 나머지 융합
frontend/src/components/GraduationV2.jsx:107:  // 미이수 시나리오: 융합 부족 시 안 들은 융합 과목 추천(부족 그룹 우선)
frontend/src/components/GraduationV2.jsx:130:      {overCap && <div style={{ fontSize: 11.5, color: "#dc2626", marginBottom: 6 }}>⚠️ 중복인정 {dupCr}학점 &gt; 한도 {cap}학점 — 일부를 제1전공/융합으로 바꾸세요.</div>}
frontend/src/components/GraduationV2.jsx:133:          ? "✅ 현재 배정으로 제1전공·융합 둘 다 졸업요건 충족"
frontend/src/components/GraduationV2.jsx:192:                      border: `1px solid ${c.taken ? "#a7f3d0" : "#e5e7eb"}`, borderRadius: 5, padding: "2px 0" }}>{c.taken ? "융합전용" : "미이수"}</span>
frontend/src/components/GraduationV2.jsx:211:    preferences: "", convergence_program_ids: [], convergence_tracks: {},
frontend/src/components/GraduationV2.jsx:257:  // 다전공·부전공 검색 옵션: 연계융합(분석지원) + 전체 학과(데모 미지원)
frontend/src/components/GraduationV2.jsx:259:    const convNames = new Set(convergencePrograms.map(([, p]) => p.name_ko));
frontend/src/components/GraduationV2.jsx:260:    const conv = convergencePrograms.map(([id, p]) => ({ key: "c:" + id, id, label: p.name_ko, supported: true }));
frontend/src/components/GraduationV2.jsx:267:    if (o.supported) { if (!ctx.convergence_program_ids.includes(o.id)) toggleConv(o.id); }
frontend/src/components/GraduationV2.jsx:272:  const convergencePrograms = Object.entries(programs).filter(([, p]) => p.track_type === "convergence");
frontend/src/components/GraduationV2.jsx:274:    const on = c.convergence_program_ids.includes(id);
frontend/src/components/GraduationV2.jsx:275:    const ids = on ? c.convergence_program_ids.filter((x) => x !== id) : [...c.convergence_program_ids, id];
frontend/src/components/GraduationV2.jsx:276:    const tracks = { ...c.convergence_tracks };
frontend/src/components/GraduationV2.jsx:278:    return { ...c, convergence_program_ids: ids, convergence_tracks: tracks };
frontend/src/components/GraduationV2.jsx:280:  const setConvTrack = (id, track) => setCtx((c) => ({ ...c, convergence_tracks: { ...c.convergence_tracks, [id]: track } }));
frontend/src/components/GraduationV2.jsx:369:                {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
frontend/src/components/GraduationV2.jsx:374:          {/* 다전공·부전공 (연계융합 포함, 검색) */}
frontend/src/components/GraduationV2.jsx:376:            <span style={labelStyle}>다전공 · 부전공 (연계·융합전공 포함, 검색)</span>
frontend/src/components/GraduationV2.jsx:378:              <input style={inputStyle} placeholder="학과/전공 검색 후 선택 (데모 분석: 데이터사이언스융합·모빌리티데이터분석)"
frontend/src/components/GraduationV2.jsx:396:              {convergencePrograms.filter(([id]) => ctx.convergence_program_ids.includes(id)).map(([id, p]) => (
frontend/src/components/GraduationV2.jsx:400:                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
frontend/src/components/GraduationV2.jsx:416:            {ctx.convergence_program_ids.length === 0 && otherMajors.length === 0 && (
frontend/src/components/GraduationV2.jsx:532:                <div style={{ width: 120, background: GRADE_COLOR[audit.risk.grade], color: "#fff",
frontend/src/components/GraduationV2.jsx:534:                  <div style={{ fontSize: 46, fontWeight: 800, lineHeight: 1 }}>{audit.risk.grade}</div>
frontend/src/components/GraduationV2.jsx:535:                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{audit.risk.label}</div>
frontend/src/components/GraduationV2.jsx:544:                      height: 9, background: GRADE_COLOR[audit.risk.grade] }} />
frontend/src/components/GraduationV2.jsx:547:                    {audit.risk.reasons.length === 0 && <span style={{ fontSize: 12, color: C.ok }}>리스크 요인 없음 — 졸업요건 충족</span>}
frontend/src/components/GraduationV2.jsx:548:                    {audit.risk.reasons.map((r, i) => (
frontend/src/components/GraduationV2.jsx:608:              {audit.audit.missing_required_names.length > 0 && (
frontend/src/components/GraduationV2.jsx:609:                <p style={{ color: C.danger, fontSize: 13, margin: "8px 0 0" }}>미이수 필수지정: {audit.audit.missing_required_names.join(", ")}</p>
frontend/src/components/GraduationV2.jsx:616:            {/* 연계·융합전공 — 교육과정 전체 + 이수 강조 + 이수구분 배정 */}
frontend/src/components/GraduationV2.jsx:617:            {audit.audit.convergence_checks?.length > 0 && (
frontend/src/components/GraduationV2.jsx:619:                <div style={sectionTitle}>🔗 연계·융합전공 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>(학점 중복인정 반영)</span></div>
frontend/src/components/GraduationV2.jsx:620:                {audit.audit.convergence_checks.map((cc, i) => (
frontend/src/components/GraduationV2.jsx:621:                  <ConvergenceBlock key={i} cc={cc} C={C} first={i === 0} />
frontend/src/components/GraduationV2.jsx:629:              {audit.roadmap.status === "not_generated" && <p style={{ color: C.muted, fontSize: 13 }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
frontend/src/components/GraduationV2.jsx:630:              {audit.roadmap.status === "blocked" && <p style={{ color: C.danger, fontSize: 13 }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
frontend/src/components/GraduationV2.jsx:631:              {audit.roadmap.status === "generated" && audit.roadmap.terms.length === 0 && (
frontend/src/components/GraduationV2.jsx:633:                  ✅ {audit.roadmap.why_this_plan}
frontend/src/components/GraduationV2.jsx:640:                if (audit.audit.missing_required_names?.length) rem.push(`필수지정 ${audit.audit.missing_required_names.length}과목`);
frontend/src/components/GraduationV2.jsx:642:                (audit.audit.convergence_checks || []).forEach((cc) => { if (cc.gap > 0) rem.push(`${cc.name} ${cc.gap}학점`); });
frontend/src/components/GraduationV2.jsx:645:                return rem.length > 0 && audit.roadmap.terms.length > 0 ? (
frontend/src/components/GraduationV2.jsx:652:              {audit.roadmap.terms.length > 0 && (
frontend/src/components/GraduationV2.jsx:654:                  {audit.roadmap.terms.map((t, i) => (
frontend/src/components/GraduationV2.jsx:676:              {audit.roadmap.feasible === false && audit.roadmap.blocked_reason && (
frontend/src/components/GraduationV2.jsx:678:                  ⚠️ {audit.roadmap.blocked_reason}{audit.roadmap.relaxation_hint ? ` · ${audit.roadmap.relaxation_hint}` : ""}
frontend/src/components/GraduationV2.jsx:681:              {audit.roadmap.why_this_plan && audit.roadmap.terms.length > 0 && (
frontend/src/components/GraduationV2.jsx:683:                  <strong style={{ color: C.navy }}>왜 이 계획:</strong> {audit.roadmap.why_this_plan}</p>
frontend/src/components/GraduationV2.jsx:685:              {audit.roadmap.assumptions?.length > 0 && <p style={{ fontSize: 11, color: C.muted, margin: "8px 0 0" }}>가정: {audit.roadmap.assumptions.join(" / ")}</p>}
frontend/src/components/GraduationV2.jsx:687:              {audit.roadmap.overflow && (
frontend/src/components/GraduationV2.jsx:691:                    {[["부족 학점", `${audit.roadmap.overflow.shortfall_credits}학점`],
frontend/src/components/GraduationV2.jsx:692:                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
frontend/src/components/GraduationV2.jsx:693:                      ["필요 총학기", `${audit.roadmap.overflow.total_semesters_needed}학기`],
frontend/src/components/GraduationV2.jsx:694:                      ["초과학기", `${audit.roadmap.overflow.extra_semesters}학기`],
frontend/src/components/GraduationV2.jsx:695:                      ["예상 졸업", audit.roadmap.overflow.projected_graduation_term || "—"]].map(([k, v]) => (
frontend/src/components/GraduationV2.jsx:702:                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{audit.roadmap.overflow.note}</div>

exec
/bin/bash -lc 'rg -n "graduation/v2|compute_audit|run_planner|compute_risk|masked_student_id|student_id" -S .' in /home/carol/kmu_genai
 succeeded in 0ms:
./scripts/build_v2_catalog.py:4:  - data/graduation/v2/sources/course_code_2025_2.xlsx  (2025-2 교육과정 교과목코드 현황)
./scripts/build_v2_catalog.py:5:  - data/graduation/v2/overrides_<program_id>.json       (요람 p.xxx 필수/선수 보강)
./scripts/build_v2_catalog.py:7:  - data/graduation/v2/catalog_<program_id>.json
./scripts/build_v2_catalog.py:8:  - data/graduation/v2/programs.json                     (프로그램 레지스트리)
./scripts/build_v2_catalog.py:9:  - data/graduation/v2/catalog_build_report.json         (행수·중복·미해소 보고)
./docs/codex_scenario_design.md:161:7. Remove or stop using the special-case branches in `run_planner()` that say:
./agent/answer_builder.py:246:    if issue_type == "student_id":
./agent/planner.py:42:    "student_id": [
./agent/planner.py:44:            "action_id": "student_id_issue_guide",
./agent/planner.py:123:    "student_id",
./agent/guard.py:10:    "student_id": re.compile(r"\b20\d{6,8}\b|학번", re.IGNORECASE),
./agent/classifier.py:12:    "student_id": ["학생증", "모바일학생증", "모바일 학생증", "k-card", "kcard", "케이카드", "국제학생증", "재발급", "카드 인식", "안 찍"],
./agent/answer_validator.py:13:    "student_id_value": re.compile(r"(?<!\d)20\d{6,8}(?!\d)"),
./agent/student_playbook.py:62:    "student_id": {
./agent/student_playbook.py:197:        "issue_type": "student_id",
./docs/demo_queries.md:14:| 5 | 모바일학생증이 안 찍혀요 | student_id | 모바일학생증 | playbook override 발동 |
./tests/test_v2_pipeline.py:18:CATALOG = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
./tests/test_v2_pipeline.py:72:    from graduation_center.v2.audit_v2 import compute_audit
./tests/test_v2_pipeline.py:95:    au = compute_audit(vt, prof)
./tests/test_v2_pipeline.py:198:    cat = json.loads(Path("data/graduation/v2/catalog_dsci_convergence.json").read_text(encoding="utf-8"))["courses"]
./tests/test_v2_pipeline.py:232:    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
./tests/test_answer_validator.py:29:    assert "student_id_value" in result["flags"]
./tests/test_actions.py:125:def test_student_id_action_drafts_checklist():
./tests/test_actions.py:127:    result = continue_action("student_id_issue_guide", slots)
./test/3_app.py:210:                    st.success(f"파싱 완료: {transcript.name} ({transcript.student_id})")
./test/3_app.py:218:            student_id = st.text_input("학번", placeholder="20210001")
./test/3_app.py:249:                    student_id=student_id,
./test/3_app.py:265:        c1.metric("이름/학번", f"{t.name} ({t.student_id})")
./test/3_app.py:308:            file_name=f"졸업진단_{t.student_id}.txt",
./test/3_app.py:419:                file_name=f"역량번역_{t.student_id}_{target_job}.txt",
./tests/test_guard.py:4:def test_privacy_guard_blocks_student_id_and_grades():
./tests/test_guard.py:7:    assert "student_id" in result.flags
./tests/test_graduation_real_e2e.py:137:    masked_student_id = transcript.get("masked_student_id")
./tests/test_graduation_real_e2e.py:139:    _assert_safe(masked_student_id is None or "*" in masked_student_id, "학번 마스킹 계약이 깨졌습니다.")
./tests/test_api_contract.py:241:    assert "student_id_value" in data["safety_flags"]
./tests/test_graduation_center.py:24:        "masked_student_id": "2020****",
./docs/agent_product_planning.md:244:| `student_id` | 학생증, 모바일학생증, K-CARD |
./docs/agent_product_planning.md:297:| `student_id` | 실제 학번 또는 "학번" 입력 |
./docs/agent_product_planning.md:574:| `student_id_issue_guide` | 학생증 발급 체크리스트 | `student_id` |
./WORK_STATUS.md:203:| `guard.py` | **개인정보 차단 + 근거 없으면 응답 금지** 강제. 5종 정규식(`student_id`, `resident_number`, `portal_password`, `grade_report`, `phone`) | 사용자 질문 텍스트 / 검색된 청크 목록 | `GuardResult(blocked, flags, message)` |
./tests/test_classifier.py:10:    assert classify_issue("모바일 학생증 재발급은 어떻게 해?")["issue_type"] == "student_id"
./data/actions/attendance_action_schema.json:14:    "student_id",
./frontend/src/components/ActionForm.jsx:44:const PREVIEW_STUDENT_ID = "학번 미기입";
./frontend/src/components/ActionForm.jsx:143:                <td>{PREVIEW_STUDENT_ID}</td>
./frontend/src/components/ActionForm.jsx:206:                <td>{PREVIEW_STUDENT_ID}</td>
./frontend/src/components/ActionForm.jsx:278:                <td>{PREVIEW_STUDENT_ID}</td>
./frontend/src/components/GraduationCenter.jsx:389:        <span>학번</span><strong>{transcript.masked_student_id || "마스킹됨"}</strong>
./app.py:247:@app.get("/graduation/v2/status")
./app.py:280:@app.post("/graduation/v2/verify")
./app.py:312:@app.post("/graduation/v2/audit")
./frontend/src/components/GraduationV2.jsx:208:    student_id: "", program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
./frontend/src/components/GraduationV2.jsx:225:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
./frontend/src/components/GraduationV2.jsx:239:    const m = String(ctx.student_id || "").match(/(20\d{2})/);
./frontend/src/components/GraduationV2.jsx:247:    masked_student_id: ctx.student_id ? ctx.student_id.slice(0, 4) + "XXXX" : null,
./frontend/src/components/GraduationV2.jsx:289:      const r = await fetch(`${apiBase}/graduation/v2/verify`, { method: "POST", body: form });
./frontend/src/components/GraduationV2.jsx:313:      const r = await fetch(`${apiBase}/graduation/v2/audit`, {
./frontend/src/components/GraduationV2.jsx:365:              <input style={inputStyle} placeholder="예: 2025" value={ctx.student_id} onChange={(e) => setCtx({ ...ctx, student_id: e.target.value })} /></Field>
./test/2_agents.py:120:    student_id: str
./test/2_agents.py:372:        student_id=학번,
./test/2_agents.py:385:    student_id = _extract(full_text, r"학\s*번[:\s]+(\d{7,10})", "미확인")
./test/2_agents.py:392:        int("20" + student_id[:2])
./test/2_agents.py:393:        if student_id != "미확인" and student_id[:2].isdigit()
./test/2_agents.py:423:        student_id=student_id,
./test/2_agents.py:772:학번: {transcript.student_id}
./crawler/kmu_student_support.py:35:            doc_id="student_support_student_id",
./crawler/kmu_student_support.py:48:            issue_types=["student_id", "student_support", "portal_access"],
./crawler/kmu_student_support.py:52:            actions=["student_id_issue_guide"],
./tools/checklist.py:34:    elif issue_type == "student_id":
./tools/contact_router.py:12:    "student_id": [{"label": "학생증 발급 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4060"}, {"label": "금융카드 수령/발급", "name": "우리은행 국민대학교 지점"}],
./tools/document_drafter.py:67:    "student_id_issue_guide": {
./tools/document_drafter.py:69:        "issue_type": "student_id",
./tools/document_drafter.py:191:    "student_id_issue_guide": "official_chunk_required",
./tools/document_drafter.py:248:    if action_id == "student_id_issue_guide":
./tools/document_drafter.py:249:        return _student_id_guide(slots)
./tools/document_drafter.py:367:def _student_id_guide(slots: dict) -> dict:
./graduation_center/models.py:25:    masked_student_id: str | None = None
./graduation_center/parser.py:110:    student_id = _extract(full_text, r"학\s*번[:\s]+(\d{7,10})", "")
./graduation_center/parser.py:114:    admission_year = _admission_year(student_id)
./graduation_center/parser.py:139:        student_id=student_id,
./graduation_center/parser.py:283:    student_id = str(data.get("학번", "")).strip()
./graduation_center/parser.py:286:        student_id=student_id,
./graduation_center/parser.py:288:        admission_year=int(data.get("입학연도") or _admission_year(student_id) or 0) or None,
./graduation_center/parser.py:299:    student_id: str,
./graduation_center/parser.py:328:        masked_student_id=_mask_student_id(student_id),
./graduation_center/parser.py:354:def _admission_year(student_id: str) -> int | None:
./graduation_center/parser.py:355:    student_id = student_id.strip()
./graduation_center/parser.py:356:    if len(student_id) >= 4 and student_id[:4].isdigit():
./graduation_center/parser.py:357:        return int(student_id[:4])
./graduation_center/parser.py:358:    if len(student_id) >= 2 and student_id[:2].isdigit():
./graduation_center/parser.py:359:        return int("20" + student_id[:2])
./graduation_center/parser.py:380:def _mask_student_id(student_id: str) -> str | None:
./graduation_center/parser.py:381:    digits = re.sub(r"\D", "", student_id or "")
./graduation_center/service.py:558:    ("student_id",       r"\b20\d{6,8}\b",                                          "[학번 마스킹]",     0),
./graduation_center/v2/risk.py:21:def compute_risk(
./graduation_center/v2/planner.py:528:def run_planner(
./graduation_center/v2/models_v2.py:31:    masked_student_id: str | None = None             # 표시용(뒷자리 마스킹)
./docs/graduation_center_spec_en.md:50:  → compute_audit()                    [deterministic]  → AuditResult
./docs/graduation_center_spec_en.md:55:  → compute_risk()                     [deterministic]  → RiskAssessment   (after validation — feasibility/offering risk now known)
./docs/graduation_center_spec_en.md:71:| `audit.py` | `compute_audit(verified, profile)` → per-area gaps, missing required courses | Det |
./docs/graduation_center_spec_en.md:72:| `risk.py` | `compute_risk(audit, context)` → grade + reason components | Det |
./graduation_center/v2/catalog.py:3:- 카탈로그/요건/교양은 data/graduation/v2/ 의 빌드 산출물에서 로드(캐시).
./graduation_center/v2/catalog.py:18:V2_DIR = Path("data/graduation/v2")
./graduation_center/v2/pipeline.py:8:from graduation_center.v2.audit_v2 import compute_audit
./graduation_center/v2/pipeline.py:15:from graduation_center.v2.planner import run_planner
./graduation_center/v2/pipeline.py:16:from graduation_center.v2.risk import compute_risk
./graduation_center/v2/pipeline.py:51:    audit = compute_audit(verified, profile, convergence_program_ids=ctx.convergence_program_ids,
./graduation_center/v2/pipeline.py:53:    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
./graduation_center/v2/pipeline.py:55:    risk = compute_risk(audit, ctx, roadmap_feasible=feasible)
./graduation_center/v2/audit_v2.py:236:def compute_audit(
./docs/backend_product_planning.md:265:  "safety_flags": ["student_id", "grade_report"],
./docs/backend_product_planning.md:293:| `student_id` | 학번 | `20`으로 시작하는 학번 패턴, `학번` |
./docs/backend_product_planning.md:329:| `student_id` | 학생증, 모바일학생증, K-Card, 재발급 |
./docs/backend_product_planning.md:500:| `student_id_issue_guide` | 학생증 발급 체크리스트 생성 | `student_id` |
./docs/backend_product_planning.md:674:| `masked_student_id` | 마스킹된 학번 |

I’m going to run the existing v2 tests and a couple of targeted probes. The point is not to prove correctness, but to confirm whether suspected failures are live behavior or only theoretical gaps.
exec
/bin/bash -lc "sed -n '230,340p' app.py" in /home/carol/kmu_genai
 succeeded in 0ms:
def graduation_customized_major(request: CustomizedMajorRequest) -> dict:
    """Guide Customized major recognition checks."""
    return _graduation_analysis_response(
        "customized_major",
        request.transcript,
        {"desired_field": request.desired_field, "target_recognition": request.target_recognition},
    )


@app.post("/graduation/credit-drop")
def graduation_credit_drop(request: CreditDropRequest) -> dict:
    """Guide credit-drop / grade-waiver policy checks."""
    return _graduation_analysis_response("credit_drop", request.transcript, {"concern": request.concern})


# --- 졸업센터 v2 (Bounded Audit Agent) — 엑셀 수강내역 기반, Chroma 비의존 ---

@app.get("/graduation/v2/status")
def graduation_v2_status() -> dict:
    """v2 준비 상태 (프로그램 목록·LLM 키 유무). Chroma와 무관."""
    import os
    from graduation_center.v2.catalog import program_total_min, regular_term_cap
    progs = load_programs()
    # 학사규정 제32조 학기당 이수학점 상한을 프로그램별로 미리 계산해 노출(프론트 기본값).
    for pid, p in progs.items():
        total = program_total_min(pid)
        p["total_credits_min"] = total
        p["max_credits_per_term"] = regular_term_cap(total) if total else None
    # 전체 학과 목록(다전공·부전공 선택 UI용 검색 목록). 데모 분석 지원은 convergence 프로그램만.
    departments = []
    try:
        import json as _json
        from pathlib import Path as _Path
        dept = _json.loads(_Path("data/graduation/graduation_requirements.json").read_text(encoding="utf-8"))["departments"]
        seen = set()
        for v in dept.values():
            nm = v.get("학과_전공명") or ""
            if nm and nm not in seen:
                seen.add(nm); departments.append({"name": nm, "college": v.get("대학", "")})
        departments.sort(key=lambda d: (d["college"], d["name"]))
    except Exception:
        pass
    return {
        "programs": progs,
        "departments": departments,
        "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "note": "엑셀 수강내역 업로드 기반. 결정론 진단/리스크는 키 없이도 동작, 로드맵만 LLM 사용.",
    }


@app.post("/graduation/v2/verify")
async def graduation_v2_verify(request: Request) -> dict:
    """수강내역 엑셀(여러 학기) → 매칭 → 편집 가능한 검증 테이블(HITL)."""
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="python-multipart 패키지가 필요합니다.") from exc
    uploads = form.getlist("files") or ([form.get("file")] if form.get("file") else [])
    files: list[tuple[bytes, str]] = []
    for up in uploads:
        if up is None or not hasattr(up, "read"):
            continue
        fn = str(getattr(up, "filename", "") or "")
        if not fn.lower().endswith((".xls", ".xlsx")):
            raise HTTPException(status_code=400, detail=f"엑셀(.xls/.xlsx)만 업로드할 수 있습니다: {fn}")
        content = await up.read()
        missing = v2_fail_fast_columns(content, fn)
        if missing:
            raise HTTPException(status_code=422, detail={"file": fn, "missing_columns": missing})
        files.append((content, fn))
    if not files:
        raise HTTPException(status_code=400, detail="files 필드에 수강내역 엑셀을 1개 이상 업로드해 주세요.")
    context_raw = form.get("context")
    context = json.loads(context_raw) if context_raw else {}
    if "program_id" not in context:
        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다 (예: ai_bigdata, mirae_mobility).")
    try:
        return v2_pipeline.run_verify(files, context)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc


@app.post("/graduation/v2/audit")
def graduation_v2_audit(payload: dict) -> dict:
    """사용자 확정 테이블 → 진단 → 로드맵(LLM+검증) → 리스크 → 컨설팅 응답."""
    if "context" not in payload or "program_id" not in payload.get("context", {}):
        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다.")
    try:
        return v2_pipeline.run_audit(payload).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc


_EMPTY_ANSWER_VALIDATION = {"ok": True, "flags": [], "markers": [], "citation_ids": []}
_EMPTY_OUTPUT_PRIVACY = {"ok": True, "flags": []}
_ACTION_LLM_DEFAULT = {"used": False, "reason": "not_applicable"}

# B6 (§20): per-/ask operational telemetry. Mirrors llm_client._record_usage —
# no raw question/answer/slots are ever written, and file IO fails silently so a
# logging problem never breaks an answer.
AGENT_USAGE_LOG_PATH = Path("data/state/agent_usage.jsonl")


def _llm_usage_flags(llm_metadata: dict) -> dict:
    """Derive boolean LLM-assist flags from /ask llm metadata for usage logging."""
    qe = llm_metadata.get("query_expansion", {}) or {}
    rr = llm_metadata.get("rerank", {}) or {}
    pol = llm_metadata.get("polish", {}) or {}
    return {
        "llm_query_expansion_used": bool(qe.get("used")),
        "llm_rerank_used": bool(rr.get("used")),

exec
/bin/bash -lc 'pytest tests/test_v2_pipeline.py -q' in /home/carol/kmu_genai
exec
/bin/bash -lc "sed -n '1,130p' graduation_center/v2/pipeline.py" in /home/carol/kmu_genai
exec
/bin/bash -lc "sed -n '1,280p' tests/test_v2_pipeline.py" in /home/carol/kmu_genai
 succeeded in 0ms:
"""v2 오케스트레이션 — verify / audit 두 단계 + JSON-first 응답 조립.

run_verify: 엑셀(여러 학기) → 매칭 → 편집 가능한 검증 테이블 반환(HITL).
run_audit : 사용자 확정 테이블 → 진단 → 로드맵(LLM+검증) → 리스크 → AuditPipelineResponse.
"""
from __future__ import annotations

from graduation_center.v2.audit_v2 import compute_audit
from graduation_center.v2.catalog import assemble_requirement_profile
from graduation_center.v2.excel_parser import parse_many
from graduation_center.v2.models_v2 import (
    AuditPipelineResponse, CourseMatch, NodeTraceEvent, Source, StudentContext,
    VerifiedCourse,
)
from graduation_center.v2.planner import run_planner
from graduation_center.v2.risk import compute_risk
from graduation_center.v2.verification import build_verification_table, finalize_transcript


def run_verify(files: list[tuple[bytes, str]], context: dict) -> dict:
    ctx = StudentContext.model_validate(context)
    lines, retakes = parse_many(files)
    table, unresolved, retakes = build_verification_table(lines, ctx.program_id, retakes)
    matched_n = sum(1 for t in table if t.course_id and not t.aggregate_only)
    agg_n = sum(1 for t in table if t.aggregate_only)
    trace = [
        NodeTraceEvent(node="요람 로딩", kind="tool", summary=f"{ctx.program_id} 카탈로그·요건 로드"),
        NodeTraceEvent(node="데이터 수집", kind="tool",
                       summary=f"{len(files)}개 학기 파일 · {len(lines)}개 수강행", branch_taken=f"{len(files)}개 학기 병합"),
        NodeTraceEvent(node="코드 매칭", kind="tool",
                       summary=f"매칭 {matched_n} · 집계 {agg_n} · 미해소 {len(unresolved)}",
                       branch_taken=("미해소 있음" if unresolved else "전부 분류")),
    ]
    return {
        "context": ctx.model_dump(),
        "verification_table": [t.model_dump() for t in table],
        "unresolved": [u.model_dump() for u in unresolved],
        "possible_retakes": retakes,
        "node_trace": [e.model_dump() for e in trace],
    }


def run_audit(payload: dict, client=None) -> AuditPipelineResponse:
    ctx = StudentContext.model_validate(payload["context"])
    table = [VerifiedCourse.model_validate(x) for x in payload.get("verification_table", [])]
    unresolved = [CourseMatch.model_validate(x) for x in payload.get("unresolved", [])]
    retakes = payload.get("possible_retakes", [])

    verified = finalize_transcript(table, unresolved, retakes)
    profile = assemble_requirement_profile(ctx)
    audit = compute_audit(verified, profile, convergence_program_ids=ctx.convergence_program_ids,
                          convergence_tracks=ctx.convergence_tracks)
    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
    feasible = plan.feasible if plan.status != "not_generated" else None
    risk = compute_risk(audit, ctx, roadmap_feasible=feasible)
    sources = [Source.model_validate(s) for s in pctx.get("sources", [])]

    conv_n = len(audit.convergence_checks)
    plan_branch = {"generated": "로드맵 생성", "not_generated": "미생성(LLM 없음)", "blocked": "실현불가(blocked)"}.get(plan.status, plan.status)
    if plan.status == "generated" and not plan.terms:
        plan_branch = "갭 없음(이미 충족)"
    trace = [
        NodeTraceEvent(node="데이터 검증", kind="hitl",
                       summary=f"확정 {len(verified.confirmed_courses)} · 제외 {len(verified.excluded)} · {verified.total_earned}학점",
                       branch_taken="사용자 확정"),
        NodeTraceEvent(node="갭 계산", kind="tool",
                       summary=f"총 부족 {audit.total_gap} · 필수누락 {len(audit.missing_required_names)} · 연계융합 {conv_n}건",
                       branch_taken=(f"연계융합 {conv_n}개 검사" if conv_n else ("부족 있음" if audit.total_gap > 0 else "충족"))),
        NodeTraceEvent(node="로드맵 플래닝", kind="llm",
                       status="ok" if plan.status == "generated" else ("warn" if plan.status == "not_generated" else "fail"),
                       summary=plan.why_this_plan or plan.blocked_reason or "", branch_taken=plan_branch),
        NodeTraceEvent(node="검증/repair", kind="validator",
                       status=("ok" if (vrep.ok and not vrep.repair_attempted) else ("fail" if not vrep.ok else "warn")),
                       summary=("통과" if vrep.ok else f"{len(vrep.errors)}건 오류"),
                       branch_taken=("blocked" if plan.status == "blocked"
                                     else ("repair 후 통과" if vrep.repair_attempted and vrep.ok
                                           else ("repair 실패" if vrep.repair_attempted else "통과")))),
        NodeTraceEvent(node="리스크 산정", kind="tool",
                       summary=f"{risk.grade} {risk.label} ({risk.score})", branch_taken=f"{risk.grade} {risk.label}"),
    ]
    md = _markdown(ctx, profile, audit, risk, plan)
    return AuditPipelineResponse(
        context=ctx, verified_transcript=verified, audit=audit, risk=risk,
        roadmap=plan, sources=sources, node_trace=trace, report_markdown=md,
    )


def _markdown(ctx, profile, audit, risk, plan) -> str:
    L = [f"# 졸업사정 컨설팅 리포트 — {profile.department_name_ko}",
         f"**종합 판정: {risk.grade} {risk.label}**  ·  총 {audit.total_earned:.0f}/{audit.total_required:.0f}학점"
         f"  ·  적용 요람 {profile.applied_yoram}", "", "## 영역별 현황"]
    for g in audit.area_gaps:
        mark = "✅" if g.gap <= 0 else f"⚠️ {g.gap:.0f} 부족"
        L.append(f"- {g.area}: {g.earned:.0f}/{g.required:.0f} {mark}")
    if audit.convergence_checks:
        L += ["", "## 연계·융합전공 (학점 중복인정 반영)"]
        for cc in audit.convergence_checks:
            mark = "✅" if cc["gap"] <= 0 else f"⚠️ {cc['gap']:.0f} 부족"
            L.append(f"- {cc['name']}({cc['track']}·{cc['conv_type']}): {cc['earned']:.0f}/{cc['required']:.0f} {mark}"
                     f"  [제1전공과 겹침 {cc['overlap_credits']:.0f} 중 중복인정 가능 {cc['double_recognizable']:.0f}/{cc['double_cap']:.0f}]")
            for gc in cc.get("group_checks", []):
                gm = "✅" if gc["gap"] <= 0 else f"⚠️ {gc['gap']:.0f} 부족"
                L.append(f"    · {gc['group']}: {gc['earned']:.0f}/{gc['required']:.0f} {gm}")
            if cc["recommend_double_count"]:
                L.append(f"  · 중복인정 신청 권장: {', '.join(cc['recommend_double_count'])}")
            if cc.get("note"):
                L.append(f"  · {cc['note']}")
    if not profile.required_course_ids:
        L += ["", f"※ {profile.department_name_ko} 요람 필수지정 과목 데이터 미구축 — 필수과목 체크 제외(확인 필요)"]
    if audit.missing_required_names:
        L += ["", "## 미이수 필수지정"] + [f"- {n}" for n in audit.missing_required_names]
    core_short = [g for g in audit.core_area_gaps if g.gap > 0]
    if core_short:
        L += ["", "## 핵심교양 영역 부족"] + [f"- {g.area}: {g.earned:.0f}/{g.required:.0f}" for g in core_short]
    L += ["", "## 추천 로드맵"]
    if plan.status == "not_generated":
        L.append("- (LLM 미설정 — 결정론 진단만 제공)")
    elif plan.status == "blocked":
        L.append(f"- 실현 가능한 계획 없음: {plan.blocked_reason}  · {plan.relaxation_hint or ''}")
    elif not plan.terms:
        L.append(f"- {plan.why_this_plan}")
    else:
        for t in plan.terms:
            courses = ", ".join(f"{c.name_ko}({c.credits:.0f})" for c in t.courses)
            L.append(f"- {t.term}: {courses}")
        if plan.why_this_plan:
            L.append(f"  - 왜 이 계획: {plan.why_this_plan}")
    if plan.overflow:
        o = plan.overflow
        L += ["", "## ⚠️ 초과학기 예상 시나리오",

 succeeded in 0ms:
"""졸업센터 v2 파이프라인 테스트 (외부 파일·네트워크 비의존).

합성 수강내역 엑셀을 메모리에서 생성해 verify→audit를 검증한다. LLM 플래너는
FakeClient 주입 또는 무키(not_generated) 경로로 테스트한다.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import openpyxl
import pytest

from graduation_center.v2 import pipeline, planner
from graduation_center.v2.models_v2 import RoadmapPlan

CATALOG = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
COURSES = {c["name_ko"]: c for c in CATALOG["courses"]}


def _xlsx(rows: list[dict], term="2025학년도 1학기") -> bytes:
    """수강신청확인서 형식 .xlsx (메모리)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["2025-2 수강신청 확인서"])
    ws.append(["학번", "", "20250000", "", "", "성명", "", "테스트"])
    ws.append(["수강학기", "", term])
    ws.append([])
    ws.append(["교과목코드", "분반", "", "교과목명", "이수구분", "", "학점", "시간", "", "담당교수", "비고"])
    for r in rows:
        ws.append([r["code"], "01", "", r["name"], r.get("area", "전공선택"), "",
                   r["credits"], "", "", "교수", ""])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _major(*names):
    return [{"code": COURSES[n]["course_id"], "name": n, "credits": COURSES[n]["credits"]} for n in names]


def test_catalog_loaded():
    assert len(CATALOG["courses"]) == 39
    assert any(c["is_required"] for c in CATALOG["courses"])


def test_verify_merges_and_matches():
    rows = _major("경영통계", "회계학원론", "AI빅데이터프로그래밍Ⅰ")
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata"})
    assert len(v["verification_table"]) == 3
    assert all(t["course_id"] for t in v["verification_table"])  # 코드 매칭됨


def test_audit_detects_gap_and_missing_required(monkeypatch):
    # LLM 비활성으로 고정(환경 독립) → 결정론 진단/리스크만 검증
    monkeypatch.setattr(planner, "_get_client", lambda: None)
    rows = _major("경영통계", "회계학원론", "현대경영과기업가정신", "경영정보학원론")
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata", "remaining_semesters": 2})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
    resp = pipeline.run_audit(payload)
    assert resp.audit.total_gap > 0
    assert "0910501" in resp.audit.missing_required_course_ids  # 인공지능수학
    assert resp.risk.grade in {"B", "C", "D"}
    # 결정론 통합 플래너: 현재 학기 미입력 → 학기 배치는 생략하되 status는 generated(권장 과목 안내)
    assert resp.roadmap.status == "generated"
    assert resp.roadmap.terms == []  # current_term 없어 배치 생략


def test_planner_fake_client_generates_valid_roadmap():
    from graduation_center.v2.audit_v2 import compute_audit
    from graduation_center.v2.catalog import assemble_requirement_profile
    from graduation_center.v2.models_v2 import StudentContext, VerifiedCourse
    from graduation_center.v2.verification import finalize_transcript

    required = [c for c in CATALOG["courses"] if c["is_required"]]
    electives = [c for c in CATALOG["courses"] if not c["is_required"] and c["requirement_area"] == "전공"]
    # 필수 전부 + 전공 갭이 작게 남도록 일부 전공선택 이수 (필수누락 없음)
    confirmed = list(required)
    major_target = 48 - 3  # 전공 45 → 갭 3
    for c in electives:
        if sum(x["credits"] for x in confirmed) >= major_target:
            break
        confirmed.append(c)
    rows = [{"code": c["course_id"], "name": c["name_ko"], "credits": c["credits"]} for c in confirmed]
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata",
                            "current_term": "2026-1", "remaining_semesters": 3, "max_courses_per_term": 5})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}

    ctx = StudentContext.model_validate(payload["context"])
    vt = finalize_transcript([VerifiedCourse.model_validate(x) for x in payload["verification_table"]], [], [])
    prof = assemble_requirement_profile(ctx)
    au = compute_audit(vt, prof)
    assert not au.missing_required_course_ids  # 필수 전부 이수
    pctx = planner.build_planning_context(au, prof, ctx, vt)
    major_gap = next(g["gap"] for g in pctx["audit_result"]["gaps"] if g["area"] == "전공")
    # 2학기 개설 후보로 2026-2에 갭 충당
    cand2 = [c for c in pctx["candidate_courses"] if "2" in c["offered_terms"]]
    picked, acc = [], 0
    for c in cand2:
        if acc >= major_gap:
            break
        picked.append(c); acc += c["credits"]
    fake = {"feasible": True, "why_this_plan": "갭 충당", "blocked_reason": None,
            "relaxation_hint": None, "assumptions": [],
            "terms": [{"term": "2026-2", "courses": [
                {"course_id": c["course_id"], "name_ko": c["name_ko"], "credits": c["credits"],
                 "satisfies": "전공", "reason": "갭", "source_ids": [c["source_id"]]} for c in picked],
                "term_credits": acc, "term_risk": "low", "notes": []}]}

    class Fake:
        class responses:
            @staticmethod
            def create(**k):
                class R:
                    output_text = json.dumps(fake, ensure_ascii=False)
                return R()

    resp = pipeline.run_audit(payload, client=Fake())
    assert resp.roadmap.status == "generated"
    assert resp.roadmap.feasible is True


def test_validator_rejects_invented_course():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [], "sources": [], "non_major_gap_areas": [],
            "audit_result": {"total_gap": 3, "gaps": [{"area": "전공", "gap": 3}],
                             "missing_required_course_ids": []}}
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2026-2", "courses": [{"course_id": "9999999", "name_ko": "가짜", "credits": 3,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 3, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert not rep.ok
    assert any(e.code == "unknown_course" for e in rep.errors)


def test_validator_rejects_credit_inflation():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
            "requirement_area": "전공", "is_required": True, "prerequisites": [], "offered_terms": ["1"],
            "source_id": "G1"}],
            "sources": [{"id": "G1"}], "non_major_gap_areas": [], "completed_ids": [],
            "audit_result": {"total_gap": 48, "gaps": [{"area": "전공", "gap": 48}], "missing_required_course_ids": []}}
    # 3학점 과목에 48학점 위조
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2026-2", "courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 48,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 48, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert not rep.ok
    assert any(e.code == "credit_mismatch" for e in rep.errors)
    # 인공지능수학은 1학기 개설인데 2026-2(2학기) → not_offered도 잡힘
    assert any(e.code == "not_offered" for e in rep.errors)


def test_validator_rejects_out_of_range_term():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
            "requirement_area": "전공", "is_required": False, "prerequisites": [], "offered_terms": ["1"],
            "source_id": "G1"}],
            "sources": [{"id": "G1"}], "non_major_gap_areas": [], "completed_ids": [],
            "audit_result": {"total_gap": 3, "gaps": [{"area": "전공", "gap": 3}], "missing_required_course_ids": []}}
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2035-1", "courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 3, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert any(e.code == "term_out_of_range" for e in rep.errors)


def test_convergence_overlay(monkeypatch):
    # 주전공 ai_bigdata + 융합전공 dsci_convergence — 융합전공 과목 이수분이 별도 집계됨
    monkeypatch.setattr(planner, "_get_client", lambda: None)
    rows = _major("경영통계", "수리통계", "빅데이터처리와시각화")  # dsci 융합전공에도 속한 과목들
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata",
                            "remaining_semesters": 4, "convergence_program_ids": ["dsci_convergence"]})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
    resp = pipeline.run_audit(payload)
    cc = resp.audit.convergence_checks
    assert len(cc) == 1 and cc[0]["program_id"] == "dsci_convergence"
    assert cc[0]["required"] == 36
    assert cc[0]["earned"] > 0          # 융합전공 과목 이수분 집계
    assert cc[0]["gap"] == 36 - cc[0]["earned"]


def test_convergence_duplicate_credit_cap_and_exclusion():
    # 학사규정 제77조: 제1전공 전공과목(앞5자리 동일)만 중복인정, 다전공 12 / 부전공 융합 6,
    # 교양·일반선택은 중복인정 불가
    from graduation_center.v2.audit_v2 import _convergence_checks
    from graduation_center.v2.models_v2 import VerifiedTranscript, VerifiedCourse
    cat = json.loads(Path("data/graduation/v2/catalog_dsci_convergence.json").read_text(encoding="utf-8"))["courses"]
    major, tot = [], 0
    for c in cat:
        if tot >= 15:  # 12 초과하도록
            break
        major.append(VerifiedCourse(course_id=c["course_id"], name_ko=c["name_ko"],
                                    credits=c["credits"], requirement_area="전공"))
        tot += c["credits"]
    # 교양으로 이수한 dsci-prefix 과목 → 중복인정 불가(제외돼야)
    gyo = VerifiedCourse(course_id=cat[0]["course_id"], name_ko="교양수강분", credits=3, requirement_area="핵심교양")
    vt = VerifiedTranscript(confirmed_courses=major + [gyo])
    total_major = round(sum(c.credits for c in major), 1)
    # primary=dsci_convergence → 모든 designated가 제1전공과 겹침 → cap(double_recognizable) 검증
    da = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "다전공"}, "dsci_convergence")[0]
    assert da["required"] == 36 and da["double_cap"] == 12 and da["conv_type"] == "융합전공"
    # 융합전공 인정 = 들은 융합 과목 전부(교양 gyo 제외) — cap이 깎지 않음
    assert da["earned"] == total_major
    assert da["double_recognizable"] == 12          # 그중 제1전공 중복인정 가능 최대 12
    bu = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "부전공"}, "dsci_convergence")[0]
    assert bu["required"] == 18 and bu["double_cap"] == 6 and bu["double_recognizable"] == 6
    assert bu["earned"] == total_major              # 부전공도 인정학점 자체는 동일


def test_gen_ed_gap_planned_as_slot():
    # 교양만 부족 → 결정론 통합 플래너가 '교양 슬롯'으로 학기에 배치(codex 설계)
    from graduation_center.v2.audit_v2 import AuditResult, AreaGap
    from graduation_center.v2.catalog import assemble_requirement_profile
    from graduation_center.v2.models_v2 import StudentContext, VerifiedTranscript
    ctx = StudentContext(program_id="ai_bigdata", current_term="2026-1", remaining_semesters=2)
    prof = assemble_requirement_profile(ctx)
    au = AuditResult(total_required=130, total_earned=128, total_gap=2,
                     area_gaps=[AreaGap(area="기초교양", required=7, earned=5, gap=2)],
                     missing_required_course_ids=[])
    vt = VerifiedTranscript(total_earned=128)
    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
    assert plan.status == "generated"
    placed = [c for t in plan.terms for c in t.courses]
    assert any("기초교양" in c.satisfies for c in placed)        # 교양 슬롯이 배치됨
    assert all(c.manual_check for c in placed if c.confidence == "generic_slot")

 exited 2 in 558ms:

==================================== ERRORS ====================================
__________________ ERROR collecting tests/test_v2_pipeline.py __________________
ImportError while importing test module '/home/carol/kmu_genai/tests/test_v2_pipeline.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
../exit/lib/python3.8/importlib/__init__.py:127: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests/test_v2_pipeline.py:15: in <module>
    from graduation_center.v2 import pipeline, planner
graduation_center/__init__.py:3: in <module>
    from graduation_center.service import GraduationCenterService
graduation_center/service.py:12: in <module>
    from graduation_center.models import GraduationAnalysisResponse, TranscriptSummary
graduation_center/models.py:7: in <module>
    from pydantic import BaseModel, Field
E   ModuleNotFoundError: No module named 'pydantic'
=========================== short test summary info ============================
ERROR tests/test_v2_pipeline.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.43s

exec
/bin/bash -lc "sed -n '1,220p' data/graduation/graduation_requirements.json" in /home/carol/kmu_genai
 succeeded in 0ms:
{
  "departments": {
    "미분류_한국어문학부글로벌한국어전공": {
      "대학": "미분류",
      "학과_전공명": "한국어문학부글로벌한국어전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 42,
      "일반선택": 58,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "미분류_영미어문전공": {
      "대학": "미분류",
      "학과_전공명": "영미어문전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_영어영문학부글로벌커뮤니케이션영어전공": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "영어영문학부글로벌커뮤니케이션영어전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_중국어문전공": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "중국어문전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 42,
      "일반선택": 58,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_중국학부중국정경전공": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "중국학부중국정경전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_한국역사학과": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "한국역사학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_행정학과": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "행정학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_정치외교학과": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "정치외교학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "글로벌·인문지역대학_사회학과": {
      "대학": "글로벌·인문지역대학",
      "학과_전공명": "사회학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_미디어전공": {
      "대학": "사회과학대학",
      "학과_전공명": "미디어전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_미디어·광고학부광고홍보학전공": {
      "대학": "사회과학대학",
      "학과_전공명": "미디어 · 광고학부광고홍보학전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 45,
      "일반선택": 55,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_교육학과": {
      "대학": "사회과학대학",
      "학과_전공명": "교육학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 50,
      "일반선택": 50,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_러시아‧유라시아학과": {
      "대학": "사회과학대학",
      "학과_전공명": "러시아‧유라시아학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 48,
      "일반선택": 52,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_일본학과": {
      "대학": "사회과학대학",
      "학과_전공명": "일본학과",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 42,
      "일반선택": 58,
      "졸업_최저합계": 130,
      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
    },
    "사회과학대학_공법학전공": {
      "대학": "사회과학대학",
      "학과_전공명": "공법학전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30
      },
      "전공_최저": 48,
      "일반선택": 58,
      "졸업_최저합계": 136,
      "비고": "총 136학점 이상 (공학·과학기술·체육·소프트웨어 계열)"
    },
    "법과대학_법학부사법학전공": {
      "대학": "법과대학",
      "학과_전공명": "법학부사법학전공",
      "교양": {
        "기초교양": 13,
        "핵심교양": 15,
        "자유교양": 2,
        "소계": 30

exec
/bin/bash -lc "ls data/graduation/v2 && sed -n '1,220p' data/graduation/v2/programs.json" in /home/carol/kmu_genai
 succeeded in 0ms:
catalog_ai_bigdata.json
catalog_build_report.json
catalog_dsci_convergence.json
catalog_mirae_mobility.json
catalog_mobility_data_convergence.json
gen_ed_catalog.json
groups_dsci_convergence.json
groups_mobility_data_convergence.json
overrides_ai_bigdata.json
overrides_mirae_mobility.json
programs.json
required_names_by_year.json
requirements_by_year.json
sources
{
  "programs": {
    "ai_bigdata": {
      "name_ko": "AI빅데이터융합경영학과",
      "requirements_key": "경영대학_AI빅데이터",
      "catalog_file": "catalog_ai_bigdata.json",
      "yoram_page": 693,
      "track_type": "primary",
      "convergence_required": null
    },
    "mirae_mobility": {
      "name_ko": "미래모빌리티학과",
      "requirements_key": "자동차융합대학_미래모빌리티학과",
      "catalog_file": "catalog_mirae_mobility.json",
      "yoram_page": 772,
      "track_type": "primary",
      "convergence_required": null
    },
    "dsci_convergence": {
      "name_ko": "데이터사이언스융합전공",
      "requirements_key": null,
      "catalog_file": "catalog_dsci_convergence.json",
      "yoram_page": 882,
      "track_type": "convergence",
      "convergence_required": 36
    },
    "mobility_data_convergence": {
      "name_ko": "모빌리티데이터분석융합전공",
      "requirements_key": null,
      "catalog_file": "catalog_mobility_data_convergence.json",
      "yoram_page": 889,
      "track_type": "convergence",
      "convergence_required": 36
    }
  }
}
exec
/bin/bash -lc "sed -n '280,560p' tests/test_v2_pipeline.py" in /home/carol/kmu_genai
 succeeded in 0ms:
exec
/bin/bash -lc "nl -ba graduation_center/v2/planner.py | sed -n '50,585p'" in /home/carol/kmu_genai
exec
/bin/bash -lc "nl -ba graduation_center/v2/audit_v2.py | sed -n '100,310p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   100	    if profile.admission_year:
   101	        return int(profile.admission_year)
   102	    years = [int(m.group(1)) for c in verified.confirmed_courses
   103	             if (m := re.search(r"(20\d{2})", c.term_label or ""))]
   104	    return min(years) if years else None
   105	
   106	
   107	# TODO(동시배정 최적화 — 미구현): 겹침 과목을 제1전공/다전공 vs 융합전공 중 어디에 산입할지
   108	# 최적 배정 + 이수구분정정 추천. 제약:
   109	#   (1) 중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 0). 동시인정은 cap까지만.
   110	#   (2) 그룹별 최저(다전공 12·부전공 6) + 총 최저(36·18) 모두 충족하도록 배정.
   111	#   (3) **제1전공/다전공의 전공필수(is_required) 과목은 융합전공 전용으로 넘길 수 없음**
   112	#       (필수는 해당 전공에 고정; 중복인정만 가능, 이동 불가).
   113	# 현재는 "각 요건 독립 판정 + 중복인정 한도 표시"까지만 구현.
   114	def _convergence_checks(verified: VerifiedTranscript, program_ids, tracks, primary_program_id,
   115	                        primary_major_required: float = 0.0, primary_major_earned: float = 0.0) -> list[dict]:
   116	    """연계·융합전공 졸업요건 + 학점 중복인정(학사규정 제77조). **교과목코드 기반.**
   117	
   118	    이수구분 텍스트가 부정확할 수 있어, 과목 분류를 교과목코드 앞5자리로 판정:
   119	      - 연계융합 designated = 학생 이수과목 중 앞5자리가 연계융합 카탈로그에 있는 것(교양 제외).
   120	      - 그중 제1전공 카탈로그(앞5자리)에도 있으면 'shared'(중복인정 대상), 아니면 '융합전용'.
   121	    - 최저: 다전공 36 / 부전공 18.  중복인정 한도: 다전공 12 / 부전공(융합 6, 연계 불인정).
   122	    - 인정 학점 = 융합전용 학점 + min(shared 학점, cap).  (shared 초과분은 제1전공에만 인정)
   123	    """
   124	    tracks = tracks or {}
   125	    GYO = {"기초교양", "핵심교양", "자유교양"}
   126	    # 프로그램별 코드 앞5자리 집합 (제1전공 + 선언한 모든 다전공)
   127	    prog_prefixes: dict[str, set] = {}
   128	    for ppid in [primary_program_id, *(program_ids or [])]:
   129	        if ppid in prog_prefixes:
   130	            continue
   131	        try:
   132	            prog_prefixes[ppid] = {c.course_id[:5] for c in load_catalog(ppid)["courses"] if c.course_id}
   133	        except KeyError:
   134	            prog_prefixes[ppid] = set()
   135	    out = []
   136	    for pid in program_ids or []:
   137	        # 중복인정 겹침 = 제1전공 또는 '다른' 다전공의 전공과목과 동일(앞5자리) (학사규정 제77조)
   138	        other_prefixes = set().union(*[pf for ppid, pf in prog_prefixes.items() if ppid != pid]) \
   139	            if len(prog_prefixes) > 1 else prog_prefixes.get(primary_program_id, set())
   140	        try:
   141	            cat = load_catalog(pid)
   142	        except KeyError:
   143	            continue
   144	        name = cat["department_name_ko"]
   145	        is_yeonge = "연계전공" in name
   146	        track = tracks.get(pid, "다전공")
   147	        req = 36.0 if track == "다전공" else 18.0
   148	        cap = 12.0 if track == "다전공" else (0.0 if is_yeonge else 6.0)
   149	        prefix_to_group = {c.course_id[:5]: c.group for c in cat["courses"] if c.course_id}
   150	        conv_prefixes = set(prefix_to_group)
   151	        # 연계융합 designated 과목(교양 제외) — 코드 앞5자리 기준. 들은 건 전부 융합전공에 인정.
   152	        designated = [c for c in verified.confirmed_courses
   153	                      if c.course_id and c.course_id[:5] in conv_prefixes and c.requirement_area not in GYO]
   154	        earned = round(sum(c.credits for c in designated), 1)
   155	        gap = max(0.0, round(req - earned, 1))
   156	        # 그룹별 최저(다전공 12 / 부전공 6) 체크
   157	        rules = (cat.get("group_rules") or {}).get(track, {})
   158	        per_group_min = float(rules.get("per_group_min", 12 if track == "다전공" else 6))
   159	        all_groups = sorted({g for g in prefix_to_group.values() if g})
   160	        group_earned = {g: 0.0 for g in all_groups}
   161	        for c in designated:
   162	            g = prefix_to_group.get(c.course_id[:5])
   163	            if g:
   164	                group_earned[g] = round(group_earned.get(g, 0) + c.credits, 1)
   165	        group_checks = [{"group": g, "earned": group_earned[g], "required": per_group_min,
   166	                         "gap": max(0.0, round(per_group_min - group_earned[g], 1))} for g in all_groups]
   167	        # 그중 제1전공/다른 다전공과 겹치는 과목 = 중복인정 가능 후보(최대 cap까지 양쪽 동시 인정)
   168	        overlap = sorted([c for c in designated if c.course_id[:5] in other_prefixes], key=lambda x: -x.credits)
   169	        overlap_cr = round(sum(c.credits for c in overlap), 1)
   170	        double_recognizable = round(min(overlap_cr, cap), 1)
   171	        # 제1전공/다른 다전공의 '전공필수' 코드 앞5자리 — 중복인정 권장 우선순위
   172	        required_prefixes: set = set()
   173	        for ppid in prog_prefixes:
   174	            if ppid == pid:
   175	                continue
   176	            try:
   177	                required_prefixes |= {c.course_id[:5] for c in load_catalog(ppid)["courses"]
   178	                                      if c.course_id and c.is_required}
   179	            except KeyError:
   180	                pass
   181	        taken_prefixes = {c.course_id[:5] for c in designated}
   182	        # 교육과정 전체 과목 + 이수 강조 + 겹침/이수 여부
   183	        courses_view = []
   184	        for cc in cat["courses"]:
   185	            if not cc.course_id:
   186	                continue
   187	            pfx = cc.course_id[:5]
   188	            courses_view.append({
   189	                "name_ko": cc.name_ko, "group": cc.group or "", "credits": cc.credits,
   190	                "taken": pfx in taken_prefixes, "overlap": pfx in other_prefixes,
   191	                "primary_required": pfx in required_prefixes,
   192	                "course_id": cc.course_id, "offered_terms": list(cc.offered_terms or []),
   193	                "prerequisites": list(cc.prerequisites or []),
   194	            })
   195	        # 중복인정 '추천' = 들은 겹침과목 중 제1전공/다전공 '전공필수' 우선(없으면 학점순), 한도(cap)까지.
   196	        # 한도를 넘는 겹침 과목은 '후보'일 뿐(실제 중복인정 X, 한쪽에만 산입).
   197	        rec_pool = sorted([c for c in courses_view if c["taken"] and c["overlap"]],
   198	                          key=lambda c: (not c["primary_required"], -c["credits"]))
   199	        rec, rec_keys, acc = [], set(), 0.0
   200	        for c in rec_pool:
   201	            if acc >= cap:
   202	                break
   203	            rec.append(c["name_ko"]); rec_keys.add(id(c)); acc += c["credits"]
   204	        # 이수구분 기본 라벨(표시용). 겹침(중복인정 가능) 과목은 프론트에서 3-way로 사용자 선택.
   205	        for c in courses_view:
   206	            if not c["taken"]:
   207	                c["assignment"], c["selectable"] = "미이수", False
   208	            elif not c["overlap"]:
   209	                c["assignment"], c["selectable"] = "융합전용", False
   210	            else:
   211	                c["assignment"], c["selectable"] = "중복인정", True   # 기본 중복인정, 사용자 변경 가능
   212	        # 고정분: 겹침을 제외한 나머지. 제1전공 non-overlap / 융합전용. 겹침은 전부 사용자 배정 풀.
   213	        primary_base = round(primary_major_earned - overlap_cr, 1)    # 제1전공 non-overlap (예: 43)
   214	        fusion_base = round(earned - overlap_cr, 1)                   # 융합전용 (예: 18)
   215	        overlap_courses = [{"name_ko": c.name_ko, "credits": c.credits,
   216	                            "group": prefix_to_group.get(c.course_id[:5]) or "",
   217	                            "primary_required": c.course_id[:5] in required_prefixes}
   218	                           for c in overlap]
   219	        group_short = [gc for gc in group_checks if gc["gap"] > 0]
   220	        note = (f"제1전공과 겹치는 {overlap_cr:.0f}학점은 중복인정(양쪽 동시) 최대 {cap:.0f}까지. "
   221	                f"한도 초과·미선택분은 제1전공 또는 {('연계' if is_yeonge else '융합')}전공 한쪽에만 인정돼 양쪽 학점이 달라집니다.")
   222	        out.append({
   223	            "program_id": pid, "name": name, "track": track,
   224	            "conv_type": "연계전공" if is_yeonge else "융합전공",
   225	            "required": req, "double_cap": cap, "per_group_min": per_group_min,
   226	            "earned": earned, "gap": gap, "group_checks": group_checks,
   227	            "overlap_credits": overlap_cr, "double_recognizable": double_recognizable,
   228	            "recommend_double_count": rec, "note": note, "courses": courses_view,
   229	            # 동시배정: 제1전공 = primary_base + (중복인정+제1전공 선택분), 융합 = fusion_base + (중복인정+융합 선택분)
   230	            "primary_base": primary_base, "fusion_base": fusion_base,
   231	            "primary_required": primary_major_required, "overlap_courses": overlap_courses,
   232	        })
   233	    return out
   234	
   235	
   236	def compute_audit(
   237	    verified: VerifiedTranscript, profile: RequirementProfile,
   238	    convergence_program_ids=(), convergence_tracks=None,
   239	) -> AuditResult:
   240	    earned = verified.earned_by_area
   241	    # 핵심교양 영역별 최저(별표5 단과대 override 반영 — 예: 미래모빌리티 소통 5)
   242	    gen = load_gen_ed().get("core_liberal", {})
   243	    core_min = float(profile.core_area_min or 3)
   244	    overrides = profile.core_area_min_overrides or {}
   245	    gen_areas = gen.get("areas", [])
   246	    # 핵심교양 총 요건 = 영역별 최저 합(소통 override 포함). 예: 미래모빌리티 5+3+3+3+3=17
   247	    core_total_required = sum(float(overrides.get(a, core_min)) for a in gen_areas) or float(profile.area_min.get("핵심교양", 0))
   248	
   249	    area_gaps: list[AreaGap] = []
   250	    for area in HARD_AREAS:
   251	        # 핵심교양은 영역별 최저 합을 요건으로(학번 요람 별표5 반영)
   252	        req = core_total_required if area == "핵심교양" else float(profile.area_min.get(area, 0))
   253	        got = float(earned.get(area, 0))
   254	        if req <= 0:
   255	            continue
   256	        area_gaps.append(AreaGap(area=area, required=req, earned=got, gap=max(0.0, req - got)))
   257	
   258	    core_gaps: list[AreaGap] = []
   259	    for area in gen_areas:
   260	        req = float(overrides.get(area, core_min))
   261	        got = float(verified.core_area_earned.get(area, 0))
   262	        core_gaps.append(AreaGap(area=area, required=req, earned=got, gap=max(0.0, req - got)))
   263	
   264	    # 필수과목 누락 — 학번(입학연도) 요람 기준 '이름' 매칭(코드 무관 → 연도별 현황 엑셀 불필요).
   265	    # 교육과정은 해마다 개편돼 명칭·코드가 바뀌므로, 학생 학번에 맞는 요람의 필수명과
   266	    # 학생 수강내역 과목명을 정규화해 대조한다. 연도 데이터가 없으면 카탈로그 코드 prefix로 폴백.
   267	    cat = load_catalog(profile.program_id)
   268	    year = _admission_year(profile, verified)
   269	    req_names, applied_year = _required_names_for_year(profile.program_id, year)
   270	    if req_names:
   271	        confirmed_norm = {normalize_name(c.name_ko) for c in verified.confirmed_courses}
   272	        aliases = _required_aliases(profile.program_id)
   273	
   274	        def _taken(rn: str) -> bool:
   275	            nn = normalize_name(rn)
   276	            if nn in confirmed_norm:
   277	                return True
   278	            return any(a in confirmed_norm for a in aliases.get(nn, []))  # 명칭 드리프트 동치
   279	        missing_names = [rn for rn in req_names if not _taken(rn)]
   280	        missing_ids = []                       # 이름 기준 — 코드 없음
   281	        required_available = True
   282	        if applied_year:
   283	            profile.applied_yoram = f"{applied_year} 요람 (학번 {year} 기준)" if year else f"{applied_year} 요람"
   284	    else:
   285	        confirmed_prefixes = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
   286	        missing_ids = [cid for cid in profile.required_course_ids if cid[:5] not in confirmed_prefixes]
   287	        missing_names = [cat["by_code"][cid].name_ko for cid in missing_ids if cid in cat["by_code"]]
   288	        required_available = bool(profile.required_course_ids)
   289	
   290	    total_req = float(profile.total_credits_min or 0)
   291	    total_earned = float(verified.total_earned)
   292	    unresolved_credits = round(sum(m.raw.credits for m in verified.unresolved), 1)
   293	
   294	    return AuditResult(
   295	        total_required=total_req,
   296	        total_earned=total_earned,
   297	        total_gap=max(0.0, round(total_req - total_earned, 1)),
   298	        area_gaps=area_gaps,
   299	        core_area_gaps=core_gaps,
   300	        missing_required_course_ids=missing_ids,
   301	        missing_required_names=missing_names,
   302	        required_check_available=required_available,
   303	        gen_basic_courses=_gen_basic_view(verified, profile.program_id, year),
   304	        convergence_checks=_convergence_checks(verified, convergence_program_ids, convergence_tracks,
   305	                                               profile.program_id, float(profile.area_min.get("전공", 0)),
   306	                                               float(earned.get("전공", 0))),
   307	        unresolved_credits=unresolved_credits,
   308	    )

 succeeded in 0ms:
    50	    count, steps = 0, 0
    51	    while steps < 60:
    52	        steps += 1
    53	        so += 1
    54	        if so > 4:
    55	            so = 1; y += 1
    56	        if so in (1, 3):                      # 정규학기만 카운트
    57	            count += 1
    58	            if count == n:
    59	                return f"{y}-{label[so]}"
    60	    return None
    61	
    62	
    63	def project_overflow(audit: AuditResult, profile: RequirementProfile, context: StudentContext):
    64	    """잔여 정규학기로 부족 학점을 못 채우면 초과학기 예상 시나리오 산출(결정론).
    65	
    66	    capacity = 잔여학기 × 학기당 상한(+직전 3.75↑ 보너스 1회). shortfall(총 졸업학점 부족)이
    67	    capacity를 넘으면, 필요한 총 정규학기 수와 초과학기 수·예상 졸업학기를 계산한다.
    68	    """
    69	    from graduation_center.v2.models_v2 import OverflowScenario
    70	    # 더 채워야 하는 학점 = max(졸업최저 부족, 영역별 부족 합). 총학점은 충분해도 특정 영역
    71	    # (예: 전공)이 부족하면 그만큼 추가 이수가 필요하므로 영역 갭 합도 본다.
    72	    area_shortfall = round(sum(g.gap for g in audit.area_gaps if g.gap > 0), 1)
    73	    shortfall = max(float(audit.total_gap), area_shortfall)
    74	    if shortfall <= 0:
    75	        return None
    76	    cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
    77	    if cap <= 0:
    78	        return None
    79	    bonus = PREV_GPA_BONUS if context.prev_term_gpa_ge_375 else 0.0
    80	    remaining = int(context.remaining_semesters)
    81	    if shortfall <= remaining * cap + bonus:
    82	        return None                            # 잔여 학기로 충분 → 시나리오 불필요
    83	    # 필요한 최소 정규학기 수(첫 학기에만 보너스 1회)
    84	    k = 1
    85	    while k * cap + bonus < shortfall and k < 60:
    86	        k += 1
    87	    return OverflowScenario(
    88	        shortfall_credits=round(shortfall, 1),
    89	        per_term_credit_cap=cap,
    90	        remaining_semesters=remaining,
    91	        total_semesters_needed=k,
    92	        extra_semesters=max(0, k - remaining),
    93	        projected_graduation_term=_nth_regular_term(context.current_term, k),
    94	        note=f"잔여 {remaining}학기·학기당 최대 {cap:.0f}학점으로는 부족 {shortfall:.0f}학점을 채울 수 없습니다. "
    95	             f"최소 {k}학기(초과학기 {max(0, k - remaining)}학기)가 필요합니다.",
    96	    )
    97	
    98	
    99	def build_planning_context(
   100	    audit: AuditResult, profile: RequirementProfile, context: StudentContext,
   101	    verified: VerifiedTranscript,
   102	) -> dict:
   103	    cat = load_catalog(context.program_id)
   104	    confirmed_ids = {c.course_id for c in verified.confirmed_courses if c.course_id}
   105	    unresolved_norms = {normalize_name(m.raw.course_name) for m in verified.unresolved}
   106	
   107	    gap_areas = {g.area for g in audit.area_gaps if g.gap > 0}
   108	    candidates, sources = [], []
   109	    src_idx = {}
   110	
   111	    def src_for(course):
   112	        if course.course_id not in src_idx:
   113	            sid = f"G{len(sources) + 1}"
   114	            src_idx[course.course_id] = sid
   115	            sources.append(Source(id=sid,
   116	                                  doc=course.source.get("doc", "2025-2 교육과정 교과목코드 현황"),
   117	                                  page=course.source.get("page"),
   118	                                  source_type="catalog_course", ref=course.course_id))
   119	        return src_idx[course.course_id]
   120	
   121	    want_major = bool(gap_areas & MAJOR_AREAS) or bool(audit.missing_required_course_ids)
   122	    for c in cat["courses"]:
   123	        if c.course_id in confirmed_ids or normalize_name(c.name_ko) in unresolved_norms:
   124	            continue
   125	        is_missing_required = c.course_id in audit.missing_required_course_ids
   126	        if (want_major and c.requirement_area in MAJOR_AREAS) or is_missing_required:
   127	            candidates.append({
   128	                "course_id": c.course_id, "name_ko": c.name_ko, "credits": c.credits,
   129	                "requirement_area": c.requirement_area, "is_required": c.is_required,
   130	                "prerequisites": c.prerequisites, "offered_terms": c.offered_terms,
   131	                "source_id": src_for(c),
   132	            })
   133	    # 비-major(교양) 갭은 후보 카탈로그가 없어 자동계획 불가 → 별도 표기
   134	    non_major_gap_areas = sorted(gap_areas - MAJOR_AREAS)
   135	    # 학사규정 제32조: 정규학기 상한(사용자 override 우선), 계절 6학점, 직전 3.75↑ → 첫 학기 +3
   136	    term_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
   137	    caps = {
   138	        "regular_term_credits": term_cap,
   139	        "seasonal_term_credits": SEASONAL_TERM_CAP,
   140	        "first_term_bonus": PREV_GPA_BONUS if context.prev_term_gpa_ge_375 else 0.0,
   141	        "prev_term_gpa_ge_375": context.prev_term_gpa_ge_375,
   142	    }
   143	    return {
   144	        "student_context": {
   145	            "current_term": context.current_term, "remaining_semesters": context.remaining_semesters,
   146	            "seasonal_semester_allowed": context.seasonal_semester_allowed,
   147	            "max_credits_per_term": term_cap,
   148	            "seasonal_credit_cap": SEASONAL_TERM_CAP,
   149	            "first_regular_term_extra_credits": caps["first_term_bonus"],
   150	            "preferences": context.preferences,
   151	        },
   152	        "caps": caps,
   153	        "audit_result": {
   154	            "total_gap": audit.total_gap,
   155	            "gaps": [{"area": g.area, "gap": g.gap} for g in audit.area_gaps if g.gap > 0],
   156	            "missing_required_course_ids": audit.missing_required_course_ids,
   157	            "missing_required_names": audit.missing_required_names,
   158	        },
   159	        "completed_ids": sorted(confirmed_ids),
   160	        "candidate_courses": candidates,
   161	        "non_major_gap_areas": non_major_gap_areas,
   162	        "sources": [s.model_dump() for s in sources],
   163	    }
   164	
   165	
   166	_SCHEMA = {
   167	    "type": "object", "additionalProperties": False,
   168	    "properties": {
   169	        "feasible": {"type": "boolean"},
   170	        "terms": {"type": "array", "maxItems": 12, "items": {
   171	            "type": "object", "additionalProperties": False,
   172	            "properties": {
   173	                "term": {"type": "string"},
   174	                "courses": {"type": "array", "items": {
   175	                    "type": "object", "additionalProperties": False,
   176	                    "properties": {
   177	                        "course_id": {"type": "string"}, "name_ko": {"type": "string"},
   178	                        "credits": {"type": "number"}, "satisfies": {"type": "string"},
   179	                        "reason": {"type": "string"},
   180	                        "source_ids": {"type": "array", "items": {"type": "string"}},
   181	                    }, "required": ["course_id", "name_ko", "credits", "satisfies", "reason", "source_ids"]}},
   182	                "term_credits": {"type": "number"},
   183	                "term_risk": {"type": "string", "enum": ["low", "medium", "high"]},
   184	                "notes": {"type": "array", "items": {"type": "string"}},
   185	            }, "required": ["term", "courses", "term_credits", "term_risk", "notes"]}},
   186	        "why_this_plan": {"type": "string"},
   187	        "blocked_reason": {"type": ["string", "null"]},
   188	        "relaxation_hint": {"type": ["string", "null"]},
   189	        "assumptions": {"type": "array", "items": {"type": "string"}},
   190	    },
   191	    "required": ["feasible", "terms", "why_this_plan", "blocked_reason", "relaxation_hint", "assumptions"],
   192	}
   193	
   194	_SYS = ("너는 졸업 로드맵 플래너다. 제공된 candidate_courses와 사실만 사용해 남은 학기에 들을 "
   195	        "과목을 배치한다. 새 과목·학점·요건을 지어내지 마라. 선수과목 순서·개설학기를 지키고, "
   196	        "학기당 이수학점 상한(student_context.max_credits_per_term, 계절학기는 seasonal_credit_cap, "
   197	        "첫 정규학기는 first_regular_term_extra_credits만큼 추가 허용)을 넘기지 마라. "
   198	        "학생 선호를 반영한다. 출력은 스키마 JSON만.")
   199	
   200	
   201	def _get_client():
   202	    if not os.getenv("OPENAI_API_KEY", "").strip():
   203	        return None
   204	    try:
   205	        from openai import OpenAI
   206	        return OpenAI()
   207	    except Exception:
   208	        return None
   209	
   210	
   211	def plan_roadmap(planning_context: dict, client=None) -> RoadmapPlan:
   212	    client = client or _get_client()
   213	    if client is None:
   214	        return RoadmapPlan(status="not_generated",
   215	                           why_this_plan="LLM 미설정(OPENAI_API_KEY 없음) — 결정론 진단/리스크만 제공.")
   216	    model = os.getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini")
   217	    kwargs = {
   218	        "model": model,
   219	        "input": [{"role": "system", "content": _SYS},
   220	                  {"role": "user", "content": json.dumps(planning_context, ensure_ascii=False)}],
   221	        "text": {"format": {"type": "json_schema", "name": "roadmap_plan",
   222	                            "schema": _SCHEMA, "strict": True}},
   223	    }
   224	    if any(model.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")):
   225	        kwargs["reasoning"] = {"effort": "minimal"}
   226	    else:
   227	        kwargs["temperature"] = 0.1
   228	    resp = client.responses.create(**kwargs)
   229	    text = getattr(resp, "output_text", "") or ""
   230	    data = json.loads(text)
   231	    return RoadmapPlan(
   232	        status="generated",
   233	        feasible=data.get("feasible"),
   234	        terms=data.get("terms", []),
   235	        why_this_plan=data.get("why_this_plan", ""),
   236	        blocked_reason=data.get("blocked_reason"),
   237	        relaxation_hint=data.get("relaxation_hint"),
   238	        assumptions=data.get("assumptions", []),
   239	    )
   240	
   241	
   242	def _allowed_terms(context: StudentContext) -> set[str] | None:
   243	    """current_term·잔여학기·계절학기로 허용 가능한 학기 라벨 집합 생성."""
   244	    if not context.current_term:
   245	        return None
   246	    try:
   247	        y, s = context.current_term.split("-")
   248	        y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
   249	    except Exception:
   250	        return None
   251	    label = {1: "1", 2: "S", 3: "2", 4: "W"}
   252	    allowed, reg, steps = set(), 0, 0
   253	    while reg < context.remaining_semesters and steps < 40:
   254	        steps += 1
   255	        so += 1
   256	        if so > 4:
   257	            so = 1; y += 1
   258	        lab = f"{y}-{label[so]}"
   259	        if so in (1, 3):           # 정규학기
   260	            allowed.add(lab); reg += 1
   261	        elif context.seasonal_semester_allowed:  # 계절학기(허용 시)
   262	            allowed.add(lab)
   263	    return allowed
   264	
   265	
   266	def validate_roadmap(plan: RoadmapPlan, ctx: dict, context: StudentContext) -> ValidationReport:
   267	    errors: list[ValidationError] = []
   268	    cand = {c["course_id"]: c for c in ctx["candidate_courses"]}
   269	    src_ids = {s["id"] for s in ctx["sources"]}
   270	    completed = set(ctx.get("completed_ids", []))
   271	    allowed = _allowed_terms(context)
   272	    planned: set[str] = set()          # 전체 계획된 course_id
   273	    prior_planned: set[str] = set()    # 앞 학기까지 계획된 course_id (선수 검사용)
   274	    seen_terms: set[str] = set()
   275	    planned_by_area: dict[str, float] = {}
   276	
   277	    caps = ctx.get("caps", {})
   278	    reg_cap = float(caps.get("regular_term_credits", 19.0))
   279	    seasonal_cap = float(caps.get("seasonal_term_credits", SEASONAL_TERM_CAP))
   280	    first_bonus = float(caps.get("first_term_bonus", 0.0))
   281	    # 직전학기 3.75↑ 보너스는 첫 '정규학기'에만 — 계획상 가장 이른 정규학기 식별
   282	    first_regular = None
   283	    for t in sorted(plan.terms, key=lambda x: _term_key(x.term)):
   284	        if _term_sem(t.term) in ("1", "2"):
   285	            first_regular = t.term
   286	            break
   287	
   288	    # 잔여학기 상한은 '정규학기' 수 기준(계절학기는 _allowed_terms에서 별도 허용·6학점 cap)
   289	    regular_count = sum(1 for t in plan.terms if _term_sem(t.term) in ("1", "2"))
   290	    if regular_count > context.remaining_semesters:
   291	        errors.append(ValidationError(code="too_many_terms",
   292	                      detail=f"정규학기 수 {regular_count} > 잔여 {context.remaining_semesters}"))
   293	
   294	    for t in plan.terms:
   295	        sem = _term_sem(t.term)
   296	        if t.term in seen_terms:
   297	            errors.append(ValidationError(code="dup_term", detail=f"학기 라벨 중복: {t.term}"))
   298	        seen_terms.add(t.term)
   299	        if allowed is not None and t.term not in allowed:
   300	            errors.append(ValidationError(code="term_out_of_range",
   301	                          detail=f"{t.term}은 허용 학기({sorted(allowed)}) 밖"))
   302	        # 학사규정 제32조 학기당 이수학점 상한(정규/계절 + 첫 정규학기 보너스)
   303	        is_seasonal = sem in ("S", "W")
   304	        term_cap = seasonal_cap if is_seasonal else (reg_cap + (first_bonus if t.term == first_regular else 0.0))
   305	        term_credit_total = sum(float(c.credits) for c in t.courses)
   306	        if term_credit_total > term_cap + 0.01:
   307	            errors.append(ValidationError(code="over_credit_cap",
   308	                          detail=f"{t.term} 이수학점 {term_credit_total:.0f} > 상한 {term_cap:.0f}"))
   309	        if sem in ("S", "W") and not context.seasonal_semester_allowed:
   310	            errors.append(ValidationError(code="seasonal_not_allowed", detail=f"{t.term} 계절학기 불가"))
   311	        cur_term_ids = []
   312	        catalog_credit_sum = 0.0
   313	        for c in t.courses:
   314	            if c.course_id not in cand:
   315	                errors.append(ValidationError(code="unknown_course", detail=c.name_ko, course_id=c.course_id))
   316	                continue
   317	            cc = cand[c.course_id]
   318	            if c.course_id in planned:
   319	                errors.append(ValidationError(code="dup_course", detail=c.name_ko, course_id=c.course_id))
   320	            planned.add(c.course_id)
   321	            cur_term_ids.append(c.course_id)
   322	            # 학점은 카탈로그 값이 진실 — LLM 값 위조 방지
   323	            if abs(float(c.credits) - float(cc["credits"])) > 0.01:
   324	                errors.append(ValidationError(code="credit_mismatch",
   325	                              detail=f"{c.name_ko} 학점 {c.credits}≠카탈로그 {cc['credits']}", course_id=c.course_id))
   326	            catalog_credit_sum += cc["credits"]
   327	            # satisfies는 카탈로그 영역과 일치해야
   328	            if cc["requirement_area"] not in (c.satisfies or "") and (c.satisfies or "") not in ("필수", "전공필수"):
   329	                errors.append(ValidationError(code="bad_satisfies",
   330	                              detail=f"{c.name_ko} satisfies={c.satisfies}≠{cc['requirement_area']}", course_id=c.course_id))
   331	            if sem and sem not in cc["offered_terms"]:
   332	                errors.append(ValidationError(code="not_offered", detail=f"{c.name_ko} {t.term} 미개설", course_id=c.course_id))
   333	            # 선수과목: 이미 이수 or 앞 학기에 계획돼야 (같은 학기/뒤 학기 불가)
   334	            for pre in cc.get("prerequisites", []):
   335	                if pre not in completed and pre not in prior_planned:
   336	                    errors.append(ValidationError(code="prereq_unmet",
   337	                                  detail=f"{c.name_ko} 선수과목 미충족", course_id=c.course_id))
   338	            if any(sid not in src_ids for sid in c.source_ids):
   339	                errors.append(ValidationError(code="bad_source", detail=c.name_ko, course_id=c.course_id))
   340	            planned_by_area[cc["requirement_area"]] = planned_by_area.get(cc["requirement_area"], 0.0) + cc["credits"]
   341	        # term_credits는 카탈로그 학점 합과 일치해야
   342	        if abs(round(catalog_credit_sum, 1) - float(t.term_credits)) > 0.01:
   343	            errors.append(ValidationError(code="term_credits_mismatch", detail=f"{t.term} 학점합 불일치"))
   344	        prior_planned |= set(cur_term_ids)
   345	
   346	    for mid in ctx["audit_result"]["missing_required_course_ids"]:
   347	        if mid not in planned:
   348	            errors.append(ValidationError(code="required_not_planned", detail="필수지정 과목 미포함", course_id=mid))
   349	    for g in ctx["audit_result"]["gaps"]:
   350	        if g["area"] in MAJOR_AREAS and planned_by_area.get(g["area"], 0.0) < g["gap"]:
   351	            errors.append(ValidationError(code="gap_not_closed",
   352	                          detail=f"{g['area']} 계획 {planned_by_area.get(g['area'],0)}<부족 {g['gap']}"))
   353	    return ValidationReport(ok=not errors, errors=errors)
   354	
   355	
   356	# ============ 결정론 통합 플래너 (codex 설계: 후보 정규화 → greedy 배치 → 검증) ============
   357	def _ordered_terms(context: StudentContext, reg_cap: float) -> list[list]:
   358	    """허용 학기를 시간순 [[label, cap]]로. 첫 정규학기 +직전3.75 보너스, 계절=6."""
   359	    if not context.current_term:
   360	        return []
   361	    try:
   362	        y, s = context.current_term.split("-"); y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
   363	    except Exception:
   364	        return []
   365	    label = {1: "1", 2: "S", 3: "2", 4: "W"}
   366	    out, reg, steps, first = [], 0, 0, True
   367	    while reg < context.remaining_semesters and steps < 40:
   368	        steps += 1; so += 1
   369	        if so > 4:
   370	            so = 1; y += 1
   371	        lab = f"{y}-{label[so]}"
   372	        if so in (1, 3):
   373	            cap = reg_cap + (PREV_GPA_BONUS if (first and context.prev_term_gpa_ge_375) else 0.0)
   374	            out.append([lab, cap]); reg += 1; first = False
   375	        elif context.seasonal_semester_allowed:
   376	            out.append([lab, SEASONAL_TERM_CAP])
   377	    return out
   378	
   379	
   380	def _required_meta(program_id: str, year: int | None) -> dict:
   381	    """학번 요람 필수 과목의 학점·개설학기 메타 {정규화이름: {credits, terms}}."""
   382	    import json
   383	    p = V2_DIR / "required_names_by_year.json"
   384	    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
   385	    if not by_year:
   386	        return {}
   387	    avail = sorted(int(y) for y in by_year)
   388	    pick = year if (year and str(year) in by_year) else (
   389	        [y for y in avail if not year or y <= year][-1:] or [avail[-1]])[0]
   390	    meta = {}
   391	    for it in by_year.get(str(pick), []):
   392	        if isinstance(it, dict):
   393	            meta[normalize_name(it["name"])] = {"credits": float(it.get("credits", 3.0)),
   394	                                                "terms": list(it.get("terms") or [])}
   395	    return meta
   396	
   397	
   398	def build_unified_candidates(audit: AuditResult, profile: RequirementProfile,
   399	                             verified: VerifiedTranscript) -> tuple[list[dict], list[dict]]:
   400	    """남은 졸업 의무를 단일 후보 풀로 정규화(전공·필수·융합·교양). 반환 (선택후보, 요건요약)."""
   401	    cat = load_catalog(profile.program_id)
   402	    confirmed_norm = {normalize_name(c.name_ko) for c in verified.confirmed_courses}
   403	    confirmed_pref = {c.course_id[:5] for c in verified.confirmed_courses if c.course_id}
   404	    reqs: list[dict] = []
   405	
   406	    # 1) 미이수 필수(이름) — 전부 이수 필요. 요람 메타로 학점·개설학기 반영
   407	    if audit.missing_required_names:
   408	        rmeta = _required_meta(profile.program_id, profile.admission_year)
   409	        items = []
   410	        for n in audit.missing_required_names:
   411	            m = rmeta.get(normalize_name(n), {})
   412	            terms = m.get("terms") or []
   413	            items.append({"name_ko": n, "credits": m.get("credits", 3.0), "satisfies": "필수지정",
   414	                          "offered_terms": terms or ["1", "2"],
   415	                          "confidence": "catalog_verified" if terms else "name_only",
   416	                          "manual": not terms})
   417	        reqs.append({"label": "필수지정 미이수", "area": "전공", "priority": 1, "need": None, "items": items})
   418	    # 2) 연계융합 부족 — 부족 그룹 우선 미이수 융합과목
   419	    for cc in audit.convergence_checks:
   420	        if cc.get("gap", 0) > 0:
   421	            short = {g["group"] for g in cc.get("group_checks", []) if g["gap"] > 0}
   422	            untaken = sorted([c for c in cc.get("courses", []) if not c["taken"]],
   423	                             key=lambda c: (c.get("group") not in short, -c.get("credits", 0)))
   424	            reqs.append({"label": f"{cc['name']} 부족", "area": "융합전공", "priority": 2, "need": cc["gap"],
   425	                         "pool": [{"name_ko": c["name_ko"], "course_id": c.get("course_id", ""),
   426	                                   "credits": c["credits"], "assignment": "융합전공",
   427	                                   "satisfies": f"{cc['name']} {c.get('group', '')}".strip(),
   428	                                   "offered_terms": c.get("offered_terms") or ["1", "2"],
   429	                                   # 융합 카탈로그는 현황 기반 → 개설학기 known(있으면 hard-check)
   430	                                   "confidence": "catalog_verified" if c.get("offered_terms") else "name_only",
   431	                                   "manual": not c.get("offered_terms")} for c in untaken]})
   432	    # 3) 전공 부족 — 제1전공 카탈로그 미이수
   433	    major_gap = next((g.gap for g in audit.area_gaps if g.area == "전공"), 0.0)
   434	    if major_gap > 0:
   435	        pool = [{"name_ko": c.name_ko, "course_id": c.course_id, "credits": c.credits, "satisfies": "전공 부족",
   436	                 "offered_terms": c.offered_terms, "prerequisites": c.prerequisites, "confidence": "catalog_verified"}
   437	                for c in cat["courses"]
   438	                if not ((c.course_id and c.course_id[:5] in confirmed_pref) or normalize_name(c.name_ko) in confirmed_norm)]
   439	        reqs.append({"label": "전공 부족", "area": "전공", "priority": 3, "need": major_gap, "pool": pool})
   440	    # 4) 기초교양 — 필수 미이수 과목명이 있으면 그것을, 없으면 영역 부족분을 슬롯으로
   441	    missing_basic = [g for g in (audit.gen_basic_courses or []) if not g["taken"]]
   442	    basic_gap = next((g.gap for g in audit.area_gaps if g.area == "기초교양"), 0.0)
   443	    if missing_basic:
   444	        reqs.append({"label": "기초교양 필수", "area": "기초교양", "priority": 4, "need": None,
   445	                     "items": [{"name_ko": g["name_ko"], "credits": 3.0, "satisfies": "기초교양 필수",
   446	                                "confidence": "name_only", "manual": True} for g in missing_basic]})
   447	    elif basic_gap > 0:
   448	        reqs.append({"label": "기초교양", "area": "기초교양", "priority": 4, "need": basic_gap,
   449	                     "pool": [{"name_ko": "기초교양 선택", "credits": basic_gap, "satisfies": "기초교양",
   450	                               "confidence": "generic_slot", "manual": True}]})
   451	    # 5) 핵심교양 영역별 부족 → 영역 슬롯
   452	    for g in audit.core_area_gaps:
   453	        if g.gap > 0:
   454	            reqs.append({"label": f"핵심교양 {g.area}", "area": "핵심교양", "priority": 4, "need": g.gap,
   455	                         "pool": [{"name_ko": f"핵심교양 {g.area} 선택", "credits": g.gap,
   456	                                   "satisfies": f"핵심교양-{g.area}", "confidence": "generic_slot", "manual": True}]})
   457	    # 6) 자유교양 부족 → 슬롯
   458	    free_gap = next((g.gap for g in audit.area_gaps if g.area == "자유교양"), 0.0)
   459	    if free_gap > 0:
   460	        reqs.append({"label": "자유교양", "area": "자유교양", "priority": 4, "need": free_gap,
   461	                     "pool": [{"name_ko": "자유교양 선택", "credits": free_gap, "satisfies": "자유교양",
   462	                               "confidence": "generic_slot", "manual": True}]})
   463	
   464	    # 요건 → 후보 선택(quota 충족까지). 이름 중복 제거(필수지정이 전공부족 후보와 겹침 방지)
   465	    selected: list[dict] = []
   466	    seen: set[str] = set()
   467	    for r in reqs:
   468	        if r.get("items") is not None:
   469	            for it in r["items"]:
   470	                key = normalize_name(it["name_ko"])
   471	                if key in seen:
   472	                    continue
   473	                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]})
   474	        else:
   475	            acc = 0.0
   476	            for it in r["pool"]:
   477	                if acc >= r["need"]:
   478	                    break
   479	                key = normalize_name(it["name_ko"])
   480	                if key in seen:
   481	                    continue
   482	                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]}); acc += it["credits"]
   483	    return selected, reqs
   484	
   485	
   486	def plan_greedy(selected: list[dict], terms: list[list]) -> tuple[list[RoadmapTerm], list[str], list[dict]]:
   487	    """선택 후보를 학기에 greedy 배치(우선순위·개설학기[아는 경우]·학점상한). 반환 (terms, assumptions, unplaced)."""
   488	    items = sorted(selected, key=lambda c: (c["priority"], -c.get("credits", 0)))
   489	    used = {lab: 0.0 for lab, _ in terms}
   490	    bucket: dict[str, list] = {lab: [] for lab, _ in terms}
   491	    unplaced = []
   492	    for it in items:
   493	        off = it.get("offered_terms")
   494	        known = it.get("confidence") == "catalog_verified"
   495	        placed = False
   496	        # 1차: 개설학기 아는 과목은 해당 학기, 불확실 과목은 정규학기에만. 2차: 계절학기까지 허용
   497	        for allow_seasonal in (False, True):
   498	            for lab, cap in terms:
   499	                sem = _term_sem(lab)
   500	                if known and off and sem not in off:
   501	                    continue
   502	                if not known and sem in ("S", "W") and not allow_seasonal:
   503	                    continue            # 개설학기 불확실 과목은 정규학기 우선
   504	                if used[lab] + it["credits"] <= cap + 0.01:
   505	                    bucket[lab].append(it); used[lab] += it["credits"]; placed = True; break
   506	            if placed:
   507	                break
   508	        if not placed:
   509	            unplaced.append(it)
   510	    out = []
   511	    for lab, cap in terms:
   512	        if not bucket[lab]:
   513	            continue
   514	        courses = [RoadmapCourse(course_id=it.get("course_id", "") or "", name_ko=it["name_ko"],
   515	                                 credits=it["credits"], satisfies=it.get("satisfies", ""),
   516	                                 assignment=it.get("assignment", ""),
   517	                                 offered_terms=(it.get("offered_terms") or []) if it.get("confidence") == "catalog_verified" else [],
   518	                                 confidence=it.get("confidence", "catalog_verified"),
   519	                                 manual_check=it.get("manual", False)) for it in bucket[lab]]
   520	        out.append(RoadmapTerm(term=lab, courses=courses, term_credits=round(used[lab], 1),
   521	                               term_risk="medium" if used[lab] > cap - 3 else "low"))
   522	    assumptions = []
   523	    if any(it.get("manual") for it in selected):
   524	        assumptions.append("이름기준·교양 슬롯 과목은 개설학기·학점을 수강신청 전 확인하세요.")
   525	    return out, assumptions, unplaced
   526	
   527	
   528	def run_planner(
   529	    audit: AuditResult, profile: RequirementProfile, context: StudentContext,
   530	    verified: VerifiedTranscript, client=None,
   531	) -> tuple[RoadmapPlan, ValidationReport, dict]:
   532	    """결정론 통합 플래너: 남은 의무 → 단일 후보 풀 → greedy 학기배치 → 검증.
   533	    (LLM 배치 미사용 — codex 권장. plan_roadmap 등 LLM 함수는 보존만.)"""
   534	    overflow = project_overflow(audit, profile, context)
   535	    selected, reqs = build_unified_candidates(audit, profile, verified)
   536	    summary = [{"label": r["label"], "area": r["area"],
   537	                "need": (r.get("need") if r.get("need") is not None else sum(i["credits"] for i in r.get("items", [])))}
   538	               for r in reqs]
   539	    ctx = {"sources": [], "requirements_summary": summary}
   540	
   541	    if not selected:
   542	        return (RoadmapPlan(status="generated", feasible=True, terms=[],
   543	                            why_this_plan="졸업요건을 모두 충족했습니다. 추가 수강 계획이 필요 없습니다."),
   544	                ValidationReport(ok=True), ctx)
   545	
   546	    reg_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
   547	    terms = _ordered_terms(context, reg_cap)
   548	    if not terms:
   549	        # 현재 학기 미상 → 학기 배치 불가. 무엇을 들어야 하는지만 안내.
   550	        names = ", ".join(f"{it['name_ko']}({it['credits']:.0f})" for it in selected[:12])
   551	        return (RoadmapPlan(status="generated", feasible=None, terms=[],
   552	                            why_this_plan=f"현재 학기 미입력 — 학기 배치 생략. 추가 이수 권장: {names}",
   553	                            assumptions=["현재 학기를 입력하면 학기별 배치를 제공합니다."], overflow=overflow),
   554	                ValidationReport(ok=True), ctx)
   555	
   556	    placed, assumptions, unplaced = plan_greedy(selected, terms)
   557	    errors = []
   558	    for t in placed:
   559	        cap = next((c for lab, c in terms if lab == t.term), reg_cap)
   560	        if t.term_credits > cap + 0.01:
   561	            errors.append(ValidationError(code="over_credit_cap", detail=f"{t.term} {t.term_credits} > {cap}"))
   562	    report = ValidationReport(ok=not errors, errors=errors)
   563	
   564	    parts = [f"{s['label']}" for s in summary]
   565	    why = "남은 요건(" + ", ".join(parts) + ")을 잔여 학기에 배치했습니다." if parts else ""
   566	    plan = RoadmapPlan(status="generated", feasible=not unplaced, terms=placed,
   567	                       why_this_plan=why, assumptions=assumptions, overflow=overflow)
   568	    if unplaced:
   569	        un = ", ".join(f"{it['name_ko']}({it['credits']:.0f})" for it in unplaced)
   570	        hint = "잔여 학기를 늘리거나 계절학기를 활용하세요."
   571	        if overflow:
   572	            hint = overflow.note + " " + hint
   573	        plan.feasible = False
   574	        plan.blocked_reason = f"잔여 학기에 다 배치하지 못한 과목: {un}"
   575	        plan.relaxation_hint = hint
   576	    return plan, report, ctx

exec
/bin/bash -lc "nl -ba graduation_center/v2/catalog.py | sed -n '1,150p'" in /home/carol/kmu_genai
exec
/bin/bash -lc "nl -ba graduation_center/v2/risk.py | sed -n '1,115p'" in /home/carol/kmu_genai
 succeeded in 0ms:
     1	"""졸업 리스크 등급 (결정론 · 재현 가능).
     2	
     3	grade = 충족 못 한 최악 트리거(D>C>B>A). score = clamp(100 - Σseverity).
     4	planner 미가동(키 없음)은 강등 사유가 아니다. roadmap 실현불가(검증 실패)만 강등에 반영.
     5	"""
     6	from __future__ import annotations
     7	
     8	from graduation_center.v2.models_v2 import (
     9	    AuditResult, RiskAssessment, RiskReason, StudentContext,
    10	)
    11	from graduation_center.v2.catalog import PREV_GPA_BONUS, SEASONAL_TERM_CAP
    12	
    13	GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
    14	LABELS = {"A": "안전", "B": "주의", "C": "위험", "D": "졸업불가 가능성"}
    15	
    16	
    17	def _worse(a: str, b: str) -> str:
    18	    return a if GRADE_RANK[a] >= GRADE_RANK[b] else b
    19	
    20	
    21	def compute_risk(
    22	    audit: AuditResult, context: StudentContext, roadmap_feasible: bool | None = None,
    23	) -> RiskAssessment:
    24	    reasons: list[RiskReason] = []
    25	    grade = "A"
    26	    gap = audit.total_gap
    27	    # 미이수 필수는 이름 기준(학번 요람) 경로·코드 경로 모두 names를 채우므로 names로 카운트
    28	    missing = len(audit.missing_required_names)
    29	    max_area_gap = max((g.gap for g in audit.area_gaps), default=0.0)
    30	    core_missing = [g for g in audit.core_area_gaps if g.gap > 0]
    31	
    32	    if gap > 15:
    33	        grade = _worse(grade, "D")
    34	        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족(15 초과)", severity=30))
    35	    elif gap >= 7:
    36	        grade = _worse(grade, "C")
    37	        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=20))
    38	    elif gap > 0:
    39	        grade = _worse(grade, "B")
    40	        reasons.append(RiskReason(factor="총학점", detail=f"{gap:.0f}학점 부족", severity=10))
    41	
    42	    if missing >= 2:
    43	        grade = _worse(grade, "C")
    44	        reasons.append(RiskReason(factor="전공필수", detail=f"필수지정 {missing}과목 미이수", severity=18))
    45	    elif missing == 1:
    46	        grade = _worse(grade, "B")
    47	        reasons.append(RiskReason(factor="전공필수", detail="필수지정 1과목 미이수", severity=10))
    48	
    49	    # 영역(이수구분) 갭 — 총학점과 무관하게 등급에 반영(worst trigger)
    50	    if max_area_gap > 15:
    51	        grade = _worse(grade, "D")
    52	        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족(15 초과)", severity=20))
    53	    elif max_area_gap >= 7:
    54	        grade = _worse(grade, "C")
    55	        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=14))
    56	    elif max_area_gap > 0:
    57	        grade = _worse(grade, "B")
    58	        reasons.append(RiskReason(factor="영역", detail=f"이수구분 영역 {max_area_gap:.0f}학점 부족", severity=8))
    59	
    60	    # 잔여학기 수용량(결정론): 학사규정 제32조 학기당 이수학점 상한 기반
    61	    # (계절학기 허용 시 6학점, 직전 3.75↑면 +3 한 번)
    62	    term_cap = float(context.max_credits_per_term or 18)
    63	    capacity = context.remaining_semesters * term_cap
    64	    if context.prev_term_gpa_ge_375:
    65	        capacity += PREV_GPA_BONUS
    66	    if context.seasonal_semester_allowed:
    67	        capacity += SEASONAL_TERM_CAP
    68	    if gap > 0 and capacity > 0 and gap > capacity:
    69	        grade = _worse(grade, "D")
    70	        reasons.append(RiskReason(factor="잔여학기",
    71	                      detail=f"부족 {gap:.0f}학점 > 잔여 {context.remaining_semesters}학기 수용량(~{capacity:.0f})", severity=20))
    72	
    73	    if core_missing:
    74	        grade = _worse(grade, "B")
    75	        areas = ", ".join(g.area for g in core_missing)
    76	        reasons.append(RiskReason(factor="핵심교양", detail=f"영역 미충족: {areas}", severity=8))
    77	
    78	    for cc in audit.convergence_checks:
    79	        group_short = [gc for gc in cc.get("group_checks", []) if gc["gap"] > 0]
    80	        eff_gap = max(cc.get("gap", 0), *(gc["gap"] for gc in group_short)) if group_short else cc.get("gap", 0)
    81	        if eff_gap > 0:
    82	            grade = _worse(grade, "C" if eff_gap >= 9 else "B")
    83	            detail = f"{cc['name']} 총 {cc['gap']:.0f}학점 부족" if cc["gap"] > 0 else f"{cc['name']}"
    84	            if group_short:
    85	                detail += " · 그룹 부족: " + ", ".join(f"{gc['group']} {gc['gap']:.0f}" for gc in group_short)
    86	            reasons.append(RiskReason(factor="융합전공", detail=detail, severity=14 if eff_gap >= 9 else 8))
    87	
    88	    if context.gpa_min_met == "no":
    89	        grade = _worse(grade, "C")
    90	        reasons.append(RiskReason(factor="평점", detail="졸업 평점 기준 미달", severity=20))
    91	    elif context.gpa_min_met == "unknown":
    92	        reasons.append(RiskReason(factor="평점", detail="평점 기준 충족 여부 확인 필요", severity=0))
    93	
    94	    if roadmap_feasible is False:
    95	        grade = _worse(grade, "C")
    96	        reasons.append(RiskReason(factor="로드맵", detail="잔여 학기 내 실현 가능한 계획 없음", severity=15))
    97	
    98	    if grade == "A" and not reasons:
    99	        reasons.append(RiskReason(factor="종합", detail="확인된 부족·위험 항목 없음", severity=0))
   100	
   101	    score = max(0, min(100, 100 - sum(r.severity for r in reasons)))
   102	    return RiskAssessment(grade=grade, label=LABELS[grade], score=score, reasons=reasons)

 succeeded in 0ms:
     1	"""v2 카탈로그·요건 로딩 + 과목 매칭 (결정론).
     2	
     3	- 카탈로그/요건/교양은 data/graduation/v2/ 의 빌드 산출물에서 로드(캐시).
     4	- match_course: 교과목코드 7자리 정확매칭 우선 → 이름 정규화 → 미스 시 unresolved.
     5	- 카탈로그 밖(교양·타과)은 자동분류 금지: 이수구분 원문으로 집계영역만 부여(aggregate_only).
     6	"""
     7	from __future__ import annotations
     8	
     9	import json
    10	from functools import lru_cache
    11	from pathlib import Path
    12	
    13	from graduation_center.v2.models_v2 import (
    14	    Area, CatalogCourse, CourseMatch, RawLine, RequirementProfile, StudentContext,
    15	)
    16	from graduation_center.v2.text_norm import normalize_code, normalize_name
    17	
    18	V2_DIR = Path("data/graduation/v2")
    19	GRAD_REQ = Path("data/graduation/graduation_requirements.json")
    20	
    21	# 이수구분 원문 → 집계 영역
    22	_ISU_TO_AREA: dict[str, Area] = {
    23	    "전공필수": "전공", "전공선택": "전공", "전공": "전공",
    24	    "기초교양": "기초교양", "핵심교양": "핵심교양", "자유교양": "자유교양",
    25	    "일반선택": "일반선택", "교직": "일반선택", "다전공": "일반선택",
    26	}
    27	
    28	
    29	def area_from_isugubun(isu: str | None) -> Area:
    30	    s = str(isu or "").strip()
    31	    for key, area in _ISU_TO_AREA.items():
    32	        if key in s:
    33	            return area
    34	    return "일반선택"
    35	
    36	
    37	@lru_cache(maxsize=1)
    38	def load_programs() -> dict:
    39	    p = V2_DIR / "programs.json"
    40	    return json.loads(p.read_text(encoding="utf-8"))["programs"] if p.exists() else {}
    41	
    42	
    43	# 학사규정 제32조(학기당 이수학점): 졸업 최저이수학점 → 정규학기 상한.
    44	SEASONAL_TERM_CAP = 6.0          # 제32조 ④ 계절학기 6학점
    45	PREV_GPA_BONUS = 3.0             # 제32조 ①-4 직전학기 평점평균 3.75 이상 → +3학점
    46	
    47	
    48	def regular_term_cap(total_credits_min: float) -> float:
    49	    """졸업 최저이수학점 → 학기당 정규 이수학점 상한(제32조 ①)."""
    50	    t = float(total_credits_min or 0)
    51	    if t >= 136:
    52	        return 19.0
    53	    if t >= 130:
    54	        return 18.0
    55	    if t >= 120:
    56	        return 17.0
    57	    return 18.0                   # 미상 시 보수적 기본값
    58	
    59	
    60	def program_total_min(program_id: str) -> float | None:
    61	    """프로그램의 졸업 최저이수학점(요건 데이터). 연계·융합전공(키 없음)은 None."""
    62	    progs = load_programs()
    63	    key = progs.get(program_id, {}).get("requirements_key")
    64	    if not key:
    65	        return None
    66	    try:
    67	        req = json.loads(GRAD_REQ.read_text(encoding="utf-8"))["departments"][key]
    68	        return float(req.get("졸업_최저합계", 0)) or None
    69	    except Exception:
    70	        return None
    71	
    72	
    73	@lru_cache(maxsize=1)
    74	def load_gen_ed() -> dict:
    75	    p = V2_DIR / "gen_ed_catalog.json"
    76	    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    77	
    78	
    79	@lru_cache(maxsize=8)
    80	def load_catalog(program_id: str) -> dict:
    81	    """프로그램 카탈로그 로드 → {by_code, by_norm, courses}."""
    82	    progs = load_programs()
    83	    if program_id not in progs:
    84	        raise KeyError(f"unknown program_id: {program_id}")
    85	    data = json.loads((V2_DIR / progs[program_id]["catalog_file"]).read_text(encoding="utf-8"))
    86	    by_code: dict[str, CatalogCourse] = {}
    87	    by_norm: dict[str, list[str]] = {}
    88	    for c in data["courses"]:
    89	        cc = CatalogCourse.model_validate(c)
    90	        by_code[cc.course_id] = cc
    91	        by_norm.setdefault(cc.name_norm, []).append(cc.course_id)
    92	        for al in cc.aliases:
    93	            by_norm.setdefault(normalize_name(al), []).append(cc.course_id)
    94	    return {"by_code": by_code, "by_norm": by_norm, "courses": list(by_code.values()),
    95	            "requirements_key": progs[program_id]["requirements_key"],
    96	            "department_name_ko": progs[program_id]["name_ko"],
    97	            "track_type": progs[program_id].get("track_type", "primary"),
    98	            "convergence_required": progs[program_id].get("convergence_required"),
    99	            "group_rules": data.get("group_rules")}
   100	
   101	
   102	def _requirements_by_year(program_id: str, year: int | None) -> dict | None:
   103	    """학번(입학연도) 요람 별표5 영역 최저학점. 없으면 None."""
   104	    if not year:
   105	        return None
   106	    p = V2_DIR / "requirements_by_year.json"
   107	    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
   108	    if not by_year:
   109	        return None
   110	    # 정확 연도만 적용(기본값 graduation_requirements.json이 최신 요람 기준이므로 임의 근사 금지)
   111	    return by_year.get(str(year))
   112	
   113	
   114	def assemble_requirement_profile(context: StudentContext) -> RequirementProfile:
   115	    """graduation_requirements.json(카테고리 총계) + 카탈로그 필수과목으로 요건 프로파일 구성.
   116	
   117	    학번(입학연도) 요람 별표5(requirements_by_year.json)가 있으면 영역 최저학점은 그것을 우선.
   118	    """
   119	    cat = load_catalog(context.program_id)
   120	    req = json.loads(GRAD_REQ.read_text(encoding="utf-8"))["departments"][cat["requirements_key"]]
   121	    gyo = req.get("교양", {})
   122	    yr = _requirements_by_year(context.program_id, context.admission_year)
   123	    area_min = {
   124	        "전공": float((yr or {}).get("전공", req.get("전공_최저", 0))),
   125	        "기초교양": float((yr or {}).get("기초교양", gyo.get("기초교양", 0))),
   126	        "핵심교양": float((yr or {}).get("핵심교양", gyo.get("핵심교양", 0))),
   127	        "자유교양": float((yr or {}).get("자유교양", gyo.get("자유교양", 0))),
   128	        "일반선택": float((yr or {}).get("일반선택", req.get("일반선택", 0))),
   129	    }
   130	    total_min = float((yr or {}).get("졸업_최저합계", req.get("졸업_최저합계", 0)))
   131	    required_ids = [c.course_id for c in cat["courses"] if c.is_required]
   132	    gen = load_gen_ed().get("core_liberal", {})
   133	    applied = f"{context.admission_year} 요람 (학번 기준)" if (yr and context.admission_year) else "2025 요람"
   134	    return RequirementProfile(
   135	        program_id=context.program_id,
   136	        department_name_ko=cat["department_name_ko"],
   137	        admission_year=context.admission_year,
   138	        total_credits_min=total_min,
   139	        area_min=area_min,
   140	        required_course_ids=required_ids,
   141	        core_area_min=float(gen.get("area_min_credits", 3)),
   142	        core_area_min_overrides={k: float(v) for k, v in (req.get("핵심교양_영역최저") or {}).items()},
   143	        core_total_min=float(gen.get("total_min_credits", 15)),
   144	        applied_yoram=applied,
   145	    )
   146	
   147	
   148	def match_course(raw: RawLine, program_id: str) -> CourseMatch:
   149	    cat = load_catalog(program_id)
   150	    gen = load_gen_ed().get("core_liberal", {})

The existing tests cannot run in this environment because `pydantic` is not installed, so I’m treating that as a verification blocker rather than evidence. I have enough code context now; I’m just collecting precise line references for the final ranked list.
exec
/bin/bash -lc "nl -ba frontend/src/components/GraduationV2.jsx | sed -n '360,430p'" in /home/carol/kmu_genai
exec
/bin/bash -lc "nl -ba frontend/src/components/GraduationV2.jsx | sed -n '80,190p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   360	
   361	          {/* ① 학적 정보 */}
   362	          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "2px 0 8px" }}>① 학적 정보</div>
   363	          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
   364	            <Field label="입학연도 (학번 앞 4자리)" hint={admissionYear() ? `→ ${admissionYear()} 요람 적용` : "입학연도 기준 요람 적용"}>
   365	              <input style={inputStyle} placeholder="예: 2025" value={ctx.student_id} onChange={(e) => setCtx({ ...ctx, student_id: e.target.value })} /></Field>
   366	            <Field label="주전공">
   367	              <select style={inputStyle} value={ctx.program_id} onChange={(e) => onProgramChange(e.target.value)}>
   368	                {primaryPrograms.map(([id, p]) => <option key={id} value={id}>{p.name_ko}</option>)}
   369	                {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
   370	              </select>
   371	            </Field>
   372	          </div>
   373	
   374	          {/* 다전공·부전공 (연계융합 포함, 검색) */}
   375	          <div style={{ marginTop: 12 }}>
   376	            <span style={labelStyle}>다전공 · 부전공 (연계·융합전공 포함, 검색)</span>
   377	            <div style={{ position: "relative", marginTop: 4 }}>
   378	              <input style={inputStyle} placeholder="학과/전공 검색 후 선택 (데모 분석: 데이터사이언스융합·모빌리티데이터분석)"
   379	                value={majorQuery} onChange={(e) => setMajorQuery(e.target.value)} />
   380	              {majorQuery.trim() && (
   381	                <div style={{ position: "absolute", zIndex: 5, left: 0, right: 0, top: "100%", maxHeight: 190, overflow: "auto",
   382	                  background: "#fff", border: `1px solid ${C.border}`, borderRadius: 8, marginTop: 2, boxShadow: "0 4px 12px rgba(16,24,40,.1)" }}>
   383	                  {majorOptions().filter((o) => o.label.includes(majorQuery.trim())).slice(0, 30).map((o) => (
   384	                    <div key={o.key} onClick={() => pickMajor(o)}
   385	                      style={{ padding: "6px 10px", fontSize: 12.5, cursor: "pointer", borderBottom: "1px solid #f1f4f8",
   386	                        color: o.supported ? C.text : "#9aa6b8" }}>
   387	                      {o.label}{o.supported ? <span style={{ color: C.accent, fontSize: 10.5, marginLeft: 6 }}>분석지원</span>
   388	                        : <span style={{ fontSize: 10.5, marginLeft: 6 }}>(데모 미지원)</span>}
   389	                    </div>
   390	                  ))}
   391	                </div>
   392	              )}
   393	            </div>
   394	            {/* 선택된 추가전공 칩 */}
   395	            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
   396	              {convergencePrograms.filter(([id]) => ctx.convergence_program_ids.includes(id)).map(([id, p]) => (
   397	                <div key={id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
   398	                  border: `1px solid ${C.accent}`, background: "#eef5ff", fontSize: 12.5 }}>
   399	                  <span style={{ fontWeight: 600 }}>{p.name_ko}</span>
   400	                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
   401	                    style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px" }}>
   402	                    <option value="다전공">다전공 · 36/중복12</option>
   403	                    <option value="부전공">부전공 · 18/중복6</option>
   404	                  </select>
   405	                  <span onClick={() => toggleConv(id)} style={{ cursor: "pointer", color: C.muted }}>✕</span>
   406	                </div>
   407	              ))}
   408	              {otherMajors.map((nm, i) => (
   409	                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
   410	                  border: `1px solid ${C.border}`, background: "#f3f4f6", fontSize: 12.5, color: "#9aa6b8" }}>
   411	                  {nm} (데모 미지원)
   412	                  <span onClick={() => setOtherMajors((o) => o.filter((x) => x !== nm))} style={{ cursor: "pointer" }}>✕</span>
   413	                </div>
   414	              ))}
   415	            </div>
   416	            {ctx.convergence_program_ids.length === 0 && otherMajors.length === 0 && (
   417	              <div style={{ fontSize: 11.5, color: "#b45309", marginTop: 8, background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: "7px 10px" }}>
   418	                ※ 다전공·부전공을 모두 이수하지 않는 경우 <strong>심화전공(심화과정)</strong>을 이수해야 합니다 (학사규정 제33조).
   419	              </div>
   420	            )}
   421	          </div>
   422	
   423	          {/* ② 학기 */}
   424	          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "16px 0 8px" }}>② 학기</div>
   425	          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
   426	            <Field label="현재 학기" hint="형식: 연도-학기 (1=1학기, 2=2학기). 예: 2026-1">
   427	              <input style={inputStyle} placeholder="예: 2026-1" value={ctx.current_term} onChange={(e) => setCtx({ ...ctx, current_term: e.target.value })} /></Field>
   428	            <Field label="남은 학기" hint="현재 학기 다음부터 들을 정규학기 수 (현재 학기는 수강내역에 포함 → 제외)">
   429	              <input style={inputStyle} type="number" value={ctx.remaining_semesters} onChange={(e) => setCtx({ ...ctx, remaining_semesters: e.target.value })} /></Field>
   430	          </div>

 succeeded in 0ms:
    80	
    81	function ConvergenceBlock({ cc, C, first }) {
    82	  const ov = cc.overlap_courses || [];
    83	  const cap = cc.double_cap || 0;
    84	  // 기본 선택: 전공필수 우선 중복인정(한도까지) → 제1전공 부족분 채움(제1전공) → 나머지 융합
    85	  const defaultSel = React.useMemo(() => {
    86	    const order = [...ov.keys()].sort((i, j) =>
    87	      (ov[j].primary_required - ov[i].primary_required) || (ov[j].credits - ov[i].credits));
    88	    const s = {}; let dup = 0;
    89	    for (const i of order) { if (dup + ov[i].credits <= cap) { s[i] = "dup"; dup += ov[i].credits; } }
    90	    let pneed = Math.max(0, (cc.primary_required || 0) - (cc.primary_base || 0) - dup);
    91	    for (const i of order) {
    92	      if (s[i]) continue;
    93	      if (pneed > 0) { s[i] = "primary"; pneed -= ov[i].credits; } else s[i] = "fusion";
    94	    }
    95	    return s;
    96	  }, [cc]);
    97	  const [sel, setSel] = React.useState(defaultSel);
    98	  React.useEffect(() => { setSel(defaultSel); }, [defaultSel]);
    99	
   100	  const sum = (pred) => ov.reduce((s, f, i) => s + (pred(sel[i]) ? f.credits : 0), 0);
   101	  const dupCr = sum((x) => x === "dup");
   102	  const primaryCr = (cc.primary_base || 0) + sum((x) => x === "dup" || x === "primary");
   103	  const fusionCr = (cc.fusion_base || 0) + sum((x) => x === "dup" || x === "fusion");
   104	  const overCap = dupCr > cap;
   105	  const fits = !overCap && primaryCr >= (cc.primary_required || 0) && fusionCr >= cc.required;
   106	
   107	  // 미이수 시나리오: 융합 부족 시 안 들은 융합 과목 추천(부족 그룹 우선)
   108	  const untaken = (cc.courses || []).filter((c) => !c.taken);
   109	  const fusionGap = Math.max(0, cc.required - fusionCr);
   110	  const shortGroups = new Set((cc.group_checks || []).filter((g) => g.gap > 0).map((g) => g.group));
   111	  const suggest = [];
   112	  if (fusionGap > 0) {
   113	    const pool = [...untaken].sort((a, b) => (shortGroups.has(b.group) - shortGroups.has(a.group)));
   114	    let acc = 0;
   115	    for (const c of pool) { if (acc >= fusionGap) break; suggest.push(c); acc += c.credits; }
   116	  }
   117	
   118	  const groups = [...new Set((cc.courses || []).map((c) => c.group || "기타"))].sort();
   119	  const taken = (cc.courses || []).filter((c) => c.taken).length;
   120	  const selByName = {}; ov.forEach((f, i) => { selByName[f.name_ko] = sel[i]; });
   121	
   122	  return (
   123	    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 14, background: C.soft, marginTop: first ? 0 : 14 }}>
   124	      <div style={{ fontWeight: 700, fontSize: 14, color: C.navy, marginBottom: 8 }}>{cc.name} <span style={{ fontSize: 11.5, color: C.muted, fontWeight: 400 }}>{cc.track}·{cc.conv_type} · 이수 {taken}/{(cc.courses || []).length}과목 · 중복인정 한도 {cap}학점</span></div>
   125	
   126	      <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
   127	        <StatBox label="제1전공 전공 (배정 반영)" earned={primaryCr} required={cc.primary_required || 0} C={C} />
   128	        <StatBox label={`${cc.conv_type} 이수 (배정 반영)`} earned={fusionCr} required={cc.required} C={C} />
   129	      </div>
   130	      {overCap && <div style={{ fontSize: 11.5, color: "#dc2626", marginBottom: 6 }}>⚠️ 중복인정 {dupCr}학점 &gt; 한도 {cap}학점 — 일부를 제1전공/융합으로 바꾸세요.</div>}
   131	      <div style={{ fontSize: 11.5, color: fits ? "#047857" : "#b45309", marginBottom: 8 }}>
   132	        {fits
   133	          ? "✅ 현재 배정으로 제1전공·융합 둘 다 졸업요건 충족"
   134	          : (primaryCr < (cc.primary_required || 0)
   135	            ? `⚠️ 제1전공 ${((cc.primary_required || 0) - primaryCr).toFixed(0)}학점 부족 — 겹침과목을 제1전공으로 더 돌리거나 제1전공 과목 추가 이수`
   136	            : `⚠️ ${cc.conv_type} ${fusionGap.toFixed(0)}학점 부족 — 아래 미이수 과목 추가 이수 필요`)}
   137	      </div>
   138	
   139	      {/* 미이수 시나리오 — 무엇을 더 들어 어떤 이수구분으로 빼면 졸업 가능 */}
   140	      {suggest.length > 0 && (
   141	        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: 10, marginBottom: 8 }}>
   142	          <div style={{ fontSize: 11.5, fontWeight: 700, color: "#b45309", marginBottom: 4 }}>📋 졸업 가능 시나리오 (미이수 과목 추가 이수)</div>
   143	          <div style={{ fontSize: 11.5, color: "#7c4a12" }}>
   144	            다음 {cc.conv_type} 과목을 추가 이수하면 충족: {suggest.map((c) => `${c.name_ko}(${c.credits}${c.group ? "·" + c.group : ""})`).join(", ")}
   145	          </div>
   146	        </div>
   147	      )}
   148	
   149	      {cc.recommend_double_count?.length > 0 && (
   150	        <div style={{ fontSize: 11.5, color: C.accent, marginBottom: 8 }}>
   151	          💡 중복인정(양쪽 동시) 권장 — 제1전공·다전공 전공필수 우선: <strong>{cc.recommend_double_count.join(", ")}</strong>
   152	        </div>
   153	      )}
   154	
   155	      {/* 교육과정 전체 — 그룹별. 겹침(이수) 과목은 옆에서 3-way 이수구분 선택 */}
   156	      <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden", background: "#fff" }}>
   157	        {groups.map((g) => (
   158	          <div key={g}>
   159	            <div style={{ background: C.soft, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, color: C.navy, borderTop: `1px solid ${C.border}` }}>{g}</div>
   160	            {(cc.courses || []).filter((c) => (c.group || "기타") === g).map((c, ci) => {
   161	              const ovIdx = ov.findIndex((f) => f.name_ko === c.name_ko);
   162	              const selectable = c.taken && c.overlap && ovIdx >= 0;
   163	              return (
   164	                <div key={ci} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", fontSize: 12,
   165	                  borderTop: "1px solid #f1f4f8", opacity: c.taken ? 1 : 0.5, background: c.taken ? "#fafcff" : "#fff" }}>
   166	                  <span style={{ width: 16 }}>{c.taken ? "✅" : "⬜"}</span>
   167	                  <span style={{ flex: 1, fontWeight: c.taken ? 600 : 400 }}>
   168	                    {c.name_ko}
   169	                    {c.primary_required && <span style={{ marginLeft: 5, fontSize: 9.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 4, padding: "0 4px" }}>전공필수</span>}
   170	                  </span>
   171	                  <span style={{ width: 24, textAlign: "right", color: C.muted }}>{c.credits}</span>
   172	                  {selectable ? (
   173	                    <span style={{ display: "inline-flex", border: `1px solid ${C.border}`, borderRadius: 6, overflow: "hidden" }}>
   174	                      {SEL3.map(([key, lbl, col, bg, bd]) => {
   175	                        const on = sel[ovIdx] === key;
   176	                        // 중복인정은 한도(cap) 초과하면 선택 불가
   177	                        const wouldExceed = key === "dup" && !on && (dupCr + ov[ovIdx].credits > cap);
   178	                        return (
   179	                          <button key={key} disabled={wouldExceed}
   180	                            onClick={() => !wouldExceed && setSel((s) => ({ ...s, [ovIdx]: key }))}
   181	                            title={wouldExceed ? `중복인정 한도 ${cap}학점 초과` : ""}
   182	                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 6px",
   183	                              cursor: wouldExceed ? "not-allowed" : "pointer", border: "none",
   184	                              borderLeft: key !== "dup" ? `1px solid ${C.border}` : "none",
   185	                              background: on ? bg : "#fff", color: on ? col : (wouldExceed ? "#d1d5db" : "#9aa6b8") }}>{lbl}</button>
   186	                        );
   187	                      })}
   188	                    </span>
   189	                  ) : (
   190	                    <span style={{ width: 70, textAlign: "center", fontSize: 10.5, fontWeight: 600,

exec
/bin/bash -lc "nl -ba frontend/src/components/GraduationV2.jsx | sed -n '208,255p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   208	    student_id: "", program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
   209	    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
   210	    seasonal_semester_allowed: true, gpa_min_met: "unknown",
   211	    preferences: "", convergence_program_ids: [], convergence_tracks: {},
   212	  });
   213	  const [departments, setDepartments] = React.useState([]);   // 전체 학과(검색용)
   214	  const [otherMajors, setOtherMajors] = React.useState([]);   // 데모 미지원 다전공/부전공(표시만)
   215	  const [majorQuery, setMajorQuery] = React.useState("");
   216	  const [files, setFiles] = React.useState([]);
   217	  const [verify, setVerify] = React.useState(null);
   218	  const [table, setTable] = React.useState([]);
   219	  const [audit, setAudit] = React.useState(null);
   220	  const [busy, setBusy] = React.useState("");
   221	  const [error, setError] = React.useState("");
   222	  const [showSources, setShowSources] = React.useState(false);
   223	
   224	  React.useEffect(() => {
   225	    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
   226	      .then((d) => {
   227	        const progs = d.programs || {};
   228	        setPrograms(progs);
   229	        setDepartments(d.departments || []);
   230	        // 초기 주전공의 학사규정 상한을 기본값으로
   231	        setCtx((c) => {
   232	          const cap = progs[c.program_id]?.max_credits_per_term;
   233	          return cap ? { ...c, max_credits_per_term: cap } : c;
   234	        });
   235	      }).catch(() => {});
   236	  }, [apiBase]);
   237	
   238	  const admissionYear = () => {
   239	    const m = String(ctx.student_id || "").match(/(20\d{2})/);
   240	    return m ? Number(m[1]) : null;
   241	  };
   242	  const contextPayload = () => ({
   243	    ...ctx,
   244	    remaining_semesters: Number(ctx.remaining_semesters),
   245	    max_credits_per_term: Number(ctx.max_credits_per_term),
   246	    admission_year: admissionYear(),
   247	    masked_student_id: ctx.student_id ? ctx.student_id.slice(0, 4) + "XXXX" : null,
   248	    preferences: ctx.preferences ? ctx.preferences.split(",").map((s) => s.trim()).filter(Boolean) : [],
   249	  });
   250	
   251	  // 주전공 변경 시 학사규정 제32조 학기당 상한을 기본값으로 자동 채움
   252	  const onProgramChange = (id) => {
   253	    const cap = programs[id]?.max_credits_per_term;
   254	    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
   255	  };

exec
/bin/bash -lc "nl -ba frontend/src/components/GraduationV2.jsx | sed -n '620,710p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   620	                {audit.audit.convergence_checks.map((cc, i) => (
   621	                  <ConvergenceBlock key={i} cc={cc} C={C} first={i === 0} />
   622	                ))}
   623	              </div>
   624	            )}
   625	
   626	            {/* 로드맵 */}
   627	            <div style={card}>
   628	              <div style={sectionTitle}>🗺️ 추천 학기별 로드맵</div>
   629	              {audit.roadmap.status === "not_generated" && <p style={{ color: C.muted, fontSize: 13 }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
   630	              {audit.roadmap.status === "blocked" && <p style={{ color: C.danger, fontSize: 13 }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
   631	              {audit.roadmap.status === "generated" && audit.roadmap.terms.length === 0 && (
   632	                <div style={{ padding: "14px 16px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 10, color: "#047857", fontSize: 13.5, fontWeight: 600 }}>
   633	                  ✅ {audit.roadmap.why_this_plan}
   634	                </div>
   635	              )}
   636	              {/* 남은 요건 요약 */}
   637	              {(() => {
   638	                const rem = [];
   639	                const mg = audit.audit.area_gaps.find((g) => g.area === "전공");
   640	                if (audit.audit.missing_required_names?.length) rem.push(`필수지정 ${audit.audit.missing_required_names.length}과목`);
   641	                if (mg && mg.gap > 0) rem.push(`전공 ${mg.gap}학점`);
   642	                (audit.audit.convergence_checks || []).forEach((cc) => { if (cc.gap > 0) rem.push(`${cc.name} ${cc.gap}학점`); });
   643	                (audit.audit.core_area_gaps || []).filter((g) => g.gap > 0).forEach((g) => rem.push(`핵심교양 ${g.area} ${g.gap}학점`));
   644	                ["기초교양", "자유교양"].forEach((a) => { const g = audit.audit.area_gaps.find((x) => x.area === a); if (g && g.gap > 0) rem.push(`${a} ${g.gap}학점`); });
   645	                return rem.length > 0 && audit.roadmap.terms.length > 0 ? (
   646	                  <div style={{ fontSize: 12, marginBottom: 10 }}>
   647	                    <span style={{ color: C.muted, fontWeight: 600 }}>남은 요건: </span>
   648	                    {rem.map((r, i) => <span key={i} style={{ display: "inline-block", background: "#fff7ed", border: "1px solid #fed7aa", color: "#b45309", borderRadius: 12, padding: "2px 8px", marginRight: 5, marginBottom: 4 }}>{r}</span>)}
   649	                  </div>
   650	                ) : null;
   651	              })()}
   652	              {audit.roadmap.terms.length > 0 && (
   653	                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
   654	                  {audit.roadmap.terms.map((t, i) => (
   655	                    <div key={i} style={{ display: "flex", gap: 12 }}>
   656	                      <div style={{ minWidth: 64, fontWeight: 700, color: C.navy, fontSize: 13.5, paddingTop: 2 }}>{t.term}<div style={{ fontSize: 10.5, color: C.muted, fontWeight: 400 }}>{t.term_credits}학점</div></div>
   657	                      <div style={{ flex: 1, borderLeft: `3px solid ${C.accent}`, paddingLeft: 12, display: "flex", flexDirection: "column", gap: 5 }}>
   658	                        {t.courses.map((c, ci) => {
   659	                          const offered = (c.offered_terms || []).length ? `${c.offered_terms.map((x) => (x === "1" ? "1학기" : x === "2" ? "2학기" : x)).join("·")} 개설` : null;
   660	                          return (
   661	                            <div key={ci} style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", fontSize: 12.5 }}>
   662	                              <span style={{ fontWeight: 600 }}>{c.name_ko}</span>
   663	                              <span style={{ color: C.muted }}>{c.credits}학점</span>
   664	                              {c.satisfies && <span style={{ fontSize: 10.5, background: "#eef5ff", color: C.accent, border: "1px solid #cfe1fb", borderRadius: 5, padding: "1px 6px" }}>{c.satisfies}</span>}
   665	                              {c.assignment && <span style={{ fontSize: 10.5, background: "#ede9fe", color: "#6d28d9", border: "1px solid #c4b5fd", borderRadius: 5, padding: "1px 6px" }}>{c.assignment}</span>}
   666	                              {offered && <span style={{ fontSize: 10.5, color: "#047857" }}>· {offered}</span>}
   667	                              {c.manual_check && <span style={{ fontSize: 10.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 5, padding: "1px 6px" }}>개설학기 확인필요</span>}
   668	                            </div>
   669	                          );
   670	                        })}
   671	                      </div>
   672	                    </div>
   673	                  ))}
   674	                </div>
   675	              )}
   676	              {audit.roadmap.feasible === false && audit.roadmap.blocked_reason && (
   677	                <div style={{ fontSize: 12.5, color: "#b45309", margin: "10px 0 0", padding: "10px 12px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8 }}>
   678	                  ⚠️ {audit.roadmap.blocked_reason}{audit.roadmap.relaxation_hint ? ` · ${audit.roadmap.relaxation_hint}` : ""}
   679	                </div>
   680	              )}
   681	              {audit.roadmap.why_this_plan && audit.roadmap.terms.length > 0 && (
   682	                <p style={{ fontSize: 12.5, color: C.text, margin: "12px 0 0", padding: "10px 12px", background: C.soft, borderRadius: 8 }}>
   683	                  <strong style={{ color: C.navy }}>왜 이 계획:</strong> {audit.roadmap.why_this_plan}</p>
   684	              )}
   685	              {audit.roadmap.assumptions?.length > 0 && <p style={{ fontSize: 11, color: C.muted, margin: "8px 0 0" }}>가정: {audit.roadmap.assumptions.join(" / ")}</p>}
   686	
   687	              {audit.roadmap.overflow && (
   688	                <div style={{ marginTop: 12, padding: 14, borderRadius: 10, background: "#fff7ed", border: "1px solid #fed7aa" }}>
   689	                  <div style={{ fontWeight: 700, color: "#b45309", fontSize: 13.5, marginBottom: 8 }}>⏳ 초과학기 예상 시나리오</div>
   690	                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 8 }}>
   691	                    {[["부족 학점", `${audit.roadmap.overflow.shortfall_credits}학점`],
   692	                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
   693	                      ["필요 총학기", `${audit.roadmap.overflow.total_semesters_needed}학기`],
   694	                      ["초과학기", `${audit.roadmap.overflow.extra_semesters}학기`],
   695	                      ["예상 졸업", audit.roadmap.overflow.projected_graduation_term || "—"]].map(([k, v]) => (
   696	                      <div key={k}>
   697	                        <div style={{ fontSize: 11, color: C.muted }}>{k}</div>
   698	                        <div style={{ fontSize: 15, fontWeight: 700, color: "#b45309" }}>{v}</div>
   699	                      </div>
   700	                    ))}
   701	                  </div>
   702	                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{audit.roadmap.overflow.note}</div>
   703	                </div>
   704	              )}
   705	            </div>
   706	
   707	            {/* 워크플로우 그래프 — 별도 페이지로 분리 */}
   708	            <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
   709	              <div>
   710	                <div style={{ fontSize: 13.5, fontWeight: 700, color: C.navy }}>🔀 워크플로우 실행 그래프</div>

exec
/bin/bash -lc "nl -ba data/graduation/v2/requirements_by_year.json && nl -ba data/graduation/v2/required_names_by_year.json | sed -n '1,145p'" in /home/carol/kmu_genai
 succeeded in 0ms:
     1	{
     2	  "_source": "학번(입학연도)별 요람 별표5 이수구분별 최저이수학점. 없으면 graduation_requirements.json 기본값.",
     3	  "programs": {
     4	    "mirae_mobility": {
     5	      "2023": {
     6	        "전공": 62,
     7	        "기초교양": 8,
     8	        "자유교양": 2,
     9	        "일반선택": 47,
    10	        "졸업_최저합계": 136
    11	      }
    12	    }
    13	  }
    14	}
     1	{
     2	  "_source": "학번(입학연도)별 요람 교과과정 비고 필수 — 이름 기준(코드 무관). 2023=2023요람 p739-740, 2025=2025요람 p772-773",
     3	  "programs": {
     4	    "mirae_mobility": {
     5	      "2023": [
     6	        {
     7	          "name": "일반물리Ⅰ",
     8	          "credits": 3,
     9	          "terms": [
    10	            "1"
    11	          ]
    12	        },
    13	        {
    14	          "name": "일반물리실험Ⅰ",
    15	          "credits": 1,
    16	          "terms": [
    17	            "1"
    18	          ]
    19	        },
    20	        {
    21	          "name": "S-TEAM Class",
    22	          "credits": 1,
    23	          "terms": [
    24	            "1"
    25	          ]
    26	        },
    27	        {
    28	          "name": "공학기초수학",
    29	          "credits": 3,
    30	          "terms": [
    31	            "1"
    32	          ]
    33	        },
    34	        {
    35	          "name": "Python프로그래밍",
    36	          "credits": 3,
    37	          "terms": [
    38	            "1"
    39	          ]
    40	        },
    41	        {
    42	          "name": "미래모빌리티기초",
    43	          "credits": 3,
    44	          "terms": [
    45	            "1"
    46	          ]
    47	        },
    48	        {
    49	          "name": "공학수학Ⅰ",
    50	          "credits": 3,
    51	          "terms": [
    52	            "2"
    53	          ]
    54	        },
    55	        {
    56	          "name": "정역학",
    57	          "credits": 3,
    58	          "terms": [
    59	            "2"
    60	          ]
    61	        },
    62	        {
    63	          "name": "일반물리Ⅱ",
    64	          "credits": 2,
    65	          "terms": [
    66	            "2"
    67	          ]
    68	        },
    69	        {
    70	          "name": "일반물리실험Ⅱ",
    71	          "credits": 1,
    72	          "terms": [
    73	            "2"
    74	          ]
    75	        },
    76	        {
    77	          "name": "미래모빌리티AD",
    78	          "credits": 3,
    79	          "terms": [
    80	            "2"
    81	          ]
    82	        },
    83	        {
    84	          "name": "기초선형대수",
    85	          "credits": 3,
    86	          "terms": [
    87	            "1"
    88	          ]
    89	        },
    90	        {
    91	          "name": "회로이론",
    92	          "credits": 3,
    93	          "terms": [
    94	            "1"
    95	          ]
    96	        },
    97	        {
    98	          "name": "확률및통계",
    99	          "credits": 3,
   100	          "terms": [
   101	            "2"
   102	          ]
   103	        },
   104	        {
   105	          "name": "동역학",
   106	          "credits": 3,
   107	          "terms": [
   108	            "2"
   109	          ]
   110	        },
   111	        {
   112	          "name": "자료구조및알고리즘",
   113	          "credits": 3,
   114	          "terms": [
   115	            "2"
   116	          ]
   117	        },
   118	        {
   119	          "name": "전자회로",
   120	          "credits": 3,
   121	          "terms": [
   122	            "2"
   123	          ]
   124	        },
   125	        {
   126	          "name": "미래모빌리티실험",
   127	          "credits": 2,
   128	          "terms": [
   129	            "2"
   130	          ]
   131	        },
   132	        {
   133	          "name": "다학제간캡스톤디자인Ⅰ",
   134	          "credits": 3,
   135	          "terms": [
   136	            "1"
   137	          ]
   138	        },
   139	        {
   140	          "name": "다학제간캡스톤디자인Ⅱ",
   141	          "credits": 3,
   142	          "terms": [
   143	            "2"
   144	          ]
   145	        }

exec
/bin/bash -lc "rg -n '\"name_ko\"|\"course_id\"|\"credits\"|\"offered_terms\"|\"prerequisites\"|\"group\"' data/graduation/v2/catalog_mirae_mobility.json | head -80" in /home/carol/kmu_genai
exec
/bin/bash -lc "rg -n '\"핵심교양_영역최저\"|미래모빌리티|AI빅데이터|경영대학_AI빅데이터|자동차융합대학_미래모빌리티학과' data/graduation/graduation_requirements.json" in /home/carol/kmu_genai
 succeeded in 0ms:
829:    "경영대학_AI빅데이터": {
955:    "자동차융합대학_미래모빌리티학과": {
957:      "학과_전공명": "미래모빌리티학과",
968:      "핵심교양_영역최저": {

 succeeded in 0ms:
14:      "course_id": "0118810",
15:      "name_ko": "일반물리실험I",
18:      "credits": 1.0,
21:      "prerequisites": [],
24:      "offered_terms": [
27:      "group": null,
34:      "course_id": "0119410",
35:      "name_ko": "일반물리I",
38:      "credits": 3.0,
41:      "prerequisites": [],
44:      "offered_terms": [
47:      "group": null,
54:      "course_id": "0533411",
55:      "name_ko": "공학기초수학",
58:      "credits": 3.0,
61:      "prerequisites": [],
64:      "offered_terms": [
67:      "group": null,
74:      "course_id": "0547210",
75:      "name_ko": "Python프로그래밍",
78:      "credits": 3.0,
81:      "prerequisites": [],
84:      "offered_terms": [
87:      "group": null,
94:      "course_id": "0733010",
95:      "name_ko": "자동차모빌리티기초",
98:      "credits": 3.0,
101:      "prerequisites": [],
104:      "offered_terms": [
107:      "group": null,
114:      "course_id": "1621601",
115:      "name_ko": "S-TEAM Class",
118:      "credits": 1.0,
121:      "prerequisites": [],
124:      "offered_terms": [
127:      "group": null,
134:      "course_id": "0053010",
135:      "name_ko": "정역학",
138:      "credits": 3.0,
141:      "prerequisites": [],
144:      "offered_terms": [
147:      "group": null,
154:      "course_id": "0156810",
155:      "name_ko": "C프로그래밍",
158:      "credits": 3.0,
161:      "prerequisites": [],
164:      "offered_terms": [
167:      "group": null,
174:      "course_id": "0533010",
175:      "name_ko": "공학수학Ⅰ",
178:      "credits": 3.0,
181:      "prerequisites": [
186:      "offered_terms": [
189:      "group": null,
196:      "course_id": "0533710",
197:      "name_ko": "일반물리II",
200:      "credits": 2.0,
203:      "prerequisites": [],
206:      "offered_terms": [
209:      "group": null,
216:      "course_id": "0533910",
217:      "name_ko": "일반물리실험II",
220:      "credits": 1.0,
223:      "prerequisites": [],
226:      "offered_terms": [
229:      "group": null,
236:      "course_id": "0590915",
237:      "name_ko": "자동차모빌리티 Adventure Design",
240:      "credits": 3.0,
243:      "prerequisites": [],
246:      "offered_terms": [
249:      "group": null,
256:      "course_id": "0056110",
257:      "name_ko": "회로이론",
260:      "credits": 3.0,
263:      "prerequisites": [],
266:      "offered_terms": [
269:      "group": null,
276:      "course_id": "0579207",
277:      "name_ko": "고체역학",

exec
/bin/bash -lc "rg -n '\"prerequisites\": \\[["'^'"\\]]+\\]' data/graduation/v2/catalog_*.json" in /home/carol/kmu_genai
 exited 1 in 0ms:
exec
/bin/bash -lc "nl -ba data/graduation/v2/catalog_mirae_mobility.json | sed -n '168,190p'" in /home/carol/kmu_genai
exec
/bin/bash -lc "nl -ba data/graduation/graduation_requirements.json | sed -n '829,875p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   829	    "경영대학_AI빅데이터": {
   830	      "대학": "경영대학",
   831	      "학과_전공명": "A I 빅데이터",
   832	      "교양": {
   833	        "기초교양": 7,
   834	        "핵심교양": 15,
   835	        "자유교양": 2,
   836	        "소계": 24
   837	      },
   838	      "전공_최저": 48,
   839	      "일반선택": 58,
   840	      "졸업_최저합계": 130,
   841	      "비고": "총 130학점 이상 (인문·사회·예술 계열 일반)"
   842	    },
   843	    "경영대학_융합경영학과기업경영학부기업경영전공": {
   844	      "대학": "경영대학",
   845	      "학과_전공명": "융합경영학과기업경영학부기업경영전공",
   846	      "교양": {
   847	        "기초교양": 7,
   848	        "핵심교양": 15,
   849	        "자유교양": 2,
   850	        "소계": 24
   851	      },
   852	      "전공_최저": 87,
   853	      "일반선택": 9,
   854	      "졸업_최저합계": 120,
   855	      "비고": "총 120학점 이상 (KMU International Business School, 기업경영전공 등)"
   856	    },
   857	    "경영대학_회계세무학과": {
   858	      "대학": "경영대학",
   859	      "학과_전공명": "회계세무학과",
   860	      "교양": {
   861	        "기초교양": 7,
   862	        "핵심교양": 15,
   863	        "자유교양": 2,
   864	        "소계": 24
   865	      },
   866	      "전공_최저": 87,
   867	      "일반선택": 9,
   868	      "졸업_최저합계": 120,
   869	      "비고": "총 120학점 이상 (KMU International Business School, 기업경영전공 등)"
   870	    },
   871	    "경영대학_소프트웨어학부소프트웨어전공": {
   872	      "대학": "경영대학",
   873	      "학과_전공명": "소프트웨어학부소프트웨어전공",
   874	      "교양": {
   875	        "기초교양": 7,

 succeeded in 0ms:
   168	      "source": {
   169	        "doc": "2025-2 교육과정 교과목코드 현황",
   170	        "dept": "미래모빌리티학과"
   171	      }
   172	    },
   173	    {
   174	      "course_id": "0533010",
   175	      "name_ko": "공학수학Ⅰ",
   176	      "name_norm": "공학수학1",
   177	      "aliases": [],
   178	      "credits": 3.0,
   179	      "requirement_area": "전공",
   180	      "is_required": true,
   181	      "prerequisites": [
   182	        "0533411"
   183	      ],
   184	      "prereq_external": [],
   185	      "grade_level": 1,
   186	      "offered_terms": [
   187	        "2"
   188	      ],
   189	      "group": null,
   190	      "source": {

exec
/bin/bash -lc "nl -ba data/graduation/graduation_requirements.json | sed -n '955,978p'" in /home/carol/kmu_genai
 succeeded in 0ms:
   955	    "자동차융합대학_미래모빌리티학과": {
   956	      "대학": "자동차융합대학",
   957	      "학과_전공명": "미래모빌리티학과",
   958	      "교양": {
   959	        "기초교양": 7,
   960	        "핵심교양": 15,
   961	        "자유교양": 2,
   962	        "소계": 24
   963	      },
   964	      "전공_최저": 62,
   965	      "일반선택": 50,
   966	      "졸업_최저합계": 136,
   967	      "비고": "총 136학점 이상 (공학·과학기술·체육·소프트웨어 계열)",
   968	      "핵심교양_영역최저": {
   969	        "소통": 5
   970	      }
   971	    },
   972	    "독립학부_KMUInternationalInternationalBusiness전공": {
   973	      "대학": "독립학부",
   974	      "학과_전공명": "KMU International International Business 전공",
   975	      "교양": {
   976	        "기초교양": 7,
   977	        "핵심교양": 15,
   978	        "자유교양": 2,

One more concrete issue: planner/risk use `context.max_credits_per_term` directly, and the frontend always sends a number, so the backend will trust a stale or user-edited cap instead of recalculating from the applied 요람. I’m including that because it can directly flip feasibility in a live demo.
**HIGH**

1. [graduation_center/v2/planner.py:556](/home/carol/kmu_genai/graduation_center/v2/planner.py:556) `run_planner()` never calls `validate_roadmap()`. It only rechecks credit caps at [557-562](/home/carol/kmu_genai/graduation_center/v2/planner.py:557), so the real validator’s checks for prerequisites, required inclusion, duplicate courses, term range, offered terms, sources, and gap closure are bypassed. This is demo-breaking because the trace says “검증/repair 통과” even when no real validation ran.  
Fix: build a full validation context for deterministic candidates and call `validate_roadmap()` before returning. If it fails, mark `blocked` or repair.

2. [graduation_center/v2/planner.py:486](/home/carol/kmu_genai/graduation_center/v2/planner.py:486) `plan_greedy()` does not enforce prerequisites. Example: `공학수학Ⅰ` has prerequisite `공학기초수학` in [catalog_mirae_mobility.json:181](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:181), but greedy only sorts by priority/credits and offered term. It can schedule `공학수학Ⅰ` in the first available 2학기 before `공학기초수학` is scheduled in a later 1학기.  
Fix: topologically order catalog candidates by prerequisites and disallow placement unless prereqs are already completed or placed in earlier terms.

3. [graduation_center/v2/planner.py:407](/home/carol/kmu_genai/graduation_center/v2/planner.py:407) + [433](/home/carol/kmu_genai/graduation_center/v2/planner.py:433) missing required 전공 credits are not subtracted from `major_gap`. If a student is missing one 3-credit required course and has a 3-credit 전공 gap, the planner selects the required course, then still selects another 3-credit 전공 course because `major_gap` remains unchanged.  
Fix: after adding required 전공 candidates, reduce the 전공 shortage quota by their credits before selecting elective 전공 candidates.

4. [graduation_center/v2/audit_v2.py:152](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:152) + [154](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:154) convergence earned credits count all designated courses, including overlap beyond the duplicate-credit cap. This violates the rule that over-cap overlap must count to 제1전공 or 융합 only, not both. Backend can report both 제1전공 and 융합 as satisfied when the allocation is impossible.  
Fix: implement backend allocation/optimization and derive both primary and convergence earned/gaps from that allocation. Do not leave this as frontend-only state.

5. [frontend/src/components/GraduationV2.jsx:100](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100) frontend recomputes convergence allocation locally, but backend risk/roadmap still use `cc.gap` from the old all-designated calculation. The StatBox can say “충족” while “남은 요건” and roadmap still show a 융합 gap, or the reverse. See roadmap remaining summary at [642](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:642).  
Fix: send allocation choices back to backend and rerun audit/risk/planner, or make the backend own the allocation and render it read-only.

6. [graduation_center/v2/planner.py:420](/home/carol/kmu_genai/graduation_center/v2/planner.py:420) convergence roadmap candidates are only created when total `cc.gap > 0`. If total 융합 credits are 36 but group minimum is short, risk sees the group problem, but the roadmap will not plan any group-filling courses.  
Fix: trigger convergence planning when either total gap or any `group_checks[].gap` is positive; select courses from short groups until group floors are met.

7. [graduation_center/v2/catalog.py:102](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102) and [data/graduation/v2/requirements_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4) year-aware area rules exist only for `mirae_mobility` 2023 and require exact-year match. Meanwhile required-name logic picks nearest prior year at [audit_v2.py:41](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:41). A 2024 미래모빌리티 student can get 2025 area minima but 2023 required names, while UI says one applied 요람.  
Fix: use the same year-selection policy for all requirement dimensions, and expose “data unavailable for year” instead of silently mixing years.

8. [frontend/src/components/GraduationV2.jsx:242](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:242) spreads `ctx`, including `student_id`, into the API payload. The UI label says “입학연도” but state is `student_id`; if a user enters a real full 학번, v2 collects/transmits it raw. This violates the project privacy rule.  
Fix: replace this with a strict 4-digit `admission_year` field, remove `student_id` entirely from state/payload, and validate before request.

**MEDIUM**

9. [graduation_center/v2/planner.py:63](/home/carol/kmu_genai/graduation_center/v2/planner.py:63) `project_overflow()` only considers total and hard area gaps. It ignores missing required courses and convergence/group shortfalls. A student can have no total gap but still need extra required/융합 courses, and overflow will be `None`.  
Fix: compute projected required credits from the actual selected roadmap obligations, including required-name candidates and convergence group deficits.

10. [graduation_center/v2/risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62) risk capacity uses `context.max_credits_per_term or 18`, not the applied profile’s `regular_term_cap(profile.total_credits_min)`. Since frontend always sends `max_credits_per_term` at [GraduationV2.jsx:245](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:245), stale/user-edited caps can flip feasibility and risk.  
Fix: backend should compute legal cap from applied 요람 and only allow bounded overrides below that cap.

11. [graduation_center/v2/planner.py:449](/home/carol/kmu_genai/graduation_center/v2/planner.py:449), [455](/home/carol/kmu_genai/graduation_center/v2/planner.py:455), [461](/home/carol/kmu_genai/graduation_center/v2/planner.py:461) generic 교양 slots use the entire gap as one pseudo-course. If 자유교양/기초교양 gap is larger than one term cap, greedy marks it unplaced even though multiple real courses across terms could work.  
Fix: split generic slots into realistic 2- or 3-credit chunks, capped by term capacity.

12. [graduation_center/v2/catalog.py:148](/home/carol/kmu_genai/graduation_center/v2/catalog.py:148) `match_course()` falls back to name matching even when a non-primary course code is present and not in the selected major catalog. A 타과 course with the same normalized name as a primary-major course can be counted as 제1전공.  
Fix: if a code exists and does not match the primary catalog, do not upgrade by name to primary 전공 unless an explicit alias/equivalence table says so.

13. [graduation_center/v2/audit_v2.py:271](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:271) required-name completion checks all confirmed course names regardless of area/code. A 교양 or 타과 course with the same name as a required major can satisfy a major required course.  
Fix: match required courses against primary-major catalog code/prefix or verified primary-major classification, then use aliases only inside that bounded set.

14. [graduation_center/v2/audit_v2.py:247](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:247) 핵심교양 total is recomputed as sum of current `core_area_min_overrides`, not necessarily the year-specific `profile.area_min["핵심교양"]`. This can silently override the applied-year total.  
Fix: store year-specific core area minima in `requirements_by_year.json` and derive both total and per-area checks from the same applied profile.

**LOW**

15. [frontend/src/components/GraduationV2.jsx:208](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:208) `seasonal_semester_allowed` defaults to `true`, while the domain says 계절학기 is a scenario/constraint. This makes optimistic roadmaps by default.  
Fix: default false or make it an explicit required choice before audit.

16. [graduation_center/v2/planner.py:539](/home/carol/kmu_genai/graduation_center/v2/planner.py:539) deterministic planner returns `sources: []`, so roadmap courses are not grounded to catalog/requirement sources even though older `build_planning_context()` had source construction.  
Fix: include requirement and catalog sources in deterministic `ctx` and render them.

Verification note: I tried `pytest tests/test_v2_pipeline.py -q`, but test collection failed because `pydantic` is not installed in this environment.
