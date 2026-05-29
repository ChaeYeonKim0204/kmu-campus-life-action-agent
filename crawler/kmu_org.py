"""Kookmin organization/contact crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUOrgCrawler(BaseCrawler):
    """Crawler adapter for organization and contact pages."""

    source_type = "organization"
    source_tier = 7
    pages = [
        SourcePage(
            doc_id="univ_org_academic",
            title="국민대학교 대학조직 - 교무처",
            url="https://www.kookmin.ac.kr/user/unIntr/unSttu/univOrgn/index.do",
            department="교무처",
            fallback_text="교학부총장 산하 본부 조직에는 교무처가 있으며, 교무처에는 교무팀과 교원지원팀 등이 있다.",
            keywords=["교무처", "교무팀", "수강신청", "휴학", "복학", "학사"],
            search_hints=["수강신청 어디 문의", "휴학 복학 문의처", "교무팀"],
            issue_types=["attendance", "leave_return", "course_registration", "graduation"],
            contacts=[{"label": "학사 행정 확인", "name": "교무팀"}],
            actions=["draft_contact_message"],
        ),
        SourcePage(
            doc_id="univ_org_student",
            title="국민대학교 대학조직 - 학생처",
            url="https://www.kookmin.ac.kr/user/unIntr/unSttu/univOrgn/index.do",
            department="학생처",
            fallback_text="교학부총장 산하 본부 조직에는 학생처가 있으며, 학생처에는 학생지원팀, 병무지원팀, 학생생활상담센터가 있다.",
            keywords=["학생처", "학생지원팀", "병무지원팀", "예비군", "상담"],
            search_hints=["예비군 문의처", "병무지원팀", "학생지원 문의"],
            issue_types=["military", "certificate", "student_support"],
            contacts=[{"label": "병무/예비군 문의", "name": "병무지원팀"}, {"label": "학생지원 문의", "name": "학생지원팀"}],
            actions=["draft_contact_message"],
        ),
    ]
