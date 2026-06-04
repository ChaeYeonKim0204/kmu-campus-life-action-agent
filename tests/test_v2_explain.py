"""규정 근거 해설 노드(보고서 내장 RAG) 테스트 — 무네트워크(fake client·retrieval 주입)."""
from __future__ import annotations

import json

import pytest

from graduation_center.v2 import explain
from graduation_center.v2.models_v2 import AreaGap, AuditResult, RequirementProfile, StudentContext


def _audit(**kw):
    base = dict(total_required=130, total_earned=100, total_gap=30,
                area_gaps=[AreaGap(area="전공", required=48, earned=30, gap=18)],
                missing_required_names=["캡스톤디자인Ⅰ"],
                convergence_checks=[{
                    "program_id": "dsci_convergence", "name": "데이터사이언스융합전공",
                    "track": "다전공", "earned": 27.0, "required": 36.0, "gap": 9.0,
                    "double_used": 12.0, "double_cap": 12.0,
                    "group_checks": [{"group": "B그룹", "required": 12.0, "earned": 6.0, "gap": 6.0}],
                }])
    base.update(kw)
    return AuditResult(**base)


PROFILE = RequirementProfile(program_id="ai_bigdata", department_name_ko="AI빅데이터융합경영학과")
CTX = StudentContext(program_id="ai_bigdata")


def test_select_items_priority_and_cap():
    items = explain.select_explain_items(_audit(), PROFILE, CTX)
    assert len(items) <= explain.MAX_ITEMS
    assert items[0]["key"] == "missing_required"          # 필수 > 융합 > 영역
    assert items[1]["key"] == "conv:dsci_convergence"
    assert "중복인정 12/12" in items[1]["context"]


def test_select_items_empty_when_satisfied():
    a = _audit(total_gap=0, area_gaps=[], missing_required_names=[], convergence_checks=[])
    assert explain.select_explain_items(a, PROFILE, CTX) == []


def _items_chunks():
    items = [{"key": "k1", "title": "제목", "query": "q", "context": "전공 30/48학점 (부족 18)"}]
    chunks = [{"page": 693, "section": "졸업요건", "text": "전공 최저 48학점을 이수해야 한다."}]
    by_item = {"k1": chunks}
    id_by = {id(chunks[0]): "Y1"}
    return items, by_item, id_by


def test_validator_resolves_and_flags():
    items, by_item, id_by = _items_chunks()
    raw = {"explanations": [{"item_key": "k1", "lines": [
        {"text": "전공은 최저 48학점 이수가 필요합니다.", "source_ids": ["Y1"]},          # 정상
        {"text": "졸업까지 99학점이 더 필요합니다.", "source_ids": ["Y1"]},               # 새 수치 99 → 미확인
        {"text": "근거 없는 주장입니다.", "source_ids": []},                              # 인용 없음 → 미확인
        {"text": "학번 20231234 학생은 유의하세요.", "source_ids": ["Y1"]},               # 마스킹
    ]}]}
    secs = explain.validate_explanations(raw, items, by_item, id_by)
    assert len(secs) == 1
    lines = secs[0].lines
    assert lines[0].grounded is True
    assert lines[1].grounded is False and "공식 출처 미확인" in lines[1].text
    assert lines[2].grounded is False
    assert "2023XXXX" in lines[3].text and "20231234" not in lines[3].text


def test_validator_blocks_regulation_corruption():
    """취득학점(진단 숫자)을 최저요건으로 바꿔 말하는 오염은 차단, 진단 참조 줄은 허용."""
    items = [{"key": "k1", "title": "전공 부족", "query": "q", "context": "전공 30/48학점 (부족 18)"}]
    chunks = [{"page": 693, "section": "졸업요건", "text": "전공 최저 48학점을 이수해야 한다."}]
    by_item = {"k1": chunks}
    id_by = {id(chunks[0]): "Y1"}
    raw = {"explanations": [{"item_key": "k1", "lines": [
        {"text": "전공은 최저 30학점만 이수하면 됩니다.", "source_ids": ["Y1"]},              # 오염
        {"text": "전공 최저 48학점 이수가 요건입니다.", "source_ids": ["Y1"]},                # chunk 원문
        {"text": "진단 결과 현재 30학점을 이수해 18학점이 부족합니다.", "source_ids": ["Y1"]},  # 진단 참조
    ]}]}
    lines = explain.validate_explanations(raw, items, by_item, id_by)[0].lines
    assert [ln.grounded for ln in lines] == [False, True, True]


def test_validator_drops_unknown_item_and_foreign_citation():
    items, by_item, id_by = _items_chunks()
    raw = {"explanations": [
        {"item_key": "없는키", "lines": [{"text": "x", "source_ids": ["Y1"]}]},
        {"item_key": "k1", "lines": [{"text": "타 항목 인용", "source_ids": ["Y9"]}]},   # 미지 id 제거
    ]}
    secs = explain.validate_explanations(raw, items, by_item, id_by)
    assert len(secs) == 1
    assert secs[0].lines[0].source_ids == [] and secs[0].lines[0].grounded is False


class _FakeClient:
    """retrieve는 monkeypatch, LLM 응답만 흉내."""
    class _Resp:
        def __init__(self, text): self.output_text = text

    class responses:  # noqa: N801
        @staticmethod
        def create(**kwargs):
            return _FakeClient._Resp(json.dumps({"explanations": [{
                "item_key": "missing_required",
                "lines": [{"text": "필수지정 과목은 졸업 전 반드시 이수해야 합니다.", "source_ids": ["Y1"]}],
            }]}, ensure_ascii=False))


def test_run_explain_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(explain, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(explain, "retrieve_yoram",
                        lambda q, c, top_k=4: [{"page": 693, "section": "졸업요건",
                                                "text": "필수지정 과목 이수 규정"}])
    a = _audit(convergence_checks=[], area_gaps=[])
    secs, sources, trace, fb = explain.run_explain(a, PROFILE, CTX, client=_FakeClient())
    assert fb is None and len(secs) == 1
    assert secs[0].lines[0].grounded is True
    assert [s.id for s in sources] == ["Y1"] and sources[0].source_type == "yoram_rag"
    assert [e.node for e in trace] == ["요람 RAG 해설", "해설 검증"]
    assert trace[0].kind == "llm" and trace[1].kind == "validator"
    # 캐시: 같은 입력 2회차는 client 없이도 동일 결과
    secs2, sources2, trace2, fb2 = explain.run_explain(a, PROFILE, CTX, client=None)
    assert [s.model_dump() for s in secs2] == [s.model_dump() for s in secs]
    assert "캐시" in trace2[0].summary


def test_run_explain_no_key_degrades(monkeypatch, tmp_path):
    monkeypatch.setattr(explain, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(explain, "_get_client", lambda: None)
    secs, sources, trace, fb = explain.run_explain(_audit(), PROFILE, CTX, client=None)
    assert secs == [] and sources == []
    assert fb and "LLM 미설정" in fb
    assert trace[0].status == "skip"


def test_run_explain_llm_failure_degrades(monkeypatch, tmp_path):
    monkeypatch.setattr(explain, "CACHE_PATH", tmp_path / "cache.json")

    class _Boom:
        class responses:  # noqa: N801
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("api down")
        class embeddings:  # noqa: N801
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("api down")

    secs, sources, trace, fb = explain.run_explain(_audit(), PROFILE, CTX, client=_Boom())
    assert secs == [] and fb and "해설 생성 불가" in fb
    assert trace[0].status == "fail"
