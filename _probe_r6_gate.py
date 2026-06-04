import io, json
from pathlib import Path
import openpyxl
from graduation_center.v2 import pipeline, planner
CAT = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
COURSES = {c["name_ko"]: c for c in CAT["courses"]}
# show all major courses w/ offered_terms to find a near-complete transcript leaving extra==1
maj=[c for c in CAT["courses"] if c["requirement_area"]=="전공"]
print("major count", len(maj), "total major cr", sum(c["credits"] for c in maj))
for c in maj:
    print(f"  {c['course_id']} {c['name_ko']:18s} cr={c['credits']} req={c['is_required']} terms={c['offered_terms']} prereq={c.get('prerequisites')}")
