"""졸업 시나리오 상담 Agent (what-if) 테스트 — LLM 비의존(FakeClient·캐시).

검증 라운드 발견의 재발 방지 테스트 포함: 휴학=시작 지연(잔여 불변·복학 전 학기 배치 제외),
model_validate 재검증, 빈 enum 금지, trace 노드명 무충돌, 캐시 키 학생 분리, degrade(500 금지).
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest

from graduation_center.v2 import pipeline, planner, whatif
from graduation_center.v2.models_v2 import (
    AreaGap, AuditResult, RiskAssessment, RoadmapPlan, RoadmapTerm, StudentContext,
    WhatIfDelta,
)

CATALOG = json.loads(Path("data/graduation/v2/catalog_ai_bigdata.json").read_text(encoding="utf-8"))
COURSES = {c["name_ko"]: c for c in CATALOG["courses"]}
AUDIT_NODE_NAMES = {"요람 로딩", "데이터 수집", "코드 매칭", "데이터 검증", "갭 계산",
                    "로드맵 배치", "로드맵 검증", "초과학기 시나리오", "리스크 산정",
                    "요람 RAG 해설", "해설 검증"}


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


def _payload(context: dict) -> dict:
    """필수+전공선택을 두루 이수한 합성 학생의 audit payload."""
    required = [c for c in CATALOG["courses"] if c["is_required"]]
    electives = [c for c in CATALOG["courses"]
                 if not c["is_required"] and c["requirement_area"] == "전공"]
    confirmed = list(required)
    for c in electives:
        if sum(x["credits"] for x in confirmed) >= 45:
            break
        confirmed.append(c)
    rows = [{"code": c["course_id"], "name": c["name_ko"], "credits": c["credits"]}
            for c in confirmed]
    v = pipeline.run_verify([(_xlsx(rows), "a.xlsx")], context)
    return {"context": v["context"], "verification_table": v["verification_table"],
            "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}


def _fake_client(raw: dict):
    class Fake:
        class responses:
            @staticmethod
            def create(**k):
                return SimpleNamespace(output_text=json.dumps(raw, ensure_ascii=False))
    return Fake()


def _raw(category: str, summary: str, **delta) -> dict:
    base = {"calendar_delay_terms": None, "remaining_semesters_change": None,
            "seasonal_semester_allowed": None, "max_credits_per_term": None,
            "prev_term_gpa_ge_375": None, "add_convergence": [], "drop_convergence": []}
    base.update(delta)
    return {"category": category, "interpretable": True,
            "question_summary": summary, "delta": base}


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """실캐시 오염 방지 + LLM 환경 독립."""
    monkeypatch.setattr(whatif, "CACHE_PATH", tmp_path / "whatif_cache.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(planner, "_get_client", lambda: None)


CTX = {"program_id": "ai_bigdata", "admission_year": 2025,
       "current_term": "2026-1", "remaining_semesters": 3,
       "seasonal_semester_allowed": True}


# ---------- ① 휴학 vs 수강학기 변경 의미론 (검증 라운드 핵심) ----------
def test_leave_shifts_calendar_only():
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면 어떻게 되나요?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "ok"
    d = resp.diff
    # 갭·리스크는 불변(수강 능력 동일) — 졸업 시점만 지연
    assert d.total_gap_before == d.total_gap_after
    assert d.risk_before == d.risk_after
    if d.graduation_term_before and d.graduation_term_after:
        assert d.graduation_term_after > d.graduation_term_before
    # 잔여 수강 학기 수는 그대로, current_term은 복학 직전 계절 슬롯
    assert resp.after.context.remaining_semesters == 3
    assert resp.after.context.current_term == "2026-W"
    # 휴학 중 학기(2026-S·2026-2·2026-W)는 after 로드맵에 배치 금지
    placed = {t.term for t in resp.after.roadmap.terms}
    assert placed.isdisjoint({"2026-S", "2026-2", "2026-W"})
    # 복학 첫 학기 보너스 보수적 미적용
    assert resp.after.context.prev_term_gpa_ge_375 is False
    assert any("휴학" in c for c in resp.applied_changes)


def test_remaining_change_differs_from_leave():
    payload = {**_payload(CTX), "question": "한 학기 줄이면?"}
    client = _fake_client(_raw("수강학기변경", "잔여 1학기 축소", remaining_semesters_change=-1))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "ok"
    assert resp.after.context.remaining_semesters == 2     # 실제 수강 학기 감소
    assert resp.after.context.current_term == "2026-1"     # 시작점은 그대로 (휴학과 구분)


def test_leave_requires_current_term():
    ctx = {**CTX, "current_term": None}
    payload = {**_payload({k: v for k, v in ctx.items() if v is not None}),
               "question": "휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "unsupported"
    assert "현재 학기" in resp.unsupported_reason


# ---------- ② 조건 가드 ----------
def test_credit_cap_above_legal_is_rejected_with_rule():
    payload = {**_payload(CTX), "question": "한 학기에 21학점씩 들으면?"}
    client = _fake_client(_raw("학점상한", "상한 21", max_credits_per_term=21))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "unsupported"
    assert "제32조" in resp.unsupported_reason             # 규정 인용 가드


def test_out_of_range_delta_degrades_not_500():
    payload = {**_payload(CTX), "question": "10년 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 20학기", calendar_delay_terms=20))
    resp = whatif.run_whatif(payload, client=client)       # ValidationError → 빈 delta
    assert resp.status == "unsupported"


def test_drop_unknown_convergence_rejected():
    payload = {**_payload(CTX), "question": "부전공 빼면?"}
    client = _fake_client(_raw("다전공변경", "융합 포기", drop_convergence=["dsci_convergence"]))
    resp = whatif.run_whatif(payload, client=client)       # ctx에 융합 미선언
    assert resp.status == "unsupported"
    assert "신청하지 않은" in resp.unsupported_reason


def test_uninterpretable_returns_guidance_with_exit_node():
    payload = {**_payload(CTX), "question": "조기졸업 되나요?"}
    raw = _raw("기타", "조기졸업 요건 질문")
    raw["interpretable"] = False
    resp = whatif.run_whatif(payload, client=_fake_client(raw))
    assert resp.status == "unsupported" and resp.after is None
    nodes = [e.node for e in resp.node_trace]
    assert "안내 종료" in nodes and "조건 가드" in nodes


def test_noop_same_setting_is_unsupported():
    payload = {**_payload(CTX), "question": "계절학기 들으면?"}   # 이미 허용 상태
    client = _fake_client(_raw("계절학기", "계절 허용", seasonal_semester_allowed=True))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "unsupported"
    assert "동일" in resp.unsupported_reason


# ---------- ③ 융합전공 drop·diff ----------
def test_drop_convergence_reflected_in_diff():
    ctx = {**CTX, "convergence_program_ids": ["dsci_convergence"],
           "convergence_tracks": {"dsci_convergence": "다전공"}}
    payload = {**_payload(ctx), "question": "다전공 빼면?"}
    client = _fake_client(_raw("다전공변경", "융합 포기", drop_convergence=["dsci_convergence"]))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "ok"
    assert resp.after.context.convergence_program_ids == []
    assert resp.after.context.convergence_tracks == {}     # stale track 동반 제거
    assert resp.after.audit.convergence_checks == []
    assert resp.diff.convergence_changes                   # 융합 변화가 diff에 표면화


# ---------- ④ 결정론·캐시 ----------
def test_same_input_same_diff():
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    a = whatif.run_whatif(payload, client=client)
    b = whatif.run_whatif(payload, client=client)
    assert a.diff.model_dump() == b.diff.model_dump()
    assert a.applied_changes == b.applied_changes


def test_cache_enables_offline_fallback():
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    first = whatif.run_whatif(payload, client=client)
    assert first.status == "ok"
    # 두 번째: client·키 없음 → 캐시 히트로 동작 (데모 오프라인 폴백)
    second = whatif.run_whatif(payload, client=None)
    assert second.status == "ok"
    assert second.diff.model_dump() == first.diff.model_dump()
    assert any("캐시" in e.summary for e in second.node_trace if e.node == "질문 분류")


def test_no_cache_no_key_degrades():
    payload = {**_payload(CTX), "question": "처음 보는 질문?"}
    resp = whatif.run_whatif(payload, client=None)
    assert resp.status == "unsupported"
    assert "LLM 미설정" in resp.unsupported_reason


def test_cache_key_separates_convergence_state():
    c1 = StudentContext.model_validate(CTX)
    c2 = StudentContext.model_validate({**CTX, "convergence_program_ids": ["dsci_convergence"],
                                        "convergence_tracks": {"dsci_convergence": "다전공"}})
    add1, _ = whatif._candidates(c1)
    add2, _ = whatif._candidates(c2)
    assert whatif._cache_key("m", "부전공 빼면?", c1, add1) != \
           whatif._cache_key("m", "부전공 빼면?", c2, add2)


# ---------- ⑤ trace·그래프 계약 ----------
def test_whatif_trace_never_reuses_audit_node_names():
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    resp = whatif.run_whatif(payload, client=client)
    whatif_nodes = {e.node for e in resp.node_trace}
    assert whatif_nodes.isdisjoint(AUDIT_NODE_NAMES)       # byNode 덮어쓰기 방지(라운드1 HIGH)
    kinds = {e.kind for e in resp.node_trace}
    assert kinds <= {"tool", "llm", "validator"}           # "branch" 금지(라운드3)


def test_skip_explain_keeps_placeholders_and_omits_llm():
    payload = _payload(CTX)
    resp = pipeline.run_audit(payload, skip_explain=True)
    assert resp.explanations == [] and resp.explain_fallback is None
    nodes = {e.node: e for e in resp.node_trace}
    assert nodes["요람 RAG 해설"].status == "skip"          # 그래프 고립 방지 placeholder
    assert nodes["해설 검증"].status == "skip"


# ---------- ⑥ 헬퍼·schema 단위 ----------
def test_valid_term_accepts_seasonal_labels():
    # 휴학 구현의 숨은 전제(라운드2 H1) — 깨지면 전 설계 무효
    assert StudentContext(program_id="ai_bigdata", current_term="2026-W").current_term == "2026-W"
    assert StudentContext(program_id="ai_bigdata", current_term="2027-S").current_term == "2027-S"


def test_graduation_term_helper_cases():
    def resp_with(plan):
        return SimpleNamespace(roadmap=plan)
    term = lambda lab: RoadmapTerm(term=lab, courses=[], term_credits=0)
    # 정규학기 포함 feasible
    assert whatif._graduation_term(resp_with(RoadmapPlan(
        status="generated", feasible=True, terms=[term("2026-2"), term("2027-1")]))) == ("2027-1", False)
    # 전부 계절 → 산출 불가(IndexError 금지 — 라운드3)
    assert whatif._graduation_term(resp_with(RoadmapPlan(
        status="generated", feasible=True, terms=[term("2026-S")]))) == (None, False)
    # 이미 충족
    assert whatif._graduation_term(resp_with(RoadmapPlan(
        status="generated", feasible=True, terms=[]))) == (None, True)


def test_strict_schema_never_emits_empty_enum():
    s = whatif._schema([], [])
    txt = json.dumps(s)
    assert '"enum": []' not in txt
    assert s["properties"]["delta"]["properties"]["add_convergence"]["maxItems"] == 0
    assert s["properties"]["delta"]["properties"]["drop_convergence"]["maxItems"] == 0
    s2 = whatif._schema(["dsci_convergence"], [])
    assert s2["properties"]["delta"]["properties"]["add_convergence"]["items"][
        "properties"]["program_id"]["enum"] == ["dsci_convergence"]


def test_model_validate_revalidates_context():
    # model_copy는 validator 미실행(라운드1 실측) → apply_delta는 model_validate 경유 확인
    ctx = StudentContext.model_validate(CTX)
    bad = ctx.model_copy(update={"remaining_semesters": -3})
    assert bad.remaining_semesters == -3                   # copy는 가드 우회(전제 확인)
    with pytest.raises(Exception):
        StudentContext.model_validate({**ctx.model_dump(), "remaining_semesters": -3})


def test_leave_plus_already_met_headline_mentions_delay():
    # 라운드2 L1: 이미 충족 학생의 휴학 → "변화 없음"이 아니라 지연 명시
    mk = lambda grade: SimpleNamespace(
        risk=RiskAssessment(grade=grade, label="안전"),
        audit=AuditResult(total_required=130, total_earned=130, total_gap=0,
                          area_gaps=[], convergence_checks=[], to_fusion_total=0.0,
                          missing_required_course_ids=[]),
        roadmap=RoadmapPlan(status="generated", feasible=True, terms=[]))
    diff = whatif.build_diff(mk("A"), mk("A"), WhatIfDelta(calendar_delay_terms=1))
    assert "휴학" in diff.headline and "늦어" in diff.headline


# ---------- ⑧ 코드 검증 라운드1 회귀 ----------
def test_out_of_range_is_not_cached_and_message_mentions_limit():
    # 캐시 포이즈닝 방지(코드R2 HIGH): 검증 실패 raw는 캐시 미저장 + 한도 안내 메시지
    payload = {**_payload(CTX), "question": "10년 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 20학기", calendar_delay_terms=20))
    first = whatif.run_whatif(payload, client=client)
    assert first.status == "unsupported" and "한도" in first.unsupported_reason
    # 미캐시 증명: client 없이 재시도 → 캐시 히트가 아니라 'LLM 미설정'으로 떨어져야 함
    second = whatif.run_whatif(payload, client=None)
    assert "LLM 미설정" in second.unsupported_reason


def test_leave_when_blocked_headline_still_mentions_delay():
    # 코드R1 HIGH: 교양 부족 blocked(overflow 없음) 학생의 휴학 → '변화 없음' 금지
    mk = lambda: SimpleNamespace(
        risk=RiskAssessment(grade="C", label="주의"),
        audit=AuditResult(total_required=130, total_earned=90, total_gap=40,
                          area_gaps=[AreaGap(area="기초교양", required=7, earned=0, gap=7)],
                          convergence_checks=[], to_fusion_total=0.0,
                          missing_required_course_ids=[]),
        roadmap=RoadmapPlan(status="blocked", feasible=False, terms=[], overflow=None))
    diff = whatif.build_diff(mk(), mk(), WhatIfDelta(calendar_delay_terms=1))
    assert "휴학" in diff.headline and "변화가 없습니다" not in diff.headline


def test_remaining_change_clamped_to_12_no_400():
    # 코드R1 MEDIUM: 12+4=16이 StudentContext le=12에 걸려 400으로 새는 경로 차단
    ctx = {**CTX, "remaining_semesters": 12}
    payload = {**_payload(ctx), "question": "두 학기 더 다니면?"}
    client = _fake_client(_raw("수강학기변경", "잔여 +4", remaining_semesters_change=4))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status in ("ok", "unsupported")        # 예외·400 금지
    if resp.status == "ok":
        assert resp.after.context.remaining_semesters == 12


def test_low_credit_cap_rejected_with_range():
    # 코드R2 MEDIUM: 0.5학점 상한 → '0학점으로 제한'+'변화 없음' 모순 카드 방지
    payload = {**_payload(CTX), "question": "0.5학점만 들으면?"}
    client = _fake_client(_raw("학점상한", "상한 0.5", max_credits_per_term=0.5))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "unsupported" and "9~" in resp.unsupported_reason


def test_leave_with_gpa_request_is_noted_not_silent():
    # 코드R1 MEDIUM: 휴학+3.75 동시 요청 — 침묵 무시 금지, 가정으로 명시
    payload = {**_payload(CTX), "question": "휴학하고 복학해서 3.75 받으면?"}
    client = _fake_client(_raw("휴학", "휴학+성적우수", calendar_delay_terms=1,
                               prev_term_gpa_ge_375=True))
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "ok"
    assert resp.after.context.prev_term_gpa_ge_375 is False
    assert any("3.75" in a for a in resp.assumptions)


def test_next_actions_no_contradiction_when_overflow_resolved():
    # 코드R1 MEDIUM: 초과학기 해소인데 '변경 전이 더 안전'·등록금 경고 동시 출력 금지
    diff = whatif.WhatIfDiff(
        risk_before="B", risk_after="C", total_gap_before=10, total_gap_after=10,
        graduation_term_before="2027-1", graduation_term_after="2027-2",
        overflow_before=True, overflow_after=False, headline="x")
    acts = whatif.suggest_next_actions(diff, WhatIfDelta(seasonal_semester_allowed=True),
                                       StudentContext.model_validate(CTX))
    assert any("해소" in a for a in acts)
    assert not any("변경 전 계획이 더 안전" in a for a in acts)
    assert not any("등록금" in a for a in acts)


def test_run_audit_failure_degrades_to_unsupported(monkeypatch):
    # 코드R1 LOW·계획 §6-12: 재실행 내부 예외 → 200 + unsupported (500·400 금지)
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))
    def boom(*a, **k):
        raise KeyError("broken_program")
    monkeypatch.setattr(whatif, "run_audit", boom)
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "unsupported"
    assert "시뮬레이션할 수 없습니다" in resp.unsupported_reason


# ---------- ⑨ 코드 검증 라운드2 회귀 ----------
def test_poisoned_cache_is_evicted_and_reinterpreted():
    # 코드R2 HIGH: 오염 캐시 영구 고착 금지 — evict 후 LLM 재해석 1회
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    ctx = StudentContext.model_validate(payload["context"])
    add_ids, _ = whatif._candidates(ctx)
    key = whatif._cache_key("gpt-5-mini", "다음 학기 휴학하면?", ctx, add_ids)
    whatif._cache_put(key, _raw("휴학", "오염", calendar_delay_terms=99))   # 오염 주입
    client = _fake_client(_raw("휴학", "휴학 1학기", calendar_delay_terms=1))  # 재해석은 정상값
    resp = whatif.run_whatif(payload, client=client)
    assert resp.status == "ok"                                  # 고착 아님 — 재해석 성공
    fresh = whatif._cache_get(key)
    assert fresh["delta"]["calendar_delay_terms"] == 1          # 캐시가 정상값으로 교체됨


def test_leave_headline_asymmetric_before_only():
    # 코드R2 MUST: gt_b만 산출되는 비대칭 — '늦어집니다' 단정 대신 산출 불가 명시
    term = lambda lab: SimpleNamespace(term=lab)
    before = SimpleNamespace(
        risk=RiskAssessment(grade="B", label="양호"),
        audit=AuditResult(total_required=130, total_earned=110, total_gap=20,
                          area_gaps=[], convergence_checks=[], to_fusion_total=0.0,
                          missing_required_course_ids=[]),
        roadmap=RoadmapPlan(status="generated", feasible=True,
                            terms=[RoadmapTerm(term="2026-2", courses=[], term_credits=0)]))
    after = SimpleNamespace(
        risk=RiskAssessment(grade="B", label="양호"),
        audit=before.audit,
        roadmap=RoadmapPlan(status="blocked", feasible=False, terms=[], overflow=None))
    diff = whatif.build_diff(before, after, WhatIfDelta(calendar_delay_terms=1))
    assert "산출되지 않았습니다" in diff.headline
    assert "변화가 없습니다" not in diff.headline


def test_category_rederived_from_delta_not_llm_label():
    # 코드R2(e2e LOW): LLM 라벨 오기('다전공변경')가 그래프 분기 pill에 점등되는 것 방지
    payload = {**_payload(CTX), "question": "다음 학기 휴학하면?"}
    raw = _raw("다전공변경", "휴학 1학기", calendar_delay_terms=1)   # 라벨은 틀리고 delta는 맞음
    resp = whatif.run_whatif(payload, client=_fake_client(raw))
    assert resp.status == "ok"
    assert resp.category == "휴학"                                # delta 기반 재도출
    cls = next(e for e in resp.node_trace if e.node == "질문 분류")
    assert cls.branch_taken == "휴학"


def test_track_change_attempt_message():
    # 코드R2 LOW: 같은 전공 재추가(track 변경 시도) — 오도 메시지 금지
    ctx = {**CTX, "convergence_program_ids": ["dsci_convergence"],
           "convergence_tracks": {"dsci_convergence": "다전공"}}
    payload = {**_payload(ctx), "question": "부전공으로 바꾸면?"}
    raw = _raw("다전공변경", "트랙 변경",
               add_convergence=[{"program_id": "dsci_convergence", "track": "부전공"}])
    resp = whatif.run_whatif(payload, client=_fake_client(raw))
    assert resp.status == "unsupported"
    assert "트랙 변경" in resp.unsupported_reason


# ---------- ⑩ 코드 검증 라운드3 회귀 ----------
def test_semantic_guard_strips_hallucinated_convergence():
    # 코드R3 MUST: strict schema를 '형식상' 통과한 환각(질문에 없는 융합 포기) 결정론 차단
    ctx = {**CTX, "convergence_program_ids": ["dsci_convergence"],
           "convergence_tracks": {"dsci_convergence": "다전공"}}
    payload = {**_payload(ctx), "question": "계절학기를 못 듣게 되면?"}   # 융합 언급 없음
    raw = _raw("계절학기", "계절 불가", seasonal_semester_allowed=False,
               drop_convergence=["dsci_convergence"])                    # LLM 환각 동반
    resp = whatif.run_whatif(payload, client=_fake_client(raw))
    assert resp.status == "ok"
    assert resp.after.context.convergence_program_ids == ["dsci_convergence"]  # 포기 미적용
    assert not any("포기" in c for c in resp.applied_changes)
    assert any("환각 가드" in a for a in resp.assumptions)               # 침묵 무시 금지
    assert resp.category == "계절학기"


def test_semantic_guard_allows_explicit_convergence_question():
    # 질문이 전공 변경을 명시하면 가드 미발동(과잉 차단 금지)
    ctx = {**CTX, "convergence_program_ids": ["dsci_convergence"],
           "convergence_tracks": {"dsci_convergence": "다전공"}}
    payload = {**_payload(ctx), "question": "다전공 빼면?"}
    raw = _raw("다전공변경", "융합 포기", drop_convergence=["dsci_convergence"])
    resp = whatif.run_whatif(payload, client=_fake_client(raw))
    assert resp.status == "ok"
    assert resp.after.context.convergence_program_ids == []


def test_leave_headline_covers_after_only_direction():
    # 코드R3-①: (gt_b=None → gt_a=산출) 역방향도 '변화 없음' 금지
    term = lambda lab: RoadmapTerm(term=lab, courses=[], term_credits=0)
    before = SimpleNamespace(
        risk=RiskAssessment(grade="C", label="주의"),
        audit=AuditResult(total_required=130, total_earned=110, total_gap=20,
                          area_gaps=[], convergence_checks=[], to_fusion_total=0.0,
                          missing_required_course_ids=[]),
        roadmap=RoadmapPlan(status="blocked", feasible=False, terms=[], overflow=None))
    after = SimpleNamespace(
        risk=RiskAssessment(grade="C", label="주의"),
        audit=before.audit,
        roadmap=RoadmapPlan(status="generated", feasible=True, terms=[term("2027-2")]))
    diff = whatif.build_diff(before, after, WhatIfDelta(calendar_delay_terms=1))
    assert "변화가 없습니다" not in diff.headline
    assert "휴학" in diff.headline


# ---------- ⑪ 실가동 점검 회귀 ----------
def test_inconsistent_extraction_not_cached_and_retried():
    # 실가동 발견: interpretable=true + 빈 delta(추출 실패)가 캐시되면 해당 질문 영구 '범위 밖'.
    ctx = {**CTX, "convergence_program_ids": ["dsci_convergence"],
           "convergence_tracks": {"dsci_convergence": "다전공"}}
    payload = {**_payload(ctx), "question": "다전공·부전공을 빼면?"}
    sctx = StudentContext.model_validate(payload["context"])
    add_ids, _ = whatif._candidates(sctx)
    key = whatif._cache_key("gpt-5-mini", "다전공·부전공을 빼면?", sctx, add_ids)
    # ① 오염 주입: 해석됨+빈 delta (실서버 S1 실사례 재현)
    bad = _raw("계절학기", "다전공 포기 문의")          # delta 전부 null
    whatif._cache_put(key, bad)
    # ② 정상 재해석 클라이언트로 호출 → evict+재해석으로 자가 치유
    good = _raw("다전공변경", "융합 포기", drop_convergence=["dsci_convergence"])
    resp = whatif.run_whatif(payload, client=_fake_client(good))
    assert resp.status == "ok" and resp.category == "다전공변경"
    assert whatif._cache_get(key)["delta"]["drop_convergence"] == ["dsci_convergence"]
    # ③ 신규 출력 자체가 빈 추출이면: 캐시 미저장 + 재시도 안내(한도 메시지 아님)
    whatif._cache_evict(key)
    resp2 = whatif.run_whatif(payload, client=_fake_client(bad))
    assert resp2.status == "unsupported" and "추출하지 못했습니다" in resp2.unsupported_reason
    assert whatif._cache_get(key) is None                  # 자기모순 출력 캐시 금지
    # ④ interpretable=false + 빈 delta는 정당한 '범위 밖' — 캐시 유지(기존 정책 불변)
    out = _raw("기타", "조기졸업 문의"); out["interpretable"] = False
    resp3 = whatif.run_whatif(payload, client=_fake_client(out))
    assert resp3.status == "unsupported" and "범위 밖" in resp3.unsupported_reason
    assert whatif._cache_get(key) is not None


# ---------- ⑦ API 레벨 ----------
def test_api_validation_and_degrade(monkeypatch):
    from fastapi.testclient import TestClient
    import app as app_module
    # app import가 .env를 로드해 실제 키가 복원될 수 있음 — 라이브 LLM 호출 차단
    monkeypatch.setattr(whatif, "_get_client", lambda: None)
    client = TestClient(app_module.app)
    payload = _payload(CTX)
    r = client.post("/graduation/v2/whatif", json=payload)             # question 누락
    assert r.status_code == 400
    r = client.post("/graduation/v2/whatif", json={**payload, "question": "x" * 201})
    assert r.status_code == 400
    r = client.post("/graduation/v2/whatif", json={**payload, "question": "휴학하면?"})
    assert r.status_code == 200                                        # 키 없음 → 200 + unsupported
    assert r.json()["status"] == "unsupported"


def test_explicit_cap_overrides_gpa_bonus():
    """'12학점 이내로' 명시 상한 시 성적우수 보너스(+3) 미적용 — 첫 학기 15 배치 버그
    (2026-06-05 사용자 발견). 보너스는 상한 확대 옵션이지 의무가 아님."""
    from graduation_center.v2.planner import _ordered_terms
    from graduation_center.v2.models_v2 import StudentContext
    ctx = StudentContext(program_id="ai_bigdata", current_term="2026-1", remaining_semesters=2,
                         prev_term_gpa_ge_375=True, max_credits_per_term=12)
    terms = _ordered_terms(ctx, reg_cap=12)
    regs = [cap for lab, cap in terms if not lab.endswith(("S", "W"))]
    assert regs and all(c == 12 for c in regs)          # 첫 학기 포함 전부 12
    ctx2 = ctx.model_copy(update={"max_credits_per_term": None})
    terms2 = _ordered_terms(ctx2, reg_cap=18)
    regs2 = [cap for lab, cap in terms2 if not lab.endswith(("S", "W"))]
    assert regs2[0] == 21                               # 명시 상한 없으면 보너스 유지
