"""Phase 5 P5 — 졸업센터 8 task 풀 회귀 (실제 OpenAI 호출).

agent_product_planning.md §15.3 (8 task 명세) + §15.4 (5섹션 통일, P2) +
§7.3·§15.2 (sanitization, P3) 통합 contract 검증.

기본 skip (live_llm 마크). 풀 회귀:
    pytest tests/test_graduation_8_tasks.py -m live_llm
또는:
    RUN_LIVE_LLM=1 pytest tests/test_graduation_8_tasks.py
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import app


pytestmark = pytest.mark.live_llm

client = TestClient(app)


def _base_transcript() -> dict:
    """공통 비식별 transcript (소프트웨어학부 100/130학점, 평점 yes)."""
    return {
        "department": "소프트웨어학부",
        "admission_year": 2021,
        "total_credits": 100.0,
        "category_credits": {"전공": 50, "기초교양": 18, "핵심교양": 12, "자유교양": 20},
        "gpa_minimum_met": "yes",
        "courses": [
            {"name": "데이터구조", "credits": 3, "category": "전공필수"},
            {"name": "운영체제", "credits": 3, "category": "전공필수"},
            {"name": "알고리즘", "credits": 3, "category": "전공필수"},
            {"name": "데이터베이스", "credits": 3, "category": "전공선택"},
            {"name": "소프트웨어공학", "credits": 3, "category": "전공선택"},
            {"name": "글쓰기", "credits": 3, "category": "기초교양"},
            {"name": "영어회화1", "credits": 2, "category": "기초교양"},
            {"name": "인공지능과 사회", "credits": 3, "category": "핵심교양"},
            {"name": "철학의 이해", "credits": 3, "category": "자유교양"},
        ],
    }


# (task_name, endpoint, task-specific RequestModel extras)
TASK_CASES: list[tuple[str, str, dict]] = [
    ("audit", "/graduation/audit", {}),
    ("early_graduation", "/graduation/early-graduation", {
        "registered_semesters": 6,
        "is_five_year_architecture": False,
        "has_transfer_or_readmission": False,
        "has_academic_warning": False,
        "has_repeated_semester": False,
        "has_grade_waiver_history": False,
        "has_disciplinary_record": False,
    }),
    ("post_graduation_checklist", "/graduation/post-graduation-checklist", {}),
    ("substitute_courses", "/graduation/substitute-courses", {"course_name": "데이터구조"}),
    ("micro_degree", "/graduation/micro-degree", {}),
    ("career_translator", "/graduation/career-translator", {"target_job": "데이터 엔지니어"}),
    ("customized_major", "/graduation/customized-major",
     {"desired_field": "AI", "target_recognition": "자기설계 전공"}),
    ("credit_drop", "/graduation/credit-drop", {"concern": "조기졸업 위해 성적포기 고려"}),
]


# P2 매핑 — task별 §15.4 4번째 섹션 라벨
PLAN_SECTION_PER_TASK = {
    "audit": "[다음 학기 수강계획에 반영할 항목]",
    "early_graduation": "[다음 학기 수강계획에 반영할 항목]",
    "substitute_courses": "[다음 학기 수강계획에 반영할 항목]",
    "micro_degree": "[다음 학기 수강계획에 반영할 항목]",
    "customized_major": "[다음 학기 수강계획에 반영할 항목]",
    "credit_drop": "[다음 학기 수강계획에 반영할 항목]",
    "post_graduation_checklist": "[다음 행동]",
    "career_translator": "[다음 행동]",
}


# P3 sanitization 검증용 — 출력에 나오면 안 되는 raw 패턴
SENSITIVE_LEAK_PATTERNS = (
    (r"\b20\d{6,8}\b", "학번 raw"),
    (r"\d{6}-\d{7}", "주민번호 raw"),
    (r"01[016789]-?\d{3,4}-?\d{4}", "연락처 raw"),
    (r"GPA\s*[:：]?\s*\d+\.\d+", "GPA 숫자 raw"),
    (r"평점평균\s*[:：]?\s*\d+\.\d+", "평점평균 raw"),
    (r"\b\d\.\d{1,2}\s*/\s*4(?:\.\d+)?", "GPA 분수형 raw"),
    (r"(?:성적|학점|grade|score)\s*[:=]?\s*[ABCDF][+\-0]?", "성적 letter raw"),
)


@pytest.mark.parametrize("task,endpoint,extra", TASK_CASES,
                         ids=[c[0] for c in TASK_CASES])
def test_graduation_8_tasks_full_contract(task: str, endpoint: str, extra: dict):
    """8 task × 6 contract 검증 — 실제 OpenAI 호출 발생."""
    body = {"transcript": _base_transcript(), **extra}
    r = client.post(endpoint, json=body)
    assert r.status_code == 200, f"{task} HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()

    # 1. status completed
    assert data.get("status") == "completed", f"{task} status={data.get('status')}"

    # 2. P2 §15.4 섹션 매핑
    answer = data.get("answer", "")
    expected_section = PLAN_SECTION_PER_TASK[task]
    for required_section in ("[자동 분석 결과]", "[부족·불확실 항목]",
                              "[학과·교무팀에 확인할 질문]", expected_section,
                              "[최종 확인]", "[근거]"):
        assert required_section in answer, f"{task} {required_section} 누락"

    # 3. [G1]~ citation ≥ 1
    assert "[G1]" in answer, f"{task} citation [G1] 누락"

    # 4. P3 7 패턴 출력 누출 0
    for pattern, label in SENSITIVE_LEAK_PATTERNS:
        leaks = re.findall(pattern, answer)
        assert not leaks, f"{task} 민감정보 {label} 누출: {leaks}"

    # 5. sources ≥ 1
    assert len(data.get("sources", [])) >= 1, f"{task} sources 비어있음"

    # 6. llm.model=gpt-5-mini + used=True
    llm_meta = data.get("llm", {})
    assert llm_meta.get("model") == "gpt-5-mini", f"{task} llm.model={llm_meta.get('model')}"
    assert llm_meta.get("used") is True, f"{task} llm.used={llm_meta.get('used')}"
