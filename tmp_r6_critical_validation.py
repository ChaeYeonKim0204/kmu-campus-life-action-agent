from __future__ import annotations

import copy
import io
import json
import time
from pathlib import Path

import openpyxl
from pydantic import ValidationError

from graduation_center.v2 import pipeline
from graduation_center.v2.catalog import load_catalog, regular_term_cap
from graduation_center.v2.models_v2 import VerifiedCourse


DOWNLOADS = Path("/mnt/c/Users/user/Downloads")
REAL_FILES = [
    "1차학기.xls",
    "2차학기.xls",
    "2학년 하계.xls",
    "3차학기.xls",
    "3학년 동계.xls",
    "4차학기.xls",
    "5차학기.xls",
    "6차학기.xls",
    "7차학기.xls",
]


def xlsx(rows: list[dict], term: str = "2025학년도 1학기") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["2025-2 수강신청 확인서"])
    ws.append(["학번", "", "20250000", "", "", "성명", "", "테스트"])
    ws.append(["수강학기", "", term])
    ws.append([])
    ws.append(["교과목코드", "분반", "", "교과목명", "이수구분", "", "학점", "시간", "", "담당교수", "비고"])
    for r in rows:
        ws.append([
            r.get("code", ""),
            "01",
            "",
            r["name"],
            r.get("area", "전공선택"),
            "",
            r["credits"],
            "",
            "",
            "교수",
            r.get("note", ""),
        ])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def payload_from_verify(v: dict) -> dict:
    return {
        "context": v["context"],
        "verification_table": v["verification_table"],
        "unresolved": v["unresolved"],
        "possible_retakes": v["possible_retakes"],
    }


def run_real() -> dict:
    files = [(DOWNLOADS.joinpath(name).read_bytes(), name) for name in REAL_FILES]
    ctx = {
        "program_id": "ai_bigdata",
        "admission_year": 2025,
        "current_term": "2026-1",
        "remaining_semesters": 2,
        "seasonal_semester_allowed": True,
        "gpa_min_met": "unknown",
    }
    v = pipeline.run_verify(files, ctx)
    resp = pipeline.run_audit(payload_from_verify(v))
    assert resp.audit.total_required > 0
    assert resp.roadmap.status in {"generated", "blocked", "not_generated"}
    resp.model_dump_json()
    return {
        "real_rows": len(v["verification_table"]),
        "real_total": resp.audit.total_earned,
        "real_status": resp.roadmap.status,
        "real_risk": resp.risk.grade,
    }


def make_blocked_extra_one_payload(remaining: int = 1, current_term: str | None = "2026-1") -> dict:
    cat = load_catalog("ai_bigdata")["courses"]
    missing_id = "0910501"  # 인공지능수학, 1학기 전용
    table = []
    total = 0.0
    for c in cat:
        if c.course_id == missing_id:
            continue
        table.append(VerifiedCourse(
            course_id=c.course_id,
            name_ko=c.name_ko,
            credits=c.credits,
            requirement_area=c.requirement_area,
            included=True,
        ).model_dump())
        total += c.credits
    filler = 127.0 - total
    i = 0
    while filler > 0.01:
        i += 1
        cr = min(30.0, round(filler, 1))
        table.append(VerifiedCourse(
            course_id=f"GEN{i:04d}",
            name_ko=f"일반선택충당{i}",
            credits=cr,
            requirement_area="일반선택",
            included=True,
            aggregate_only=True,
        ).model_dump())
        filler = round(filler - cr, 1)
    return {
        "context": {
            "program_id": "ai_bigdata",
            "admission_year": 2025,
            "current_term": current_term,
            "remaining_semesters": remaining,
            "seasonal_semester_allowed": False,
            "gpa_min_met": "yes",
            "max_courses_per_term": 99,
        },
        "verification_table": table,
        "unresolved": [],
        "possible_retakes": [],
    }


