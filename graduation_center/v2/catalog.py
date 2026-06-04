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
    # 연도 선택 정책 통일(필수명·메타와 동일): 정확연도 → 입학연도 이하 가장 가까운 요람 → 없으면 None
    if str(year) in by_year:
        return by_year[str(year)]
    le = [int(y) for y in by_year if int(y) <= year]
    return by_year[str(max(le))] if le else None


def assemble_requirement_profile(context: StudentContext) -> RequirementProfile:
    """graduation_requirements.json(카테고리 총계) + 카탈로그 필수과목으로 요건 프로파일 구성.

    학번(입학연도) 요람 별표5(requirements_by_year.json)가 있으면 영역 최저학점은 그것을 우선.
    """
    cat = load_catalog(context.program_id)
    if not cat.get("requirements_key"):
        # 연계·융합전공은 요건키가 없음 — 제1전공으로 지정 불가(KeyError: None 방지)
        raise ValueError(f"'{context.program_id}'는 제1전공으로 선택할 수 없습니다(연계·융합전공은 다전공/부전공으로 추가).")
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
