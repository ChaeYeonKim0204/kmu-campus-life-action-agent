"""Citation helpers for NotebookLM-style source references."""

from __future__ import annotations


def build_citations(chunks: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """Assign stable S-style citation labels to retrieved chunks."""
    labels: dict[str, str] = {}
    citations: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue
        label = f"S{len(citations) + 1}"
        seen.add(chunk_id)
        labels[chunk_id] = label
        citations.append(
            {
                "id": label,
                "chunk_id": chunk_id,
                "title": chunk.get("title"),
                "url": chunk.get("url"),
                "source_type": chunk.get("source_type"),
                "source_tier": chunk.get("source_tier"),
                "department": chunk.get("department"),
                "published_at": chunk.get("published_at"),
                "fetched_from_network": chunk.get("fetched_from_network"),
                "used_fallback": chunk.get("used_fallback"),
                "fetch_status": chunk.get("fetch_status"),
                "http_status": chunk.get("http_status"),
                "text": chunk.get("text"),
            }
        )
    return labels, citations


def cite(chunk: dict | None, labels: dict[str, str]) -> str:
    """Return a citation marker for a chunk when available."""
    if not chunk:
        return ""
    label = labels.get(chunk.get("chunk_id", ""))
    return f"[{label}]" if label else ""
