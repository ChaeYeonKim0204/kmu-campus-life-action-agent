"""졸업센터 v2 파이프라인 테스트 (외부 파일·네트워크 비의존).

합성 수강내역 엑셀을 메모리에서 생성해 verify→audit를 검증한다. LLM 플래너는
FakeClient 주입 또는 무키(not_generated) 경로로 테스트한다.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import openpyxl
import pytest

from graduation_center.v2 import pipeline, planner
from graduation_center.v2.models_v2 import RoadmapPlan

CATALOG = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
COURSES = {c["name_ko"]: c for c in CATALOG["courses"]}


def _xlsx(rows: list[dict], term="2025학년도 1학기") -> bytes:
    """수강신청확인서 형식 .xlsx (메모리)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["2025-2 수강신청 확인서"])
    ws.append(["학번", "", "20250000", "", "", "성명", "", "테스트"])
    ws.append(["수강학기", "", term])
    ws.append([])
    ws.append(["교과목코드", "분반", "", "교과목명", "이수구분", "", "학점", "시간", "", "담당교수", "비고"])
    for r in rows:
        ws.append([r["code"], "01", "", r["name"], r.get("area", "전공선택"), "",
                   r["credits"], "", "", "교수", ""])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _major(*names):
    return [{"code": COURSES[n]["course_id"], "name": n, "credits": COURSES[n]["credits"]} for n in names]


def test_catalog_loaded():
    assert len(CATALOG["courses"]) == 39
    assert any(c["is_required"] for c in CATALOG["courses"])


def test_verify_merges_and_matches():
    rows = _major("경영통계", "회계학원론", "AI빅데이터프로그래밍Ⅰ")
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata"})
    assert len(v["verification_table"]) == 3
    assert all(t["course_id"] for t in v["verification_table"])  # 코드 매칭됨


def test_audit_detects_gap_and_missing_required(monkeypatch):
    # LLM 비활성으로 고정(환경 독립) → 결정론 진단/리스크만 검증
    monkeypatch.setattr(planner, "_get_client", lambda: None)
    rows = _major("경영통계", "회계학원론", "현대경영과기업가정신", "경영정보학원론")
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata", "remaining_semesters": 2})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
    resp = pipeline.run_audit(payload)
    assert resp.audit.total_gap > 0
    assert "0910501" in resp.audit.missing_required_course_ids  # 인공지능수학
    assert resp.risk.grade in {"B", "C", "D"}
    # 결정론 통합 플래너: 현재 학기 미입력 → 학기 배치는 생략하되 status는 generated(권장 과목 안내)
    assert resp.roadmap.status == "generated"
    assert resp.roadmap.terms == []  # current_term 없어 배치 생략


