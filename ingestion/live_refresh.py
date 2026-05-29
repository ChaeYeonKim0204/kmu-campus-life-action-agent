"""Live, issue-scoped refresh for official KMU sources.

This is intentionally narrower than the full ingestion pipeline. It checks only
the public pages relevant to a classified issue and updates the local chunks
only when a network fetch succeeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from crawler.base import BaseCrawler, RawDocument, SourcePage
from ingestion.pipeline import (
    CHUNKS_PATH,
    CRAWLERS,
    STATE_PATH,
    document_to_chunks,
    load_chunks,
    load_state,
    summarize_fetches,
    write_chunks,
    write_state,
)


LIVE_REFRESH_COOLDOWN_SECONDS = 60
LIVE_REFRESH_MAX_PAGES = 3
_LIVE_REFRESH_LOCK = Lock()


def refresh_sources_for_issue(
    issue_type: str | None,
    query: str = "",
    *,
    max_pages: int = LIVE_REFRESH_MAX_PAGES,
    cooldown_seconds: int = LIVE_REFRESH_COOLDOWN_SECONDS,
    chunks_path: Path = CHUNKS_PATH,
    state_path: Path = STATE_PATH,
    vector_retriever=None,
) -> dict[str, Any]:
    """Refresh official public pages relevant to an issue before retrieval."""
    base_result = {
        "attempted": False,
        "status": "skipped",
        "issue_type": issue_type,
        "selected_pages": [],
        "documents_seen": 0,
        "updated_documents": 0,
        "chunks_written": len(load_chunks(chunks_path)),
        "network_success": 0,
        "fallback_used": 0,
        "network_failed": 0,
        "failed_urls": [],
        "failures": [],
        "updated": False,
        "cooldown_remaining_seconds": 0,
    }
    if not issue_type or issue_type == "other":
        return {**base_result, "message": "실시간 확인 대상 이슈가 아닙니다."}

    if not _LIVE_REFRESH_LOCK.acquire(blocking=False):
        return {**base_result, "message": "이미 실시간 확인이 실행 중입니다. 기존 근거로 답변합니다."}

    try:
        return _refresh_sources_for_issue_locked(
            issue_type,
            query=query,
            max_pages=max_pages,
            cooldown_seconds=cooldown_seconds,
            chunks_path=chunks_path,
            state_path=state_path,
            vector_retriever=vector_retriever,
        )
    finally:
        _LIVE_REFRESH_LOCK.release()


def _refresh_sources_for_issue_locked(
    issue_type: str,
    query: str = "",
    *,
    max_pages: int,
    cooldown_seconds: int,
    chunks_path: Path,
    state_path: Path,
    vector_retriever=None,
) -> dict[str, Any]:
    existing_chunks = load_chunks(chunks_path)
    state = load_state(state_path)
    cooldown = _live_cooldown_remaining(state, issue_type, cooldown_seconds)
    selected = _select_pages(issue_type, query=query, max_pages=max_pages)
    selected_pages = [
        {"source": source_name, "doc_id": page.doc_id, "title": page.title, "url": page.url}
        for source_name, _crawler_cls, page in selected
    ]
    if not selected:
        return {
            "attempted": False,
            "status": "skipped",
            "message": "분류된 이슈에 연결된 공개 공식 소스가 없습니다.",
            "issue_type": issue_type,
            "selected_pages": [],
            "documents_seen": 0,
            "updated_documents": 0,
            "chunks_written": len(existing_chunks),
            "network_success": 0,
            "fallback_used": 0,
            "network_failed": 0,
            "failed_urls": [],
            "failures": [],
            "updated": False,
            "cooldown_remaining_seconds": 0,
        }
    if cooldown > 0:
        return {
            "attempted": False,
            "status": "skipped",
            "message": "학교 서버 보호를 위해 같은 이슈의 실시간 확인은 잠시 후 다시 시도합니다.",
            "issue_type": issue_type,
            "selected_pages": selected_pages,
            "documents_seen": 0,
            "updated_documents": 0,
            "chunks_written": len(existing_chunks),
            "network_success": 0,
            "fallback_used": 0,
            "network_failed": 0,
            "failed_urls": [],
            "failures": [],
            "updated": False,
            "cooldown_remaining_seconds": cooldown,
        }

    failures: list[dict[str, str]] = []
    documents: list[RawDocument] = []
    for source_name, crawler_cls, pages in _group_selected_pages(selected):
        crawler = crawler_cls()
        crawler.pages = pages
        try:
            documents.extend(crawler.crawl(limit=len(pages), state=state))
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            failures.append({"source": source_name, "error": str(exc)})

    fetch_summary = summarize_fetches(documents)
    network_documents = [document for document in documents if document.metadata.get("fetched_from_network")]
    updated_doc_ids = {document.doc_id for document in network_documents}

    if network_documents:
        preserved_chunks = [chunk for chunk in existing_chunks if chunk.get("doc_id") not in updated_doc_ids]
        generated_chunks: list[dict[str, Any]] = []
        for document in network_documents:
            generated_chunks.extend(document_to_chunks(document))
            state.setdefault("documents", {})[document.doc_id] = {
                "title": document.title,
                "url": document.url,
                "source_type": document.source_type,
                "content_hash": document.content_hash,
                "last_seen_at": _now(),
                **document.response_headers,
            }
        all_chunks = sorted(
            preserved_chunks + generated_chunks,
            key=lambda item: (int(item.get("source_tier", 9)), item.get("source_type", ""), item.get("chunk_id", "")),
        )
        write_chunks(chunks_path, all_chunks)
        if vector_retriever is not None:
            try:
                vector_retriever.upsert(all_chunks)
            except Exception as exc:  # pragma: no cover - vector failures must not break answers
                failures.append({"source": "vector", "error": str(exc)})
    else:
        all_chunks = existing_chunks

    state.setdefault("last_live_refresh", {})[issue_type] = {
        "completed_at": _now(),
        "selected_pages": selected_pages,
        "documents_seen": len(documents),
        "updated_documents": len(network_documents),
        "fetch_summary": fetch_summary,
        "failures": failures,
    }
    write_state(state_path, state)

    return {
        "attempted": True,
        "status": "completed",
        "message": "관련 공식 공개 소스 실시간 확인을 완료했습니다.",
        "issue_type": issue_type,
        "selected_pages": selected_pages,
        "documents_seen": len(documents),
        "updated_documents": len(network_documents),
        "chunks_written": len(all_chunks),
        "failures": failures,
        "updated": bool(network_documents),
        "cooldown_remaining_seconds": 0,
        **fetch_summary,
    }


def _select_pages(issue_type: str, query: str = "", max_pages: int = LIVE_REFRESH_MAX_PAGES) -> list[tuple[str, type[BaseCrawler], SourcePage]]:
    candidates: list[tuple[str, type[BaseCrawler], SourcePage]] = []
    for source_name, crawler_cls in CRAWLERS.items():
        for page in crawler_cls.pages:
            if issue_type in (page.issue_types or []):
                candidates.append((source_name, crawler_cls, page))
    scored = sorted(candidates, key=lambda item: (-_page_score(item[2], issue_type, query), int(item[2].source_tier or item[1].source_tier), item[2].doc_id))
    return scored[:max_pages]


def _page_score(page: SourcePage, issue_type: str, query: str) -> int:
    normalized = (query or "").lower()
    score = 0
    if issue_type in (page.issue_types or []):
        score += 10
    for value in [page.title, page.fallback_text, *(page.keywords or []), *(page.search_hints or [])]:
        text = str(value).lower()
        if any(piece and len(piece) >= 2 and piece in text for piece in normalized.split()):
            score += 2
        if str(value).lower() in normalized:
            score += 3
    return score


def _group_selected_pages(
    selected: list[tuple[str, type[BaseCrawler], SourcePage]]
) -> list[tuple[str, type[BaseCrawler], list[SourcePage]]]:
    grouped: dict[str, tuple[type[BaseCrawler], list[SourcePage]]] = {}
    for source_name, crawler_cls, page in selected:
        grouped.setdefault(source_name, (crawler_cls, []))[1].append(page)
    return [(source_name, crawler_cls, pages) for source_name, (crawler_cls, pages) in grouped.items()]


def _live_cooldown_remaining(state: dict[str, Any], issue_type: str, cooldown_seconds: int) -> int:
    last_refresh = state.get("last_live_refresh", {}).get(issue_type, {})
    completed_at = last_refresh.get("completed_at")
    if not completed_at:
        return 0
    try:
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return 0
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - completed).total_seconds()
    return max(0, int(cooldown_seconds - elapsed))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
