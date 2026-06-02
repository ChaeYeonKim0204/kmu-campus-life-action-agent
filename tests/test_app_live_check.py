from fastapi.testclient import TestClient

import app as app_module
from agent.answer_builder import _live_check_note


def test_live_check_note_success():
    note = _live_check_note({"attempted": True, "network_success": 2, "fallback_used": 0, "network_failed": 0})
    assert note is not None and "최신 공식 자료 확인 완료" in note and "2건" in note


def test_live_check_note_failure():
    note = _live_check_note({"attempted": True, "network_success": 0, "fallback_used": 0, "network_failed": 1})
    assert note is not None and "실패" in note


def test_live_check_note_fallback():
    note = _live_check_note({"attempted": True, "network_success": 0, "fallback_used": 1, "network_failed": 0})
    assert note is not None and "저장/대체 근거" in note


def test_live_check_note_cooldown():
    note = _live_check_note({"attempted": False, "cooldown_remaining_seconds": 30})
    assert note is not None and "재확인" in note


def test_live_check_note_none_when_not_attempted():
    assert _live_check_note({"attempted": False, "cooldown_remaining_seconds": 0}) is None
    assert _live_check_note(None) is None


def test_live_check_note_skipped_when_requested_but_no_source():
    note = _live_check_note({"attempted": False, "status": "skipped", "cooldown_remaining_seconds": 0})
    assert note is not None and "저장된 근거" in note


def test_ask_live_check_note_appears_in_answer_body(monkeypatch):
    def fake_refresh(issue_type, query="", **kwargs):
        return {"attempted": True, "updated": False, "network_success": 1, "fallback_used": 0, "network_failed": 0,
                "cooldown_remaining_seconds": 0}

    monkeypatch.setattr(app_module, "refresh_sources_for_issue", fake_refresh)
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 기간 언제야?", "live_check": True})

    assert response.status_code == 200
    data = response.json()
    assert "[주의]" in data["answer"]
    assert "최신 확인: 최신 공식 자료 확인 완료" in data["answer"]


def test_ask_runs_live_check_when_requested(monkeypatch):
    calls = []

    def fake_refresh(issue_type, query="", **kwargs):
        calls.append({"issue_type": issue_type, "query": query, **kwargs})
        return {"attempted": True, "updated": False, "network_success": 0, "fallback_used": 0, "network_failed": 0}

    monkeypatch.setattr(app_module, "refresh_sources_for_issue", fake_refresh)
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 기간 언제야?", "live_check": True})

    assert response.status_code == 200
    assert calls
    assert response.json()["live_check"]["attempted"] is True


def test_ask_skips_live_check_when_privacy_blocks(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "refresh_sources_for_issue", lambda *args, **kwargs: calls.append(args))
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "내 학번이랑 성적으로 처리해줘.", "live_check": True})

    assert response.status_code == 200
    assert response.json()["issue_type"] == "privacy_blocked"
    assert response.json()["live_check"]["attempted"] is False
    assert calls == []


def test_ask_polishes_answer_when_enabled(monkeypatch):
    class FakeLLM:
        enabled = True
        polish_enabled = True

        def expand_search_query(self, question, issue_type, student_context=None):
            return {"used": False, "expanded_query": question, "keywords": [], "error": None}

        def rerank_chunks(self, question, issue_type, chunks, limit=None):
            return chunks[:limit], {"used": False, "selected_chunk_ids": [], "error": None}

        def polish_answer(self, answer):
            return {"used": True, "answer": f"{answer}\n\n[polished]", "error": None, "rejected_reason": None}

    monkeypatch.setattr(app_module, "llm_client", FakeLLM())
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 완료됐는지 어디서 확인해?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].endswith("[polished]")
    assert data["llm"]["polish"]["used"] is True


def test_ask_rejects_polish_when_final_citation_contract_breaks(monkeypatch):
    class FakeLLM:
        enabled = True
        polish_enabled = True

        def expand_search_query(self, question, issue_type, student_context=None):
            return {"used": False, "expanded_query": question, "keywords": [], "error": None}

        def rerank_chunks(self, question, issue_type, chunks, limit=None):
            return chunks[:limit], {"used": False, "selected_chunk_ids": [], "error": None}

        def polish_answer(self, answer):
            return {"used": True, "answer": answer.replace("[S1]", "[S999]", 1), "error": None, "rejected_reason": None}

    monkeypatch.setattr(app_module, "llm_client", FakeLLM())
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 완료됐는지 어디서 확인해?"})

    assert response.status_code == 200
    data = response.json()
    assert "[S999]" not in data["answer"]
    assert data["answer_validation"]["ok"] is True
    assert data["llm"]["polish"]["used"] is False
    assert data["llm"]["polish"]["rejected_reason"] == "final_output_guard_failed"


def test_ask_rejects_polish_when_sensitive_output_is_added(monkeypatch):
    class FakeLLM:
        enabled = True
        polish_enabled = True

        def expand_search_query(self, question, issue_type, student_context=None):
            return {"used": False, "expanded_query": question, "keywords": [], "error": None}

        def rerank_chunks(self, question, issue_type, chunks, limit=None):
            return chunks[:limit], {"used": False, "selected_chunk_ids": [], "error": None}

        def polish_answer(self, answer):
            return {
                "used": True,
                "answer": f"{answer}\n참고 값: 2026123456",
                "error": None,
                "rejected_reason": None,
            }

    monkeypatch.setattr(app_module, "llm_client", FakeLLM())
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 완료됐는지 어디서 확인해?"})

    assert response.status_code == 200
    data = response.json()
    assert "2026123456" not in data["answer"]
    assert data["output_privacy"]["ok"] is True
    assert data["llm"]["polish"]["used"] is False
    assert data["llm"]["polish"]["rejected_reason"] == "final_output_guard_failed"
