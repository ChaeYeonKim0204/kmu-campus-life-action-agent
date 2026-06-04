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


# ---- Phase 5 follow-up: 졸업센터 sanitize와 통일된 GPA/성적/이메일 검증 ----

import pytest


@pytest.mark.parametrize("text,expected_flag", [
    ("GPA: 3.8 으로 확인됨",          "gpa_value_korean"),
    ("평점평균 3.85 입력",            "gpa_value_korean"),
    ("학생 평점 3.8/4.5 기록",        "gpa_value_fraction"),
    ("학점이 3.8입니다",              "gpa_value_decimal_nearby"),
    ("내 학점 3.85",                  "gpa_value_decimal_nearby"),
    ("평점 4.0 받음",                 "gpa_value_decimal_nearby"),
    ("문의 example@kookmin.ac.kr",    "email_value"),
    ("성적: A+ 로 받음",              "grade_letter_nearby"),
    ("grade: B0 acquired",            "grade_letter_nearby"),
])
def test_validate_output_privacy_detects_unified_with_graduation_center(text, expected_flag):
    """졸업센터 sanitize 8 패턴과 통일된 GPA/성적/이메일 패턴이 /ask 출력 검증에도 잡힘."""
    result = validate_output_privacy(text)
    assert result["ok"] is False, f"{text!r} → flag 안 뜸"
    assert expected_flag in result["flags"], f"{text!r} → 기대 flag {expected_flag} 누락, 실제 {result['flags']}"


def test_validate_output_privacy_no_false_positive_on_normal_credit_numbers():
    """학점 수치('전공 50학점' 등 정수)는 GPA decimal 패턴에 안 잡힘."""
    result = validate_output_privacy("총 130학점 중 전공 50학점, 부족 36학점.")
    assert result["ok"] is True, f"false positive: {result['flags']}"


def test_validate_output_privacy_no_false_positive_on_natural_english_text():
    """letter grade 단독 ('A great course')은 grade_letter_nearby에 안 잡힘 (근접 키워드 필요)."""
    result = validate_output_privacy("A great course on data structures. B level performance.")
    assert result["ok"] is True, f"false positive: {result['flags']}"
