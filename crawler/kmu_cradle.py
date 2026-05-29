"""Kookmin cradle/yearbook crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUCradleCrawler(BaseCrawler):
    """Crawler adapter for cradle/yearbook pages."""

    source_type = "cradle"
    source_tier = 6
    pages = [
        SourcePage(
            doc_id="cradle_2025_graduation",
            title="국민대학교 요람/규정집",
            url="https://www.kookmin.ac.kr/user/unIntr/unSttu/pdfCmmn/cradle/index.do",
            department="국민대학교",
            fallback_text=(
                "국민대학교 요람/규정집 페이지는 연도별 요람을 제공하며, 졸업요건, 교육과정, 학과별 "
                "이수체계 확인의 공식 출처로 사용할 수 있다. 졸업요건은 총 이수학점, 전공 이수학점, "
                "교양 이수영역, 학과별 필수과목을 함께 확인해야 한다."
            ),
            keywords=["요람", "졸업요건", "교육과정", "이수체계", "학과"],
            search_hints=["졸업요건 어디서 확인", "학과별 교육과정", "요람"],
            issue_types=["graduation", "course_planning"],
            actions=["graduation_audit", "recommend_course_plan"],
        )
    ]
