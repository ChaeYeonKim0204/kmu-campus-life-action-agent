"""졸업센터 v2 카탈로그 빌드.

입력(repo 내, 재현 가능):
  - data/graduation/v2/sources/course_code_2025_2.xlsx  (2025-2 교육과정 교과목코드 현황)
  - data/graduation/v2/overrides_<program_id>.json       (요람 p.xxx 필수/선수 보강)
출력:
  - data/graduation/v2/catalog_<program_id>.json
  - data/graduation/v2/programs.json                     (프로그램 레지스트리)
  - data/graduation/v2/catalog_build_report.json         (행수·중복·미해소 보고)

규칙(plan/codex 반영):
  - course_id = 교과목코드(7자리 문자열, leading-zero·문자 보존).
  - requirement_area = "전공"(현황은 전부 전공선택). 전공필수는 학점영역이 아니라
    is_required(요람 비고) 과목 체크리스트.
  - 같은 코드 충돌(이름/학점 다름) → report에 기록(빌드 실패 사유).
  - override 필수/선수 이름이 카탈로그에서 미해소/모호 → report에 기록 후 빌드 실패.

실행: conda run -n kmu-agent python scripts/build_v2_catalog.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from graduation_center.v2.text_norm import normalize_code, normalize_name  # noqa: E402

V2 = ROOT / "data" / "graduation" / "v2"
SRC_XLSX = V2 / "sources" / "course_code_2025_2.xlsx"
SRC_GENED_PDF = V2 / "sources" / "korean_curriculum_2025.pdf"

# 핵심교양 5영역 (요람: 인문Ⅰ, 인문Ⅱ, 소통, 글로벌, 창의 / 각 영역 최소 3학점, 총 15)
CORE_AREAS = ["인문Ⅰ", "인문Ⅱ", "소통", "글로벌", "창의"]

# 현황 xlsx 컬럼 인덱스 (헤더행 기준): 연번0 대학명1 배정학과코드2 배정학과명3 학년4 학기5
# 이수구분6 코드7(7자리)7 코드5 8 교과목명9 학점10 수업시간11...
COL = {"univ": 1, "dept": 3, "grade": 4, "term": 5, "area": 6, "code": 7, "name": 9, "credits": 10}

PROGRAMS = [
    # 주전공 (졸업요건 = graduation_requirements.json)
    {"program_id": "ai_bigdata", "yoram_dept": "AI빅데이터융합경영학과",
     "req_key": "경영대학_AI빅데이터", "name_ko": "AI빅데이터융합경영학과", "yoram_page": 693,
     "track_type": "primary"},
    {"program_id": "mirae_mobility", "yoram_dept": "미래모빌리티학과",
     "req_key": "자동차융합대학_미래모빌리티학과", "name_ko": "미래모빌리티학과", "yoram_page": 772,
     "track_type": "primary"},
    # 연계·융합전공 (다전공) — 최저 36학점 (요람 p.814). 주전공에 오버레이로 체크.
    {"program_id": "dsci_convergence", "yoram_dept": "데이터사이언스융합전공",
     "req_key": None, "name_ko": "데이터사이언스융합전공", "yoram_page": 882,
     "track_type": "convergence", "requirement_area": "융합전공", "convergence_required": 36},
    {"program_id": "mobility_data_convergence", "yoram_dept": "모빌리티데이터분석융합전공",
     "req_key": None, "name_ko": "모빌리티데이터분석융합전공", "yoram_page": 889,
     "track_type": "convergence", "requirement_area": "융합전공", "convergence_required": 36},
]


def _terms(term: str | None) -> list[str]:
    t = str(term or "").strip()
    if "1학기" in t:
        return ["1"]
    if "2학기" in t:
        return ["2"]
    return ["1", "2"]  # 전학기/전체/미상


def _grade_level(grade: str | None):
    g = str(grade or "").strip()
    if g.isdigit():
        return int(g)
    return None  # '1-4' / '1~4' 등 다학년


def _load_rows() -> list[tuple]:
    wb = openpyxl.load_workbook(SRC_XLSX, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    return [r for r in ws.iter_rows(values_only=True) if r]


def build_program(prog: dict, rows: list[tuple], report: dict) -> dict:
    pid = prog["program_id"]
    dept = prog["yoram_dept"]
    raw = [r for r in rows if (r[COL["dept"]] or "") == dept]
    courses: dict[str, dict] = {}
    by_norm: dict[str, list[str]] = defaultdict(list)
    dup_codes, conflicts = [], []

    for r in raw:
        code = normalize_code(r[COL["code"]])
        name = str(r[COL["name"]] or "").strip()
        if not code or not name:
            continue
        try:
            credits = float(r[COL["credits"]])
        except (TypeError, ValueError):
            credits = 0.0
        nn = normalize_name(name)
        entry = {
            "course_id": code,
            "name_ko": name,
            "name_norm": nn,
            "aliases": [],
            "credits": credits,
            "requirement_area": prog.get("requirement_area", "전공"),
            "is_required": False,
            "prerequisites": [],
            "prereq_external": [],
            "grade_level": _grade_level(r[COL["grade"]]),
            "offered_terms": _terms(r[COL["term"]]),
            "group": None,
            "source": {"doc": "2025-2 교육과정 교과목코드 현황", "dept": dept},
        }
        if code in courses:
            prev = courses[code]
            if prev["name_ko"] != name or prev["credits"] != credits:
                conflicts.append({"code": code, "a": prev["name_ko"], "b": name})
            dup_codes.append(code)
            continue
        courses[code] = entry
        by_norm[nn].append(code)

    # --- override 적용 (요람 필수/선수) ---
    ov_path = V2 / f"overrides_{pid}.json"
    unresolved_required, ambiguous, unresolved_prereq = [], [], []
    if ov_path.exists():
        ov = json.loads(ov_path.read_text(encoding="utf-8"))
        # aliases: name_norm 보강
        for code, names in (ov.get("aliases") or {}).items():
            if code in courses:
                courses[code]["aliases"].extend(names)
        # required (이름 매칭)
        for rn in ov.get("required_names", []):
            nn = normalize_name(rn)
            hits = by_norm.get(nn, [])
            if len(hits) == 1:
                courses[hits[0]]["is_required"] = True
            elif len(hits) == 0:
                unresolved_required.append(rn)
            else:
                ambiguous.append({"name": rn, "codes": hits})
        # required (코드 직접 지정 — 이름 모호 해소용)
        for code in ov.get("required_codes", []):
            if code in courses:
                courses[code]["is_required"] = True
            else:
                unresolved_required.append(f"code:{code}")
        # prerequisites: name → code
        for course_name, prereqs in (ov.get("prerequisites") or {}).items():
            if isinstance(prereqs, str):       # 단일 선수 문자열 → 1원소 리스트(글자 단위 분해 방지)
                prereqs = [prereqs]
            nn = normalize_name(course_name)
            hits = by_norm.get(nn, [])
            if len(hits) != 1:
                (unresolved_required if not hits else ambiguous).append(
                    {"prereq_owner": course_name, "codes": hits})
                continue
            owner = courses[hits[0]]
            for p in prereqs:
                pn = normalize_name(p)
                phits = by_norm.get(pn, [])
                if len(phits) == 1:
                    owner["prerequisites"].append(phits[0])
                else:
                    owner["prereq_external"].append(p)  # 외부/미해소 → 확인 필요
                    unresolved_prereq.append({"owner": course_name, "prereq": p})

    # --- 연계융합 그룹 배정 (요람 그룹 → 카탈로그 과목, 이름 매칭) ---
    group_unmatched, group_rules = [], None
    gp_path = V2 / f"groups_{pid}.json"
    if gp_path.exists():
        gp = json.loads(gp_path.read_text(encoding="utf-8"))
        group_rules = gp.get("rules")
        for gname, gdata in gp.get("groups", {}).items():
            for nm in gdata.get("courses", []):
                hits = by_norm.get(normalize_name(nm), [])
                if hits:
                    for code in hits:
                        courses[code]["group"] = gname
                else:
                    group_unmatched.append({"group": gname, "name": nm})

    catalog = {
        "program_id": pid,
        "department_name_ko": prog["name_ko"],
        "group_rules": group_rules,
        "requirements_key": prog["req_key"],
        "track_type": prog.get("track_type", "primary"),
        "convergence_required": prog.get("convergence_required"),
        "yoram": {"doc": "2025 국민대학교 요람", "page": prog["yoram_page"]},
        "courses": list(courses.values()),
    }
    report[pid] = {
        "course_count": len(courses),
        "duplicate_codes": sorted(set(dup_codes)),
        "code_conflicts": conflicts,
        "ambiguous_name_norm": {k: v for k, v in by_norm.items() if len(v) > 1},
        "required_marked": sum(1 for c in courses.values() if c["is_required"]),
        "unresolved_required": unresolved_required,
        "ambiguous_override": ambiguous,
        "unresolved_prereq": unresolved_prereq,
        "group_unmatched": group_unmatched,
        "grouped": sum(1 for c in courses.values() if c.get("group")),
    }
    return catalog


def build_gen_ed(report: dict) -> dict:
    """교양교육과정 PDF(p4)에서 핵심교양 영역별 과목 매핑 추출.

    핵심교양은 5개 학문영역별로 각 3학점·총 15학점 이수 요건이 있어, 학생의
    핵심교양 과목을 영역별로 분류해 영역별 충족을 점검하는 데 쓴다. (기초/자유교양은
    이수구분 집계로 충분 → 별도 영역 매핑 없이 둠.)
    """
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover
        report["gen_ed"] = {"error": f"pdfplumber 없음: {exc}"}
        return {}
    with pdfplumber.open(SRC_GENED_PDF) as pdf:
        tb = pdf.pages[3].extract_tables()[0]  # p4 핵심교양 학점 배정표
    core: dict[str, list[dict]] = {}
    name_to_area: dict[str, str] = {}
    for i, row in enumerate(tb[1:1 + len(CORE_AREAS)]):
        area = CORE_AREAS[i]
        names = [t for t in str(row[2] or "").replace("\n", " ").split(" ") if t.strip()]
        core[area] = []
        for nm in names:
            nn = normalize_name(nm)
            core[area].append({"name_ko": nm, "name_norm": nn, "credits": 3})
            name_to_area[nn] = area
    gen_ed = {
        "source": {"doc": "2025 교양교육과정", "page": 4},
        "core_liberal": {
            "areas": CORE_AREAS,
            "area_min_credits": 3,
            "total_min_credits": 15,
            "courses_by_area": core,
            "name_norm_to_area": name_to_area,
        },
    }
    report["gen_ed"] = {"core_area_course_counts": {a: len(core[a]) for a in CORE_AREAS}}
    return gen_ed


def main() -> int:
    rows = _load_rows()
    report: dict = {}
    registry = {}

    gen_ed = build_gen_ed(report)
    (V2 / "gen_ed_catalog.json").write_text(
        json.dumps(gen_ed, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = report.get("gen_ed", {}).get("core_area_course_counts", {})
    print(f"[gen_ed] 핵심교양 영역별 과목수: {counts} → gen_ed_catalog.json")
    for prog in PROGRAMS:
        catalog = build_program(prog, rows, report)
        out = V2 / f"catalog_{prog['program_id']}.json"
        out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        registry[prog["program_id"]] = {
            "name_ko": prog["name_ko"], "requirements_key": prog["req_key"],
            "catalog_file": out.name, "yoram_page": prog["yoram_page"],
            "track_type": prog.get("track_type", "primary"),
            "convergence_required": prog.get("convergence_required"),
        }
        print(f"[{prog['program_id']}] {report[prog['program_id']]['course_count']}과목 "
              f"(필수 {report[prog['program_id']]['required_marked']}) → {out.name}")

    (V2 / "programs.json").write_text(
        json.dumps({"programs": registry}, ensure_ascii=False, indent=2), encoding="utf-8")
    (V2 / "catalog_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 빌드 실패 조건: 코드 충돌 또는 override 미해소/모호
    fatal = []
    for pid in registry:
        rep = report[pid]
        if rep["code_conflicts"]:
            fatal.append(f"{pid}: code_conflicts {rep['code_conflicts']}")
        if rep["unresolved_required"]:
            fatal.append(f"{pid}: unresolved_required {rep['unresolved_required']}")
        if rep["ambiguous_override"]:
            fatal.append(f"{pid}: ambiguous_override {rep['ambiguous_override']}")
    if fatal:
        print("\n[BUILD FAILED]")
        for f in fatal:
            print("  -", f)
        return 1
    print("\n[OK] catalog build clean. report → catalog_build_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