def test_planner_fake_client_generates_valid_roadmap():
    from graduation_center.v2.audit_v2 import compute_audit
    from graduation_center.v2.catalog import assemble_requirement_profile
    from graduation_center.v2.models_v2 import StudentContext, VerifiedCourse
    from graduation_center.v2.verification import finalize_transcript

    required = [c for c in CATALOG["courses"] if c["is_required"]]
    electives = [c for c in CATALOG["courses"] if not c["is_required"] and c["requirement_area"] == "전공"]
    # 필수 전부 + 전공 갭이 작게 남도록 일부 전공선택 이수 (필수누락 없음)
    confirmed = list(required)
    major_target = 48 - 3  # 전공 45 → 갭 3
    for c in electives:
        if sum(x["credits"] for x in confirmed) >= major_target:
            break
        confirmed.append(c)
    rows = [{"code": c["course_id"], "name": c["name_ko"], "credits": c["credits"]} for c in confirmed]
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata",
                            "current_term": "2026-1", "remaining_semesters": 3, "max_courses_per_term": 5})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}

    ctx = StudentContext.model_validate(payload["context"])
    vt = finalize_transcript([VerifiedCourse.model_validate(x) for x in payload["verification_table"]], [], [])
    prof = assemble_requirement_profile(ctx)
    au = compute_audit(vt, prof)
    assert not au.missing_required_course_ids  # 필수 전부 이수
    pctx = planner.build_planning_context(au, prof, ctx, vt)
    major_gap = next(g["gap"] for g in pctx["audit_result"]["gaps"] if g["area"] == "전공")
    # 2학기 개설 후보로 2026-2에 갭 충당
    cand2 = [c for c in pctx["candidate_courses"] if "2" in c["offered_terms"]]
    picked, acc = [], 0
    for c in cand2:
        if acc >= major_gap:
            break
        picked.append(c); acc += c["credits"]
    fake = {"feasible": True, "why_this_plan": "갭 충당", "blocked_reason": None,
            "relaxation_hint": None, "assumptions": [],
            "terms": [{"term": "2026-2", "courses": [
                {"course_id": c["course_id"], "name_ko": c["name_ko"], "credits": c["credits"],
                 "satisfies": "전공", "reason": "갭", "source_ids": [c["source_id"]]} for c in picked],
                "term_credits": acc, "term_risk": "low", "notes": []}]}

    class Fake:
        class responses:
            @staticmethod
            def create(**k):
                class R:
                    output_text = json.dumps(fake, ensure_ascii=False)
                return R()

    resp = pipeline.run_audit(payload, client=Fake())
    assert resp.roadmap.status == "generated"
    assert resp.roadmap.feasible is True


def test_validator_rejects_invented_course():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [], "sources": [], "non_major_gap_areas": [],
            "audit_result": {"total_gap": 3, "gaps": [{"area": "전공", "gap": 3}],
                             "missing_required_course_ids": []}}
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2026-2", "courses": [{"course_id": "9999999", "name_ko": "가짜", "credits": 3,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 3, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert not rep.ok
    assert any(e.code == "unknown_course" for e in rep.errors)


def test_validator_rejects_credit_inflation():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
            "requirement_area": "전공", "is_required": True, "prerequisites": [], "offered_terms": ["1"],
            "source_id": "G1"}],
            "sources": [{"id": "G1"}], "non_major_gap_areas": [], "completed_ids": [],
            "audit_result": {"total_gap": 48, "gaps": [{"area": "전공", "gap": 48}], "missing_required_course_ids": []}}
    # 3학점 과목에 48학점 위조
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2026-2", "courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 48,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 48, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert not rep.ok
    assert any(e.code == "credit_mismatch" for e in rep.errors)
    # 인공지능수학은 1학기 개설인데 2026-2(2학기) → not_offered도 잡힘
    assert any(e.code == "not_offered" for e in rep.errors)


def test_validator_rejects_out_of_range_term():
    from graduation_center.v2.models_v2 import StudentContext
    ctx = {"program_id": "ai_bigdata", "current_term": "2026-1", "remaining_semesters": 2}
    pctx = {"candidate_courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
            "requirement_area": "전공", "is_required": False, "prerequisites": [], "offered_terms": ["1"],
            "source_id": "G1"}],
            "sources": [{"id": "G1"}], "non_major_gap_areas": [], "completed_ids": [],
            "audit_result": {"total_gap": 3, "gaps": [{"area": "전공", "gap": 3}], "missing_required_course_ids": []}}
    plan = RoadmapPlan(status="generated", feasible=True, terms=[{
        "term": "2035-1", "courses": [{"course_id": "0910501", "name_ko": "인공지능수학", "credits": 3,
        "satisfies": "전공", "reason": "x", "source_ids": ["G1"]}],
        "term_credits": 3, "term_risk": "low", "notes": []}])
    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
    assert any(e.code == "term_out_of_range" for e in rep.errors)


