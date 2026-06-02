"""Unit tests for the out-of-scope intent detector."""

import pytest

from agent.intent_scope import (
    build_out_of_scope_answer,
    detect_out_of_scope,
    suggested_questions,
)


@pytest.mark.parametrize(
    "query,expected_category",
    [
        ("오늘 점심 뭐먹을까?", "food"),
        ("점심 뭐먹지", "food"),
        ("맛집 추천해줘", "food"),
        ("안녕", "greeting"),
        ("ㅎㅇ", "greeting"),
        ("내일 날씨 어때?", "weather"),
        ("심심한데 뭐하지", "smalltalk"),
        ("내 mbti 맞춰봐", "personal"),
    ],
)
def test_detect_out_of_scope_flags_casual_queries(query, expected_category):
    result = detect_out_of_scope(query)
    assert result["out_of_scope"] is True
    assert result["category"] == expected_category
    assert result["matched_terms"]


@pytest.mark.parametrize(
    "query",
    [
        "오늘 학식 메뉴 뭐야?",  # 학식 academic override beats 오늘+점심 hint
        "출석인정신청서 어떻게 써?",
        "이번 주 학사일정 알려줘",
        "졸업하려면 뭐 해야 돼?",
        "기숙사 식당 점심 운영시간",  # 기숙사/식당 academic override
        "수강신청 언제부터야?",
    ],
)
def test_detect_out_of_scope_lets_academic_queries_through(query):
    result = detect_out_of_scope(query)
    assert result["out_of_scope"] is False
    assert result["category"] is None


def test_detect_out_of_scope_handles_empty():
    assert detect_out_of_scope("") == {"out_of_scope": False, "category": None, "matched_terms": []}
    assert detect_out_of_scope("   ") == {"out_of_scope": False, "category": None, "matched_terms": []}


def test_build_out_of_scope_answer_includes_intro_and_samples():
    answer = build_out_of_scope_answer("food")
    assert "식사" in answer
    assert "[주의]" in answer
    # All three sample chips appear as bullets
    assert answer.count("•") == 3


def test_build_out_of_scope_answer_falls_back_for_unknown_category():
    answer = build_out_of_scope_answer(None)
    assert "국민대" in answer
    assert "•" in answer


def test_suggested_questions_limit():
    assert len(suggested_questions(3)) == 3
    assert len(suggested_questions(1)) == 1
