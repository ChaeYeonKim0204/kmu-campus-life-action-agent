from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from graduation_center.v2 import pipeline


FILES = [
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


def nth_regular(current: str | None, n: int) -> str | None:
    if not current or n <= 0:
        return None
    try:
        y_s, sem = current.split("-")
        y = int(y_s)
        order = {"1": 1, "S": 2, "2": 3, "W": 4}[sem]
    except Exception:
        return None
    labels = {1: "1", 3: "2"}
    count = 0
    for _ in range(60):
        order += 1
        if order > 4:
            order = 1
            y += 1
        if order in (1, 3):
            count += 1
            if count == n:
                return f"{y}-{labels[order]}"
    return None


def regular_after(term: str | None, extra: int) -> str | None:
    if not term or extra <= 0:
        return term
    try:
        y_s, sem = term.split("-")
        y = int(y_s)
        order = {"1": 1, "S": 2, "2": 3, "W": 4}[sem]
    except Exception:
        return None
    labels = {1: "1", 3: "2"}
    count = 0
    for _ in range(60):
        order += 1
        if order > 4:
            order = 1
            y += 1
        if order in (1, 3):
            count += 1
            if count == extra:
                return f"{y}-{labels[order]}"
    return None


def verify_api_guards() -> list[str]:
    errors = []
    client = TestClient(app)
    first = FILES[0]

    with first.open("rb") as f:
        resp = client.post(
            "/graduation/v2/verify",
            files=[("files", (first.name, f, "application/vnd.ms-excel"))],
            data={"context": json.dumps({"program_id": "dsci_convergence"}, ensure_ascii=False)},
        )
    if resp.status_code != 400:
        errors.append(f"융합전공 제1전공 guard expected 400 got {resp.status_code}: {resp.text[:200]}")

    with first.open("rb") as f:
        resp = client.post(
            "/graduation/v2/verify",
            files=[("files", (first.name, f, "application/vnd.ms-excel"))],
            data={"context": '{"program_id": "ai_bigdata"'},
        )
    if resp.status_code != 400:
        errors.append(f"깨진 JSON guard expected 400 got {resp.status_code}: {resp.text[:200]}")

    resp = client.post(
        "/graduation/v2/verify",
        files=[("files", ("broken.xls", b"not an excel file", "application/vnd.ms-excel"))],
        data={"context": json.dumps({"program_id": "ai_bigdata"}, ensure_ascii=False)},
    )
    if resp.status_code != 422:
        errors.append(f"손상 엑셀 guard expected 422 got {resp.status_code}: {resp.text[:200]}")
    return errors


def markdown_terms(markdown: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for line in markdown.splitlines():
        m = re.match(r"^- (20\d{2}-(?:1|2|S|W)): (.+)$", line.strip())
        if not m:
            continue
        courses = []
        for name, credits in re.findall(r"([^,()]+)\((\d+(?:\.\d+)?)\)", m.group(2)):
            courses.append((name.strip(), float(credits)))
        out[m.group(1)] = courses
    return out


def risk_number_errors(resp) -> list[str]:
    errors = []
    audit = resp.audit
    total_gap = round(float(audit.total_gap))
    max_area = round(max((g.gap for g in audit.area_gaps), default=0.0))
    capacity = None
    for reason in resp.risk.reasons:
        nums = [int(x) for x in re.findall(r"(\d+)학점", reason.detail)]
        if reason.factor == "총학점" and nums and nums[0] != total_gap:
            errors.append(f"risk 총학점 숫자 {nums[0]} != audit.total_gap {total_gap}")
        if reason.factor == "영역" and nums and nums[0] != max_area:
            errors.append(f"risk 영역 숫자 {nums[0]} != max area gap {max_area}")
        if reason.factor == "잔여학기":
            m = re.search(r"부족 (\d+)학점 > 잔여 (\d+)학기 수용량\(~(\d+)\)", reason.detail)
            if m:
                if int(m.group(1)) != total_gap:
                    errors.append(f"risk 잔여학기 부족 {m.group(1)} != audit.total_gap {total_gap}")
                capacity = int(m.group(3))
    return errors


def audit_context(context: dict):
    files = [(p.read_bytes(), p.name) for p in FILES]
    verify = pipeline.run_verify(files, context)
    payload = {
        "context": verify["context"],
        "verification_table": verify["verification_table"],
        "unresolved": verify["unresolved"],
        "possible_retakes": verify["possible_retakes"],
    }
    return pipeline.run_audit(payload)


def check_response(label: str, resp) -> list[str]:
    errors = []
    plan = resp.roadmap
    if plan.status == "blocked" and plan.terms:
        md = markdown_terms(resp.report_markdown)
        js = {
            t.term: [(c.name_ko, float(c.credits)) for c in t.courses]
            for t in plan.terms
        }
        if md != js:
            errors.append(f"{label}: blocked markdown terms != JSON terms: md={md} js={js}")
    lines = [ln.strip() for ln in resp.report_markdown.splitlines() if ln.strip()]
    dup_lines = sorted({ln for ln in lines if lines.count(ln) > 1 and not ln.startswith("#")})
    if dup_lines:
        errors.append(f"{label}: markdown duplicate lines: {dup_lines}")
    if plan.blocked_reason:
        count = resp.report_markdown.count(plan.blocked_reason)
        if count > 1:
            errors.append(f"{label}: blocked_reason repeated {count} times")
    if plan.overflow:
        expected = nth_regular(resp.context.current_term, plan.overflow.total_semesters_needed)
        if plan.overflow.projected_graduation_term != expected:
            errors.append(
                f"{label}: overflow projected {plan.overflow.projected_graduation_term} != "
                f"current+total_needed {expected}"
            )
        regular_terms = [t.term for t in plan.terms if t.term.endswith("-1") or t.term.endswith("-2")]
        if regular_terms:
            from_last = regular_after(regular_terms[-1], plan.overflow.extra_semesters)
            if plan.overflow.projected_graduation_term != from_last:
                errors.append(
                    f"{label}: overflow projected {plan.overflow.projected_graduation_term} != "
                    f"last_regular+extra {from_last}"
                )
    errors.extend(f"{label}: {e}" for e in risk_number_errors(resp))
    return errors


def check_frontend_branch() -> list[str]:
    text = Path("frontend/src/components/GraduationV2.jsx").read_text(encoding="utf-8")
    errors = []
    if 'audit.roadmap.terms.length > 0 && (' not in text:
        errors.append("프론트 terms 렌더 분기 누락")
    idx = text.find('audit.roadmap.terms.length > 0 && (')
    prefix = text[max(0, idx - 180):idx]
    if "status" in prefix and "blocked" in prefix:
        errors.append("프론트 terms 렌더가 blocked status에 의해 막힐 가능성")
    if 'audit.roadmap.feasible === false && audit.roadmap.blocked_reason' not in text:
        errors.append("프론트 blocked_reason 표시 분기 누락")
    return errors


def main() -> int:
    errors = []
    missing = [str(p) for p in FILES if not p.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")

    errors.extend(verify_api_guards())
    contexts = [
        ("real-main-1rem", {
            "program_id": "ai_bigdata",
            "admission_year": 2022,
            "current_term": "2026-1",
            "remaining_semesters": 1,
            "seasonal_semester_allowed": False,
            "convergence_program_ids": ["dsci_convergence"],
            "convergence_tracks": {"dsci_convergence": "다전공"},
            "gpa_min_met": "unknown",
        }),
        ("real-main-2rem-seasonal-bonus", {
            "program_id": "ai_bigdata",
            "admission_year": 2022,
            "current_term": "2026-1",
            "remaining_semesters": 2,
            "seasonal_semester_allowed": True,
            "prev_term_gpa_ge_375": True,
            "convergence_program_ids": ["dsci_convergence"],
            "convergence_tracks": {"dsci_convergence": "다전공"},
            "gpa_min_met": "unknown",
        }),
        ("real-main-0rem", {
            "program_id": "ai_bigdata",
            "admission_year": 2022,
            "current_term": "2026-1",
            "remaining_semesters": 0,
            "seasonal_semester_allowed": False,
            "convergence_program_ids": ["dsci_convergence"],
            "convergence_tracks": {"dsci_convergence": "다전공"},
            "gpa_min_met": "unknown",
        }),
    ]
    summaries = []
    for label, context in contexts:
        resp = audit_context(context)
        summaries.append({
            "label": label,
            "status": resp.roadmap.status,
            "feasible": resp.roadmap.feasible,
            "terms": [(t.term, t.term_credits, [c.name_ko for c in t.courses]) for t in resp.roadmap.terms],
            "overflow": resp.roadmap.overflow.model_dump() if resp.roadmap.overflow else None,
            "risk": (resp.risk.grade, [r.detail for r in resp.risk.reasons]),
            "total_gap": resp.audit.total_gap,
            "area_gaps": [(g.area, g.gap) for g in resp.audit.area_gaps],
        })
        errors.extend(check_response(label, resp))
    errors.extend(check_frontend_branch())
    print(json.dumps({"errors": errors, "summaries": summaries}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
