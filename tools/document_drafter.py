"""Draft action documents and guides from schema-like action definitions."""

from __future__ import annotations

from tools.course_planner import recommend_course_plan
from tools.graduation import audit_graduation_requirements


ACTION_SCHEMAS: dict[str, dict] = {
    "draft_attendance_recognition_form": {
        "label": "출석인정신청서 초안 작성",
        "issue_type": "attendance",
        "required_slots": [
            "event_date",
            "absence_reason",
            "course_name",
            "instructor_name_optional",
            "evidence_document_type",
            "planned_submission_date",
        ],
        "questions": {
            "event_date": "결석일 또는 훈련일은 언제인가요? 예: 2026-05-15",
            "absence_reason": "결석 사유를 적어주세요. 예: 예비군 훈련",
            "course_name": "대상 수업명은 무엇인가요?",
            "instructor_name_optional": "담당 교강사명을 적어주세요. 모르면 '담당 교강사'라고 적어도 됩니다.",
            "evidence_document_type": "준비할 증빙서류는 무엇인가요? 예: 예비군 소집통지서 또는 훈련필증",
            "planned_submission_date": "제출 예정일은 언제인가요? 예: 2026-05-20",
        },
    },
    "draft_leave_checklist": {
        "label": "휴학 준비 체크리스트 생성",
        "issue_type": "leave_return",
        "required_slots": ["leave_type", "target_semester", "evidence_document_type_optional"],
        "questions": {
            "leave_type": "휴학 유형은 무엇인가요? 예: 가사휴학, 질병휴학",
            "target_semester": "대상 학기는 언제인가요? 예: 2026-2학기",
            "evidence_document_type_optional": "준비 가능한 증빙서류가 있나요? 없으면 '없음'이라고 적어주세요.",
        },
    },
    "draft_return_checklist": {
        "label": "복학 준비 체크리스트 생성",
        "issue_type": "leave_return",
        "required_slots": ["target_semester", "current_leave_type_optional"],
        "questions": {
            "target_semester": "복학하려는 학기는 언제인가요? 예: 2026-2학기",
            "current_leave_type_optional": "현재 휴학 유형을 적어주세요. 모르면 '일반'이라고 적어주세요.",
        },
    },
    "course_registration_checklist": {
        "label": "수강신청/폐강 확인 체크리스트 생성",
        "issue_type": "course_registration",
        "required_slots": ["target_semester", "concern"],
        "questions": {
            "target_semester": "확인하려는 학기는 언제인가요? 예: 2026-2학기",
            "concern": "확인하고 싶은 내용을 적어주세요. 예: 수강신청 완료 여부, 폐강 여부",
        },
    },
    "certificate_issue_guide": {
        "label": "증명서 발급 경로 확인",
        "issue_type": "certificate",
        "required_slots": ["certificate_type", "purpose_optional"],
        "questions": {
            "certificate_type": "필요한 증명서 종류는 무엇인가요? 예: 졸업예정증명서",
            "purpose_optional": "사용 목적을 간단히 적어주세요. 없으면 '확인용'이라고 적어주세요.",
        },
    },
    "student_id_issue_guide": {
        "label": "학생증 발급 체크리스트 생성",
        "issue_type": "student_id",
        "required_slots": ["card_type", "student_status_optional"],
        "questions": {
            "card_type": "필요한 학생증 유형은 무엇인가요? 예: 신규, 재발급, 모바일학생증, 국제학생증",
            "student_status_optional": "현재 상태를 개인정보 없이 적어주세요. 예: 신입생, 재학생, 휴학생",
        },
    },
    "scholarship_notice_checklist": {
        "label": "장학공지 확인 체크리스트 생성",
        "issue_type": "scholarship",
        "required_slots": ["scholarship_type", "target_semester_optional"],
        "questions": {
            "scholarship_type": "확인하려는 장학 유형은 무엇인가요? 예: 국가장학금, 근로장학금, 교외장학금",
            "target_semester_optional": "대상 학기를 적어주세요. 모르면 '미정'이라고 적어주세요.",
        },
    },
    "portal_access_checklist": {
        "label": "포털/eCampus 접근 체크리스트 생성",
        "issue_type": "portal_access",
        "required_slots": ["service_name", "problem_summary"],
        "questions": {
            "service_name": "어떤 서비스인가요? 예: ON국민 포털, eCampus",
            "problem_summary": "문제를 개인정보 없이 적어주세요. 예: 비밀번호를 잊음, 수강신청 메뉴를 못 찾음",
        },
    },
    "academic_schedule_digest": {
        "label": "오늘 기준 학사일정 체크리스트 생성",
        "issue_type": "schedule",
        "required_slots": ["target_period", "concern_optional"],
        "questions": {
            "target_period": "확인할 기간은 언제인가요? 예: 이번 주, 이번 달, 2026-2학기",
            "concern_optional": "특히 확인할 항목이 있나요? 예: 수강신청, 등록, 휴학/복학",
        },
    },
    "campus_facility_guide": {
        "label": "생활지원 이용 체크리스트 생성",
        "issue_type": "campus_facility",
        "required_slots": ["facility_type", "need_summary_optional"],
        "questions": {
            "facility_type": "확인할 생활지원 항목은 무엇인가요? 예: 통학버스, 주차, 생활관, 도서관 열람석, 오늘의 메뉴",
            "need_summary_optional": "확인하고 싶은 내용을 적어주세요. 없으면 '이용방법'이라고 적어주세요.",
        },
    },
    "academic_record_correction_checklist": {
        "label": "학적부 정정 체크리스트 생성",
        "issue_type": "academic_record",
        "required_slots": ["correction_item", "reason_optional"],
        "questions": {
            "correction_item": "정정하려는 학적 정보 항목은 무엇인가요? 예: 이름, 영문명, 주소",
            "reason_optional": "정정 사유를 개인정보 없이 적어주세요. 없으면 '정정 필요'라고 적어주세요.",
        },
    },
    "student_insurance_checklist": {
        "label": "학생보험 청구 체크리스트 생성",
        "issue_type": "student_insurance",
        "required_slots": ["incident_type", "incident_date_optional"],
        "questions": {
            "incident_type": "사고/상해 유형을 개인정보 없이 적어주세요. 예: 교내 활동 중 부상",
            "incident_date_optional": "발생일을 적어주세요. 모르면 '미정'이라고 적어주세요.",
        },
    },
    "military_service_checklist": {
        "label": "병무/예비군 체크리스트 생성",
        "issue_type": "military",
        "required_slots": ["military_topic", "class_absence_optional"],
        "questions": {
            "military_topic": "확인할 병무/예비군 주제는 무엇인가요? 예: 예비군 훈련, 병무 상담",
            "class_absence_optional": "수업 결석과 관련 있나요? 예: 예, 아니오",
        },
    },
    "graduation_audit": {
        "label": "졸업요건 간이 진단",
        "issue_type": "graduation",
        # P4: target_*_optional은 이름대로 진짜 optional로 분리 — 비어있으면 policy_chunks 또는 default 130/60 사용.
        "required_slots": ["total_credits", "major_credits"],
        "questions": {
            "total_credits": "현재 총 이수학점을 숫자로 적어주세요. 개인 성적표 원본은 입력하지 마세요.",
            "major_credits": "현재 전공 이수학점을 숫자로 적어주세요.",
            "target_total_credits_optional": "기준 총 졸업학점을 알면 숫자로 적어주세요. 모르면 130이라고 적어주세요.",
            "target_major_credits_optional": "기준 전공 졸업학점을 알면 숫자로 적어주세요. 모르면 60이라고 적어주세요.",
        },
    },
    "recommend_course_plan": {
        "label": "수강계획 방향 추천",
        "issue_type": "graduation",
        "required_slots": ["interests_optional", "total_credit_gap", "major_credit_gap"],
        "questions": {
            "interests_optional": "관심 분야를 쉼표로 적어주세요. 없으면 '없음'이라고 적어주세요.",
            "total_credit_gap": "부족한 총 학점을 숫자로 적어주세요.",
            "major_credit_gap": "부족한 전공 학점을 숫자로 적어주세요.",
        },
    },
    "draft_contact_message": {
        "label": "문의문 초안 작성",
        "issue_type": "contact",
        "required_slots": ["topic", "destination_optional", "question_summary"],
        "questions": {
            "topic": "문의 주제를 적어주세요. 예: 질병휴학 서류 확인",
            "destination_optional": "문의할 부서를 알면 적어주세요. 모르면 '담당 부서'라고 적어주세요.",
            "question_summary": "묻고 싶은 내용을 개인정보 없이 요약해 주세요.",
        },
    },
}


