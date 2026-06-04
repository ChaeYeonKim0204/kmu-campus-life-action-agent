import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


client = TestClient(app, raise_server_exceptions=False)

REAL_FILES = [
    "/mnt/c/Users/user/Downloads/1차학기.xls",
    "/mnt/c/Users/user/Downloads/2차학기.xls",
    "/mnt/c/Users/user/Downloads/2학년 하계.xls",
    "/mnt/c/Users/user/Downloads/3차학기.xls",
    "/mnt/c/Users/user/Downloads/3학년 동계.xls",
    "/mnt/c/Users/user/Downloads/4차학기.xls",
    "/mnt/c/Users/user/Downloads/5차학기.xls",
    "/mnt/c/Users/user/Downloads/6차학기.xls",
    "/mnt/c/Users/user/Downloads/7차학기.xls",
]


def post_verify(file_specs, context):
    files = []
    handles = []
    try:
        for filename, content_type, data in file_specs:
            if isinstance(data, (str, Path)):
                h = open(data, "rb")
                handles.append(h)
                files.append(("files", (filename, h, content_type)))
            else:
                files.append(("files", (filename, data, content_type)))
        return client.post("/graduation/v2/verify", files=files, data={"context": context})
    finally:
        for h in handles:
            h.close()


def compact(resp):
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:300]
    return {"status": resp.status_code, "json": isinstance(body, (dict, list)), "body": body}


def show(name, resp):
    print(f"CASE {name}")
    print(json.dumps(compact(resp), ensure_ascii=False, default=str)[:2000])


base_context = {
    "program_id": "ai_bigdata",
    "admission_year": 2022,
    "current_term": "2026-1",
    "remaining_semesters": 2,
    "seasonal_semester_allowed": True,
    "prev_term_gpa_ge_375": True,
    "convergence_program_ids": ["dsci_convergence"],
    "convergence_tracks": {"dsci_convergence": "다전공"},
}

real_specs = [(Path(p).name, "application/vnd.ms-excel", p) for p in REAL_FILES]

verify_ok = post_verify(real_specs, json.dumps(base_context, ensure_ascii=False))
show("verify_real_ok", verify_ok)

if verify_ok.status_code == 200:
    verify_payload = verify_ok.json()
    audit_payload = {
        "context": verify_payload["context"],
        "verification_table": verify_payload["verification_table"],
        "unresolved": verify_payload.get("unresolved", []),
        "possible_retakes": verify_payload.get("possible_retakes", []),
    }
    audit_ok = client.post("/graduation/v2/audit", json=audit_payload)
    show("audit_real_ok", audit_ok)

    mutants = []
    m = copy.deepcopy(audit_payload)
    m["context"]["convergence_program_ids"] = ["unknown_conv_a", "unknown_conv_b"]
    m["context"]["convergence_tracks"] = {"unknown_conv_a": "다전공", "unknown_conv_b": "부전공"}
    mutants.append(("audit_unknown_multi_convergence", m))

    for val in [-1, 13]:
        m = copy.deepcopy(audit_payload)
        m["context"]["remaining_semesters"] = val
        mutants.append((f"audit_remaining_{val}", m))

    m = copy.deepcopy(audit_payload)
    m["context"]["max_credits_per_term"] = 0
    mutants.append(("audit_max_credits_0", m))

    m = copy.deepcopy(audit_payload)
    m["context"]["max_credits_per_term"] = "abc"
    mutants.append(("audit_credits_abc", m))

    for name, payload in mutants:
        show(name, client.post("/graduation/v2/audit", json=payload))


bad_file_cases = [
    ("verify_corrupt_xlsx_zip", [("bad.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04not a workbook")], json.dumps({"program_id": "ai_bigdata"})),
    ("verify_empty_xlsx", [("empty.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"")], json.dumps({"program_id": "ai_bigdata"})),
    ("verify_empty_xls", [("empty.xls", "application/vnd.ms-excel", b"")], json.dumps({"program_id": "ai_bigdata"})),
]
for name, specs, context in bad_file_cases:
    show(name, post_verify(specs, context))

for raw in ["[1,2,3]", '"text"', "null"]:
    show(f"verify_context_{raw}", post_verify(real_specs[:1], raw))

for payload in [
    {"context": [1, 2], "verification_table": []},
    {"context": "text", "verification_table": []},
    {"context": None, "verification_table": []},
    ["not", "object"],
]:
    show(f"audit_context_{type(payload).__name__}_{payload if not isinstance(payload, dict) else type(payload.get('context')).__name__}", client.post("/graduation/v2/audit", json=payload))
