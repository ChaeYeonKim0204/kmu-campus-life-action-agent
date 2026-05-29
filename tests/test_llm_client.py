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


class FakeResponsesWithTempReject:
    """Simulate a model that rejects the temperature parameter on first N calls."""

    def __init__(self, payload, fail_n: int = 1):
        self.payload = payload
        self.calls = []
        self._fail_remaining = fail_n

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "temperature" in kwargs and self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError(
                "400 Bad Request: Unsupported value: 'temperature' is not supported with this model."
            )
        return type("FakeResponse", (), {"output_text": json.dumps(self.payload, ensure_ascii=False)})()


class FakeOpenAIClientWithTempReject:
    def __init__(self, payload, fail_n: int = 1):
        self.responses = FakeResponsesWithTempReject(payload, fail_n=fail_n)


def test_json_response_falls_back_when_temperature_rejected():
    fake = FakeOpenAIClientWithTempReject(
        {"expanded_query": "이캠 안돼요 eCampus", "keywords": ["eCampus"]},
        fail_n=1,
    )
    client = GuardedLLMClient(enabled=True, client=fake)

    result = client.expand_search_query("이캠 안돼요", "portal_access")

    assert result["used"] is True
    assert len(fake.responses.calls) == 2
    assert "temperature" in fake.responses.calls[0]
    assert "temperature" not in fake.responses.calls[1]
    assert client._supports_temperature is False


def test_json_response_passes_max_output_tokens_per_method():
    fake_expand = FakeOpenAIClient({"expanded_query": "q", "keywords": []})
    GuardedLLMClient(enabled=True, client=fake_expand).expand_search_query("질문", "attendance")
    assert fake_expand.responses.calls[0]["max_output_tokens"] == 400

    fake_rerank = FakeOpenAIClient({"selected_chunk_ids": ["c1"]})
    client_rerank = GuardedLLMClient(enabled=True, client=fake_rerank)
    client_rerank.rerank_chunks("질문", "attendance", [{"chunk_id": "c1", "title": "t", "text": "x"}])
    assert fake_rerank.responses.calls[0]["max_output_tokens"] == 400

    answer = "[답변 요약]\n안내.[S1]\n\n[근거]\n- [S1] src / url / x"
    fake_polish = FakeOpenAIClient({"polished_body": "[답변 요약]\n안내 드립니다.[S1]"})
    client_polish = GuardedLLMClient(enabled=True, client=fake_polish)
    client_polish.polish_enabled = True
    client_polish.polish_answer(answer)
    assert fake_polish.responses.calls[0]["max_output_tokens"] == 1500


def test_reasoning_effort_minimal_added_for_gpt5_model():
    fake = FakeOpenAIClient({"expanded_query": "q", "keywords": []})
    client = GuardedLLMClient(enabled=True, client=fake, model="gpt-5-mini")

    client.expand_search_query("질문", "attendance")

    assert fake.responses.calls[0].get("reasoning") == {"effort": "minimal"}


def test_reasoning_param_omitted_for_non_reasoning_model():
    fake = FakeOpenAIClient({"expanded_query": "q", "keywords": []})
    client = GuardedLLMClient(enabled=True, client=fake, model="gpt-4o-mini")

    client.expand_search_query("질문", "attendance")

    assert "reasoning" not in fake.responses.calls[0]


def test_supports_temperature_flag_cached_after_rejection():
    fake = FakeOpenAIClientWithTempReject(
        {"expanded_query": "q", "keywords": []},
        fail_n=1,
    )
    client = GuardedLLMClient(enabled=True, client=fake)

    client.expand_search_query("질문1", "attendance")
    client.expand_search_query("질문2", "attendance")

    # 첫 호출: temperature 포함(실패) → 재시도(성공) = 2회
    # 두 번째 호출: 캐싱된 _supports_temperature=False로 temperature 미포함 = 1회
    assert len(fake.responses.calls) == 3
    assert "temperature" in fake.responses.calls[0]
    assert "temperature" not in fake.responses.calls[1]
    assert "temperature" not in fake.responses.calls[2]


# ---- P1 회귀: usage 로그 ----

