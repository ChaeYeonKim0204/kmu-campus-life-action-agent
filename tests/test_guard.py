from agent.guard import inspect_privacy, require_sources


def test_privacy_guard_blocks_student_id_and_grades():
    result = inspect_privacy("내 학번이랑 성적으로 처리해줘.")
    assert result.blocked
    assert "student_id" in result.flags
    assert "grade_report" in result.flags


def test_privacy_guard_allows_recovery_and_certificate_questions():
    assert not inspect_privacy("eCampus 비밀번호를 잊었어").blocked
    assert not inspect_privacy("성적증명서 어디서 발급해?").blocked


def test_privacy_guard_blocks_actual_password_text():
    result = inspect_privacy("제 비밀번호는 abcD1234입니다.")
    assert result.blocked
    assert "portal_password" in result.flags


def test_requires_sources():
    result = require_sources([])
    assert result.blocked
