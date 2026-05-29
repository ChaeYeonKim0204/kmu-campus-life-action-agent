from pathlib import Path

from crawler.base import BaseCrawler, SourcePage
from ingestion import live_refresh
from ingestion.live_refresh import refresh_sources_for_issue
from ingestion.pipeline import load_chunks, load_state, write_chunks, write_state


class SuccessfulCrawler(BaseCrawler):
    source_type = "fake"
    source_tier = 2
    pages = [
        SourcePage(
            doc_id="fake_attendance",
            title="출석인정 안내",
            url="https://example.edu/attendance",
            fallback_text="오래된 fallback",
            keywords=["출석인정"],
            issue_types=["attendance"],
        )
    ]

    def _fetch_page_text(self, url, state=None):
        return "네트워크에서 가져온 최신 출석인정 안내", {"etag": "v2"}, {"fetch_status": "success", "http_status": 200}


class FailedCrawler(BaseCrawler):
    source_type = "fake"
    source_tier = 2
    pages = SuccessfulCrawler.pages

    def _fetch_page_text(self, url, state=None):
        return "", {}, {"fetch_status": "failed", "fetch_error": "offline"}


def test_live_refresh_updates_chunks_only_for_network_success(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(live_refresh, "CRAWLERS", {"fake": SuccessfulCrawler})

    result = refresh_sources_for_issue(
        "attendance",
        query="출석인정",
        chunks_path=chunks_path,
        state_path=state_path,
        cooldown_seconds=0,
    )

    chunks = load_chunks(chunks_path)
    state = load_state(state_path)
    assert result["attempted"] is True
    assert result["updated"] is True
    assert result["network_success"] == 1
    assert chunks[0]["doc_id"] == "fake_attendance"
    assert "최신 출석인정" in chunks[0]["text"]
    assert state["documents"]["fake_attendance"]["etag"] == "v2"


def test_live_refresh_preserves_existing_chunks_when_network_fails(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(live_refresh, "CRAWLERS", {"fake": FailedCrawler})
    write_chunks(
        chunks_path,
        [
            {
                "chunk_id": "fake_attendance_001",
                "doc_id": "fake_attendance",
                "source_tier": 2,
                "source_type": "fake",
                "title": "출석인정 안내",
                "url": "https://example.edu/attendance",
                "text": "기존에 저장된 공식 근거",
                "issue_types": ["attendance"],
            }
        ],
    )
    write_state(state_path, {"documents": {}})

    result = refresh_sources_for_issue(
        "attendance",
        query="출석인정",
        chunks_path=chunks_path,
        state_path=state_path,
        cooldown_seconds=0,
    )

    chunks = load_chunks(chunks_path)
    assert result["attempted"] is True
    assert result["updated"] is False
    assert result["fallback_used"] == 1
    assert result["network_failed"] == 1
    assert chunks[0]["text"] == "기존에 저장된 공식 근거"


def test_live_refresh_cooldown_skips_recent_issue(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(live_refresh, "CRAWLERS", {"fake": SuccessfulCrawler})

    first = refresh_sources_for_issue(
        "attendance",
        query="출석인정",
        chunks_path=chunks_path,
        state_path=state_path,
        cooldown_seconds=60,
    )
    second = refresh_sources_for_issue(
        "attendance",
        query="출석인정",
        chunks_path=chunks_path,
        state_path=state_path,
        cooldown_seconds=60,
    )

    assert first["updated"] is True
    assert second["attempted"] is False
    assert second["cooldown_remaining_seconds"] > 0
