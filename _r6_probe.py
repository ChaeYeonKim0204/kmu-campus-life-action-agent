"""R6 verification — ai_bigdata+dsci 다전공 축, overlap>cap math, path-gate, dsci group-min."""
import json
from graduation_center.v2.models_v2 import (
    StudentContext, VerifiedCourse, VerifiedTranscript, RequirementProfile,
)
from graduation_center.v2.catalog import load_catalog, assemble_requirement_profile
from graduation_center.v2.audit_v2 import compute_audit, _convergence_checks
from graduation_center.v2.planner import run_planner
from graduation_center.v2.risk import compute_risk

ai = load_catalog("ai_bigdata")
ds = load_catalog("dsci_convergence")
ai_pref = {c.course_id[:5] for c in ai["courses"] if c.course_id}
ds_courses = ds["courses"]


def mk_vc(c, area="전공"):
    return VerifiedCourse(course_id=c.course_id, name_ko=c.name_ko, credits=c.credits,
                          requirement_area=area, term_label="2022학년도 1학기", included=True)


# ============ ANGLE 1: overlap 21 (cap 12) distribution ============
# Build a student who took dsci overlap courses worth 21 credits (overlap-with-AI),
# all also belonging to AI major catalog. Plus dsci fusion-only courses.
print("=" * 70)
print("ANGLE 1: overlap>cap 배분 산술 (overlap=21, cap=12)")
print("=" * 70)

# overlap dsci courses (those whose prefix in ai_pref). Take 7 of them = 21 credits.
overlap_dsci = [c for c in ds_courses if c.course_id[:5] in ai_pref]
overlap_pick = overlap_dsci[:7]  # 7 * 3 = 21 credits overlap
assert abs(sum(c.credits for c in overlap_pick) - 21.0) < 0.01, sum(c.credits for c in overlap_pick)
# fusion-only dsci courses (prefix NOT in ai) — take some B그룹 ones to make groups
fusion_only = [c for c in ds_courses if c.course_id[:5] not in ai_pref][:6]  # 18 credits fusion-only

confirmed = [mk_vc(c, "전공") for c in overlap_pick] + [mk_vc(c, "전공") for c in fusion_only]
# also add extra pure-AI major courses to push primary major earned high
extra_ai = [c for c in ai["courses"] if c.course_id[:5] not in {x.course_id[:5] for x in overlap_pick}][:8]
confirmed += [mk_vc(c, "전공") for c in extra_ai]

primary_earned = sum(c.credits for c in confirmed)  # all tagged 전공
print(f"제1전공(전공) earned total = {primary_earned}")
print(f"overlap dsci picked = {[c.name_ko for c in overlap_pick]} -> 21cr")
print(f"fusion-only dsci = {[c.name_ko for c in fusion_only]} -> 18cr")

verified = VerifiedTranscript(confirmed_courses=confirmed,
                              earned_by_area={"전공": primary_earned},
                              total_earned=primary_earned)

# primary major required: use ai requirement; assume 60
checks = _convergence_checks(verified, ["dsci_convergence"], {"dsci_convergence": "다전공"},
                             "ai_bigdata", primary_major_required=60.0,
                             primary_major_earned=primary_earned)
cc = checks[0]
print(f"\noverlap_credits = {cc['overlap_credits']} (expect 21)")
print(f"double_cap = {cc['double_cap']} (expect 12)")
print(f"double_used (dup) = {cc['double_used']} (expect 12)")
print(f"fusion_base (non-overlap) = {cc['fusion_base']} (expect 18)")
print(f"primary_base (primary non-overlap) = {cc['primary_base']}")
print(f"to_fusion_credits = {cc['to_fusion_credits']}")
print(f"fusion_effective = {cc['fusion_effective']}")
print(f"primary_effective = {cc['primary_effective']}")
print(f"earned(=fusion_eff) = {cc['earned']}, gap = {cc['gap']}")
print(f"designated_total = {cc['designated_total']} (expect 39)")
# Invariant: fusion_eff = fusion_base + dup + to_fusion
calc = round(cc['fusion_base'] + cc['double_used'] + cc['to_fusion_credits'], 1)
print(f"CHECK fusion_eff == fusion_base+dup+to_fusion : {cc['fusion_effective']} == {calc} -> {abs(cc['fusion_effective']-calc)<0.01}")
# Invariant: dup + to_primary + to_fusion = overlap (every overlap course assigned once)
flex_total = round(cc['overlap_credits'] - cc['double_used'], 1)
to_primary = round(cc['primary_effective'] - cc['primary_base'] - cc['double_used'], 1)
print(f"to_primary(derived) = {to_primary}, to_fusion = {cc['to_fusion_credits']}, sum flex = {round(to_primary+cc['to_fusion_credits'],1)} (expect {flex_total})")

# primary major clamp & dedup in audit
prof = RequirementProfile(program_id="ai_bigdata", total_credits_min=130,
                          area_min={"전공": 60}, admission_year=2022)
audit = compute_audit(verified, prof, convergence_program_ids=["dsci_convergence"],
                      convergence_tracks={"dsci_convergence": "다전공"})
major_gap = next(g for g in audit.area_gaps if g.area == "전공")
print(f"\nto_fusion_total = {audit.to_fusion_total}")
print(f"전공 area: earned(effective) = {major_gap.earned}, required={major_gap.required}, gap={major_gap.gap}")
print(f"  expect earned = {primary_earned} - {audit.to_fusion_total} = {primary_earned - audit.to_fusion_total}")

# ============ ANGLE 4: dsci group-min loaded from group_rules (12) ============
print("\n" + "=" * 70)
print("ANGLE 4: dsci 다전공 per_group_min from group_rules (expect 12)")
print("=" * 70)
print(f"per_group_min = {cc['per_group_min']} (expect 12.0)")
for gc in cc["group_checks"]:
    print(f"  {gc['group']}: earned={gc['earned']}, required={gc['required']}, gap={gc['gap']}")
# B그룹 0 student
print("\n-- B그룹 0 학생 (only A그룹 dsci taken) --")
a_only = [c for c in ds_courses if c.group == "A그룹"][:5]  # 15 credits A only
conf2 = [mk_vc(c, "전공") for c in a_only]
v2 = VerifiedTranscript(confirmed_courses=conf2, earned_by_area={"전공": 15}, total_earned=15)
ck2 = _convergence_checks(v2, ["dsci_convergence"], {"dsci_convergence": "다전공"},
                          "ai_bigdata", 60.0, 15)[0]
for gc in ck2["group_checks"]:
    print(f"  {gc['group']}: earned={gc['earned']}, required={gc['required']}, gap={gc['gap']}")
b_gap = next(gc["gap"] for gc in ck2["group_checks"] if gc["group"] == "B그룹")
print(f"B그룹 gap = {b_gap} (expect 12)")
