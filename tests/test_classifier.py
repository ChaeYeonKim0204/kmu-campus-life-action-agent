from agent.classifier import classify_issue


def test_classifies_core_issues():
    assert classify_issue("예비군 때문에 결석하는데 출석인정 어떻게 해?")["issue_type"] == "attendance"
    assert classify_issue("질병휴학 하려면 뭐 필요해?")["issue_type"] == "leave_return"
    assert classify_issue("수강신청 완료됐는지 어디서 확인해?")["issue_type"] == "course_registration"
    assert classify_issue("등록금 분납은 어디서 확인해?")["issue_type"] == "registration_tuition"
    assert classify_issue("졸업예정증명서 어디서 뽑아?")["issue_type"] == "certificate"
    assert classify_issue("모바일 학생증 재발급은 어떻게 해?")["issue_type"] == "student_id"
    assert classify_issue("국가장학금 1차 신청 공지 알려줘")["issue_type"] == "scholarship"
    assert classify_issue("eCampus 비밀번호를 잊었어")["issue_type"] == "portal_access"
    assert classify_issue("통학버스 시간 어디서 봐?")["issue_type"] == "campus_facility"
    assert classify_issue("학적부 정정은 어떻게 해?")["issue_type"] == "academic_record"
    assert classify_issue("학생보험 청구하려면 뭐 필요해?")["issue_type"] == "student_insurance"
    assert classify_issue("예비군 어디에 문의해?")["issue_type"] == "military"
    assert classify_issue("이번 주 할 일 알려줘")["issue_type"] == "schedule"
    assert classify_issue("졸업요건 부족한지 확인하고 다음 학기 수강계획 짜줘")["issue_type"] == "graduation"


def test_classifies_student_slang_and_real_life_phrasing():
    assert classify_issue("이캠에 강의가 안 떠요")["issue_type"] == "portal_access"
    assert classify_issue("종정시 비번 까먹었어")["issue_type"] == "portal_access"
    assert classify_issue("국장 들어왔는지 어디서 봐?")["issue_type"] == "scholarship"
    assert classify_issue("수변 기간 언제야?")["issue_type"] == "course_registration"
    assert classify_issue("등록금 냈는데 납부확인이 안 떠")["issue_type"] == "registration_tuition"
    assert classify_issue("과사에 뭐라고 메일 보내야 해?")["issue_type"] == "contact"
    assert classify_issue("복학생인데 이번 주 뭐 해야 해?")["issue_type"] == "schedule"
