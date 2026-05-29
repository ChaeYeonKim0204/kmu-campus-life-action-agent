"""Plan tool calls and next actions for a classified query."""

from __future__ import annotations


NEXT_ACTIONS = {
    "attendance": [
        {
            "action_id": "draft_attendance_recognition_form",
            "label": "출석인정신청서 초안 작성",
            "description": "결석일, 수업명, 증빙서류 등 필요한 항목을 받아 신청서 초안을 작성합니다.",
        }
    ],
    "leave_return": [
        {
            "action_id": "draft_leave_checklist",
            "label": "휴학/복학 준비 체크리스트 생성",
            "description": "신청 경로, 기간, 서류 확인 항목을 정리합니다.",
        }
    ],
    "course_registration": [
        {
            "action_id": "course_registration_checklist",
            "label": "수강신청/폐강 확인 체크리스트 생성",
            "description": "나의 시간표, 개인수업시간표, 폐강 후 내역 확인 항목을 정리합니다.",
        }
    ],
    "registration_tuition": [
        {
            "action_id": "draft_contact_message",
            "label": "등록금 문의문 초안 작성",
            "description": "등록금 납부/분납/고지서 확인을 위해 담당 부서에 보낼 문의문을 작성합니다.",
        }
    ],
    "certificate": [
        {
            "action_id": "certificate_issue_guide",
            "label": "증명서 발급 경로 확인",
            "description": "발급 가능한 증명서와 문의처를 확인합니다.",
        }
    ],
    "student_id": [
        {
            "action_id": "student_id_issue_guide",
            "label": "학생증 발급 체크리스트 생성",
            "description": "신규/재발급/모바일학생증 경로와 준비물을 정리합니다.",
        }
    ],
    "scholarship": [
        {
            "action_id": "scholarship_notice_checklist",
            "label": "장학공지 확인 체크리스트 생성",
            "description": "장학금 유형, 신청기간, 중복지원 여부 확인 항목을 정리합니다.",
        }
    ],
    "portal_access": [
        {
            "action_id": "portal_access_checklist",
            "label": "포털/eCampus 접근 체크리스트 생성",
            "description": "로그인 경계와 공식 계정 찾기 경로를 정리합니다.",
        }
    ],
    "schedule": [
        {
            "action_id": "academic_schedule_digest",
            "label": "오늘 기준 학사일정 체크리스트 생성",
            "description": "진행 중이거나 다가오는 학사일정 확인 항목을 정리합니다.",
        }
    ],
    "campus_facility": [
        {
            "action_id": "campus_facility_guide",
            "label": "생활지원 이용 체크리스트 생성",
            "description": "통학버스, 주차, 생활관, 도서관 등 이용 경로와 확인 항목을 정리합니다.",
        }
    ],
    "academic_record": [
        {
            "action_id": "academic_record_correction_checklist",
            "label": "학적부 정정 체크리스트 생성",
            "description": "정정 항목, 신청 경로, 증빙서류 확인 항목을 정리합니다.",
        }
    ],
    "student_insurance": [
        {
            "action_id": "student_insurance_checklist",
            "label": "학생보험 청구 체크리스트 생성",
            "description": "사고 상황, 적용 대상, 제출서류 확인 항목을 정리합니다.",
        }
    ],
    "military": [
        {
            "action_id": "military_service_checklist",
            "label": "병무/예비군 체크리스트 생성",
            "description": "예비군/병무 절차와 수업 결석 시 출석인정 연결 여부를 정리합니다.",
        }
    ],
    "graduation": [
        {
            "action_id": "graduation_audit",
            "label": "졸업요건 간이 진단",
            "description": "비식별 이수학점 요약을 바탕으로 부족 학점을 계산합니다.",
        },
        {
            "action_id": "recommend_course_plan",
            "label": "수강계획 방향 추천",
            "description": "부족 학점과 관심 분야를 바탕으로 다음 학기 수강계획 방향을 정리합니다.",
        }
    ],
    "contact": [
        {
            "action_id": "draft_contact_message",
            "label": "문의문 초안 작성",
            "description": "담당 부서나 교강사에게 보낼 개인정보 없는 문의문 초안을 작성합니다.",
        }
    ],
}

CONTACT_READY_ISSUES = {
    "attendance",
    "course_registration",
    "registration_tuition",
    "student_id",
    "scholarship",
    "portal_access",
    "campus_facility",
    "academic_record",
    "student_insurance",
    "military",
}


def suggest_actions(issue_type: str, chunks: list[dict]) -> list[dict]:
    """Suggest next actions suitable for the issue type and retrieved chunks."""
    actions = list(NEXT_ACTIONS.get(issue_type, []))
    chunk_actions = []
    for chunk in chunks:
        for action_id in chunk.get("actions", []) or []:
            chunk_actions.append(action_id)
    if "draft_contact_message" in chunk_actions:
        contact_action = NEXT_ACTIONS["contact"][0]
        if contact_action not in actions:
            actions.append(contact_action)
    if issue_type in CONTACT_READY_ISSUES:
        contact_action = NEXT_ACTIONS["contact"][0]
        if contact_action not in actions:
            actions.append(contact_action)
    return _dedupe_actions(actions)


def _dedupe_actions(actions: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for action in actions:
        action_id = action.get("action_id")
        if action_id in seen:
            continue
        seen.add(action_id)
        deduped.append(action)
    return deduped
