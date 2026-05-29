"""Hybrid retriever combining keyword fallback and optional vector search."""

from __future__ import annotations

from retriever.keyword_retriever import KeywordRetriever
from retriever.vector_retriever import VectorRetriever


class HybridRetriever:
    """Search official sources with vector search when available and keyword fallback always."""

    def __init__(self, chunks_path: str = "data/processed/chunks.jsonl"):
        self.chunks_path = chunks_path
        self.keyword = KeywordRetriever(chunks_path)
        self.vector = VectorRetriever()

    def search(self, query: str, issue_type: str | None = None, limit: int = 6) -> list[dict]:
        """Merge vector and keyword search results by chunk id."""
        merged: dict[str, dict] = {}
        for result in self.vector.search(query, issue_type, limit):
            merged[result["chunk_id"]] = result
        for result in self.keyword.search(query, issue_type, limit):
            current = merged.get(result["chunk_id"])
            if not current or result.get("score", 0) > current.get("score", 0):
                merged[result["chunk_id"]] = result
        return sorted(merged.values(), key=lambda item: (-item.get("score", 0), int(item.get("source_tier", 9))))[:limit]

    def all_sources(self) -> list[dict]:
        """Return all indexed official chunks."""
        return self.keyword.all_sources()

    def reload(self) -> None:
        """Reload JSONL chunks after ingestion."""
        self.keyword = KeywordRetriever(self.chunks_path)

    def status(self) -> dict:
        """Return retriever health details for admin surfaces."""
        return {
            "keyword_chunks": len(self.all_sources()),
            "vector_available": self.vector.available,
            "vector_indexed_count": self.vector.count(),
            "vector_error": self.vector.error,
        }
