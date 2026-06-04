"""Public SWELL crawler."""

from crawler.base import BaseCrawler, SourcePage


class SWELLPublicCrawler(BaseCrawler):
    """Crawler adapter for public SWELL pages only."""

    source_type = "swell_public"
    source_tier = 8
    pages = [
        SourcePage(
            doc_id="swell_public_guidance",
            title="국민대학교 SWELL 공개 게시판 안내",
            url="https://swell.kookmin.ac.kr/",
            department="국민대학교",
            fallback_text="SWELL 공개 게시판은 일부 비교과 및 공개 신청 안내를 확인할 수 있는 경로이며, 로그인 이후 개인 신청 화면은 자동 접근하지 않는다.",
            keywords=["SWELL", "비교과", "공개 게시판", "신청"],
            search_hints=["SWELL 공개 신청 안내", "비교과 신청 어디서 확인"],
            issue_types=["student_support"],
        )
    ]