class FakeResponsesUnconditionalFail:
    """Simulate an API error unrelated to temperature so the gard does not retry."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("502 Bad Gateway: upstream timed out")


class FakeOpenAIClientUnconditionalFail:
    def __init__(self):
        self.responses = FakeResponsesUnconditionalFail()


def test_usage_log_never_contains_raw_question_or_chunk_text(usage_log_path):
    """raw 절대 미저장: question 본문·chunk text·answer body가 로그에 들어가면 안 됨."""
    raw_question = "학번 2025XXXXXX 입니다 이캠 강의가 안 떠요"  # 민감값 + 질문 본문
    raw_chunk_text = "공식안내본문_DO_NOT_LOG"
    fake = FakeOpenAIClient(
        {
            "expanded_query": "이캠 강의 안 뜸",
            "keywords": ["이캠", "강의"],
        }
    )
    client = GuardedLLMClient(enabled=True, client=fake)

    client.expand_search_query(raw_question, "portal_access", {"status": "enrolled"})

    chunks = [{"chunk_id": "c1", "title": "t", "text": raw_chunk_text}]
    fake2 = FakeOpenAIClient({"selected_chunk_ids": ["c1"]})
    client2 = GuardedLLMClient(enabled=True, client=fake2)
    client2.rerank_chunks(raw_question, "portal_access", chunks)

    log_content = usage_log_path.read_text(encoding="utf-8")
    assert raw_question not in log_content, "raw question 본문이 로그에 유출됨"
    assert "2025XXXXXX" not in log_content, "raw 학번 값이 로그에 유출됨"
    assert raw_chunk_text not in log_content, "raw chunk text가 로그에 유출됨"


def test_usage_log_records_when_used_false_on_api_failure(usage_log_path):
    """used=False (API 실패) 케이스도 1줄 기록 — 운영 메트릭에서 실패율 보이게."""
    fake = FakeOpenAIClientUnconditionalFail()
    client = GuardedLLMClient(enabled=True, client=fake)

    result = client.expand_search_query("test", "attendance")

    assert result["used"] is False
    assert result["error"] is not None
    assert usage_log_path.exists()
    lines = [line for line in usage_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["node"] == "expand"
    assert record["used"] is False
    assert record["error"] is not None
    assert record["model"]  # 모델명 채워짐


def test_polish_prompt_includes_readme_section_11_2_phrases():
    """README §11.2 권장 표현 + 금지 표현 + [주의] 톤 지시가 polish 프롬프트에 들어가있음."""
    answer = "[답변 요약]\n안내합니다.[S1]\n\n[근거]\n- [S1] src / url / x"
    fake = FakeOpenAIClient({"polished_body": "[답변 요약]\n안내드립니다.[S1]"})
    client = GuardedLLMClient(enabled=True, client=fake)
    client.polish_enabled = True

    client.polish_answer(answer)

    user_input = next(
        item["content"]
        for item in fake.responses.calls[0]["input"]
        if item["role"] == "user"
    )
    # 권장 표현 (README §11.2)
    assert "공식 근거에서 확인되는 내용은" in user_input
    assert "ON국민 포털에서 직접 확인" in user_input
    # 금지 표현
    assert "승인됩니다" in user_input
    assert "비밀번호를 입력하세요" in user_input
    assert "제가 포털에서 확인했습니다" in user_input
    # live_check 톤 보존 지시
    assert "[주의]" in user_input


def test_rerank_selected_chunk_ids_are_subset_of_input(usage_log_path):
    """rerank source contract: selected_chunk_ids ⊆ 입력 chunk_ids (사실 추가 방지)."""
    # 모델이 invalid ID('xx99')를 섞어서 반환해도 클라이언트가 입력 set 안에서만 골라야 함
    fake = FakeOpenAIClient({"selected_chunk_ids": ["c2", "xx99", "c1"]})
    client = GuardedLLMClient(enabled=True, client=fake)
    chunks = [
        {"chunk_id": "c1", "title": "A", "text": "첫 번째"},
        {"chunk_id": "c2", "title": "B", "text": "두 번째"},
        {"chunk_id": "c3", "title": "C", "text": "세 번째"},
    ]
    input_ids = {chunk["chunk_id"] for chunk in chunks}

    _, metadata = client.rerank_chunks("질문", "attendance", chunks)

    assert set(metadata["selected_chunk_ids"]).issubset(input_ids)
    assert "xx99" not in metadata["selected_chunk_ids"]
    # usage 로그에 input/selected 카운트 기록 확인
    lines = [line for line in usage_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["node"] == "rerank"
    assert record["extras"]["input_chunk_ids_n"] == 3
    assert record["extras"]["selected_chunk_ids_n"] == 2  # c1, c2 (xx99 제외)
