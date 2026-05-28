"""Guarded OpenAI API interface for optional RAG assistance.

The deterministic answer builder remains the source of truth. This client only
helps with retrieval-oriented tasks such as query expansion and result reranking.
It is deliberately optional and fails closed to the existing non-LLM behavior.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


FALSE_VALUES = {"", "0", "false", "no", "off"}


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
        try:
            data = self._json_response(
                system="You expand Korean university RAG search queries without adding factual advice.",
                user=prompt,
                schema_name="search_query_expansion",
                schema=schema,
                max_output_tokens=150,
            )
        except Exception as exc:  # pragma: no cover - network/SDK failure fallback
            self.error = str(exc)
            return {**fallback, "error": self.error}

        expanded_query = _compact_space(str(data.get("expanded_query") or question))
        keywords = [str(item).strip() for item in data.get("keywords", []) if str(item).strip()]
        if not expanded_query:
            expanded_query = question
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
        try:
            data = self._json_response(
                system="You rerank retrieved Korean university source chunks. Return IDs only.",
                user=prompt,
                schema_name="chunk_rerank",
                schema=schema,
                max_output_tokens=200,
            )
        except Exception as exc:  # pragma: no cover - network/SDK failure fallback
            self.error = str(exc)
            return chunks, {**metadata, "error": self.error}

        selected_ids = [chunk_id for chunk_id in data.get("selected_chunk_ids", []) if chunk_id in chunk_by_id]
        if not selected_ids:
            return chunks, metadata

        selected = [chunk_by_id[chunk_id] for chunk_id in selected_ids]
        selected_set = set(selected_ids)
        remainder = [chunk for chunk in chunks if str(chunk.get("chunk_id")) not in selected_set]
        reranked = [*selected, *remainder]
        if limit is not None:
            reranked = reranked[:limit]
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
            "- 개인정보나 로그인 정보 입력을 요구하지 마라.\n\n"
            f"본문:\n{body}"
        )
        try:
            data = self._json_response(
                system="You polish grounded Korean RAG answers without adding facts or changing citations.",
                user=prompt,
                schema_name="answer_polish",
                schema=schema,
                max_output_tokens=900,
            )
        except Exception as exc:  # pragma: no cover - network/SDK failure fallback
            self.error = str(exc)
            return {**fallback, "error": self.error}

        polished_body = str(data.get("polished_body") or "").strip()
        rejection = _polish_rejection_reason(body, polished_body, original_markers, original_headers)
        if rejection:
            return {**fallback, "rejected_reason": rejection}

        return {
            "used": True,
            "answer": f"{polished_body}{split_marker}{sources}",
            "error": None,
            "rejected_reason": None,
        }

    def _json_response(
        self,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        *,
        max_output_tokens: int,
    ) -> dict[str, Any]:
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
        return json.loads(output_text)

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
