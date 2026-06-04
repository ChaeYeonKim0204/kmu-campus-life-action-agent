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
planner._get_client = lambda: None
v = pipeline.run_verify([(xlsx(major("경영통계","회계학원론")),"a.xlsx")], {"program_id":"ai_bigdata","current_term":"2026-1","remaining_semesters":0,"max_credits_per_term":18,"seasonal_semester_allowed":False})
payload = {"context":v["context"],"verification_table":v["verification_table"],"unresolved":v["unresolved"],"possible_retakes":v["possible_retakes"]}
r = pipeline.run_audit(payload)
print("--- FULL MARKDOWN 추천 로드맵 부분 ---")
md=r.report_markdown
print(md[md.index("## 추천 로드맵"):])
print("--- FRONT chips render: risk.reasons ---")
for x in r.risk.reasons: print("  CHIP:", x.detail)
print("--- FRONT roadmap section conditions ---")
print("  feasible:", r.roadmap.feasible, "blocked_reason:", repr(r.roadmap.blocked_reason)[:120])
print("  relaxation_hint:", repr(r.roadmap.relaxation_hint)[:120])
print("  overflow present:", r.roadmap.overflow is not None, "terms:", len(r.roadmap.terms))
