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
    return by_year[str(pick)], pick


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
