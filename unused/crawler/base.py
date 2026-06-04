"""Crawler adapter base classes for official KMU sources."""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from ingestion.parser import extract_visible_text

try:
    import requests
except Exception:  # pragma: no cover - requests is optional at import time
    requests = None


@dataclass
class RawDocument:
    """A raw official document collected from a source."""

    doc_id: str
    title: str
    url: str
    source_type: str
    text: str
    metadata: dict
    response_headers: dict[str, str] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Return a stable content hash for incremental updates."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourcePage:
    """Static crawl target with metadata used when enriching chunks."""

    doc_id: str
    title: str
    url: str
    fallback_text: str
    source_tier: int | None = None
    department: str | None = None
    keywords: list[str] = field(default_factory=list)
    search_hints: list[str] = field(default_factory=list)
    issue_types: list[str] = field(default_factory=list)
    application_path: str | None = None
    required_documents: list[str] = field(default_factory=list)
    submit_to: str | None = None
    contacts: list[dict[str, Any]] = field(default_factory=list)
    schedule: dict[str, Any] | None = None
    deadline_rule: dict[str, Any] | None = None
    actions: list[str] = field(default_factory=list)
    published_at: str | None = None


class BaseCrawler:
    """Base class for official-source crawler adapters."""

    source_type = "base"
    source_tier = 9
    pages: list[SourcePage] = []
    min_delay_seconds = 8.0
    max_delay_seconds = 18.0
    max_pages_per_run = 3
    request_timeout_seconds = 12
    _last_request_at_by_host: dict[str, float] = {}

    def crawl(self, limit: int = 20, state: dict | None = None) -> list[RawDocument]:
        """Collect official documents from configured source pages.

        Network fetches are attempted first. When the environment is offline or
        a page blocks scraping, the crawler emits curated fallback text tied to
        the same official URL so the ingest pipeline remains demonstrable.
        """
        documents: list[RawDocument] = []
        max_pages = min(limit, self.max_pages_per_run)
        for page in self.pages[:max_pages]:
            fetched_text, response_headers, fetch_status = self._fetch_page_text(page.url, state=_document_state(state, page.doc_id))
            not_modified = fetch_status.get("fetch_status") == "not_modified"
            if not_modified:
                continue
            text = fetched_text or page.fallback_text
            if not text.strip():
                continue
            metadata = {
                "source_tier": page.source_tier or self.source_tier,
                "department": page.department,
                "keywords": page.keywords,
                "search_hints": page.search_hints,
                "issue_types": page.issue_types,
                "application_path": page.application_path,
                "required_documents": page.required_documents,
                "submit_to": page.submit_to,
                "contacts": page.contacts,
                "schedule": page.schedule,
                "deadline_rule": page.deadline_rule,
                "actions": page.actions,
                "published_at": page.published_at,
                "fetched_from_network": bool(fetched_text),
                "used_fallback": not bool(fetched_text),
                **fetch_status,
            }
            documents.append(
                RawDocument(
                    doc_id=page.doc_id,
                    title=page.title,
                    url=page.url,
                    source_type=self.source_type,
                    text=text,
                    metadata={key: value for key, value in metadata.items() if value not in (None, [], {})},
                    response_headers={**response_headers, **fetch_status},
                )
            )
        return documents

    def _fetch_page_text(self, url: str, state: dict | None = None) -> tuple[str, dict[str, str], dict[str, str | int]]:
        """Fetch and extract visible text from an official page."""
        if requests is None:
            return "", {}, {"fetch_status": "failed", "fetch_error": "requests_not_installed"}
        self._wait_for_host(url)
        headers = {
            "User-Agent": "KMU-Campus-Life-Action-Agent/1.0 (student demo; low-rate official-source checker)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        }
        if state:
            if state.get("etag"):
                headers["If-None-Match"] = state["etag"]
            if state.get("last_modified"):
                headers["If-Modified-Since"] = state["last_modified"]
        try:
            response = requests.get(
                url,
                timeout=self.request_timeout_seconds,
                headers=headers,
            )
            if response.status_code == 304:
                return "", _interesting_headers(response.headers), {"fetch_status": "not_modified", "http_status": 304}
            response.raise_for_status()
        except Exception as exc:
            return "", {}, {"fetch_status": "failed", "fetch_error": str(exc)}
        text = extract_visible_text(response.text)
        if not text:
            return "", _interesting_headers(response.headers), {"fetch_status": "empty", "http_status": response.status_code}
        return text, _interesting_headers(response.headers), {"fetch_status": "success", "http_status": response.status_code}

    def _wait_for_host(self, url: str) -> None:
        """Throttle requests to a human-paced cadence per host."""
        host = urlparse(url).netloc or "default"
        now = time.monotonic()
        last_request_at = self._last_request_at_by_host.get(host)
        if last_request_at is not None:
            elapsed = now - last_request_at
            minimum_gap = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
            if elapsed < minimum_gap:
                time.sleep(minimum_gap - elapsed)
        else:
            time.sleep(random.uniform(1.5, 4.0))
        self._last_request_at_by_host[host] = time.monotonic()


def _document_state(state: dict | None, doc_id: str) -> dict | None:
    if not state:
        return None
    return state.get("documents", {}).get(doc_id)


def _interesting_headers(headers) -> dict[str, str]:
    result: dict[str, str] = {}
    for source, target in [("ETag", "etag"), ("Last-Modified", "last_modified")]:
        value = headers.get(source)
        if value:
            result[target] = value
    last_modified = result.get("last_modified")
    if last_modified:
        try:
            result["last_modified_iso"] = parsedate_to_datetime(last_modified).isoformat()
        except Exception:
            pass
    return result