def supported_actions() -> dict[str, dict]:
    """Return action definitions."""
    return ACTION_SCHEMAS


def action_issue_type(action_id: str) -> str | None:
    """Return the issue type associated with an action."""
    return ACTION_SCHEMAS.get(action_id, {}).get("issue_type")


def missing_slots(action_id: str, slots: dict) -> list[str]:
    """Return missing slots for a supported action."""
    schema = ACTION_SCHEMAS.get(action_id)
    if not schema:
        return []
    return [slot for slot in schema["required_slots"] if not _has_value(slots.get(slot))]


def slot_questions(action_id: str, missing: list[str]) -> list[str]:
    """Create user-facing questions for missing action slots."""
    questions = ACTION_SCHEMAS.get(action_id, {}).get("questions", {})
    return [questions.get(slot, slot) for slot in missing]


def draft_action_document(action_id: str, slots: dict, policy_chunks: list[dict]) -> dict:
    """Draft a grounded action document from user-provided non-sensitive slots."""
    if action_id == "draft_attendance_recognition_form":
        return _attendance_document(slots)
    if action_id == "draft_leave_checklist":
        return _leave_checklist(slots, policy_chunks)
    if action_id == "draft_return_checklist":
        return _return_checklist(slots, policy_chunks)
    if action_id == "course_registration_checklist":
        return _course_registration_checklist(slots)
    if action_id == "certificate_issue_guide":
        return _certificate_guide(slots)
    if action_id == "student_id_issue_guide":
        return _student_id_guide(slots)
    if action_id == "scholarship_notice_checklist":
        return _scholarship_checklist(slots)
    if action_id == "portal_access_checklist":
        return _portal_access_checklist(slots)
    if action_id == "academic_schedule_digest":
        return _academic_schedule_digest(slots)
    if action_id == "campus_facility_guide":
        return _campus_facility_guide(slots)
    if action_id == "academic_record_correction_checklist":
        return _academic_record_checklist(slots)
    if action_id == "student_insurance_checklist":
        return _student_insurance_checklist(slots)
    if action_id == "military_service_checklist":
        return _military_service_checklist(slots)
    if action_id == "graduation_audit":
        return _graduation_audit(slots, policy_chunks)
    if action_id == "recommend_course_plan":
        return _course_plan(slots)
    if action_id == "draft_contact_message":
        return _contact_message(slots, policy_chunks)
    return {"document": "지원하지 않는 action입니다.", "checklist": []}


