import json

from llm_client import GuardedLLMClient


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("FakeResponse", (), {"output_text": json.dumps(self.payload, ensure_ascii=False)})()


class FakeOpenAIClient:
    def __init__(self, payload):
        self.responses = FakeResponses(payload)


def test_llm_client_disabled_preserves_query_without_importing_openai():
    client = GuardedLLMClient(enabled=False)

    result = client.expand_search_query("예비군 때문에 결석", "attendance")

    assert result["used"] is False
    assert result["expanded_query"] == "예비군 때문에 결석"


def test_llm_client_enabled_without_api_key_fails_closed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = GuardedLLMClient(enabled=True)

    result = client.expand_search_query("예비군 때문에 결석", "attendance")

    assert result["used"] is False
    assert result["error"] is None
    assert client.status()["api_key_configured"] is False
    assert client.status()["error"] == "openai_api_key_missing"


def test_expand_search_query_uses_structured_output():
    fake = FakeOpenAIClient(
        {
            "expanded_query": "예비군 때문에 결석 출석인정 공결 훈련필증",
            "keywords": ["출석인정", "예비군", "훈련필증"],
        }
    )
    client = GuardedLLMClient(enabled=True, client=fake)

    result = client.expand_search_query("예비군 때문에 결석", "attendance")

    assert result["used"] is True
    assert "출석인정" in result["expanded_query"]
    assert result["keywords"] == ["출석인정", "예비군", "훈련필증"]
    assert fake.responses.calls[0]["text"]["format"]["type"] == "json_schema"


def test_rerank_chunks_preserves_unselected_chunks_after_selected_ids():
    fake = FakeOpenAIClient({"selected_chunk_ids": ["c2"]})
    client = GuardedLLMClient(enabled=True, client=fake)
    chunks = [
        {"chunk_id": "c1", "title": "A", "text": "첫 번째"},
        {"chunk_id": "c2", "title": "B", "text": "두 번째"},
    ]

    reranked, metadata = client.rerank_chunks("질문", "attendance", chunks)

    assert metadata["used"] is True
    assert metadata["selected_chunk_ids"] == ["c2"]
    assert [chunk["chunk_id"] for chunk in reranked] == ["c2", "c1"]


def test_polish_answer_preserves_sources_block_and_citations():
    answer = "[답변 요약]\n출석인정 안내입니다.[S1]\n\n[근거]\n- [S1] 공식 문서 / https://example.edu / 원문"
    fake = FakeOpenAIClient({"polished_body": "[답변 요약]\n출석인정 안내를 확인했습니다.[S1]"})
    client = GuardedLLMClient(enabled=True, client=fake)
    client.polish_enabled = True

    result = client.polish_answer(answer)

    assert result["used"] is True
    assert result["answer"].endswith("[근거]\n- [S1] 공식 문서 / https://example.edu / 원문")
    assert "확인했습니다.[S1]" in result["answer"]


def test_polish_answer_rejects_changed_citations():
    answer = "[답변 요약]\n출석인정 안내입니다.[S1]\n\n[근거]\n- [S1] 공식 문서 / https://example.edu / 원문"
    fake = FakeOpenAIClient({"polished_body": "[답변 요약]\n출석인정 안내를 확인했습니다."})
    client = GuardedLLMClient(enabled=True, client=fake)
    client.polish_enabled = True

    result = client.polish_answer(answer)

    assert result["used"] is False
    assert result["answer"] == answer
    assert result["rejected_reason"] == "citation_markers_changed"
