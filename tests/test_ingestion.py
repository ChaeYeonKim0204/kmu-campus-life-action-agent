from datetime import datetime, timezone

from crawler.base import RawDocument
from ingestion.pipeline import _cooldown_remaining, document_to_chunks, summarize_fetches
from retriever.vector_retriever import VectorRetriever, hash_embedding


def test_document_to_chunks_preserves_official_metadata():
    document = RawDocument(
        doc_id="demo_doc",
        title="공식 문서",
        url="https://www.kookmin.ac.kr/demo",
        source_type="academic_guide",
        text="첫 문단\n둘째 문단",
        metadata={
            "source_tier": 2,
            "department": "교무팀",
            "keywords": ["출석"],
            "issue_types": ["attendance"],
        },
    )
    chunks = document_to_chunks(document)
    assert chunks[0]["chunk_id"] == "demo_doc_001"
    assert chunks[0]["source_tier"] == 2
    assert chunks[0]["department"] == "교무팀"


def test_hash_embedding_is_deterministic():
    assert hash_embedding("출석 인정") == hash_embedding("출석 인정")


def test_vector_retriever_is_safe_without_chroma():
    retriever = VectorRetriever(persist_path="/tmp/kmu-test-chroma")
    results = retriever.search("예비군", "attendance")
    assert isinstance(results, list)


def test_cooldown_blocks_recent_same_source():
    state = {"last_ingest": {"source": "all", "completed_at": datetime.now(timezone.utc).isoformat()}}
    assert _cooldown_remaining(state, "all") > 0


def test_fetch_summary_reports_fallback_and_failures():
    documents = [
        RawDocument(
            doc_id="failed_doc",
            title="실패 문서",
            url="https://www.kookmin.ac.kr/failed",
            source_type="notice",
            text="fallback",
            metadata={"fetched_from_network": False, "used_fallback": True, "fetch_status": "failed", "fetch_error": "403"},
        ),
        RawDocument(
            doc_id="ok_doc",
            title="성공 문서",
            url="https://www.kookmin.ac.kr/ok",
            source_type="notice",
            text="network",
            metadata={"fetched_from_network": True, "used_fallback": False, "fetch_status": "success"},
        ),
    ]
    summary = summarize_fetches(documents)
    assert summary["network_success"] == 1
    assert summary["fallback_used"] == 1
    assert summary["network_failed"] == 1
    assert summary["failed_urls"][0]["error"] == "403"
