"""Ingestion orchestration for official KMU sources."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from crawler.base import BaseCrawler, RawDocument
from crawler.kmu_academic_guide import KMUAcademicGuideCrawler
from crawler.kmu_cradle import KMUCradleCrawler
from crawler.kmu_notice import KMUNoticeCrawler
from crawler.kmu_org import KMUOrgCrawler
from crawler.kmu_rule import KMURuleCrawler
from crawler.kmu_schedule import KMUScheduleCrawler
from crawler.kmu_student_support import KMUStudentSupportCrawler
from crawler.swell_public import SWELLPublicCrawler
from ingestion.chunker import chunk_text


CHUNKS_PATH = Path("data/processed/chunks.jsonl")
STATE_PATH = Path("data/state/crawler_state.json")
INGEST_COOLDOWN_SECONDS = 300
_INGEST_LOCK = Lock()

CRAWLERS: dict[str, type[BaseCrawler]] = {
    "academic_guide": KMUAcademicGuideCrawler,
    "notice": KMUNoticeCrawler,
    "schedule": KMUScheduleCrawler,
    "student_support": KMUStudentSupportCrawler,
    "organization": KMUOrgCrawler,
    "cradle": KMUCradleCrawler,
    "university_rule": KMURuleCrawler,
    "swell_public": SWELLPublicCrawler,
}


def run_ingestion(source: str = "all", limit: int = 20, force_rebuild: bool = False, vector_retriever=None) -> dict:
    """Crawl official sources, rebuild JSONL chunks, and upsert vector index."""
    if not _INGEST_LOCK.acquire(blocking=False):
        return {
            "status": "skipped",
            "message": "이미 수집 작업이 실행 중입니다. 잠시 후 다시 시도하세요.",
            "cooldown_seconds": INGEST_COOLDOWN_SECONDS,
            "last_ingest": load_state(STATE_PATH).get("last_ingest"),
        }
    try:
        return _run_ingestion_locked(source, limit, force_rebuild, vector_retriever)
    finally:
        _INGEST_LOCK.release()


def _run_ingestion_locked(source: str = "all", limit: int = 20, force_rebuild: bool = False, vector_retriever=None) -> dict:
    """Run ingestion while holding the global ingest lock."""
    requested = list(CRAWLERS) if source in {"all", "seed", ""} else [source]
    existing_chunks = load_chunks(CHUNKS_PATH)
    previous_state = load_state(STATE_PATH)
    cooldown = _cooldown_remaining(previous_state, source)
    if cooldown > 0 and not force_rebuild:
        return {
            "status": "skipped",
            "message": f"학교 서버 보호를 위해 수집은 {INGEST_COOLDOWN_SECONDS}초 간격으로 제한됩니다.",
            "cooldown_remaining_seconds": cooldown,
            "chunks_written": len(existing_chunks),
            "vector_available": bool(getattr(vector_retriever, "available", False)),
            "vector_indexed": getattr(vector_retriever, "count", lambda: 0)() if vector_retriever else 0,
            "failures": [],
            "last_ingest": previous_state.get("last_ingest"),
        }
    failures: list[dict[str, str]] = []
    documents: list[RawDocument] = []

    for name in requested:
        crawler_cls = CRAWLERS.get(name)
        if not crawler_cls:
            failures.append({"source": name, "error": "unknown_source"})
            continue
        try:
            documents.extend(crawler_cls().crawl(limit=limit, state=previous_state))
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            failures.append({"source": name, "error": str(exc)})

    if not documents:
        return _result(
            status="completed",
            message="수집된 문서가 없어 기존 JSONL과 vector index를 유지했습니다.",
            existing_chunks=existing_chunks,
            failures=failures,
            vector_retriever=vector_retriever,
        )

    affected_doc_ids = {document.doc_id for document in documents}
    fetch_summary = summarize_fetches(documents)
    preserved_chunks = [chunk for chunk in existing_chunks if chunk.get("doc_id") not in affected_doc_ids]
    generated_chunks: list[dict[str, Any]] = []
    new_count = 0
    changed_count = 0
    skipped_count = 0

    for document in documents:
        prior_hash = previous_state.get("documents", {}).get(document.doc_id, {}).get("content_hash")
        if prior_hash is None:
            new_count += 1
        elif prior_hash == document.content_hash and not force_rebuild:
            skipped_count += 1
        else:
            changed_count += 1
        generated_chunks.extend(document_to_chunks(document))
        previous_state.setdefault("documents", {})[document.doc_id] = {
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
    write_chunks(CHUNKS_PATH, all_chunks)
    previous_state["last_ingest"] = {
        "source": source,
        "limit": limit,
        "force_rebuild": force_rebuild,
        "completed_at": _now(),
        "documents_seen": len(documents),
        "new_documents": new_count,
        "changed_documents": changed_count,
        "skipped_documents": skipped_count,
        "chunks_written": len(all_chunks),
        "failures": failures,
        "fetch_summary": fetch_summary,
    }
    write_state(STATE_PATH, previous_state)

    vector_indexed = 0
    vector_available = False
    vector_error = None
    if vector_retriever is not None:
        try:
            vector_available = bool(vector_retriever.available)
            vector_indexed = vector_retriever.upsert(all_chunks)
        except Exception as exc:  # pragma: no cover - vector failures must not break ingest
            vector_error = str(exc)

    return {
        "status": "completed",
        "message": "공식자료 수집, JSONL 저장, vector index 갱신을 완료했습니다.",
        "documents_seen": len(documents),
        "new_documents": new_count,
        "changed_documents": changed_count,
        "skipped_documents": skipped_count,
        "chunks_written": len(all_chunks),
        "vector_available": vector_available,
        "vector_indexed": vector_indexed,
        "vector_error": vector_error,
        "failures": failures,
        **fetch_summary,
        "last_ingest": previous_state["last_ingest"],
    }


def document_to_chunks(document: RawDocument) -> list[dict[str, Any]]:
    """Convert a raw official document to enriched retriever chunks."""
    text_chunks = chunk_text(document.text, max_chars=700)
    chunks: list[dict[str, Any]] = []
    for index, text in enumerate(text_chunks, 1):
        metadata = dict(document.metadata)
        chunk = {
            "chunk_id": f"{_slug(document.doc_id)}_{index:03d}",
            "doc_id": document.doc_id,
            "source_tier": metadata.pop("source_tier", 9),
            "source_type": document.source_type,
            "title": document.title,
            "url": document.url,
            "text": text,
            "content_hash": f"{document.content_hash}-{index}",
            **metadata,
        }
        chunks.append({key: value for key, value in chunk.items() if value not in (None, [], {})})
    return chunks


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict[str, Any]]:
    """Load JSONL chunks."""
    if not path.exists():
        return []
    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def write_chunks(path: Path, chunks: list[dict[str, Any]]) -> None:
    """Write JSONL chunks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n")


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    """Load crawler state."""
    if not path.exists():
        return {"documents": {}}
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle) if path.stat().st_size else {}
    state.setdefault("documents", {})
    return state


