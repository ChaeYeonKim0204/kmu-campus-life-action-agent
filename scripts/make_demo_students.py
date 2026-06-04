"""데모 학생 수강내역 .xls 생성기 — AI빅데이터융합경영 제1전공 + 데이터사이언스융합전공(다전공).

ON국민 수강신청확인서 형식(.xls, 학기당 1파일)으로 4명의 합성 학생을 만든다.
실제 카탈로그(catalog_ai_bigdata / catalog_dsci_convergence / gen_ed_catalog)에서
과목을 뽑으므로 코드 매칭·중복인정·그룹최저가 실데이터처럼 동작한다.

  S1 졸업반   — 잔여 1학기, 제1전공·교양 충족, dsci 겹침 21>캡12(3-way 트레이드오프)
  S2 3학년    — dsci B그룹 0학점(그룹최저 공백), 잔여 3학기 → 로드맵이 B그룹 배치
  S3 2학년    — 잔여 2학기 선언 대비 갭 큼 → blocked + 초과학기 시나리오(D)
  S4 4학년    — 계절 허용 + 직전학기 3.75↑(+3) → feasible 로드맵

실행:  PYTHONPATH=. python scripts/make_demo_students.py
출력:  data/graduation/v2/demo_students/<학생>/<n>차학기.xls
"""
from __future__ import annotations

import json
from pathlib import Path

import xlwt

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "graduation" / "v2"
OUT = V2 / "demo_students"

AI = json.loads((V2 / "catalog_ai_bigdata.json").read_text(encoding="utf-8"))
DS = json.loads((V2 / "catalog_dsci_convergence.json").read_text(encoding="utf-8"))
GEN = json.loads((V2 / "gen_ed_catalog.json").read_text(encoding="utf-8"))["core_liberal"]

AI_BY_NAME = {c["name_ko"]: c for c in AI["courses"]}
AI5 = {c["course_id"][:5] for c in AI["courses"] if c.get("course_id")}
REQUIRED = [c for c in AI["courses"] if c.get("is_required")]
ELECTIVE = [c for c in AI["courses"] if not c.get("is_required")]
OVERLAP_A = [c for c in DS["courses"] if c["course_id"][:5] in AI5 and c.get("group") == "A그룹"]
OVERLAP_B = [c for c in DS["courses"] if c["course_id"][:5] in AI5 and c.get("group") == "B그룹"]
DS_ONLY_B = [c for c in DS["courses"] if c["course_id"][:5] not in AI5 and c.get("group") == "B그룹"]

_FAKE = [9000000]


def _fc() -> str:
    """카탈로그 밖(교양·타과) 과목용 가짜 7자리 교과목코드."""
    _FAKE[0] += 1
    return str(_FAKE[0])


def major(cs):
    return [(c["course_id"], c["name_ko"], "전공선택", c["credits"]) for c in cs]


def ds_only(cs):  # dsci 전용 과목은 일반선택 이수구분으로 수강
    return [(c["course_id"], c["name_ko"], "일반선택", c["credits"]) for c in cs]


def gened(n_per_area=1):  # 핵심교양 — 실제 교양과목명(core_area 매핑 가동)
    rows = []
    for _area, cs in GEN["courses_by_area"].items():
        for c in cs[:n_per_area]:
            rows.append((_fc(), c["name_ko"], "핵심교양", c["credits"]))
    return rows


def basic():
    return [(_fc(), "지성과글", "기초교양", 3), (_fc(), "EnglishⅠ", "기초교양", 2),
            (_fc(), "컴퓨팅적사고", "기초교양", 2)]


def free():
    return [(_fc(), "교양테니스", "자유교양", 1), (_fc(), "생활과건강", "자유교양", 2)]


def filler(n, start=1):  # 일반선택 채우기(타과 과목)
    return [(_fc(), f"타과교양과목{start + i}", "일반선택", 3) for i in range(n)]


