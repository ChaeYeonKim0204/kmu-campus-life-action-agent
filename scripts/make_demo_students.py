"""데모 학생 수강내역 .xls 생성기 — AI빅데이터융합경영 제1전공 + 데이터사이언스융합전공(다전공).

ON국민 수강신청확인서 형식(.xls, 학기당 1파일)으로 4명의 합성 학생을 만든다.
실제 카탈로그(catalog_ai_bigdata / catalog_dsci_convergence / gen_ed_catalog)에서
과목을 뽑으므로 코드 매칭·중복인정·그룹최저가 실데이터처럼 동작한다.

실제 학생처럼 보이게:
- 과목 배치는 요람 학년(grade_level)·개설학기(offered_terms) 기준 — 1학년은 교양+기초전공,
  고학년으로 갈수록 전공·융합 심화.
- 학기당 학점은 법정 상한(정규 18 · 계절 6, 제32조) 준수 — 넘치면 하계/동계 파일로 분리.
- 일반선택은 실제 같은 타과 과목명 풀에서, 핵심교양은 교양과정 실과목명에서 학생별로 다르게.
- 같은 과목 중복 행(재수강 서사)은 두 학기 이상 떨어뜨려 배치.

  S1 졸업반   — 잔여 1학기, 제1전공·교양 충족, dsci 겹침 21>캡12(3-way 트레이드오프)
  S2 3학년    — dsci B그룹 0학점(그룹최저 공백), 잔여 3학기 → 로드맵이 B그룹 배치
  S3 2학년    — 잔여 2학기 선언 대비 갭 큼 → blocked + 초과학기 시나리오(D)
  S4 4학년    — 계절 허용 + 직전학기 3.75↑(+3) → feasible 로드맵

주의: 학과는 2022학년도 신설 — 최저 학번 2022.
실행:  PYTHONPATH=. python scripts/make_demo_students.py
출력:  data/graduation/v2/demo_students/<학생>/<n차학기|n학년 하계·동계>.xls
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
DS_BY_ID5 = {c["course_id"][:5]: c for c in DS["courses"] if c.get("course_id")}
REQUIRED = [c for c in AI["courses"] if c.get("is_required")]
ELECTIVE = [c for c in AI["courses"] if not c.get("is_required")]
OVERLAP_A = [c for c in DS["courses"] if c["course_id"][:5] in AI5 and c.get("group") == "A그룹"]
OVERLAP_B = [c for c in DS["courses"] if c["course_id"][:5] in AI5 and c.get("group") == "B그룹"]
DS_ONLY_B = [c for c in DS["courses"] if c["course_id"][:5] not in AI5 and c.get("group") == "B그룹"]

REG_CAP, SEASONAL_CAP = 18.0, 6.0

# 일반선택(타과) — 실제 같은 과목명 풀 (가짜 코드 → 카탈로그 밖 집계로 흐름)
ETC_POOL = [
    "심리학개론", "경제와사회", "일본어입문Ⅰ", "중국어회화Ⅰ", "서양미술의이해",
    "현대사회와법", "스타트업과기업가정신", "소비자행동의이해", "광고와대중문화",
    "영화로읽는세계사", "환경과인간", "글로벌시사영어", "협상과설득의기술",
    "디지털콘텐츠기획", "행동경제학입문", "동아시아근현대사", "스포츠마케팅",
    "미디어와젠더", "도시와공간의사회학", "빅히스토리",
]
# 기초교양 8학점(2022~2024학번 시트: 글쓰기3·College Eng/Conv 택1 2·글로벌영어1 + 영역 잔여 2)
BASIC_ROWS = [("글쓰기", 3), ("College EnglishⅠ", 2), ("컴퓨팅적사고", 2), ("글로벌영어", 1)]
FREE_POOL = [("스포츠와건강", 1), ("생활속의화학", 2), ("클래식음악의이해", 1), ("와인과세계문화", 2)]

_FAKE = [9000000]


def _fc() -> str:
    """카탈로그 밖(교양·타과) 과목용 가짜 7자리 교과목코드."""
    _FAKE[0] += 1
    return str(_FAKE[0])


def _pref(course: dict) -> int:
    """요람 학년·개설학기 → 선호 학기 인덱스(0=1-1)."""
    gl = course.get("grade_level") or 2
    term0 = (course.get("offered_terms") or ["1"])[0]
    return (gl - 1) * 2 + (0 if term0 == "1" else 1)


def major(cs):
    return [{"code": c["course_id"], "name": c["name_ko"], "area": "전공선택",
             "credits": c["credits"], "pref": _pref(c)} for c in cs]


def ds_only(cs):  # dsci 전용 과목은 일반선택 이수구분으로 수강 — 융합은 보통 2~3학년부터
    return [{"code": c["course_id"], "name": c["name_ko"], "area": "일반선택",
             "credits": c["credits"], "pref": max(4, _pref(c))} for c in cs]


def gened(offset=0, n_per_area=1):  # 핵심교양 — 실과목명, 학생별 offset으로 다양화. 1~2학년 분산.
    rows = []
    for ai_, (_area, cs) in enumerate(GEN["courses_by_area"].items()):
        for j in range(n_per_area):
            c = cs[(offset + j) % len(cs)]
            rows.append({"code": _fc(), "name": c["name_ko"], "area": "핵심교양",
                         "credits": c["credits"], "pref": ai_ % 4})
    return rows


def basic():
    return [{"code": _fc(), "name": n, "area": "기초교양", "credits": cr, "pref": i % 2}
            for i, (n, cr) in enumerate(BASIC_ROWS)]


def free(offset=0, n=2):
    return [{"code": _fc(), "name": FREE_POOL[(offset + i) % len(FREE_POOL)][0], "area": "자유교양",
             "credits": FREE_POOL[(offset + i) % len(FREE_POOL)][1], "pref": 2 + i} for i in range(n)]


def etc(n, offset=0):  # 일반선택 3학점 × n — 전 학기에 고르게(pref None → 스케줄러가 분산)
    return [{"code": _fc(), "name": ETC_POOL[(offset + i) % len(ETC_POOL)], "area": "일반선택",
             "credits": 3, "pref": None} for i in range(n)]


def schedule(rows: list[dict], n_terms: int, start_year: int):
    """학년·개설학기 선호 + 법정 상한(정규 18·계절 6)으로 학기 배치.

    반환: [(파일명, 학기라벨, rows)] — 정규 'n차학기', 넘침은 'n학년 하계/동계'.
    """
    # pref None(일반선택)은 전 학기에 고르게 분산
    nones = [r for r in rows if r["pref"] is None]
    for i, r in enumerate(nones):
        r["pref"] = (i * n_terms) // max(1, len(nones))
    # 같은 과목 중복(재수강 서사)은 두 번째 행을 2학기 뒤로
    seen: dict[str, int] = {}
    for r in rows:
        k = r["code"]
        if k in seen:
            r["pref"] = min(n_terms - 1, seen[k] + 2)
        else:
            seen[k] = min(n_terms - 1, max(0, r["pref"]))
    ordered = sorted(rows, key=lambda r: (min(n_terms - 1, max(0, r["pref"])),
                                          {"기초교양": 0, "핵심교양": 1, "전공선택": 2}.get(r["area"], 3)))
    reg = [[] for _ in range(n_terms)]
    season: dict[int, list] = {}                       # 정규 i 뒤 계절(하계=짝수 i, 동계=홀수 i)
    for r in ordered:
        p = min(n_terms - 1, max(0, r["pref"]))
        placed = False
        for t in list(range(p, n_terms)) + list(range(p - 1, -1, -1)):   # 뒤로 밀고, 안 되면 앞으로
            if sum(x["credits"] for x in reg[t]) + r["credits"] <= REG_CAP:
                reg[t].append(r)
                placed = True
                break
        if not placed:                                  # 정규 전부 만석 → 계절학기
            for t in range(n_terms):
                pool = season.setdefault(t, [])
                if sum(x["credits"] for x in pool) + r["credits"] <= SEASONAL_CAP:
                    pool.append(r)
                    placed = True
                    break
        assert placed, f"배치 실패: {r['name']}"
    # 외톨이 학기 정리: 6학점 미만 정규학기는 앞 학기 여유로 흡수(1과목짜리 학기 어색함 방지)
    for t in range(n_terms - 1, 0, -1):
        if reg[t] and sum(x["credits"] for x in reg[t]) < 6:
            for r in list(reg[t]):
                for u in range(t - 1, -1, -1):
                    if sum(x["credits"] for x in reg[u]) + r["credits"] <= REG_CAP:
                        reg[u].append(r)
                        reg[t].remove(r)
                        break
    out = []
    for i in range(n_terms):
        year, sem = start_year + i // 2, 1 + i % 2
        if reg[i]:
            out.append((f"{i + 1}차학기.xls", f"{year}학년도 {sem}학기", reg[i]))
        if season.get(i):
            grade = i // 2 + 1
            kind = "하계" if sem == 1 else "동계"
            out.append((f"{grade}학년 {kind}.xls", f"{year}학년도 {kind} 계절학기", season[i]))
    return out


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
        vals = [r["code"], "01", "", r["name"], r["area"], "", r["credits"], "", "", "교수", ""]
        for col, val in enumerate(vals):
            ws.write(5 + i, col, val)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def build_students():
    # S1 졸업반 — 겹침 21(A그룹 18 + 선형대수 B 3) > 캡 12
    s1_major = [c for c in REQUIRED if "캡스톤디자인Ⅱ" not in c["name_ko"]]
    ov7 = OVERLAP_A[:6] + OVERLAP_B[:1]
    # 겹침 과목은 제1전공 개설본 코드로 수강(예: 선형대수 0155708 — dsci 쪽 0155707은
    # 소프트웨어전공 개설본. 앞 5자리 동일교과목이라 판정은 같지만 실제 수강 패턴에 맞춤)
    s1_major += [AI_BY_NAME[c["name_ko"]] for c in ov7
                 if AI_BY_NAME.get(c["name_ko"]) and not AI_BY_NAME[c["name_ko"]].get("is_required")]
    need = 48 - sum(c["credits"] for c in s1_major)
    ov5 = {o["course_id"][:5] for o in ov7}
    s1_major += [c for c in ELECTIVE if c not in s1_major and c["course_id"][:5] not in ov5][: max(0, int(need // 3) + 1)]
    s1 = major(s1_major) + ds_only(DS_ONLY_B[:5]) + gened(0) + basic() + free(0, 2) + etc(15, 0)

    # S2 3학년 — dsci A그룹만(B그룹 0) → 그룹최저 부족. 1학년 필수는 전부 이수,
    # 고학년 필수(회귀분석·머신러닝·딥러닝)만 미이수 — 자연스러운 학년 진행
    req_y1 = [c for c in REQUIRED if (c.get("grade_level") or 9) <= 1]
    s2_major = [AI_BY_NAME.get(c["name_ko"], c) for c in req_y1 + OVERLAP_A[:4]]
    s2 = major([c for c in s2_major if c.get("course_id")]) + gened(1) + basic() + etc(6, 5)

    # S3 2학년 — 갭 큼 + 잔여 2학기 선언 → blocked·초과학기(D)
    s3 = major(REQUIRED[:3]) + ds_only(DS_ONLY_B[:2]) + basic() + gened(2)[:2] + etc(3, 11)
    for r in s3:                                       # 1학년 마친 학생 — 전부 1~2차학기 안으로
        r["pref"] = min(r["pref"], 1) if r["pref"] is not None else None

    # S4 4학년 — 계절+성적우수 → feasible. 1학년 필수 전부 + 회귀·머신러닝 이수,
    # 딥러닝(3~4학년)만 남음 — 졸업반이 막학기에 채우는 그림
    s4_req = req_y1 + [AI_BY_NAME[n] for n in ("회귀분석", "머신러닝") if n in AI_BY_NAME]
    s4_major = [AI_BY_NAME.get(c["name_ko"], c) for c in s4_req + OVERLAP_A[:5]]
    s4 = major([c for c in s4_major if c.get("course_id")]) + ds_only(DS_ONLY_B[:3]) + gened(3) + basic() + free(2, 2) + etc(10, 14)

    return [
        ("S1_졸업반_김융합", "20220001", s1, 7, 2022,
         {"current_term": "2026-1", "remaining_semesters": 1, "gpa_min_met": "yes"}),
        ("S2_3학년_박분석", "20220002", s2, 5, 2022,
         {"current_term": "2025-2", "remaining_semesters": 3, "gpa_min_met": "yes"}),
        ("S3_2학년_이지연", "20240003", s3, 2, 2024,
         {"current_term": "2025-1", "remaining_semesters": 2, "gpa_min_met": "unknown"}),
        ("S4_4학년_최계절", "20220004", s4, 6, 2022,
         {"current_term": "2026-1", "remaining_semesters": 2,
          "seasonal_semester_allowed": True, "prev_term_gpa_ge_375": True, "gpa_min_met": "yes"}),
    ]


def main():
    manifest = {}
    for slug, sid, rows, n_terms, adm_year, ctx in build_students():
        name = slug.split("_")[-1]
        terms = schedule(rows, n_terms, adm_year)
        files = []
        for fname, label, chunk in terms:
            write_xls(OUT / slug / fname, chunk, label, sid, name)
            files.append(fname)
        manifest[slug] = {
            "student_no": sid, "admission_year": adm_year, "files": files,
            "context": {"program_id": "ai_bigdata", "admission_year": adm_year,
                        "convergence_program_ids": ["dsci_convergence"],
                        "convergence_tracks": {"dsci_convergence": "다전공"}, **ctx},
        }
        loads = [f"{l.split('.')[0]}={sum(r['credits'] for r in c):.0f}" for l, _, c in terms]
        print(f"{slug}: {len(files)}개 파일 {sum(r['credits'] for r in rows):.0f}학점 | {' '.join(loads)}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n출력: {OUT}")


if __name__ == "__main__":
    main()
