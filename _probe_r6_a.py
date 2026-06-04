import io, json
from pathlib import Path
import openpyxl
from graduation_center.v2 import pipeline, planner

CAT = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
COURSES = {c["name_ko"]: c for c in CAT["courses"]}

def xlsx(rows, term="2024학년도 1학기"):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["수강신청 확인서"]); ws.append(["학번","","20240000","","","성명","","T"])
    ws.append(["수강학기","",term]); ws.append([])
    ws.append(["교과목코드","분반","","교과목명","이수구분","","학점","시간","","담당교수","비고"])
    for r in rows:
        ws.append([r["code"],"01","",r["name"],r.get("area","전공선택"),"",r["credits"],"","","교수",""])
    b=io.BytesIO(); wb.save(b); return b.getvalue()

def major(*names):
    return [{"code":COURSES[n]["course_id"],"name":n,"credits":COURSES[n]["credits"]} for n in names]

def run(rows, ctx_extra, label):
    planner._get_client = lambda: None
    v = pipeline.run_verify([(xlsx(rows),"a.xlsx")], {"program_id":"ai_bigdata", **ctx_extra})
    payload = {"context":v["context"],"verification_table":v["verification_table"],
               "unresolved":v["unresolved"],"possible_retakes":v["possible_retakes"]}
    r = pipeline.run_audit(payload)
    print("="*70)
    print(f"[{label}] grade={r.risk.grade} status={r.roadmap.status} feasible={r.roadmap.feasible}")
    print("  total_gap=", r.audit.total_gap, "earned=", r.audit.total_earned, "req=", r.audit.total_required)
    print("  RISK 로드맵 reason:", [x.detail for x in r.risk.reasons if x.factor=="로드맵"])
    ov = r.roadmap.overflow
    print("  roadmap.overflow:", None if ov is None else f"extra={ov.extra_semesters} total_needed={ov.total_semesters_needed} shortfall={ov.shortfall_credits}")
    md = r.report_markdown
    if "초과학기 예상 시나리오" in md:
        seg = md.split("## ⚠️ 초과학기 예상 시나리오")[1]
        print("  MD overflow section:", [l for l in seg.strip().splitlines()[:3]])
    else:
        print("  MD overflow section: <none>")
    print("  MD has '실현 가능한 계획 없음':", "실현 가능한 계획 없음" in md)
    for e in r.node_trace:
        if e.node in ("로드맵 배치","로드맵 검증","리스크 산정"):
            print(f"  TRACE {e.node}: status={e.status} branch={e.branch_taken!r}")
    return r

run(major("경영통계","회계학원론"), {"current_term":"2026-1","remaining_semesters":1,"max_credits_per_term":18,"seasonal_semester_allowed":False}, "rem=1 small")
run(major("경영통계"), {"current_term":"2026-1","remaining_semesters":2,"max_credits_per_term":18,"seasonal_semester_allowed":False}, "rem=2 huge gap")
run(major("경영통계","회계학원론"), {"current_term":"2026-1","remaining_semesters":0,"max_credits_per_term":18,"seasonal_semester_allowed":False}, "rem=0")
