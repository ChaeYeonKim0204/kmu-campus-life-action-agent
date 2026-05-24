"""Contact routing tool for campus-life questions."""

from __future__ import annotations


DEFAULT_CONTACTS = {
    "attendance": [{"label": "1차 제출/확인", "name": "해당 교과목 교강사"}, {"label": "행정 확인", "name": "교무팀"}],
    "leave_return": [{"label": "행정 확인", "name": "교무팀"}, {"label": "소속 확인", "name": "소속 학과사무실 또는 단과대학 교학팀"}],
    "course_registration": [{"label": "수강신청/폐강 확인", "name": "교무팀"}, {"label": "전공 과목 확인", "name": "소속 학과사무실 또는 단과대학 교학팀"}],
    "registration_tuition": [{"label": "등록금/분납 확인", "name": "재무팀 또는 등록 담당 부서"}, {"label": "학적 상태 확인", "name": "교무팀"}],
    "certificate": [{"label": "학적 관련 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4050"}],
    "student_id": [{"label": "학생증 발급 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4060"}, {"label": "금융카드 수령/발급", "name": "우리은행 국민대학교 지점"}],
    "scholarship": [{"label": "교내/국가/근로/대출 문의", "name": "학생지원팀", "phone": "02-910-4054, 4055, 4057, 4058"}],
    "portal_access": [{"label": "포털 이용/계정 확인", "name": "ON국민 포털 안내"}, {"label": "eCampus 이용", "name": "가상대학(eCampus) 안내"}],
    "schedule": [{"label": "학사일정 확인", "name": "교무팀"}, {"label": "개별 신청 상태 확인", "name": "ON국민 포털"}],
    "campus_facility": [{"label": "생활지원 확인", "name": "학생지원/시설 담당 부서"}, {"label": "생활관 문의", "name": "생활관"}, {"label": "도서관 문의", "name": "성곡도서관"}],
    "academic_record": [{"label": "학적부 정정 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4050"}],
    "student_insurance": [{"label": "학생보험 문의", "name": "학생지원팀 또는 종합서비스센터"}],
    "military": [{"label": "병무/예비군 문의", "name": "병무지원팀"}, {"label": "출석 인정 제출", "name": "해당 교과목 교강사"}],
    "graduation": [{"label": "졸업요건 확인", "name": "소속 학과사무실 또는 단과대학 교학팀"}, {"label": "학사 행정 확인", "name": "교무팀"}],
}


def route_contact(issue_type: str, policy_chunks: list[dict]) -> list[dict]:
    """Recommend official contact destinations from chunks and defaults."""
    contacts: list[dict] = []
    for chunk in policy_chunks:
        for contact in chunk.get("contacts", []) or []:
            if contact not in contacts:
                contacts.append(contact)
    for contact in DEFAULT_CONTACTS.get(issue_type, []):
        if contact not in contacts:
            contacts.append(contact)
    return contacts
