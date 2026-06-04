from retriever.hybrid_retriever import HybridRetriever


def test_retrieves_course_confirmation_source():
    results = HybridRetriever().search("수강신청 완료됐는지 어디서 확인해?", "course_registration")
    assert results
    assert any("나의 시간표" in result["text"] for result in results)


def test_retrieves_certificate_source():
    results = HybridRetriever().search("졸업예정증명서 어디서 뽑아?", "certificate")
    assert results
    assert any("증명" in result["title"] for result in results)