def write_state(path: Path, state: dict[str, Any]) -> None:
    """Write crawler state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)


def _result(status: str, message: str, existing_chunks: list[dict], failures: list[dict], vector_retriever) -> dict:
    return {
        "status": status,
        "message": message,
        "documents_seen": 0,
        "new_documents": 0,
        "changed_documents": 0,
        "skipped_documents": 0,
        "chunks_written": len(existing_chunks),
        "vector_available": bool(getattr(vector_retriever, "available", False)),
        "vector_indexed": getattr(vector_retriever, "count", lambda: 0)() if vector_retriever else 0,
        "failures": failures,
        "network_success": 0,
        "fallback_used": 0,
        "network_failed": 0,
        "failed_urls": [],
        "last_ingest": load_state(STATE_PATH).get("last_ingest"),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_]+", "_", value).strip("_").lower()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize_fetches(documents: list[RawDocument]) -> dict[str, Any]:
    """Summarize whether crawler output came from network or fallback."""
    network_success = 0
    fallback_used = 0
    network_failed = 0
    failed_urls: list[dict[str, str]] = []
    for document in documents:
        status = document.metadata.get("fetch_status")
        if document.metadata.get("fetched_from_network"):
            network_success += 1
        if document.metadata.get("used_fallback"):
            fallback_used += 1
        if status in {"failed", "empty"}:
            network_failed += 1
            failed_urls.append(
                {
                    "doc_id": document.doc_id,
                    "url": document.url,
                    "status": str(status),
                    "error": str(document.metadata.get("fetch_error", "")),
                }
            )
    return {
        "network_success": network_success,
        "fallback_used": fallback_used,
        "network_failed": network_failed,
        "failed_urls": failed_urls,
    }


def _cooldown_remaining(state: dict[str, Any], source: str) -> int:
    last = state.get("last_ingest") or {}
    if last.get("source") not in {source, "all"} and source != "all":
        return 0
    completed_at = last.get("completed_at")
    if not completed_at:
        return 0
    try:
        last_dt = datetime.fromisoformat(completed_at)
    except ValueError:
        return 0
    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
    return max(0, int(INGEST_COOLDOWN_SECONDS - elapsed))
