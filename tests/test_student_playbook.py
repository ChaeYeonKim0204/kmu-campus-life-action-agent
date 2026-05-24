from agent.answer_builder import build_final_answer
from agent.planner import suggest_actions
from agent.student_playbook import detect_student_terms, get_student_playbook


def test_detects_kmu_student_terms():
    terms = detect_student_terms("이캠에 강의 안 떠서 과사에 물어봐야 하나요?")
    assert "eCampus" in terms
    assert "학과사무실" in terms


def test_playbook_uses_specific_ecampus_missing_course_scenario():
    playbook = get_student_playbook("이캠에 강의가 안 떠요", "portal_access")
    assert playbook["scenario"] == "eCampus에 강의가 보이지 않는 상황"
    assert any("수강신청" in item for item in playbook["prechecks"])


def test_practical_issues_offer_contact_message_action():
    actions = suggest_actions("portal_access", [])
    action_ids = [action["action_id"] for action in actions]
    assert "portal_access_checklist" in action_ids
    assert "draft_contact_message" in action_ids


def test_answer_separates_student_experience_tips_from_official_sources():
    chunks = [
        {
            "chunk_id": "portal_1",
            "doc_id": "portal_ecampus_login_boundary",
            "title": "ON국민/eCampus 로그인 안내",
            "url": "https://www.kookmin.ac.kr",
            "text": "ON국민 포털과 eCampus는 로그인 이후 개인 화면에서 직접 확인해야 한다.",
            "source_type": "student_support",
            "source_tier": 2,
            "issue_types": ["portal_access"],
        }
    ]
    result = build_final_answer("이캠에 강의가 안 떠요", "portal_access", chunks, suggest_actions("portal_access", chunks))
    assert "[학생 경험 팁]" in result["answer"]
    assert "eCampus에 강의가 보이지 않는 상황" in result["answer"]
    assert "알아들은 국민대식 표현: eCampus" in result["answer"]
    assert "[근거]" in result["answer"]