def _attendance_document(slots: dict) -> dict:
    reason = slots.get("absence_reason", "예비군 훈련")
    event_date = slots.get("event_date", "")
    course = slots.get("course_name", "해당 교과목")
    instructor = slots.get("instructor_name_optional", "담당 교강사")
    evidence = slots.get("evidence_document_type", "증빙서류")
    planned = slots.get("planned_submission_date", "")

    document = f"""[출석인정신청서 초안]

신청 사유:
본인은 {reason}으로 인해 {event_date}에 {course} 수업에 출석하지 못하게 되어, 국민대학교 출석인정 안내에 따라 출석인정을 신청하고자 합니다.

대상 수업:
{course}

결석일 또는 사유 발생일:
{event_date}

제출 대상:
{instructor}

첨부 예정 증빙서류:
{evidence}

제출 예정일:
{planned}

확인 문구:
위 내용은 공식 근거를 바탕으로 작성한 초안이며, 실제 학교 양식과 담당 교강사 안내에 맞게 사용자가 직접 최종 확인 후 제출해야 합니다."""

    checklist = [
        "공식 출석인정신청서 양식이 있는지 확인합니다.",
        f"{evidence}를 준비합니다.",
        "사유 발생 7일 이내 제출 대상인지 확인합니다.",
        f"{instructor}에게 제출합니다.",
        "출석 인정 여부를 최종 확인합니다.",
    ]
    return {"document": document, "checklist": checklist}


