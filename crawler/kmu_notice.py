"""Kookmin notice crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUNoticeCrawler(BaseCrawler):
    """Crawler adapter for KMU notices."""

    source_type = "notice"
    source_tier = 5
    max_pages_per_run = 4
    pages = [
        SourcePage(
            doc_id="notice_course_registration_2026_1",
            title="2026-1학기 수강신청 일정안내",
            url="https://www.kookmin.ac.kr/user/kmuNews/notice/4/11139/view.do?currentPageNo=1",
            department="교무팀",
            published_at="2026-01-05",
            fallback_text=(
                "수강신청 후 수강신청시스템 '나의 시간표' 또는 ON국민 포털 '개인수업시간표 조회'에 "
                "표기되는 교과목만 수강신청 완료 및 수강 과목으로 인정된다. 폐강 이후에는 반드시 본인 "
                "수강신청 내역을 확인해야 한다. 교과목 거래, 매크로 사용 등 비정상적인 방식으로 수강신청을 "
                "진행하는 경우 적발된 학생의 모든 수강신청 내역이 삭제되며 학생 징계의 대상이 될 수 있다."
            ),
            keywords=["수강신청", "나의 시간표", "개인수업시간표", "폐강", "매크로"],
            search_hints=["수강신청 완료됐는지 어디서 확인해", "폐강 이후 해야 할 일", "수강신청 매크로"],
            issue_types=["course_registration"],
            application_path="수강신청시스템 나의 시간표 또는 ON국민 포털 개인수업시간표 조회",
            actions=["course_registration_checklist"],
        ),
        SourcePage(
            doc_id="notice_academic_board",
            title="국민대학교 학사공지",
            url="https://www.kookmin.ac.kr/user/kmuNews/notice/4/index.do",
            department="교무팀",
            fallback_text=(
                "학사공지는 수강신청, 계절학기, 학점교류, 전공 신청, 성적 공시 등 학기별로 변동되는 "
                "학사 행정 안내를 확인하는 공식 게시판이다. 같은 제도라도 해당 학기 공지에서 기간, 대상, "
                "제출서류, 첨부파일을 다시 확인해야 한다."
            ),
            keywords=["학사공지", "수강신청", "계절학기", "학점교류", "성적", "첨부파일"],
            search_hints=["계절학기 공지", "학사공지 확인", "수강신청 안내"],
            issue_types=["course_registration", "schedule", "graduation", "leave_return"],
            actions=["course_registration_checklist", "draft_contact_message"],
        ),
        SourcePage(
            doc_id="notice_administration_board",
            title="국민대학교 행정공지",
            url="https://www.kookmin.ac.kr/user/kmuNews/notice/5/index.do",
            department="행정 담당 부서",
            fallback_text=(
                "행정공지는 등록금 납부, 등록금 분납, 시스템 점검, 행정 서비스 안내처럼 학사안내 고정 "
                "페이지보다 시점별 변동이 큰 행정 사항을 확인하는 공식 게시판이다. 개인별 등록금 납부 상태나 "
                "고지서는 ON국민 포털에서 사용자가 직접 확인해야 한다."
            ),
            keywords=["행정공지", "등록금", "분납", "납부", "시스템공지", "ON국민"],
            search_hints=["등록금 납부", "등록금 분납", "행정공지"],
            issue_types=["registration_tuition", "portal_access", "schedule"],
            actions=["draft_contact_message", "portal_access_checklist"],
        ),
        SourcePage(
            doc_id="notice_scholarship_board",
            title="국민대학교 장학공지",
            url="https://www.kookmin.ac.kr/user/kmuNews/notice/7/index.do",
            department="학생지원팀",
            fallback_text=(
                "장학공지는 등록금지원, 등록금외지원, 등록금지원+등록금외지원, 대출, 기타 유형으로 장학 "
                "안내를 구분한다. 학생지원팀은 교내, 국가, 근로, 대출, 교외 장학 문의처를 안내하며, "
                "재학생은 국가장학금 1차 신청 등 학기별 공지의 신청기간과 대상 요건을 반드시 확인해야 한다."
            ),
            keywords=["장학공지", "장학금", "등록금지원", "등록금외지원", "국가장학금", "근로장학", "학자금 대출"],
            search_hints=["국가장학금 신청", "근로장학 신청", "장학공지"],
            issue_types=["scholarship", "registration_tuition"],
            contacts=[{"label": "학생지원팀 장학 문의", "name": "학생지원팀", "phone": "02-910-4054, 4055, 4057, 4058"}],
            actions=["scholarship_notice_checklist"],
        )
    ]
