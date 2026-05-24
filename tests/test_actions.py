from agent.action_state import continue_action, start_action


def test_attendance_action_requests_missing_slots():
    result = start_action("draft_attendance_recognition_form")
    assert result["status"] == "needs_input"
    assert "event_date" in result["missing_slots"]


def test_attendance_action_drafts_document():
    slots = {
        "event_date": "2026-05-15",
        "absence_reason": "예비군 훈련",
        "course_name": "자료구조",
        "instructor_name_optional": "담당 교강사",
        "evidence_document_type": "예비군 소집통지서 또는 훈련필증",
        "planned_submission_date": "2026-05-20",
    }
    result = continue_action("draft_attendance_recognition_form", slots)
    assert result["status"] == "completed"
    assert "출석인정신청서 초안" in result["document"]
    assert "자료구조" in result["document"]


def test_leave_action_drafts_checklist():
    slots = {
        "leave_type": "질병휴학",
        "target_semester": "2026-2학기",
        "evidence_document_type_optional": "진단서",
    }
    result = continue_action("draft_leave_checklist", slots)
    assert result["status"] == "completed"
    assert "휴학 준비 체크리스트" in result["document"]
    assert "진단서" in result["document"]


def test_graduation_action_calculates_gaps():
    slots = {
        "total_credits": "120",
        "major_credits": "52",
        "target_total_credits_optional": "130",
        "target_major_credits_optional": "60",
    }
    result = continue_action("graduation_audit", slots)
    assert result["status"] == "completed"
    assert result["audit"]["total_credit_gap"] == 10
    assert result["audit"]["major_credit_gap"] == 8


def test_student_id_action_drafts_checklist():
    slots = {"card_type": "모바일학생증", "student_status_optional": "재학생"}
    result = continue_action("student_id_issue_guide", slots)
    assert result["status"] == "completed"
    assert "학생증 발급 체크리스트" in result["document"]
    assert "모바일학생증" in result["document"]


def test_portal_access_action_does_not_request_credentials():
    slots = {"service_name": "eCampus", "problem_summary": "비밀번호를 잊음"}
    result = continue_action("portal_access_checklist", slots)
    assert result["status"] == "completed"
    assert "개인정보" in result["document"]
    assert "입력하지 않습니다" in result["document"]


def test_campus_facility_action_drafts_checklist():
    slots = {"facility_type": "통학버스", "need_summary_optional": "노선과 시간"}
    result = continue_action("campus_facility_guide", slots)
    assert result["status"] == "completed"
    assert "생활지원 이용 체크리스트" in result["document"]
    assert "통학버스" in result["document"]


def test_academic_schedule_action_drafts_checklist():
    slots = {"target_period": "이번 주", "concern_optional": "계절학기"}
    result = continue_action("academic_schedule_digest", slots)
    assert result["status"] == "completed"
    assert "오늘 기준 학사일정 체크리스트" in result["document"]
    assert "계절학기" in result["document"]


def test_academic_record_action_drafts_checklist():
    slots = {"correction_item": "영문명", "reason_optional": "정정 필요"}
    result = continue_action("academic_record_correction_checklist", slots)
    assert result["status"] == "completed"
    assert "학적부 정정 체크리스트" in result["document"]
    assert "개인정보" in result["document"]


def test_student_insurance_action_drafts_checklist():
    slots = {"incident_type": "교내 활동 중 부상", "incident_date_optional": "2026-05-19"}
    result = continue_action("student_insurance_checklist", slots)
    assert result["status"] == "completed"
    assert "학생보험 청구 체크리스트" in result["document"]
    assert "진단서" in result["document"]
