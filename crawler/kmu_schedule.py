"""Kookmin academic schedule crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUScheduleCrawler(BaseCrawler):
    """Crawler adapter for academic schedule pages."""

    source_type = "schedule"
    source_tier = 4
    pages = [
        SourcePage(
            doc_id="schedule_2026_leave_return",
            title="국민대학교 학사일정 - 2026학년도 휴학/복학",
            url="https://www.kookmin.ac.kr/user/scGuid/scSchedule/index.do",
            department="교무팀",
            fallback_text="2026학년도 2학기 휴학, 복학 신청 기간은 2026.07.06부터 2026.07.24까지이다.",
            keywords=["학사일정", "휴학", "복학", "신청기간", "2026"],
            search_hints=["2학기 휴학 복학 신청 기간", "복학 언제 신청", "휴학 신청 기간"],
            issue_types=["leave_return", "schedule"],
            schedule={"start_date": "2026-07-06", "end_date": "2026-07-24", "label": "2026학년도 2학기 휴학, 복학 신청 기간"},
        ),
        SourcePage(
            doc_id="schedule_2026_course_registration",
            title="국민대학교 학사일정 - 2026학년도 수강신청",
            url="https://www.kookmin.ac.kr/user/scGuid/scSchedule/index.do",
            department="교무팀",
            fallback_text="2026학년도 2학기 수강신청 기간은 2026.08.12부터 2026.08.26까지이다.",
            keywords=["학사일정", "수강신청", "2026", "2학기"],
            search_hints=["2학기 수강신청 기간", "수강신청 언제"],
            issue_types=["course_registration", "schedule"],
            schedule={"start_date": "2026-08-12", "end_date": "2026-08-26", "label": "2026학년도 2학기 수강신청 기간"},
        ),
        SourcePage(
            doc_id="schedule_2026_summer_session",
            title="국민대학교 학사일정 - 2026학년도 하계 계절학기",
            url="https://www.kookmin.ac.kr/user/scGuid/scSchedule/index.do",
            department="교무팀",
            fallback_text=(
                "2026학년도 하계 계절학기 장바구니 기간은 2026.05.19부터 2026.05.21까지이며, "
                "하계 계절학기 수강신청 기간은 2026.05.26부터 2026.05.28까지이다. "
                "하계 계절학기 등록 기간은 2026.06.02부터 2026.06.05까지이다."
            ),
            keywords=["학사일정", "하계 계절학기", "장바구니", "수강신청", "등록", "2026"],
            search_hints=["하계 계절학기 수강신청", "계절학기 장바구니", "계절학기 등록 기간"],
            issue_types=["course_registration", "registration_tuition", "schedule"],
            schedule={"start_date": "2026-05-19", "end_date": "2026-06-05", "label": "2026학년도 하계 계절학기 장바구니/수강신청/등록 기간"},
        ),
    ]
