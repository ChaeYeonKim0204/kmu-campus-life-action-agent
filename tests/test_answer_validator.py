from agent.answer_validator import validate_answer_contract, validate_output_privacy


def test_validate_answer_contract_accepts_resolved_markers():
    result = validate_answer_contract("안내입니다.[S1]\n\n[근거]\n- [S1] 공식 문서", [{"id": "S1"}])

    assert result["ok"] is True
    assert result["flags"] == []


def test_validate_answer_contract_rejects_unresolved_markers():
    result = validate_answer_contract("안내입니다.[S2]\n\n[근거]\n- [S1] 공식 문서", [{"id": "S1"}])

    assert result["ok"] is False
    assert "unresolved_citation_marker" in result["flags"]


def test_validate_answer_contract_rejects_missing_inline_marker():
    result = validate_answer_contract("안내입니다.\n\n[근거]\n- 공식 문서", [{"id": "S1"}])

    assert result["ok"] is False
    assert "missing_inline_citation_marker" in result["flags"]


def test_validate_output_privacy_detects_concrete_sensitive_values():
    result = validate_output_privacy("학생 값은 2026123456이고 휴대폰은 01012345678입니다.")

    assert result["ok"] is False
    assert "student_id_value" in result["flags"]
    assert "mobile_phone_value" in result["flags"]


def test_validate_output_privacy_allows_generic_recovery_words():
    result = validate_output_privacy("포털 비밀번호 찾기 메뉴에서 직접 재설정하세요.")

    assert result["ok"] is True
