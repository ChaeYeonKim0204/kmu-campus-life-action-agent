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


# ---- P4 회귀: 운영 품질화 ----

def test_graduation_action_has_no_mvp_label_in_document_or_audit():
    """Plan P4 — 문서·audit.note에서 'MVP' 표현 제거됨."""
    slots = {"total_credits": "100", "major_credits": "50"}
    result = continue_action("graduation_audit", slots)
    assert result["status"] == "completed"
    assert "MVP" not in result["document"], result["document"]
    assert "MVP" not in result["audit"]["note"]
    assert "학과사무실" in result["audit"]["note"]


def test_graduation_action_passes_policy_chunks_through_to_audit():
    """policy_chunks 흐름 — chunks 명시 졸업요건이 audit.requirements_source에 반영."""
    slots = {"total_credits": "100", "major_credits": "50"}
    chunks = [
        {
            "doc_id": "yoram_swdept_2025",
            "title": "요람 별표5 (소프트웨어학부)",
            "graduation_requirements": {"total_credits": 136, "major_credits": 66},
        }
    ]
    result = continue_action("graduation_audit", slots, chunks)
    assert result["status"] == "completed"
    audit = result["audit"]
    assert "chunk:yoram_swdept_2025" in audit["requirements_source"], audit["requirements_source"]
    assert audit["total_credit_gap"] == 36
    assert audit["major_credit_gap"] == 16
    assert "yoram_swdept_2025" in result["document"]


def test_graduation_action_audit_has_operational_fields():
    """audit dict에 next_actions_for_plan / confirm_with_department 필드 존재."""
    slots = {"total_credits": "100", "major_credits": "50"}
    result = continue_action("graduation_audit", slots)
    audit = result["audit"]
    assert isinstance(audit.get("next_actions_for_plan"), list)
    assert len(audit["next_actions_for_plan"]) >= 1
    assert isinstance(audit.get("confirm_with_department"), list)
    assert len(audit["confirm_with_department"]) >= 1


def test_graduation_audit_chunks_with_partial_requirements_no_keyerror():
    """Codex SHOULD-FIX — chunks에 major_credits 없어도 default(60)로 보강, KeyError 없음."""
    slots = {"total_credits": "100", "major_credits": "50"}
    # major_credits 누락된 chunk
    chunks = [
        {
            "doc_id": "yoram_partial",
            "graduation_requirements": {"total_credits": 136},  # major_credits 없음
        }
    ]
    result = continue_action("graduation_audit", slots, chunks)
    assert result["status"] == "completed"
    audit = result["audit"]
    assert "chunk:yoram_partial" in audit["requirements_source"]
    # total_credits=136 (chunks) + major_credits=60 (default fill)
    assert audit["total_credit_gap"] == 36  # 136-100
    assert audit["major_credit_gap"] == 10  # 60-50 (default)


def test_course_planner_action_output_ends_with_final_confirmation():
    """recommend_course_plan 출력에 §15.4 최종 확인 항목 포함."""
    slots = {
        "total_credit_gap": "10",
        "major_credit_gap": "5",
        "interests_optional": "데이터",
    }
    result = continue_action("recommend_course_plan", slots)
    assert result["status"] == "completed"
    text = "\n".join(result["checklist"])
    assert "최종 졸업요건 충족 여부는" in text
    assert "학과사무실" in text or "교무팀" in text


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