def _leave_checklist(slots: dict, chunks: list[dict]) -> dict:
    leave_type = slots.get("leave_type", "휴학")
    semester = slots.get("target_semester", "대상 학기")
    evidence = slots.get("evidence_document_type_optional", "해당 시 증빙서류")
    paths = _paths(chunks) or ["ON국민 포털 > 학사서비스 > 학적정보 > 휴학/복학신청"]
    checklist = [
        f"{semester} {leave_type} 신청 기간을 학사일정에서 확인합니다.",
        f"신청 경로를 확인합니다: {paths[0]}",
        f"증빙서류를 준비합니다: {evidence}",
        "신청 후 접수/승인 상태를 포털에서 직접 확인합니다.",
    ]
    return {"document": "[휴학 준비 체크리스트]\n" + "\n".join(f"{idx}. {item}" for idx, item in enumerate(checklist, 1)), "checklist": checklist}


def _return_checklist(slots: dict, chunks: list[dict]) -> dict:
    semester = slots.get("target_semester", "대상 학기")
    leave_type = slots.get("current_leave_type_optional", "일반")
    paths = _paths(chunks) or ["ON국민 포털 > 학사서비스 > 학적정보 > 휴학/복학신청"]
    checklist = [
        f"{semester} 복학 신청 기간을 학사일정에서 확인합니다.",
        f"현재 휴학 유형({leave_type})에 추가 서류가 필요한지 확인합니다.",
        f"신청 경로를 확인합니다: {paths[0]}",
        "복학 승인 후 수강신청 가능 상태를 확인합니다.",
    ]
    return {"document": "[복학 준비 체크리스트]\n" + "\n".join(f"{idx}. {item}" for idx, item in enumerate(checklist, 1)), "checklist": checklist}


def _course_registration_checklist(slots: dict) -> dict:
    semester = slots.get("target_semester", "대상 학기")
    concern = slots.get("concern", "수강신청 상태")
    checklist = [
        f"{semester} {concern}를 수강신청시스템 '나의 시간표'에서 확인합니다.",
        "ON국민 포털 '개인수업시간표 조회'에도 동일하게 표시되는지 확인합니다.",
        "폐강 공지가 있으면 본인 수강신청 내역을 다시 확인합니다.",
        "교과목 거래나 매크로 등 비정상 수강신청 방식은 사용하지 않습니다.",
    ]
    return {"document": "[수강신청/폐강 확인 체크리스트]\n" + "\n".join(f"{idx}. {item}" for idx, item in enumerate(checklist, 1)), "checklist": checklist}