def write_xls(path: Path, rows, term_label: str, student_no: str, name: str) -> None:
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("수강신청확인서")
    ws.write(0, 0, f"{term_label} 수강신청 확인서")
    for col, val in enumerate(["학번", "", student_no, "", "", "성명", "", name]):
        ws.write(1, col, val)
    ws.write(2, 0, "수강학기"); ws.write(2, 2, term_label)
    header = ["교과목코드", "분반", "", "교과목명", "이수구분", "", "학점", "시간", "", "담당교수", "비고"]
    for col, val in enumerate(header):
        ws.write(4, col, val)
    for i, r in enumerate(rows):
        vals = [r[0], "01", "", r[1], r[2], "", r[3], "", "", "교수", ""]
        for col, val in enumerate(vals):
            ws.write(5 + i, col, val)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def split_terms(rows, n_terms, start_year):
    """rows를 n_terms개 정규학기로 순서 분할(학기당 1파일, ON국민 형식)."""
    per = -(-len(rows) // n_terms)
    out = []
    for i in range(n_terms):
        chunk = rows[i * per:(i + 1) * per]
        if not chunk:
            break
        year = start_year + i // 2
        sem = 1 + i % 2
        out.append((f"{year}학년도 {sem}학기", chunk))
    return out


def build_students():
    # S1 졸업반 — 겹침 21(A그룹 18 + 선형대수 B 3) > 캡 12
    s1_major = [c for c in REQUIRED if "캡스톤디자인Ⅱ" not in c["name_ko"]]
    ov7 = OVERLAP_A[:6] + OVERLAP_B[:1]
    s1_major += [c for c in ov7 if AI_BY_NAME.get(c["name_ko"]) and not AI_BY_NAME[c["name_ko"]].get("is_required")]
    need = 48 - sum(c["credits"] for c in s1_major)
    ov5 = {o["course_id"][:5] for o in ov7}
    s1_major += [c for c in ELECTIVE if c not in s1_major and c["course_id"][:5] not in ov5][: max(0, int(need // 3) + 1)]
    s1 = major(s1_major) + ds_only(DS_ONLY_B[:5]) + gened(1) + basic() + free() + filler(15)

    # S2 3학년 — dsci A그룹만(B그룹 0) → 그룹최저 부족
    s2_major = [AI_BY_NAME.get(c["name_ko"], c) for c in REQUIRED[:7] + OVERLAP_A[:4]]
    s2 = major([c for c in s2_major if c.get("course_id")]) + gened(1) + basic() + filler(6)

    # S3 2학년 — 갭 큼 + 잔여 2학기 선언 → blocked·초과학기(D)
    s3 = major(REQUIRED[:3]) + ds_only(DS_ONLY_B[:2]) + basic() + gened(1)[:2] + filler(3)

    # S4 4학년 — 계절+성적우수 → feasible
    s4_major = [AI_BY_NAME.get(c["name_ko"], c) for c in REQUIRED[:8] + OVERLAP_A[:5]]
    s4 = major([c for c in s4_major if c.get("course_id")]) + ds_only(DS_ONLY_B[:3]) + gened(1) + basic() + free() + filler(11)

    return [
        ("S1_졸업반_김융합", "20210001", s1, 7, 2021,
         {"current_term": "2026-1", "remaining_semesters": 1, "gpa_min_met": "yes"}),
        ("S2_3학년_박분석", "20220002", s2, 5, 2022,
         {"current_term": "2025-2", "remaining_semesters": 3, "gpa_min_met": "yes"}),
        ("S3_2학년_이지연", "20240003", s3, 2, 2024,
         {"current_term": "2025-1", "remaining_semesters": 2, "gpa_min_met": "unknown"}),
        ("S4_4학년_최계절", "20210004", s4, 6, 2021,
         {"current_term": "2026-1", "remaining_semesters": 2,
          "seasonal_semester_allowed": True, "prev_term_gpa_ge_375": True, "gpa_min_met": "yes"}),
    ]


def main():
    manifest = {}
    for slug, sid, rows, n_terms, adm_year, ctx in build_students():
        name = slug.split("_")[-1]
        files = []
        for i, (label, chunk) in enumerate(split_terms(rows, n_terms, adm_year), start=1):
            p = OUT / slug / f"{i}차학기.xls"
            write_xls(p, chunk, label, sid, name)
            files.append(p.name)
        manifest[slug] = {
            "student_no": sid, "admission_year": adm_year, "files": files,
            "context": {"program_id": "ai_bigdata", "admission_year": adm_year,
                        "convergence_program_ids": ["dsci_convergence"],
                        "convergence_tracks": {"dsci_convergence": "다전공"}, **ctx},
        }
        print(f"{slug}: {len(files)}개 파일, {len(rows)}과목 {sum(r[3] for r in rows):.0f}학점")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n출력: {OUT}")


if __name__ == "__main__":
    main()
