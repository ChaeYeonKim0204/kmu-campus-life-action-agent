"""에이전트 총평(능동 시나리오 탐색) 테스트 — LLM 비의존(FakeClient·캐시).

계획 §6 (docs/plans/agentic_scenario_summary_plan.md): run_summary 독립 게이트(실LLM 회귀
차단), facts canonical 결정론, 관련성 필터 accept/reject + 탈락 기록 보존, 충족 학생
'검토 후 유지 권장' 정상 총평, before 별도 재계산, validator 3모드, 캐시, 상담 경로 무영향.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest

from graduation_center.v2 import pipeline, report_summary, whatif
from graduation_center.v2.models_v2 import StudentContext

CATALOG = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))


def _xlsx(rows: list[dict], term="2025학년도 1학기") -> bytes:
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


def _payload(context: dict, target_credits: float = 45) -> dict:
    required = [c for c in CATALOG["courses"] if c["is_required"]]
    electives = [c for c in CATALOG["courses"]
                 if not c["is_required"] and c["requirement_area"] == "전공"]
    confirmed = list(required)
    for c in electives:
        if sum(x["credits"] for x in confirmed) >= target_credits:
            break
        confirmed.append(c)
    rows = [{"code": c["course_id"], "name": c["name_ko"], "credits": c["credits"]}
            for c in confirmed]
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], context)
    return {"context": v["context"], "verification_table": v["verification_table"],
            "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}


CTX = {"program_id": "ai_bigdata", "admission_year": 2022, "current_term": "2026-1",
       "remaining_semesters": 3, "seasonal_semester_allowed": False}


def _delta(**kw) -> dict:
    base = {"calendar_delay_terms": None, "remaining_semesters_change": None,
            "seasonal_semester_allowed": None, "max_credits_per_term": None,
            "prev_term_gpa_ge_375": None, "add_convergence": [], "drop_convergence": []}
    base.update(kw)
    return base


def _sel_raw(*cands) -> dict:
    return {"candidates": [{"delta": d, "reason_code": rc, "rationale": ra}
                           for d, rc, ra in cands]}


def _sum_raw(lines, headline="갈림길 요약", rec="변경 검토") -> dict:
    return {"headline": headline, "recommendation": rec,
            "lines": [{"text": t, "fact_ids": ids} for t, ids in lines]}


class SeqFake:
    """responses.create 호출마다 준비된 출력을 순서대로 반환 + 호출 횟수 기록."""

    def __init__(self, outputs: list[dict]):
        self.calls = 0
        outer = self

        class _R:
            @staticmethod
            def create(**k):
                out = outputs[min(outer.calls, len(outputs) - 1)]
                outer.calls += 1
                return SimpleNamespace(output_text=json.dumps(out, ensure_ascii=False))
        self.responses = _R()


@pytest.fixture(autouse=True)
def _no_planner_llm(monkeypatch):
    from graduation_center.v2 import planner
    monkeypatch.setattr(planner, "_get_client", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ---------- 게이트 (적대 H1·H2) ----------
def test_run_summary_gate_default_off_no_llm():
    """기존 run_audit(payload) 직접 호출은 총평 로직 자체 미진입 — LLM 0콜·필드 None·노드 0."""
    payload = _payload(CTX)
    called = {"n": 0}

    def boom():
        called["n"] += 1
        return None
    orig = report_summary._get_client
    report_summary._get_client = boom
    try:
        resp = pipeline.run_audit(payload)               # 기본 run_summary=False
    finally:
        report_summary._get_client = orig
    assert called["n"] == 0                              # 총평 로직 미진입
    assert resp.agent_summary is None and resp.summary_fallback is None
    assert not [e for e in resp.node_trace if e.node.startswith(("갈림길", "총평"))]


def test_run_summary_no_client_emits_fallback_and_skip_trace():
    """run_summary=True + LLM 없음 → fallback 사유 + 4노드 skip placeholder(그래프-카드 모순 방지)."""
    resp = pipeline.run_audit(_payload(CTX), run_summary=True)   # conftest가 client None 강제
    assert resp.agent_summary is None
    assert "LLM 미설정" in (resp.summary_fallback or "")
    nodes = [e for e in resp.node_trace if e.node.startswith(("갈림길", "총평"))]
    assert len(nodes) == 4 and all(e.status == "skip" for e in nodes)


def test_whatif_path_has_no_agent_summary():
    """상담(what-if) 경로의 after는 run_summary 기본 False — agent_summary 항상 None."""
    payload = _payload(CTX)
    fake = SeqFake([{"category": "계절학기", "interpretable": True, "question_summary": "계절수강",
                     "delta": _delta(seasonal_semester_allowed=True)}])
    resp = whatif.run_whatif({**payload, "question": "계절학기 들으면?"}, client=fake)
    assert resp.status == "ok" and resp.after is not None
    assert resp.after.agent_summary is None and resp.after.summary_fallback is None


# ---------- facts·캐시 ----------
def test_facts_canonical_and_cache_key_deterministic():
    payload = _payload(CTX)
    r1 = pipeline.run_audit(payload)
    r2 = pipeline.run_audit(payload)
    f1 = report_summary._build_facts(r1.audit, r1.risk, r1.roadmap, r1.context)
    f2 = report_summary._build_facts(r2.audit, r2.risk, r2.roadmap, r2.context)
    assert report_summary._canonical_facts(f1) == report_summary._canonical_facts(f2)
    assert report_summary._cache_key("m", f1, r1.context) == report_summary._cache_key("m", f2, r2.context)
    # 같은 수치라도 학생 정체성(전공·학번)이 다르면 키 분리(codex R1 — 동수치 타학생 충돌)
    other = r1.context.model_copy(update={"admission_year": 2023})
    assert report_summary._cache_key("m", f1, r1.context) != report_summary._cache_key("m", f1, other)


def test_cache_hit_zero_llm_calls():
    payload = _payload(CTX)
    sel = _sel_raw((_delta(seasonal_semester_allowed=True), "load_adjust", "계절로 부담 분산"))
    fake = SeqFake([sel, _sum_raw([("리스크는 F4 기준으로 유지", ["F4"])])])
    r1 = pipeline.run_audit(payload, client=fake, run_summary=True)
    assert r1.agent_summary is not None
    n_first = fake.calls
    assert n_first == 2                                  # 선정 1 + 총평 1
    r2 = pipeline.run_audit(payload, client=fake, run_summary=True)
    assert fake.calls == n_first                         # 캐시 히트 — LLM 0콜
    assert r2.agent_summary.model_dump() == r1.agent_summary.model_dump()
    # 캐시 값에 탐색 과정 포함(R4) — candidates_review까지 동일 복원
    assert r2.agent_summary.candidates_review


# ---------- 관련성 필터 — 탈락 기록 보존 (교수 R3 비타협) ----------
def test_filter_rejects_recorded_not_erased():
    payload = _payload(CTX)
    sel = _sel_raw(
        (_delta(seasonal_semester_allowed=True), "load_adjust", "계절 활용"),       # accept 기대
        (_delta(seasonal_semester_allowed=True), "timeline_extend", "기간 연장"),   # pre_mismatch(delta에 휴학/잔여+ 없음)
        (_delta(), "graduate_faster", "빈 delta"),                                  # no_op
        (_delta(drop_convergence=["dsci"]), "conv_tradeoff", "융합 포기"),          # pre_mismatch(융합 미선언)
    )
    fake = SeqFake([sel, _sum_raw([("계절학기 시나리오는 S1 참조", ["S1"])])])
    resp = pipeline.run_audit(payload, client=fake, run_summary=True)
    s = resp.agent_summary
    assert s is not None
    by = {(r.reason_code, r.verdict): r for r in s.candidates_review}
    assert ("load_adjust", "accepted") in by
    assert by[("timeline_extend", "rejected")].rejected_by == "pre_mismatch"
    assert by[("graduate_faster", "rejected")].rejected_by == "no_op"
    assert by[("conv_tradeoff", "rejected")].rejected_by == "pre_mismatch"
    assert len(s.scenarios) == 1 and s.scenarios[0].reason_code == "load_adjust"
    # trace branch에 후보→채택 수가 정직 표기
    sel_node = next(e for e in resp.node_trace if e.node == "갈림길 선정")
    assert "후보 4" in (sel_node.branch_taken or "")


def test_already_met_student_gets_normal_keep_summary():
    """충족 학생: 채택 0 → fallback이 아니라 '유지 권장' 정상 총평(교수 R3 — 분기 폐기)."""
    ctx = dict(CTX, remaining_semesters=2)
    payload = _payload(ctx, target_credits=200)          # 카탈로그 전공을 최대로 채운 학생
    sel = _sel_raw((_delta(remaining_semesters_change=1), "timeline_extend", "한 학기 더"))
    fake = SeqFake([sel, _sum_raw([("현 계획 유지가 최적 — F4 기준", ["F4"])],
                                  headline="검토 결과 현 계획 유지가 최적", rec="유지 권장")])
    resp = pipeline.run_audit(payload, client=fake, run_summary=True)
    s = resp.agent_summary
    assert s is not None and resp.summary_fallback is None
    assert s.recommendation == "유지 권장"
    assert all(r.verdict == "rejected" for r in s.candidates_review) or not s.scenarios


# ---------- 시뮬레이션 ----------
def test_before_recomputed_not_base_object(monkeypatch):
    """before는 본 보고서 객체 재사용 금지 — run_audit_fn(skip_explain=True) 별도 재계산(적대 H3)."""
    payload = _payload(CTX)
    base = pipeline.run_audit(payload)
    calls = []

    def counting_run_audit(p, client=None, *, skip_explain=False, run_summary=False):
        calls.append({"skip_explain": skip_explain, "run_summary": run_summary})
        return pipeline.run_audit(p, client=client, skip_explain=skip_explain,
                                  run_summary=run_summary)

    sel = _sel_raw((_delta(seasonal_semester_allowed=True), "load_adjust", "계절"))
    fake = SeqFake([sel, _sum_raw([("S1 관찰값 기준", ["S1"])])])
    summary, fallback, trace = report_summary.run_report_summary(
        payload, base.audit, base.risk, base.roadmap, base.context,
        run_audit_fn=counting_run_audit, client=fake)
    assert summary is not None
    # before 1회 + after 1회 — 전부 skip_explain=True·run_summary=False(재귀 구조 차단)
    assert len(calls) == 2
    assert all(c["skip_explain"] and not c["run_summary"] for c in calls)


# ---------- validator 3모드 ----------
def _run_with_summary_lines(payload, lines, sel=None):
    sel = sel or _sel_raw((_delta(seasonal_semester_allowed=True), "load_adjust", "계절"))
    raw = _sum_raw(lines)
    fake = SeqFake([sel, raw, raw])                      # 재시도 1회까지 같은 출력
    return pipeline.run_audit(payload, client=fake, run_summary=True)


def test_validator_drops_fabricated_number():
    payload = _payload(CTX)
    resp = _run_with_summary_lines(payload, [
        ("부족 학점은 9999학점입니다", ["F1"]),          # 위조 수치 → 폐기
        ("리스크는 F4 기준 유지", ["F4"]),               # 통과
    ])
    s = resp.agent_summary
    assert s is not None and len(s.lines) == 1
    assert "9999" not in s.lines[0].text


def test_validator_drops_unresolved_fact_and_all_dropped_falls_back():
    payload = _payload(CTX)
    resp = _run_with_summary_lines(payload, [("근거 없는 주장", ["F99"])])
    assert resp.agent_summary is None
    assert "총평 검증 실패" in (resp.summary_fallback or "")
    nodes = [e for e in resp.node_trace if e.node.startswith(("갈림길", "총평"))]
    assert len(nodes) == 4 and all(e.status == "skip" for e in nodes)


def test_validator_drops_grade_contradiction():
    payload = _payload(CTX)
    base = pipeline.run_audit(payload)
    other = "A" if base.risk.grade != "A" else "D"
    resp = _run_with_summary_lines(payload, [
        (f"이 학생의 등급은 {other} 입니다", ["F1"]),    # F1(총학점)엔 등급 없음 → 모순 폐기
        ("총 이수 현황은 F1 참조", ["F1"]),
    ])
    s = resp.agent_summary
    assert s is not None and len(s.lines) == 1 and other not in s.lines[0].text


def test_validator_grade_korean_adjacency_and_headline():
    """'D등급'처럼 한글 인접 등급도 모순 검출 + headline도 수치·등급·판정 검증(적대① R1)."""
    facts = [{"id": "F1", "text": "총 이수 45/130학점 · 총 부족 85학점"},
             {"id": "F4", "text": "리스크 C(주의) · 점수 40"}]
    raw = {"headline": "120학점만 더 들으면 D등급 위험 졸업 불가",   # 위조 120·D·판정 단정
           "recommendation": "유지 권장",
           "lines": [{"text": "리스크 D등급으로 위험", "fact_ids": ["F4"]},   # 한글 인접 등급 모순
                     {"text": "8학기 더 필요", "fact_ids": ["F1"]},           # 단위 동반 1자리 위조
                     {"text": "총 부족 85학점 — F1 참조", "fact_ids": ["F1"]}]}
    s, issues = report_summary._validate_summary(raw, facts, [], "C")
    assert s is not None and len(s.lines) == 1 and "85" in s.lines[0].text
    assert s.headline == ""                                # headline 위반 → 비표시
    assert any("등급" in i for i in issues) and any("headline" in i for i in issues)


def test_cap_rejections_recorded_with_honest_reasons():
    """채택 상한 초과(효과 있음)는 accept_cap, 시뮬 상한 밖은 sim_cap — post_no_change 거짓
    라벨 금지(codex R1·비타협 ②). 채택은 정확히 MAX_ACCEPTED."""
    payload = _payload(CTX)
    # 휴학 1~4학기: 전부 timeline_extend pre 통과 + 효과(졸업 지연) 기대 → 5번째는 sim_cap
    cands = [(_delta(calendar_delay_terms=k), "timeline_extend", f"휴학 {k}") for k in (1, 2, 3, 4)]
    cands.append((_delta(remaining_semesters_change=2), "timeline_extend", "잔여 +2"))
    fake = SeqFake([_sel_raw(*cands), _sum_raw([("관찰값은 S1 참조", ["S1"])])])
    resp = pipeline.run_audit(payload, client=fake, run_summary=True)
    s = resp.agent_summary
    assert s is not None
    assert len(s.scenarios) == report_summary.MAX_ACCEPTED
    by_reason = [r.rejected_by for r in s.candidates_review if r.verdict == "rejected"]
    assert "sim_cap" in by_reason                          # 5번째 후보 — 미실행 정직 표기
    assert "accept_cap" in by_reason                       # 4번째 효과 있었으나 상한
    assert "post_no_change" not in by_reason               # 거짓 사유 없음


# ---------- 노드명 disjoint (적대 M3) ----------
def test_summary_node_names_disjoint_from_existing():
    summary_nodes = {"갈림길 선정", "갈림길 시뮬레이션", "총평 생성", "총평 검증"}
    audit_nodes = {"요람 로딩", "데이터 수집", "코드 매칭", "데이터 검증", "갭 계산", "로드맵 배치",
                   "로드맵 검증", "초과학기 시나리오", "리스크 산정", "요람 RAG 해설", "해설 검증"}
    consult_nodes = {"질문 분류", "매개변수 추출", "조건 가드", "졸업사정 재실행",
                     "시나리오 비교", "다음 행동 제안", "안내 종료"}
    assert not summary_nodes & (audit_nodes | consult_nodes)
    jsx = Path("frontend/src/components/WorkflowGraph.jsx").read_text(encoding="utf-8")
    for n in summary_nodes:
        assert n in jsx, f"WorkflowGraph BASE_NODES에 '{n}' 누락"
