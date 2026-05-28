"""Guarded OpenAI API interface for optional RAG assistance.

The deterministic answer builder remains the source of truth. This client only
helps with retrieval-oriented tasks such as query expansion and result reranking.
It is deliberately optional and fails closed to the existing non-LLM behavior.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FALSE_VALUES = {"", "0", "false", "no", "off"}

USAGE_LOG_PATH = Path("data/state/llm_usage.jsonl")

# 모델별 토큰 단가 (USD / token). 출처: OpenAI 공시(2026-01). 미등록 모델은 0 처리.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5-mini": {"input": 0.25e-6, "output": 2.0e-6},
    "gpt-4o-mini": {"input": 0.15e-6, "output": 0.6e-6},
    "gpt-4o": {"input": 2.5e-6, "output": 10.0e-6},
}


def _extract_usage(response: Any, model: str) -> dict[str, Any]:
    """Pull token counts + cost estimate from a Responses API response.

    Tolerates fake/missing usage fields (test fakes don't include them) — zero-fill.
    """
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cost_usd_est": 0.0}
    input_t = int(getattr(usage_obj, "input_tokens", 0) or 0)
    output_t = int(getattr(usage_obj, "output_tokens", 0) or 0)
    reasoning_t = 0
    details = getattr(usage_obj, "output_tokens_details", None)
    if details is not None:
        reasoning_t = int(getattr(details, "reasoning_tokens", 0) or 0)
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = input_t * pricing["input"] + output_t * pricing["output"]
    return {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "reasoning_tokens": reasoning_t,
        "cost_usd_est": round(cost, 6),
    }


class GuardedLLMClient:
    """Optional OpenAI-backed helper for grounded retrieval workflows."""

    def __init__(
        self,
        enabled: bool | None = None,
        model: str | None = None,
        timeout_seconds: float = 8.0,
        client: Any | None = None,
    ):
        env_enabled = os.getenv("OPENAI_ENABLED", "false").strip().lower()
        env_polish_enabled = os.getenv("OPENAI_POLISH_ENABLED", "false").strip().lower()
        self.enabled = enabled if enabled is not None else env_enabled not in FALSE_VALUES
        self.api_key_configured = bool(os.getenv("OPENAI_API_KEY", "").strip()) or client is not None
        self.polish_enabled = self.enabled and env_polish_enabled not in FALSE_VALUES
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_seconds = timeout_seconds
        self._client = client
        self.error: str | None = "openai_api_key_missing" if self.enabled and not self.api_key_configured else None
        self._supports_temperature = True
        self._is_reasoning_model = any(self.model.startswith(prefix) for prefix in ("gpt-5", "o1", "o3", "o4"))

    def generate(self, prompt: str, grounded_context: list[dict]) -> str:
        """Generate text only from grounded context.

        The current implementation intentionally returns an empty string so the
        deterministic answer builder remains the source of truth.
        """
        _ = prompt, grounded_context
        return ""

    def status(self) -> dict[str, Any]:
        """Expose safe runtime status for admin surfaces."""
        return {
            "enabled": self.enabled,
            "api_key_configured": self.api_key_configured,
            "polish_enabled": self.polish_enabled,
            "model": self.model if self.enabled else None,
            "error": self.error,
        }

    def expand_search_query(self, question: str, issue_type: str, student_context: dict | None = None) -> dict[str, Any]:
        """Return a Korean retrieval query expanded with official KMU terms."""
        fallback = {
            "used": False,
            "expanded_query": question,
            "keywords": [],
            "error": None,
        }
        if not self.enabled or not self.api_key_configured:
            if self.enabled and not self.api_key_configured:
                self.error = "openai_api_key_missing"
            return fallback

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "expanded_query": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            },
            "required": ["expanded_query", "keywords"],
        }
        prompt = (
            "국민대학교 공식 문서 검색용 한국어 검색어를 만들어라.\n"
            "절차나 사실을 답하지 말고, 검색에 유용한 공식 용어와 동의어만 추가하라.\n"
            "개인정보, 학번, 연락처, 포털 ID/PW처럼 민감한 값은 절대 포함하지 마라.\n\n"
            f"분류: {issue_type}\n"
            f"학생 맥락: {_safe_context(student_context)}\n"
            f"질문: {question}"
        )
        start = time.perf_counter()
        try:
            data, usage = self._json_response(
                system="You expand Korean university RAG search queries without adding factual advice.",
                user=prompt,
                schema_name="search_query_expansion",
                schema=schema,
                max_output_tokens=400,
            )
        except Exception as exc:
            self.error = str(exc)
            self._record_usage(
                "expand", {}, used=False, error=self.error, rejected_reason=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
            return {**fallback, "error": self.error}

        expanded_query = _compact_space(str(data.get("expanded_query") or question))
        keywords = [str(item).strip() for item in data.get("keywords", []) if str(item).strip()]
        if not expanded_query:
            expanded_query = question
        self._record_usage(
            "expand", usage, used=True, error=None, rejected_reason=None,
            latency_ms=int((time.perf_counter() - start) * 1000),
            extras={"keywords_n": len(keywords)},
        )
        return {
            "used": True,
            "expanded_query": expanded_query,
            "keywords": keywords[:10],
            "error": None,
        }

    def rerank_chunks(self, question: str, issue_type: str, chunks: list[dict], limit: int | None = None) -> tuple[list[dict], dict[str, Any]]:
        """Ask the model to pick the most relevant already-retrieved chunks."""
        metadata = {"used": False, "selected_chunk_ids": [], "error": None}
        if not self.enabled or not self.api_key_configured or not chunks:
            if self.enabled and not self.api_key_configured:
                self.error = "openai_api_key_missing"
            return chunks, metadata

        chunk_by_id = {str(chunk.get("chunk_id")): chunk for chunk in chunks if chunk.get("chunk_id")}
        if not chunk_by_id:
            return chunks, metadata

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "selected_chunk_ids": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(chunk_by_id)},
                    "maxItems": min(len(chunk_by_id), limit or len(chunk_by_id)),
                }
            },
            "required": ["selected_chunk_ids"],
        }
        prompt = (
            "아래 후보 chunk 중 사용자 질문에 직접 근거가 되는 chunk_id만 관련도 순으로 골라라.\n"
            "새로운 사실을 만들지 말고, 반드시 제공된 chunk_id 중에서만 선택하라.\n\n"
            f"분류: {issue_type}\n"
            f"질문: {question}\n\n"
            f"후보:\n{_chunk_prompt(chunks)}"
        )
        input_ids_n = len(chunk_by_id)
        start = time.perf_counter()
        try:
            data, usage = self._json_response(
                system="You rerank retrieved Korean university source chunks. Return IDs only.",
                user=prompt,
                schema_name="chunk_rerank",
                schema=schema,
                max_output_tokens=400,
            )
        except Exception as exc:
            self.error = str(exc)
            self._record_usage(
                "rerank", {}, used=False, error=self.error, rejected_reason=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                extras={"input_chunk_ids_n": input_ids_n, "selected_chunk_ids_n": 0},
            )
            return chunks, {**metadata, "error": self.error}

        selected_ids = [chunk_id for chunk_id in data.get("selected_chunk_ids", []) if chunk_id in chunk_by_id]
        latency_ms = int((time.perf_counter() - start) * 1000)
        if not selected_ids:
            self._record_usage(
                "rerank", usage, used=False, error=None, rejected_reason=None,
                latency_ms=latency_ms,
                extras={"input_chunk_ids_n": input_ids_n, "selected_chunk_ids_n": 0},
            )
            return chunks, metadata

        selected = [chunk_by_id[chunk_id] for chunk_id in selected_ids]
        selected_set = set(selected_ids)
        remainder = [chunk for chunk in chunks if str(chunk.get("chunk_id")) not in selected_set]
        reranked = [*selected, *remainder]
        if limit is not None:
            reranked = reranked[:limit]
        self._record_usage(
            "rerank", usage, used=True, error=None, rejected_reason=None,
            latency_ms=latency_ms,
            extras={"input_chunk_ids_n": input_ids_n, "selected_chunk_ids_n": len(selected_ids)},
        )
        return reranked, {"used": True, "selected_chunk_ids": selected_ids, "error": None}

    def polish_answer(self, answer: str) -> dict[str, Any]:
        """Polish deterministic Korean answer text while preserving citations."""
        fallback = {
            "used": False,
            "answer": answer,
            "error": None,
            "rejected_reason": None,
        }
        if not self.polish_enabled or not self.api_key_configured:
            if self.polish_enabled and not self.api_key_configured:
                self.error = "openai_api_key_missing"
            return fallback

        split_marker = "\n[근거]\n"
        if split_marker not in answer:
            return {**fallback, "rejected_reason": "missing_sources_block"}
        body, sources = answer.split(split_marker, 1)
        original_markers = _citation_markers(body)
        original_headers = _section_headers(body)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "polished_body": {"type": "string"},
            },
            "required": ["polished_body"],
        }
        prompt = (
            "아래 한국어 답변 본문을 더 자연스럽고 읽기 쉽게 다듬어라.\n"
            "규칙:\n"
            "- 새로운 절차, 날짜, 부서명, 전화번호, 서류명, 신청 경로를 추가하지 마라.\n"
            "- 모든 섹션 제목과 목록 구조를 유지하라.\n"
            "- 모든 citation marker([S1], [S2] 등)를 정확히 보존하라.\n"
            "- [근거] 블록은 제공하지 않았으므로 만들지 마라.\n"
            "- 개인정보나 로그인 정보 입력을 요구하지 마라.\n"
            "- 다음 표현은 절대 사용 금지: '승인됩니다' / '확정됩니다' / '반드시 처리됩니다' /"
            " '학번을 알려주세요' / '비밀번호를 입력하세요' / '연락처를 알려주세요' /"
            " '제가 포털에서 확인했습니다'.\n"
            "- 다음 톤을 권장 (의미 변경 없이 어조만): '공식 근거에서 확인되는 내용은' /"
            " '개인 신청 상태는 ON국민 포털에서 직접 확인해야' /"
            " '문의 전에는 아래 정보를 개인정보 없이 정리해 주세요' /"
            " '최종 처리는 담당 부서 확인이 필요합니다'.\n"
            "- [주의] 섹션의 최신성/네트워크 확인 관련 문구는 자연스럽게 표현만 다듬되,"
            " 라이브 확인 결과의 의미·정확도는 변경하지 마라.\n\n"
            f"본문:\n{body}"
        )
        start = time.perf_counter()
        try:
            data, usage = self._json_response(
                system="You polish grounded Korean RAG answers without adding facts or changing citations.",
                user=prompt,
                schema_name="answer_polish",
                schema=schema,
                max_output_tokens=1500,
            )
        except Exception as exc:
            self.error = str(exc)
            self._record_usage(
                "polish", {}, used=False, error=self.error, rejected_reason=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
            return {**fallback, "error": self.error}

        polished_body = str(data.get("polished_body") or "").strip()
        rejection = _polish_rejection_reason(body, polished_body, original_markers, original_headers)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if rejection:
            self._record_usage(
                "polish", usage, used=False, error=None, rejected_reason=rejection,
                latency_ms=latency_ms,
                extras={"polished_body_len": len(polished_body)},
            )
            return {**fallback, "rejected_reason": rejection}

        self._record_usage(
            "polish", usage, used=True, error=None, rejected_reason=None,
            latency_ms=latency_ms,
            extras={"polished_body_len": len(polished_body)},
        )
        return {
            "used": True,
            "answer": f"{polished_body}{split_marker}{sources}",
            "error": None,
            "rejected_reason": None,
        }

    def _record_usage(
        self,
        node: str,
        usage: dict[str, Any],
        *,
        used: bool,
        error: str | None,
        rejected_reason: str | None,
        latency_ms: int,
        extras: dict[str, Any] | None = None,
    ) -> None:
        """Append a single-line usage record. Raw text never persisted; write failure silent."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "model": self.model,
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
            "cost_usd_est": float(usage.get("cost_usd_est", 0.0)),
            "used": bool(used),
            "error": error,
            "rejected_reason": rejected_reason,
            "latency_ms": int(latency_ms),
            "extras": extras or {},
        }
        try:
            USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with USAGE_LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # pragma: no cover - silent: operational log must not crash the API
            pass

    def _json_response(
        self,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        *,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            "max_output_tokens": max_output_tokens,
        }
        if self._is_reasoning_model:
            # gpt-5/o-series 는 max_output_tokens에 reasoning 토큰이 포함돼,
            # 짧게 잡으면 reasoning만 가득 차고 출력이 빈 응답이 됨.
            # expand/rerank/polish는 깊은 reasoning이 불필요하므로 minimal로 차단.
            kwargs["reasoning"] = {"effort": "minimal"}
        if self._supports_temperature:
            kwargs["temperature"] = 0
        try:
            response = client.responses.create(**kwargs)
        except Exception as exc:
            message = str(exc).lower()
            if self._supports_temperature and "temperature" in message:
                self._supports_temperature = False
                kwargs.pop("temperature", None)
                response = client.responses.create(**kwargs)
            else:
                raise
        output_text = getattr(response, "output_text", "") or _extract_output_text(response)
        if not output_text:
            raise ValueError("empty_openai_response")
        return json.loads(output_text), _extract_usage(response, self.model)

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - import depends on optional package
            raise RuntimeError("openai_package_not_installed") from exc
        self._client = OpenAI(timeout=self.timeout_seconds)
        return self._client