def test_convergence_overlay(monkeypatch):
    # 주전공 ai_bigdata + 융합전공 dsci_convergence — 융합전공 과목 이수분이 별도 집계됨
    monkeypatch.setattr(planner, "_get_client", lambda: None)
    rows = _major("경영통계", "수리통계", "빅데이터처리와시각화")  # dsci 융합전공에도 속한 과목들
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], {"program_id": "ai_bigdata",
                            "remaining_semesters": 4, "convergence_program_ids": ["dsci_convergence"]})
    payload = {"context": v["context"], "verification_table": v["verification_table"],
               "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
    resp = pipeline.run_audit(payload)
    cc = resp.audit.convergence_checks
    assert len(cc) == 1 and cc[0]["program_id"] == "dsci_convergence"
    assert cc[0]["required"] == 36
    assert cc[0]["earned"] > 0          # 융합전공 과목 이수분 집계
    assert cc[0]["gap"] == 36 - cc[0]["earned"]


def test_convergence_duplicate_credit_cap_and_exclusion():
    # 학사규정 제77조: 제1전공 전공과목(앞5자리 동일)만 중복인정, 다전공 12 / 부전공 융합 6,
    # 교양·일반선택은 중복인정 불가
    from graduation_center.v2.audit_v2 import _convergence_checks
    from graduation_center.v2.models_v2 import VerifiedTranscript, VerifiedCourse
    cat = json.loads(Path("data/graduation/v2/catalog_dsci_convergence.json").read_text(encoding="utf-8"))["courses"]
    major, tot = [], 0
    for c in cat:
        if tot >= 15:  # 12 초과하도록
            break
        major.append(VerifiedCourse(course_id=c["course_id"], name_ko=c["name_ko"],
                                    credits=c["credits"], requirement_area="전공"))
        tot += c["credits"]
    # 교양으로 이수한 dsci-prefix 과목 → 중복인정 불가(제외돼야)
    gyo = VerifiedCourse(course_id=cat[0]["course_id"], name_ko="교양수강분", credits=3, requirement_area="핵심교양")
    vt = VerifiedTranscript(confirmed_courses=major + [gyo])
    total_major = round(sum(c.credits for c in major), 1)
    # primary=dsci_convergence → 모든 designated가 제1전공과 겹침 → cap(double_recognizable) 검증
    da = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "다전공"}, "dsci_convergence")[0]
    assert da["required"] == 36 and da["double_cap"] == 12 and da["conv_type"] == "융합전공"
    # designated_total = 들은 융합 과목 전부(교양 gyo 제외). earned는 배정 반영값(별도).
    assert da["designated_total"] == total_major
    assert da["double_recognizable"] == 12          # 그중 제1전공 중복인정 가능 최대 12
    bu = _convergence_checks(vt, ["dsci_convergence"], {"dsci_convergence": "부전공"}, "dsci_convergence")[0]
    assert bu["required"] == 18 and bu["double_cap"] == 6 and bu["double_recognizable"] == 6
    assert bu["designated_total"] == total_major    # 부전공도 designated 총합은 동일


def test_gen_ed_gap_planned_as_slot():
    # 교양만 부족 → 결정론 통합 플래너가 '교양 슬롯'으로 학기에 배치(codex 설계)
    from graduation_center.v2.audit_v2 import AuditResult, AreaGap
    from graduation_center.v2.catalog import assemble_requirement_profile
    from graduation_center.v2.models_v2 import StudentContext, VerifiedTranscript
    ctx = StudentContext(program_id="ai_bigdata", current_term="2026-1", remaining_semesters=2)
    prof = assemble_requirement_profile(ctx)
    au = AuditResult(total_required=130, total_earned=128, total_gap=2,
                     area_gaps=[AreaGap(area="기초교양", required=7, earned=5, gap=2)],
                     missing_required_course_ids=[])
    vt = VerifiedTranscript(total_earned=128)
    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
    assert plan.status == "generated"
    placed = [c for t in plan.terms for c in t.courses]
    assert any("기초교양" in c.satisfies for c in placed)        # 교양 슬롯이 배치됨
    assert all(c.manual_check for c in placed if c.confidence == "generic_slot")
