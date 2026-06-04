"""R6 ANGLE 2 & 3: path-gate (C-relax vs D-keep) + mirae invariant."""
from graduation_center.v2.models_v2 import (
    StudentContext, VerifiedCourse, VerifiedTranscript, RequirementProfile, AuditResult, AreaGap,
)
from graduation_center.v2.catalog import load_catalog
from graduation_center.v2.audit_v2 import compute_audit
from graduation_center.v2.planner import run_planner
from graduation_center.v2.risk import compute_risk
from graduation_center.v2.pipeline import run_audit

ai = load_catalog("ai_bigdata")


def mk_vc(c, area="전공"):
    return VerifiedCourse(course_id=c.course_id, name_ko=c.name_ko, credits=c.credits,
                          requirement_area=area, term_label="2022학년도 1학기", included=True)


print("=" * 70)
print("ANGLE 2: extra=1 blocked → 잔여+1 재배치 feasible/infeasible gate")
print("=" * 70)


def build_payload(remaining, n_major_taken, total_min=130, major_min=60, seasonal=False,
                  current="2026-1"):
    # take n major courses, leave the rest as gap
    taken = ai["courses"][:n_major_taken]
    confirmed = [mk_vc(c, "전공") for c in taken]
    earned = sum(c.credits for c in confirmed)
    verified = {
        "context": {"program_id": "ai_bigdata", "admission_year": 2022,
                    "current_term": current, "remaining_semesters": remaining,
                    "seasonal_semester_allowed": seasonal, "gpa_min_met": "yes"},
        "verification_table": [v.model_dump() for v in confirmed],
        "unresolved": [], "possible_retakes": [],
    }
    return verified


# Case A: small gap that needs ~1 extra semester (blocked extra=1), reallocation feasible
# Pick remaining/courses so that gap slightly exceeds capacity
for label, remaining, n_taken in [("blocked extra likely 1", 1, 30), ("tight", 2, 28)]:
    payload = build_payload(remaining, n_taken)
    resp = run_audit(payload, client=None)
    plan = resp.roadmap
    print(f"\n[{label}] remaining={remaining}, taken={n_taken}")
    print(f"  total_gap={resp.audit.total_gap}, status={plan.status}, feasible={plan.feasible}")
    if plan.overflow:
        print(f"  overflow.extra={plan.overflow.extra_semesters}")
    print(f"  risk={resp.risk.grade} {resp.risk.label}")
    for r in resp.risk.reasons:
        if r.factor == "로드맵":
            print(f"    로드맵 reason: {r.detail}")

# Determinism: run twice and compare risk grade + overflow gate decision
print("\n-- Determinism (2x run identical?) --")
payload = build_payload(1, 30)
r1 = run_audit(payload, client=None)
r2 = run_audit(payload, client=None)
print(f"  run1: grade={r1.risk.grade}, status={r1.roadmap.status}, ov={r1.roadmap.overflow.extra_semesters if r1.roadmap.overflow else None}")
print(f"  run2: grade={r2.risk.grade}, status={r2.roadmap.status}, ov={r2.roadmap.overflow.extra_semesters if r2.roadmap.overflow else None}")
print(f"  identical: {r1.risk.grade==r2.risk.grade and r1.report_markdown==r2.report_markdown}")

# Synthetic: directly test the gate in pipeline — feasible plan_plus -> C relax; infeasible -> D keep
print("\n-- Gate logic synthetic (extra=1, +1 sem feasible vs infeasible) --")
# A case where adding 1 semester makes it feasible
payload_f = build_payload(2, 31, seasonal=False)  # leave moderate gap
rf = run_audit(payload_f, client=None)
print(f"  [feasible-ish] gap={rf.audit.total_gap} status={rf.roadmap.status} feasible={rf.roadmap.feasible} grade={rf.risk.grade}")

print("\n" + "=" * 70)
print("ANGLE 3: mirae 데모 불변식")
print("=" * 70)
import subprocess, os
# look for an existing mirae demo fixture/test