def _safe_context(student_context: dict | None) -> str:
    allowed_keys = ("status", "term", "concern")
    context = {key: str((student_context or {}).get(key, "")).strip() for key in allowed_keys}
    return json.dumps({key: value for key, value in context.items() if value}, ensure_ascii=False)


def _chunk_prompt(chunks: list[dict], text_limit: int = 420) -> str:
    lines = []
    for chunk in chunks:
        text = _compact_space(str(chunk.get("text", "")))[:text_limit]
        keywords = ", ".join(str(item) for item in (chunk.get("keywords") or [])[:8])
        lines.append(
            "\n".join(
                [
                    f"- chunk_id: {chunk.get('chunk_id')}",
                    f"  title: {chunk.get('title', '')}",
                    f"  source_tier: {chunk.get('source_tier', '')}",
                    f"  keywords: {keywords}",
                    f"  text: {text}",
                ]
            )
        )
    return "\n".join(lines)


def _compact_space(value: str) -> str:
    return " ".join(value.split())


def _extract_output_text(response: Any) -> str:
    output = getattr(response, "output", None) or []
    parts: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts)


def _citation_markers(value: str) -> list[str]:
    return re.findall(r"\[S\d+\]", value or "")


def _section_headers(value: str) -> list[str]:
    return re.findall(r"^\[[^\]\n]+\]$", value or "", flags=re.MULTILINE)


def _polish_rejection_reason(
    original_body: str,
    polished_body: str,
    original_markers: list[str],
    original_headers: list[str],
) -> str | None:
    if not polished_body:
        return "empty_polished_body"
    if "\n[근거]\n" in polished_body or "[근거]" in polished_body:
        return "sources_block_changed"
    if sorted(_citation_markers(polished_body)) != sorted(original_markers):
        return "citation_markers_changed"
    polished_headers = set(_section_headers(polished_body))
    for header in original_headers:
        if header not in polished_headers:
            return "section_header_changed"
    if len(polished_body) > max(len(original_body) * 1.35, len(original_body) + 500):
        return "polished_body_too_long"
    return None
