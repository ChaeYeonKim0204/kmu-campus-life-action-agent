"""Demo scenario regression — README §15.2 데모 릴리즈 5 시나리오.

기본은 deterministic 모드 (llm_assist=false, 비용 0). 보조 노드 검증은
@pytest.mark.live_llm 마크 케이스에서 별도 (opt-in).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def _assert_common_contract(data: dict) -> None:
    """README §15.2 / agent_product_planning.md §19.4 공통 contract."""
    assert data["answer_validation"]["ok"] is True, data["answer_validation"]
    assert data["output_privacy"]["ok"] is True, data["output_privacy"]
    assert len(data["citations"]) >= 1, "citations 비어있음"
    logs = data["tool_logs"]
    assert any("classify_issue" in log for log in logs), logs
    assert any("search_official_sources" in log for log in logs), logs
    assert any("build_final_answer" in log for log in logs), logs


def test_demo_scenario_attendance_militia():
    """예비군 결석 → attendance + 출석인정신청서 액션."""
    r = client.post("/ask", json={
        "question": "다음 주 예비군 훈련 때문에 결석하는데 어떻게 해야 하나요?",
        "student_context": {"status": "enrolled"},
        "llm_assist": False,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "attendance", data["issue_type"]
    action_ids = {a.get("action_id") for a in data.get("next_actions", [])}
    assert "draft_attendance_recognition_form" in action_ids, action_ids
    _assert_common_contract(data)


def test_demo_scenario_ecampus_no_class():
    """이캠 강의 미표시 → portal_access + playbook override (수강신청 완료 확인 안내)."""
    r = client.post("/ask", json={
        "question": "이캠에 강의가 안 떠요",
        "llm_assist": False,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "portal_access", data["issue_type"]
    # playbook override: 수강신청 완료 여부 확인 안내
    assert "수강신청" in data["answer"]
    _assert_common_contract(data)


def test_demo_scenario_returning_student_week():
    """복학생 이번 주 → schedule + returning context의 학생 맞춤 확인 섹션."""
    r = client.post("/ask", json={
        "question": "복학생인데 이번 주 뭐 해야 해?",
        "student_context": {"status": "returning"},
        "llm_assist": False,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "schedule", data["issue_type"]
    # 복학생 맞춤 확인 섹션 등장
    assert "[학생 맞춤 확인]" in data["answer"]
    _assert_common_contract(data)


def test_demo_scenario_tuition_payment_check():
    """등록금 납부확인 → registration_tuition + playbook override (은행/포털 시점 분리)."""
    r = client.post("/ask", json={
        "question": "등록금 냈는데 납부확인이 안 떠요",
        "llm_assist": False,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "registration_tuition", data["issue_type"]
    assert "납부" in data["answer"]
    _assert_common_contract(data)


def test_demo_scenario_graduation_requirements():
    """졸업요건 부족 → graduation + graduation_audit 액션."""
    r = client.post("/ask", json={
        "question": "졸업요건 부족한지 알고 싶어요",
        "llm_assist": False,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "graduation", data["issue_type"]
    action_ids = {a.get("action_id") for a in data.get("next_actions", [])}
    assert "graduation_audit" in action_ids, action_ids
    _assert_common_contract(data)


# ---- Live LLM 마크 케이스 (opt-in: pytest -m live_llm) ----

@pytest.mark.live_llm
def test_demo_scenario_attendance_with_llm_assist_uses_selection():
    """llm_assist=true에서 expand·rerank 둘 다 used=true + selected_chunk_ids 비어있지 않음.

    polish는 rejection 가능성 있어 조건부; expand/rerank는 정상 흐름에서 항상 동작해야.
    """
    r = client.post("/ask", json={
        "question": "다음 주 예비군 훈련 때문에 결석하는데 어떻게 해야 하나요?",
        "student_context": {"status": "enrolled"},
        "llm_assist": True,
        "live_check": False,
    })
    assert r.status_code == 200
    data = r.json()
    llm = data["llm"]
    # 정상 운영 흐름 강제: expand 사용 + rerank 사용 + selected_chunk_ids 비어있지 않음
    assert llm["query_expansion"]["used"], f"expand used=false (정상 운영 흐름 위반): {llm}"
    assert llm["rerank"]["used"], f"rerank used=false (정상 운영 흐름 위반): {llm}"
    assert len(llm["rerank"]["selected_chunk_ids"]) >= 1, llm["rerank"]
    # polish는 rejection 가능 (citation 보존 실패 등) — 조건부 검증
    if llm["polish"]["used"]:
        assert llm["polish"]["rejected_reason"] is None