def _certificate_guide(slots: dict) -> dict:
    certificate_type = slots.get("certificate_type", "증명서")
    purpose = slots.get("purpose_optional", "확인용")
    checklist = [
        f"인터넷 증명 발급신청 페이지에서 {certificate_type} 발급 가능 여부를 확인합니다.",
        f"사용 목적({purpose})에 맞는 국문/영문, 원본확인 방식, 수수료를 확인합니다.",
        "발급 조건이 걸려 있는 증명서는 종합서비스센터에 확인합니다.",
    ]
    document = f"[증명서 발급 안내]\n필요 증명서: {certificate_type}\n사용 목적: {purpose}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _student_id_guide(slots: dict) -> dict:
    card_type = slots.get("card_type", "학생증")
    status = slots.get("student_status_optional", "재학생")
    checklist = [
        f"{card_type} 발급 대상이 현재 상태({status})에 해당하는지 확인합니다.",
        "신규 금융카드는 우리WON뱅킹 신청 경로와 수령지를 확인합니다.",
        "재발급/비금융카드는 ON국민 포털 KCARD 메뉴에서 신청서 출력 여부를 확인합니다.",
        "종합서비스센터 방문이 필요한 경우 신분증과 신청서를 준비합니다.",
        "모바일학생증은 포털 사용자등록 후 발급 가능 시점과 휴대폰 번호 일치 여부를 확인합니다.",
    ]
    document = f"[학생증 발급 체크리스트]\n필요 유형: {card_type}\n현재 상태: {status}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _scholarship_checklist(slots: dict) -> dict:
    scholarship_type = slots.get("scholarship_type", "장학금")
    semester = slots.get("target_semester_optional", "대상 학기")
    checklist = [
        f"{semester} {scholarship_type} 공지를 장학공지에서 확인합니다.",
        "장학금 성격이 등록금지원, 등록금외지원, 등록금지원+등록금외지원, 대출, 기타 중 어디에 해당하는지 확인합니다.",
        "신청기간, 제출서류, 성적/소득/재학상태 요건을 공지 본문에서 확인합니다.",
        "한국장학재단 신청이 필요한 장학은 학교 공지와 재단 신청 상태를 모두 확인합니다.",
        "중복지원 또는 휴학/복학 상태가 수혜에 영향을 주는지 학생지원팀에 확인합니다.",
    ]
    document = f"[장학공지 확인 체크리스트]\n장학 유형: {scholarship_type}\n대상 학기: {semester}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _portal_access_checklist(slots: dict) -> dict:
    service = slots.get("service_name", "ON국민 포털")
    problem = slots.get("problem_summary", "접근 문제")
    checklist = [
        f"{service} 공식 로그인 페이지에서 계정 찾기/비밀번호 찾기 메뉴를 사용자가 직접 진행합니다.",
        "포털 ID, 비밀번호, 학번, 연락처 같은 개인정보는 에이전트나 채팅창에 입력하지 않습니다.",
        "eCampus는 포털 통합ID로 로그인하는지, 별도 계정 옵션이 필요한지 확인합니다.",
        "로그인 후 개인 화면의 신청/조회 결과는 사용자가 직접 확인합니다.",
        "계정 복구가 되지 않으면 공식 포털 안내 또는 담당 부서에 문의합니다.",
    ]
    document = f"[포털/eCampus 접근 체크리스트]\n서비스: {service}\n문제 요약: {problem}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _academic_schedule_digest(slots: dict) -> dict:
    period = slots.get("target_period", "이번 주")
    concern = slots.get("concern_optional", "주요 학사일정")
    checklist = [
        f"{period} 기준 {concern}이 학사일정에 있는지 확인합니다.",
        "일정이 신청/납부/제출 성격이면 관련 학사공지나 행정공지를 함께 확인합니다.",
        "신청 가능 여부와 개인 처리 상태는 ON국민 포털에서 직접 확인합니다.",
        "마감일이 가까운 일정은 담당 부서 문의 전에 공식 공지의 시간 기준을 먼저 확인합니다.",
    ]
    document = f"[오늘 기준 학사일정 체크리스트]\n기간: {period}\n관심 항목: {concern}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _campus_facility_guide(slots: dict) -> dict:
    facility = slots.get("facility_type", "생활지원")
    need = slots.get("need_summary_optional", "이용방법")
    checklist = [
        f"{facility} 공식 안내 페이지에서 {need}을 확인합니다.",
        "운영시간, 신청대상, 요금/좌석/노선 등 변동 가능한 항목을 최신 공지와 함께 확인합니다.",
        "생활관, 도서관, 통학버스처럼 별도 사이트가 있는 항목은 해당 사이트의 공지도 확인합니다.",
        "개인 신청이나 예약이 필요한 경우 로그인 이후 화면은 사용자가 직접 처리합니다.",
    ]
    document = f"[생활지원 이용 체크리스트]\n항목: {facility}\n확인 내용: {need}\n\n" + "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _academic_record_checklist(slots: dict) -> dict:
    item = slots.get("correction_item", "학적 정보")
    reason = slots.get("reason_optional", "정정 필요")
    checklist = [
        f"정정 항목({item})이 학적부 정정 대상인지 확인합니다.",
        "정정 사유에 맞는 증빙서류가 필요한지 공식 안내에서 확인합니다.",
        "증빙서류에 포함된 개인정보는 에이전트에 입력하지 말고 공식 포털 또는 담당 부서로 직접 제출합니다.",
        "정정 처리 후 증명서와 포털 내 정보가 반영되었는지 사용자가 직접 확인합니다.",
    ]
    document = f"[학적부 정정 체크리스트]\n정정 항목: {item}\n사유 요약: {reason}\n\n" + "\n".join(
        f"{idx}. {task}" for idx, task in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _student_insurance_checklist(slots: dict) -> dict:
    incident_type = slots.get("incident_type", "사고/상해")
    incident_date = slots.get("incident_date_optional", "미정")
    checklist = [
        f"사고/상해 유형({incident_type})과 발생일({incident_date})을 개인정보 없이 정리합니다.",
        "학생보험 적용 대상, 청구 가능 기간, 제출서류를 공식 안내에서 확인합니다.",
        "진단서, 진료비 영수증, 통장사본 등 민감 자료는 담당 부서 안내에 따라 직접 제출합니다.",
        "보험 청구 전 학과사무실 또는 학생지원 담당 부서에 문의가 필요한지 확인합니다.",
    ]
    document = f"[학생보험 청구 체크리스트]\n사고/상해 유형: {incident_type}\n발생일: {incident_date}\n\n" + "\n".join(
        f"{idx}. {task}" for idx, task in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _military_service_checklist(slots: dict) -> dict:
    topic = slots.get("military_topic", "예비군/병무")
    absence = slots.get("class_absence_optional", "미정")
    checklist = [
        f"{topic} 공식 안내에서 대상자, 신청/확인 경로, 준비서류를 확인합니다.",
        "수업 결석과 관련 있으면 출석인정 신청 가능 여부와 제출기한을 함께 확인합니다.",
        "소집통지서, 훈련필증 등 증빙서류는 제출 전 원본/사본 요건을 확인합니다.",
        f"수업 결석 관련 여부: {absence}",
    ]
    document = f"[병무/예비군 체크리스트]\n주제: {topic}\n\n" + "\n".join(
        f"{idx}. {task}" for idx, task in enumerate(checklist, 1)
    )
    return {"document": document, "checklist": checklist}


def _graduation_audit(slots: dict, policy_chunks: list[dict] | None = None) -> dict:
    # 사용자가 명시한 기준만 dict로 전달; 없으면 None → policy_chunks 또는 default 적용 (audit 내부).
    user_total = slots.get("target_total_credits_optional")
    user_major = slots.get("target_major_credits_optional")
    requirements: dict | None = None
    if user_total or user_major:
        requirements = {
            "total_credits": _to_int(user_total, 130),
            "major_credits": _to_int(user_major, 60),
        }
    result = audit_graduation_requirements(
        {"total_credits": _to_int(slots.get("total_credits")), "major_credits": _to_int(slots.get("major_credits"))},
        requirements=requirements,
        chunks=policy_chunks,
    )
    checklist = [
        f"총 졸업학점 부족분: {result['total_credit_gap']}학점",
        f"전공 졸업학점 부족분: {result['major_credit_gap']}학점",
        *result.get("next_actions_for_plan", []),
        *result.get("confirm_with_department", []),
    ]
    doc_lines = [
        "[졸업요건 간이 진단]",
        f"기준 출처: {result.get('requirements_source', '?')}",
        "",
        *(f"- {item}" for item in checklist),
        "",
        f"주의: {result.get('note', '')}",
    ]
    return {"document": "\n".join(doc_lines), "checklist": checklist, "audit": result}


def _course_plan(slots: dict) -> dict:
    interests_raw = slots.get("interests_optional", "")
    interests = [] if interests_raw in {"없음", "none", "None"} else [item.strip() for item in interests_raw.split(",") if item.strip()]
    recommendations = recommend_course_plan(
        interests,
        {"total_credit_gap": _to_int(slots.get("total_credit_gap")), "major_credit_gap": _to_int(slots.get("major_credit_gap"))},
    )
    checklist = [*recommendations, "개설 여부와 시간표 충돌은 수강신청시스템에서 최종 확인합니다."]
    return {"document": "[수강계획 방향 추천]\n" + "\n".join(f"{idx}. {item}" for idx, item in enumerate(checklist, 1)), "checklist": checklist}


def _contact_message(slots: dict, chunks: list[dict]) -> dict:
    topic = slots.get("topic", "문의")
    destination = slots.get("destination_optional") or _first_contact_name(chunks) or "담당 부서"
    summary = slots.get("question_summary", "")
    document = f"""[문의문 초안]

수신: {destination}
제목: {topic} 관련 문의

안녕하세요.
{topic}와 관련하여 아래 내용을 확인하고자 문의드립니다.

문의 내용:
{summary}

개인정보가 필요한 확인은 공식 포털 또는 담당 부서 안내에 따라 별도로 진행하겠습니다.
확인 부탁드립니다.
감사합니다."""
    checklist = ["개인정보를 본문에 넣지 않았는지 확인합니다.", f"{destination}이 적절한 문의처인지 확인합니다.", "공식 포털/학과사무실 안내와 함께 확인합니다."]
    return {"document": document, "checklist": checklist}


def _paths(chunks: list[dict]) -> list[str]:
    paths: list[str] = []
    for chunk in chunks:
        path = chunk.get("application_path")
        if path and path not in paths:
            paths.append(path)
    return paths


def _first_contact_name(chunks: list[dict]) -> str | None:
    for chunk in chunks:
        for contact in chunk.get("contacts", []) or []:
            if contact.get("name"):
                return contact["name"]
    return None


def _has_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def _to_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default