def run_blocked_extra_one() -> dict:
    payload = make_blocked_extra_one_payload()
    start = time.monotonic()
    resp = pipeline.run_audit(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 5, elapsed
    assert resp.roadmap.status == "blocked"
    assert resp.roadmap.overflow is not None
    assert resp.roadmap.overflow.extra_semesters == 1
    details = [r.detail for r in resp.risk.reasons if r.factor == "로드맵"]
    assert details and "졸업 경로 존재" in details[-1], details
    assert "실현 가능한 계획 없음" not in details[-1], details
    resp.model_dump_json()
    return {
        "blocked_elapsed": round(elapsed, 4),
        "blocked_risk": resp.risk.grade,
        "blocked_reason": details[-1],
    }


def run_context_edges() -> dict:
    rem12 = make_blocked_extra_one_payload(remaining=12, current_term="2026-1")
    rem12["context"]["max_courses_per_term"] = 5
    resp12 = pipeline.run_audit(rem12)
    assert resp12.context.remaining_semesters == 12
    assert "max_courses_per_term" not in resp12.context.model_dump()
    none_payload = make_blocked_extra_one_payload(remaining=1, current_term=None)
    none_resp = pipeline.run_audit(none_payload)
    assert none_resp.context.current_term is None
    assert none_resp.roadmap.feasible is None
    none_resp.model_dump_json()
    return {
        "rem12_status": resp12.roadmap.status,
        "current_none_status": none_resp.roadmap.status,
        "current_none_feasible": none_resp.roadmap.feasible,
    }


def run_credit_edges() -> dict:
    results = {}
    base = make_blocked_extra_one_payload()
    idx = 0
    for value, expected in [
        (True, "reject"),
        (" 3 ", "convert"),
        ("3e0", "convert"),
        ("삼", "reject"),
        ("Decimal('3')", "reject"),
        ("31", "reject"),
        ("-1", "reject"),
    ]:
        payload = copy.deepcopy(base)
        payload["verification_table"][idx]["credits"] = value
        try:
            resp = pipeline.run_audit(payload)
            got = resp.verified_transcript.confirmed_courses[idx].credits
            if expected == "reject":
                raise AssertionError(f"{value!r} accepted as {got}")
            assert got == 3.0, (value, got)
            results[repr(value)] = got
        except (ValueError, ValidationError):
            if expected != "reject":
                raise
            results[repr(value)] = "rejected"
    return results


def run_synthetic_dsci_three_rounds() -> dict:
    ai = load_catalog("ai_bigdata")["courses"]
    dsci = load_catalog("dsci_convergence")["courses"]
    rows = []
    total = 0.0
    for c in ai:
        rows.append({"code": c.course_id, "name": c.name_ko, "credits": c.credits, "area": "전공선택"})
        total += c.credits
    for c in dsci:
        if c.course_id not in {a.course_id for a in ai}:
            rows.append({"code": c.course_id, "name": c.name_ko, "credits": c.credits, "area": "전공선택"})
            total += c.credits
        if total >= 142:
            break
    v = pipeline.run_verify(
        [(xlsx(rows), "synthetic_dsci.xlsx")],
        {
            "program_id": "ai_bigdata",
            "admission_year": 2025,
            "current_term": "2026-1",
            "remaining_semesters": 3,
            "seasonal_semester_allowed": True,
            "convergence_program_ids": ["dsci_convergence"],
            "convergence_tracks": {"dsci_convergence": "다전공"},
            "gpa_min_met": "yes",
        },
    )
    payload = payload_from_verify(v)
    outputs = []
    for _ in range(3):
        resp = pipeline.run_audit(payload)
        dumped = resp.model_dump_json()
        loaded = json.loads(dumped)
        payload = {
            "context": loaded["context"],
            "verification_table": loaded["verified_transcript"]["confirmed_courses"],
            "unresolved": [],
            "possible_retakes": loaded["verified_transcript"].get("possible_retakes", []),
        }
        outputs.append({
            "risk": resp.risk.grade,
            "status": resp.roadmap.status,
            "conv": len(resp.audit.convergence_checks),
            "total": resp.audit.total_earned,
        })
    assert all(o["conv"] == 1 for o in outputs), outputs
    assert outputs[0] == outputs[1] == outputs[2], outputs
    return {"dsci_rounds": outputs[0], "rows": len(v["verification_table"])}


def main() -> None:
    summary = {}
    summary.update(run_real())
    summary.update(run_blocked_extra_one())
    summary.update(run_context_edges())
    summary["credit_edges"] = run_credit_edges()
    summary.update(run_synthetic_dsci_three_rounds())
    summary["caps"] = {str(k): regular_term_cap(k) for k in (120, 130, 136)}
    assert summary["caps"] == {"120": 17.0, "130": 18.0, "136": 19.0}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
