"""Simple JSONL keyword retriever used as the reliable fallback search path."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    """Tokenize Korean/English text for a lightweight keyword score."""
    return [token.lower() for token in TOKEN_RE.findall(text or "") if len(token) >= 2]


class KeywordRetriever:
    """Search official chunks with keyword and metadata matching."""

    def __init__(self, chunks_path: str | Path = "data/processed/chunks.jsonl"):
        self.chunks_path = Path(chunks_path)
        self.chunks = self._load_chunks()

    def _load_chunks(self) -> list[dict]:
        if not self.chunks_path.exists():
            return []
        chunks = []
        with self.chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
        return chunks

    def search(self, query: str, issue_type: str | None = None, limit: int = 6) -> list[dict]:
        """Return the most relevant chunks for a query."""
        query_tokens = set(tokenize(query))
        results: list[dict] = []
        for chunk in self.chunks:
            searchable = " ".join(
                [
                    chunk.get("text", ""),
                    chunk.get("title", ""),
                    " ".join(chunk.get("keywords", [])),
                    " ".join(chunk.get("search_hints", [])),
                ]
            )
            chunk_tokens = set(tokenize(searchable))
            keyword_hits = query_tokens & chunk_tokens
            explicit_hits = [
                keyword for keyword in chunk.get("keywords", []) if keyword and keyword.lower() in (query or "").lower()
            ]
            issue_bonus = 2 if issue_type and issue_type in chunk.get("issue_types", []) else 0
            tier_bonus = max(0, 9 - int(chunk.get("source_tier", 9))) / 10
            score = len(keyword_hits) + len(explicit_hits) * 2 + issue_bonus + tier_bonus
            if score > 0:
                enriched = dict(chunk)
                enriched["score"] = round(score, 3)
                enriched["matched_keywords"] = sorted(keyword_hits | set(explicit_hits))
                results.append(enriched)

        return sorted(results, key=lambda item: (-item["score"], int(item.get("source_tier", 9))))[:limit]

    def all_sources(self) -> list[dict]:
        """Return all chunks for source inspection."""
        return list(self.chunks)

