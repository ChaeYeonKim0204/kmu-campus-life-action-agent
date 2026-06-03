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


def assemble_requirement_profile(context: StudentContext) -> RequirementProfile:
    """graduation_requirements.json(카테고리 총계) + 카탈로그 필수과목으로 요건 프로파일 구성."""
    cat = load_catalog(context.program_id)
    req = json.loads(GRAD_REQ.read_text(encoding="utf-8"))["departments"][cat["requirements_key"]]
    gyo = req.get("교양", {})
    area_min = {
        "전공": float(req.get("전공_최저", 0)),
        "기초교양": float(gyo.get("기초교양", 0)),
        "핵심교양": float(gyo.get("핵심교양", 0)),
        "자유교양": float(gyo.get("자유교양", 0)),
        "일반선택": float(req.get("일반선택", 0)),
    }
    required_ids = [c.course_id for c in cat["courses"] if c.is_required]
    gen = load_gen_ed().get("core_liberal", {})
    return RequirementProfile(
        program_id=context.program_id,
        department_name_ko=cat["department_name_ko"],
        admission_year=context.admission_year,
        total_credits_min=float(req.get("졸업_최저합계", 0)),
        area_min=area_min,
        required_course_ids=required_ids,
        core_area_min=float(gen.get("area_min_credits", 3)),
        core_total_min=float(gen.get("total_min_credits", 15)),
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
