from fastapi.testclient import TestClient

import app as app_module


def test_ask_response_contract_for_grounded_answer():
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "졸업예정증명서 어디서 뽑아?", "llm_assist": False})

    assert response.status_code == 200
    data = response.json()
    assert data["issue_type"] == "certificate"
    assert data["answer"]
    assert data["citations"]
    assert data["answer_validation"]["ok"] is True
    assert set(data["answer_validation"]["markers"]).issubset(set(data["answer_validation"]["citation_ids"]))
    assert data["llm"]["assist_requested"] is False
    assert data["live_check"]["attempted"] is False


def test_ask_llm_assist_false_skips_llm_calls_even_when_enabled(monkeypatch):
    class FailingLLM:
        enabled = True
        polish_enabled = True

        def expand_search_query(self, *args, **kwargs):
            raise AssertionError("LLM query expansion should not run")

        def rerank_chunks(self, *args, **kwargs):
            raise AssertionError("LLM rerank should not run")

        def polish_answer(self, *args, **kwargs):
            raise AssertionError("LLM polish should not run")

    monkeypatch.setattr(app_module, "llm_client", FailingLLM())
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "수강신청 완료됐는지 어디서 확인해?", "llm_assist": False})

    assert response.status_code == 200
    data = response.json()
    assert data["answer_validation"]["ok"] is True
    assert data["llm"]["assist_requested"] is False


def test_health_exposes_llm_status_shape():
    client = TestClient(app_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "enabled" in data["llm"]
    assert "api_key_configured" in data["llm"]
    assert "polish_enabled" in data["llm"]
    assert "live_refresh" in data
    assert "count" in data["live_refresh"]
    assert "recent" in data["live_refresh"]


def test_summarize_live_refresh_state_sorts_latest_first():
    state = {
        "last_live_refresh": {
            "certificate": {
                "completed_at": "2026-05-18T00:00:00+00:00",
                "documents_seen": 1,
                "updated_documents": 1,
                "fetch_summary": {"network_success": 1, "fallback_used": 0, "network_failed": 0},
            },
            "attendance": {
                "completed_at": "2026-05-19T00:00:00+00:00",
                "documents_seen": 2,
                "updated_documents": 0,
                "fetch_summary": {"network_success": 0, "fallback_used": 1, "network_failed": 1},
            },
        }
    }

    summary = app_module._summarize_live_refresh_state(state)

    assert summary["count"] == 2
    assert summary["latest"]["issue_type"] == "attendance"
    assert summary["latest"]["fallback_used"] == 1


def test_actions_continue_returns_output_privacy_metadata():
    client = TestClient(app_module.app)
    slots = {
        "certificate_type": "졸업예정증명서",
        "purpose_optional": "확인용",
    }

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["output_privacy"]["ok"] is True


def test_actions_continue_blocks_sensitive_generated_output(monkeypatch):
    def fake_continue_action(action_id, slots, chunks):
        return {
            "status": "completed",
            "action_id": action_id,
            "document": "초안에 2026123456 값이 들어감",
            "checklist": [],
        }

    monkeypatch.setattr(app_module, "continue_action", fake_continue_action)
    client = TestClient(app_module.app)
    slots = {
        "certificate_type": "졸업예정증명서",
        "purpose_optional": "확인용",
    }

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    assert "document" not in data
    assert "student_id_value" in data["safety_flags"]


def test_actions_continue_runs_live_check_when_requested(monkeypatch):
    calls = []

    def fake_refresh(issue_type, query="", **kwargs):
        calls.append({"issue_type": issue_type, "query": query, **kwargs})
        return {"attempted": True, "updated": False, "network_success": 0, "fallback_used": 0, "network_failed": 0}

    monkeypatch.setattr(app_module, "refresh_sources_for_issue", fake_refresh)
    client = TestClient(app_module.app)
    slots = {
        "certificate_type": "졸업예정증명서",
        "purpose_optional": "확인용",
    }

    response = client.post(
        "/actions/continue",
        json={"action_id": "certificate_issue_guide", "slots": slots, "live_check": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["live_check"]["attempted"] is True
    assert calls[0]["issue_type"] == "certificate"


def test_actions_continue_skips_live_check_when_privacy_blocks(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "refresh_sources_for_issue", lambda *args, **kwargs: calls.append(args))
    client = TestClient(app_module.app)
    slots = {
        "certificate_type": "졸업예정증명서",
        "purpose_optional": "학번 2026123456",
    }

    response = client.post(
        "/actions/continue",
        json={"action_id": "certificate_issue_guide", "slots": slots, "live_check": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    assert calls == []


def test_admin_live_refresh_endpoint(monkeypatch):
    calls = []
    reloads = []

    def fake_refresh(issue_type, query="", **kwargs):
        calls.append({"issue_type": issue_type, "query": query, **kwargs})
        return {
            "attempted": True,
            "status": "completed",
            "updated": True,
            "issue_type": issue_type,
            "network_success": 1,
            "fallback_used": 0,
            "network_failed": 0,
        }

    monkeypatch.setattr(app_module, "refresh_sources_for_issue", fake_refresh)
    monkeypatch.setattr(app_module.retriever, "reload", lambda: reloads.append(True))
    client = TestClient(app_module.app)

    response = client.post(
        "/ingest/live-refresh",
        json={"issue_type": "certificate", "query": "졸업예정증명서", "max_pages": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["updated"] is True
    assert calls[0]["issue_type"] == "certificate"
    assert calls[0]["query"] == "졸업예정증명서"
    assert calls[0]["max_pages"] == 2
    assert reloads == [True]
