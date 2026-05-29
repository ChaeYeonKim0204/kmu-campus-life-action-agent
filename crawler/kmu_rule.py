"""Kookmin rule-system crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMURuleCrawler(BaseCrawler):
    """Crawler adapter for the KMU rule management system."""

    source_type = "university_rule"
    source_tier = 1
    pages = [
        SourcePage(
            doc_id="rule_academic_303",
            title="국민대학교 학사규정 - 출석/성적 관련 조항",
            url="https://rule.kookmin.ac.kr/lmxsrv/law/lawFullView.do?SEQ=303",
            department="교무팀",
            fallback_text="국민대학교 학사규정은 학사의 시행에 필요한 사항을 규정하며, 출석성적과 시험 결시자 성적처리 등 학사 운영의 제도적 근거를 제공한다.",
            keywords=["학사규정", "출석", "성적", "결시", "제도"],
            search_hints=["출석인정 제도 근거", "결석 성적 처리", "학사 규정 출석"],
            issue_types=["attendance", "course_registration", "grade"],
        )
    ]
