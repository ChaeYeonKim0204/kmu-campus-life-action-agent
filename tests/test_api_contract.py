import json

from fastapi.testclient import TestClient

import app as app_module


_ACTION_COMMON_FIELDS = (
    "answer",
    "issue_type",
    "classification",
    "tool_logs",
    "sources",
    "citations",
    "next_actions",
    "safety_flags",
    "answer_validation",
    "output_privacy",
    "llm",
    "live_check",
)


def _assert_action_common_fields(data):
    for field in _ACTION_COMMON_FIELDS:
        assert field in data, f"missing common field: {field}"
    assert isinstance(data["tool_logs"], list)
    assert isinstance(data["sources"], list)
    assert isinstance(data["citations"], list)
    assert isinstance(data["next_actions"], list)
    assert isinstance(data["safety_flags"], list)
    assert "ok" in data["answer_validation"]
    assert "ok" in data["output_privacy"]
    assert "used" in data["llm"]
    assert "attempted" in data["live_check"]


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


def test_actions_continue_completed_includes_citations_from_sources():
    client = TestClient(app_module.app)
    slots = {
        "certificate_type": "졸업예정증명서",
        "purpose_optional": "확인용",
    }

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["sources"]
    assert data["citations"]
    source_chunk_ids = {chunk.get("chunk_id") for chunk in data["sources"]}
    assert all(citation["chunk_id"] in source_chunk_ids for citation in data["citations"])


def test_actions_continue_completed_has_common_fields():
    client = TestClient(app_module.app)
    slots = {"certificate_type": "졸업예정증명서", "purpose_optional": "확인용"}

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    _assert_action_common_fields(data)
    assert data["tool_logs"]
    assert "document" in data


def test_actions_continue_needs_input_has_common_fields():
    client = TestClient(app_module.app)

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": {}})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_input"
    _assert_action_common_fields(data)
    assert data["tool_logs"]
    assert data["missing_slots"]


def test_actions_continue_privacy_blocked_has_common_fields():
    client = TestClient(app_module.app)
    slots = {"certificate_type": "졸업예정증명서", "purpose_optional": "학번 2026123456"}

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    _assert_action_common_fields(data)
    assert "guard.inspect_privacy 호출됨" in data["tool_logs"]
    assert data["safety_flags"]
    assert data["sources"] == []
    assert data["citations"] == []


def test_actions_continue_output_privacy_blocked_has_common_fields(monkeypatch):
    def fake_continue_action(action_id, slots, chunks):
        return {
            "status": "completed",
            "action_id": action_id,
            "document": "초안에 2026123456 값이 들어감",
            "checklist": [],
        }

    monkeypatch.setattr(app_module, "continue_action", fake_continue_action)
    client = TestClient(app_module.app)
    slots = {"certificate_type": "졸업예정증명서", "purpose_optional": "확인용"}

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    _assert_action_common_fields(data)
    assert "document" not in data
    assert data["output_privacy"]["ok"] is False


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


# --- B3: action grounding policy (§11.4·§12.4) ---


def test_actions_continue_blocks_when_official_source_missing(monkeypatch):
    monkeypatch.setattr(app_module, "_prefer_issue_matched_chunks", lambda *args, **kwargs: [])
    client = TestClient(app_module.app)
    slots = {"certificate_type": "졸업예정증명서", "purpose_optional": "확인용"}

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    assert data["grounding"] == "official_chunk_required"
    assert "no_official_source" in data["safety_flags"]
    assert data["sources"] == []
    assert data["citations"] == []
    assert "document" not in data
    _assert_action_common_fields(data)


def test_actions_continue_contact_only_allowed_without_official_source(monkeypatch):
    monkeypatch.setattr(app_module, "_prefer_issue_matched_chunks", lambda *args, **kwargs: [])
    client = TestClient(app_module.app)
    slots = {
        "topic": "성적 정정 문의",
        "destination_optional": "학과사무실",
        "question_summary": "정정 절차가 궁금합니다",
    }

    response = client.post("/actions/continue", json={"action_id": "draft_contact_message", "slots": slots})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] != "blocked"
    assert data["grounding"] == "contact_only"


def test_actions_continue_needs_input_not_blocked_by_grounding(monkeypatch):
    monkeypatch.setattr(app_module, "_prefer_issue_matched_chunks", lambda *args, **kwargs: [])
    client = TestClient(app_module.app)

    response = client.post("/actions/continue", json={"action_id": "certificate_issue_guide", "slots": {}})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_input"
    assert data["grounding"] == "official_chunk_required"
    assert data["missing_slots"]


# --- B6: agent_usage telemetry + /health agent_metrics (§20) ---


def test_summarize_agent_usage_handles_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "AGENT_USAGE_LOG_PATH", tmp_path / "missing.jsonl")

    summary = app_module._summarize_agent_usage()

    assert summary["count"] == 0
    assert summary["privacy_block_rate"] == 0.0
    assert summary["avg_latency_ms"] == 0.0


