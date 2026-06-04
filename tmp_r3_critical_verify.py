from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from graduation_center.v2 import pipeline
from graduation_center.v2.audit_v2 import compute_audit
from graduation_center.v2.catalog import assemble_requirement_profile, regular_term_cap
from graduation_center.v2.models_v2 import AuditResult, AreaGap, RequirementProfile, StudentContext, VerifiedTranscript
from graduation_center.v2.planner import _ordered_terms, run_planner
from graduation_center.v2.verification import finalize_transcript


REAL_FILES = [
    Path("/mnt/c/Users/user/Downloads/1차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/2차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/2학년 하계.xls"),
    Path("/mnt/c/Users/user/Downloads/3차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/3학년 동계.xls"),
    Path("/mnt/c/Users/user/Downloads/4차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/5차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/6차학기.xls"),
    Path("/mnt/c/Users/user/Downloads/7차학기.xls"),
]


def _client_files(paths):
    out = []
    for p in paths:
        out.append(("files", (p.name, p.read_bytes(), "application/vnd.ms-excel")))
    return out


def api_guard_checks():
    client = TestClient(app)
    valid_one = _client_files([REAL_FILES[0]])

    bad_primary = client.post(
        "/graduation/v2/verify",
        files=valid_one,
        data={"context": json.dumps({"program_id": "dsci_convergence"}, ensure_ascii=False)},
    )
    broken_json = client.post(
        "/graduation/v2/verify",
        files=valid_one,
        data={"context": "{bad json"},
    )
    damaged_excel = client.post(
        "/graduation/v2/verify",
        files=[("files", ("broken.xls", b"not an excel file", "application/vnd.ms-excel"))],
        data={"context": json.dumps({"program_id": "ai_bigdata"}, ensure_ascii=False)},
    )
    return {
        "bad_primary_status": bad_primary.status_code,
        "bad_primary_detail": bad_primary.json().get("detail"),
        "broken_json_status": broken_json.status_code,
        "damaged_excel_status": damaged_excel.status_code,
    }


def real_data_e2e():
    files = [(p.read_bytes(), p.name) for p in REAL_FILES]
    contexts = [
        {
            "program_id": "mirae_mobility",
            "admission_year": 2022,
            "current_term": "2026-1",
            "remaining_semesters": 2,
            "seasonal_semester_allowed": True,
            "prev_term_gpa_ge_375": True,
            "convergence_program_ids": ["mobility_data_convergence", "dsci_convergence"],
            "convergence_tracks": {
                "mobility_data_convergence": "다전공",
                "dsci_convergence": "부전공",
            },
        },
        {
            "program_id": "ai_bigdata",
            "admission_year": 2022,
            "current_term": "2026-1",
            "remaining_semesters": 2,
            "seasonal_semester_allowed": True,
            "prev_term_gpa_ge_375": True,
            "convergence_program_ids": ["dsci_convergence", "mobility_data_convergence"],
            "convergence_tracks": {
                "dsci_convergence": "다전공",
                "mobility_data_convergence": "부전공",
            },
        },
    ]
    out = []
    for ctx in contexts:
        v = pipeline.run_verify(files, ctx)
        payload = {
            "context": v["context"],
            "verification_table": v["verification_table"],
            "unresolved": v["unresolved"],
            "possible_retakes": v["possible_retakes"],
        }
        resp = pipeline.run_audit(payload)
        out.append(
            {
                "program_id": ctx["program_id"],
                "verified": len(v["verification_table"]),
                "total": resp.audit.total_earned,
                "roadmap_status": resp.roadmap.status,
                "overflow": resp.roadmap.overflow.model_dump() if resp.roadmap.overflow else None,
                "convergence": [
                    {
                        "program_id": c["program_id"],
                        "track": c["track"],
                        "earned": c["earned"],
                        "gap": c["gap"],
                        "double_cap": c["double_cap"],
                        "double_used": c["double_used"],
                    }
                    for c in resp.audit.convergence_checks
                ],
                "markdown_has_partial": (
                    resp.roadmap.status == "blocked"
                    and bool(resp.roadmap.terms)
                    and "일부만 배치 가능" in resp.report_markdown
                ),
            }
        )
    return out


def numeric_lenses():
    caps = {120: regular_term_cap(120), 130: regular_term_cap(130), 136: regular_term_cap(136)}
    ctx = StudentContext(program_id="ai_bigdata", current_term="2026-1", remaining_semesters=2, prev_term_gpa_ge_375=True, seasonal_semester_allowed=True)
    terms = _ordered_terms(ctx, regular_term_cap(130))

    profile = RequirementProfile(program_id="ai_bigdata", total_credits_min=130, area_min={"전공": 0})
    audit = AuditResult(total_required=130, total_earned=120, total_gap=10, area_gaps=[AreaGap(area="전공", required=0, earned=0, gap=0)])
    plan, report, _ = run_planner(audit, profile, ctx, VerifiedTranscript())
    return {
        "caps": caps,
        "ordered_terms": terms,
        "general_gap_plan_status": plan.status,
        "general_gap_term_credits": [t.term_credits for t in plan.terms],
        "validator_ok": report.ok,
    }


if __name__ == "__main__":
    print(json.dumps({
        "api_guards": api_guard_checks(),
        "real_data_e2e": real_data_e2e(),
        "numeric_lenses": numeric_lenses(),
    }, ensure_ascii=False, indent=2, default=str))
