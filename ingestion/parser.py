"""HTML parsing helpers for crawler output."""

from __future__ import annotations

from bs4 import BeautifulSoup


def extract_visible_text(html: str) -> str:
    """Extract visible text from HTML while removing common layout elements."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())