def test_summarize_agent_usage_computes_rates(tmp_path, monkeypatch):
    log_path = tmp_path / "agent_usage.jsonl"
    records = [
        {"privacy_blocked": True, "no_source": False, "citation_validation_ok": True,
         "output_privacy_ok": True, "live_check_attempted": False, "llm_fallback": False, "latency_ms": 10},
        {"privacy_blocked": False, "no_source": True, "citation_validation_ok": True,
         "output_privacy_ok": True, "live_check_attempted": True, "live_check_success": False,
         "llm_fallback": True, "latency_ms": 20},
        {"privacy_blocked": False, "no_source": False, "citation_validation_ok": False,
         "output_privacy_ok": False, "live_check_attempted": True, "live_check_success": True,
         "llm_fallback": False, "latency_ms": 30},
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "AGENT_USAGE_LOG_PATH", log_path)

    summary = app_module._summarize_agent_usage()

    assert summary["count"] == 3
    assert summary["privacy_block_rate"] == round(1 / 3, 4)
    assert summary["no_source_rate"] == round(1 / 3, 4)
    assert summary["citation_validation_fail_rate"] == round(1 / 3, 4)
    assert summary["output_privacy_fail_rate"] == round(1 / 3, 4)
    assert summary["live_check_success_rate"] == 0.5
    assert summary["llm_fallback_rate"] == round(1 / 3, 4)
    assert summary["avg_latency_ms"] == 20.0


def test_ask_writes_agent_usage_and_health_aggregates(tmp_path, monkeypatch):
    log_path = tmp_path / "agent_usage.jsonl"
    monkeypatch.setattr(app_module, "AGENT_USAGE_LOG_PATH", log_path)
    client = TestClient(app_module.app)

    grounded = client.post("/ask", json={"question": "졸업예정증명서 어디서 뽑아?", "llm_assist": False})
    assert grounded.status_code == 200

    blocked = client.post("/ask", json={"question": "내 학번 2026123456으로 처리해줘", "llm_assist": False})
    assert blocked.status_code == 200
    assert blocked.json()["issue_type"] == "privacy_blocked"

    metrics = client.get("/health").json()["agent_metrics"]
    assert metrics["count"] >= 2
    assert metrics["privacy_block_rate"] > 0
    assert "no_source_rate" in metrics
    assert "llm_fallback_rate" in metrics
    assert metrics["avg_latency_ms"] >= 0


def test_agent_usage_log_never_stores_raw_question(tmp_path, monkeypatch):
    log_path = tmp_path / "agent_usage.jsonl"
    monkeypatch.setattr(app_module, "AGENT_USAGE_LOG_PATH", log_path)
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "내 학번 2026123456으로 처리해줘", "llm_assist": False})
    assert response.status_code == 200

    content = log_path.read_text(encoding="utf-8")
    assert "2026123456" not in content
    record = json.loads(content.strip().splitlines()[-1])
    assert "question" not in record
    assert record["status"] == "privacy_blocked"
    assert record["privacy_blocked"] is True


# --- out-of-scope intent (casual / non-academic queries) ---


def test_ask_out_of_scope_returns_friendly_redirect_with_common_fields():
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "오늘 점심 뭐먹을까?", "llm_assist": False})

    assert response.status_code == 200
    data = response.json()
    assert data["issue_type"] == "out_of_scope"
    assert data["classification"]["issue_type"] == "out_of_scope"
    assert "out_of_scope" in data["safety_flags"]
    assert data["sources"] == []
    assert data["citations"] == []
    assert data["next_actions"] == []
    assert data["scope"]["out_of_scope"] is True
    assert data["scope"]["suggested_questions"]
    assert "intent_scope.detect_out_of_scope 호출됨" in data["tool_logs"]
    for field in _ACTION_COMMON_FIELDS:
        assert field in data, f"missing common field: {field}"


def test_ask_out_of_scope_skips_retrieval_path(monkeypatch):
    """An out-of-scope query must not exercise the retriever or LLM path."""
    called = {"search": 0}

    def fake_search(*args, **kwargs):
        called["search"] += 1
        return []

    monkeypatch.setattr(app_module.retriever, "search", fake_search)
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "안녕", "llm_assist": True})

    assert response.status_code == 200
    data = response.json()
    assert data["issue_type"] == "out_of_scope"
    assert called["search"] == 0
    assert data["llm"]["used"] is False
    assert data["llm"]["reason"] == "out_of_scope"


def test_ask_academic_food_query_is_not_blocked():
    """Queries with academic override terms must still run normal retrieval."""
    client = TestClient(app_module.app)

    response = client.post("/ask", json={"question": "오늘 학식 메뉴 어디서 확인해?", "llm_assist": False})

    assert response.status_code == 200
    data = response.json()
    assert data["issue_type"] != "out_of_scope"
