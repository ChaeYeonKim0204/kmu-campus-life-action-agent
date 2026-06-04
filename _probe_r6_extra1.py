import io, json
from pathlib import Path
import openpyxl
from graduation_center.v2 import pipeline, planner
from graduation_center.v2.planner import run_planner, project_overflow
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

# Build a transcript where only a small gap remains so overflow.extra would be 1.
# Take nearly all courses except a few, remaining_semesters=1, low term cap to force extra=1.
allmaj=[c["name_ko"] for c in CAT["courses"] if c["requirement_area"]=="전공"]
# take all but 2 majors -> small remaining major gap; plus we need total 130, so still big general gap.
# Instead: target a controlled scenario by scanning remaining_semesters & cap to find extra==1 blocked.
planner._get_client = lambda: None
import itertools
# Use a fairly complete transcript: all majors + many electives to push earned high, leaving ~ one-term gap
rows = major(*allmaj)  # 113 major credits
# add fake general credits via extra area rows
for i in range(4):
    rows.append({"code":"","name":f"교양과목{i}","credits":3.0,"area":"자유교양"})
for cap in (18,12,9,6):
  for rem in (1,2):
    v = pipeline.run_verify([(xlsx(rows),"a.xlsx")], {"program_id":"ai_bigdata","current_term":"2026-1","remaining_semesters":rem,"max_credits_per_term":cap,"seasonal_semester_allowed":False})
    payload = {"context":v["context"],"verification_table":v["verification_table"],"unresolved":v["unresolved"],"possible_retakes":v["possible_retakes"]}
    r = pipeline.run_audit(payload)
    ov=r.roadmap.overflow
    rm=[x.detail for x in r.risk.reasons if x.factor=="로드맵"]
    if ov is not None:
        print(f"cap={cap} rem={rem} grade={r.risk.grade} status={r.roadmap.status} ov.extra={ov.extra_semesters} card_present=True | RISK로드맵={rm}")
        print(f"    gap={r.audit.total_gap}")
