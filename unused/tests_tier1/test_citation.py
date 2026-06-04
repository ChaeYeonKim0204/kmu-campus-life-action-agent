from agent.citation import build_citations


def test_build_citations_preserves_fetch_provenance():
    chunks = [
        {
            "chunk_id": "source_001",
            "title": "공식 안내",
            "url": "https://example.edu",
            "source_type": "notice",
            "source_tier": 5,
            "department": "교무팀",
            "published_at": "2026-05-01",
            "fetched_from_network": True,
            "used_fallback": False,
            "fetch_status": "success",
            "http_status": 200,
            "text": "공식 안내 본문",
        }
    ]

    _labels, citations = build_citations(chunks)

    source = citations[0]
    assert source["fetched_from_network"] is True
    assert source["used_fallback"] is False
    assert source["fetch_status"] == "success"
    assert source["http_status"] == 200
    assert source["published_at"] == "2026-05-01"
