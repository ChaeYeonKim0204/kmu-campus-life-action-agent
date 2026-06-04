import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


client = TestClient(app, raise_server_exceptions=False)
REAL = Path("/mnt/c/Users/user/Downloads/1차학기.xls")


def show(name, resp):
    try:
        body = resp.json()
        json_ok = True
    except Exception:
        body = resp.text[:500]
        json_ok = False
    print(f"{name}: status={resp.status_code} json={json_ok} body={json.dumps(body, ensure_ascii=False, default=str)[:1200]}", flush=True)


def verify(name, filename, data, context):
    if isinstance(data, Path):
        with data.open("rb") as h:
            resp = client.post(
                "/graduation/v2/verify",
                files=[("files", (filename, h, "application/vnd.ms-excel"))],
                data={"context": context},
            )
    else:
        resp = client.post(
            "/graduation/v2/verify",
            files=[("files", (filename, data, "application/octet-stream"))],
            data={"context": context},
        )
    show(name, resp)
    return resp


ctx = {"program_id": "ai_bigdata", "admission_year": 2022, "current_term": "2026-1", "remaining_semesters": 2}
verify("verify_real_one_ok", REAL.name, REAL, json.dumps(ctx, ensure_ascii=False))
verify("verify_corrupt_xlsx_zip", "bad.xlsx", b"PK\x03\x04not a workbook", json.dumps({"program_id": "ai_bigdata"}))
verify("verify_empty_xlsx", "empty.xlsx", b"", json.dumps({"program_id": "ai_bigdata"}))
verify("verify_empty_xls", "empty.xls", b"", json.dumps({"program_id": "ai_bigdata"}))
verify("verify_context_list", REAL.name, REAL, "[1,2,3]")
verify("verify_context_str", REAL.name, REAL, '"text"')
verify("verify_context_null", REAL.name, REAL, "null")

minimal = {"context": ctx, "verification_table": [], "unresolved": [], "possible_retakes": []}
show("audit_minimal_ok", client.post("/graduation/v2/audit", json=minimal))

for name, context_value in [
    ("audit_context_list", [1, 2, 3]),
    ("audit_context_str", "text"),
    ("audit_context_null", None),
]:
    show(name, client.post("/graduation/v2/audit", json={"context": context_value, "verification_table": []}))

for name, patch in [
    ("audit_unknown_multi_convergence", {"convergence_program_ids": ["unknown_a", "unknown_b"], "convergence_tracks": {"unknown_a": "다전공", "unknown_b": "부전공"}}),
    ("audit_remaining_minus_1", {"remaining_semesters": -1}),
    ("audit_remaining_13", {"remaining_semesters": 13}),
    ("audit_max_credits_0", {"max_credits_per_term": 0}),
    ("audit_credits_abc", {"max_credits_per_term": "abc"}),
]:
    p = json.loads(json.dumps(minimal, ensure_ascii=False))
    p["context"].update(patch)
    show(name, client.post("/graduation/v2/audit", json=p))
