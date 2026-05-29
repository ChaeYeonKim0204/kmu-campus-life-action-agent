"""Chroma vector retriever with deterministic local embeddings.

The vector store is a first-class implementation target, but it must never be
the only execution path. If Chroma is unavailable or unhealthy, callers can keep
serving answers through the JSONL keyword retriever.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


class VectorRetriever:
    """Persistent Chroma retriever using local hash embeddings."""

    def __init__(self, persist_path: str = "data/vector/chroma", collection_name: str = "kmu_official_chunks"):
        self.persist_path = Path(persist_path)
        self.collection_name = collection_name
        self.available = False
        self.error: str | None = None
        self.client = None
        self.collection = None
        try:
            import chromadb

            self.persist_path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.persist_path))
            self.collection = self.client.get_or_create_collection(name=collection_name)
            self.available = True
        except Exception as exc:
            self.error = str(exc)

    def search(self, query: str, issue_type: str | None = None, limit: int = 6) -> list[dict]:
        """Return vector results from Chroma when available."""
        if not self.available or self.collection is None:
            return []
        try:
            response = self.collection.query(
                query_embeddings=[hash_embedding(query)],
                n_results=limit,
            )
        except Exception:
            return []

        results: list[dict] = []
        ids = response.get("ids", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        for idx, chunk_id in enumerate(ids):
            metadata = metadatas[idx] or {}
            try:
                chunk = json.loads(metadata.get("chunk_json", "{}"))
            except json.JSONDecodeError:
                chunk = {"chunk_id": chunk_id, "text": metadata.get("text", "")}
            distance = distances[idx] if idx < len(distances) else 1.0
            chunk["score"] = max(0.0, round(8.0 - float(distance), 3))
            chunk["vector_score"] = chunk["score"]
            if not issue_type or issue_type in (chunk.get("issue_types", []) or []):
                results.append(chunk)
        return results

    def upsert(self, chunks: list[dict[str, Any]]) -> int:
        """Upsert chunks into the persistent Chroma collection."""
        if not self.available or self.collection is None or not chunks:
            return 0
        ids = [str(chunk["chunk_id"]) for chunk in chunks]
        documents = [chunk.get("text", "") for chunk in chunks]
        embeddings = [hash_embedding(_embedding_text(chunk)) for chunk in chunks]
        metadatas = [metadata_for_chroma(chunk) for chunk in chunks]
        self._delete_stale_ids(set(ids))
        self.collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        return len(chunks)

    def count(self) -> int:
        """Return Chroma collection size when available."""
        if not self.available or self.collection is None:
            return 0
        try:
            return int(self.collection.count())
        except Exception:
            return 0

    def _delete_stale_ids(self, active_ids: set[str]) -> None:
        """Remove vector rows that are no longer present in JSONL source data."""
        if self.collection is None:
            return
        try:
            existing = self.collection.get()
            stale = [chunk_id for chunk_id in existing.get("ids", []) if chunk_id not in active_ids]
            if stale:
                self.collection.delete(ids=stale)
        except Exception:
            return


def metadata_for_chroma(chunk: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Convert nested chunk metadata into Chroma-compatible scalar metadata."""
    return {
        "chunk_id": str(chunk.get("chunk_id", "")),
        "doc_id": str(chunk.get("doc_id", "")),
        "title": str(chunk.get("title", "")),
        "url": str(chunk.get("url", "")),
        "source_type": str(chunk.get("source_type", "")),
        "source_tier": int(chunk.get("source_tier", 9)),
        "issue_types_text": " ".join(chunk.get("issue_types", []) or []),
        "keywords_text": " ".join(chunk.get("keywords", []) or []),
        "chunk_json": json.dumps(chunk, ensure_ascii=False, sort_keys=True),
    }


def hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Create a deterministic local embedding without model downloads."""
    vector = [0.0] * dimensions
    tokens = [token for token in text.lower().split() if token]
    if not tokens:
        tokens = [text.lower()]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for idx, byte in enumerate(digest):
            vector[idx % dimensions] += (byte - 127.5) / 127.5
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def _embedding_text(chunk: dict[str, Any]) -> str:
    parts = [
        chunk.get("title", ""),
        chunk.get("text", ""),
        " ".join(chunk.get("keywords", []) or []),
        " ".join(chunk.get("search_hints", []) or []),
        " ".join(chunk.get("issue_types", []) or []),
    ]
    return " ".join(part for part in parts if part)
