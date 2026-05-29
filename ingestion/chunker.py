"""Chunking helpers for official source text."""

from __future__ import annotations


def chunk_text(text: str, max_chars: int = 700) -> list[str]:
    """Split text into simple paragraph-aware chunks."""
    paragraphs = [paragraph.strip() for paragraph in (text or "").splitlines() if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current.strip())
    return chunks

