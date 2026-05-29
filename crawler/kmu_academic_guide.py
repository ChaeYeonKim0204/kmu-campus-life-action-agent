"""Kookmin academic guide crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUAcademicGuideCrawler(BaseCrawler):
    """Crawler adapter for academic guide pages."""

    source_type = "academic_guide"
    source_tier = 2
    pages = [
        SourcePage(
            doc_id="attendance_guide",
            title="국민대학교 학사안내 - 출석",
            url="https://www.kookmin.ac.kr/comm/menu/user/38f9c1f2d0716f9a4665578e73d98571/content/index.do",
            department="교무팀",
            fallback_text=(
                "출석인정 가능 사유로 결석하는 경우 사전 또는 사유발생 7일 이내에 출석인정신청서 및 "
                "사유별 제출서류를 준비하여 해당 교과목의 교강사에게 제출해야 한다. 예비군 훈련은 "
                "출석인정 신청 가능 사유에 해당할 수 있으며, 예비군 소집통지서 또는 훈련필증 등 관련 "
                "증빙서류를 제출해야 한다."
            ),
            keywords=["출석인정", "결석", "7일", "출석인정신청서", "예비군", "훈련필증"],
            search_hints=["출석인정 언제까지 내", "예비군 출석인정 서류", "공결 신청"],
            issue_types=["attendance", "military"],
            deadline_rule={"type": "within_days_after_event", "days": 7},
            required_documents=["출석인정신청서", "사유별 증빙서류", "예비군 소집통지서 또는 훈련필증"],
            submit_to="해당 교과목 교강사",
            actions=["draft_attendance_recognition_form"],
        ),
        SourcePage(
            doc_id="leave_return_guide",
            title="국민대학교 학사안내 - 휴학/복학",
            url="https://www.kookmin.ac.kr/comm/menu/user/e1c6c542f5c3f009ef24a10b89683abd/content/index.do",
            department="교무팀",
            fallback_text=(
                "가사휴학과 질병휴학 등 휴학 신청은 ON국민 포털의 학사서비스에서 진행하며, 신청 시기와 "
                "세부 요건은 학사안내와 학사일정을 함께 확인해야 한다. 질병휴학은 질병으로 학업을 계속할 "
                "수 없는 경우 신청하는 휴학 유형이며, 병원의 진단서 등 증빙서류 확인이 필요하다. 일반복학은 "
                "매학기 신청기간에 ON국민 포털 학사서비스의 학적정보 메뉴에서 휴학/복학신청을 통해 진행한다."
            ),
            keywords=["휴학", "복학", "질병휴학", "가사휴학", "ON국민", "진단서"],
            search_hints=["질병휴학 뭐 필요해", "복학 신청 어디서 해", "ON국민 휴학"],
            issue_types=["leave_return"],
            application_path="ON국민 포털 > 학사서비스 > 학적정보 > 휴학/복학신청",
            required_documents=["질병휴학의 경우 병원 진단서 등 질병 증빙서류"],
            actions=["draft_leave_checklist", "draft_return_checklist"],
        ),
    ]
