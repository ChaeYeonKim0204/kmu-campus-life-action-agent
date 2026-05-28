from fastapi.testclient import TestClient

import app as app_module
from graduation_center.data import load_graduation_data, policy_sources_for_task
from graduation_center.models import GraduationAnalysisResponse, TranscriptSummary
from graduation_center.parser import parse_transcript_bytes
from graduation_center.service import (
    GraduationServiceUnavailable,
    GraduationCenterService,
    TASK_TITLES,
    _build_answer,
    _credit_drop_source,
    _customized_major_source,
    _analysis_prompt,
    _official_policy_sources,
    _sanitize_sensitive_output,
    _task_specific_rules,
)


def _transcript_payload():
    return {
        "masked_name": "홍*동",
        "masked_student_id": "2020****",
        "department": "소프트웨어학부",
        "admission_year": 2020,
        "total_credits": 120,
        "category_credits": {"전공": 54, "기초교양": 13, "핵심교양": 12},
        "gpa_minimum_met": "yes",
        "courses": [{"name": "데이터베이스", "credits": 3, "category": "전공"}],
        "parse_method": "text",
        "warnings": [],
    }


def test_graduation_status_contract(monkeypatch):
    class FakeGraduationService:
        def status(self):
            return {"ready": True, "privacy": {"pdf_storage": "temporary_only"}}

    monkeypatch.setattr(app_module, "graduation_service", FakeGraduationService())
    client = TestClient(app_module.app)

    response = client.get("/graduation/status")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_graduation_analysis_endpoint_uses_sanitized_contract(monkeypatch):
    calls = []

    class FakeGraduationService:
        def analyze(self, task, transcript, extra=None):
            calls.append({"task": task, "transcript": transcript, "extra": extra})
            return GraduationAnalysisResponse(
                status="completed",
                task=task,
                answer="[졸업 진단]\n총학점 확인이 필요합니다. [G1]",
                sources=[{"id": "G1", "title": "요람", "page": "195", "section": "별표5"}],
                structured_check={"matched": True},
                llm={"used": True, "model": "fake"},
            )

    monkeypatch.setattr(app_module, "graduation_service", FakeGraduationService())
    client = TestClient(app_module.app)

    response = client.post("/graduation/audit", json={"transcript": _transcript_payload()})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["llm"]["used"] is True
    assert calls[0]["task"] == "audit"
    assert isinstance(calls[0]["transcript"], TranscriptSummary)


def test_new_graduation_policy_endpoints_forward_extra_fields(monkeypatch):
    calls = []

    class FakeGraduationService:
        def analyze(self, task, transcript, extra=None):
            calls.append({"task": task, "transcript": transcript, "extra": extra or {}})
            return GraduationAnalysisResponse(
                status="completed",
                task=task,
                answer=f"[{task}]\n확인했습니다. [G1]",
                sources=[{"id": "G1", "title": "요람", "page": "195", "section": "별표5"}],
                structured_check={"matched": True},
                llm={"used": True, "model": "fake"},
            )

    monkeypatch.setattr(app_module, "graduation_service", FakeGraduationService())
    client = TestClient(app_module.app)

    base = {"transcript": _transcript_payload()}
    requests = [
        (
            "/graduation/early-graduation",
            {
                **base,
                "registered_semesters": 6,
                "has_grade_waiver_history": True,
                "has_academic_warning": True,
            },
        ),
        (
            "/graduation/customized-major",
            {**base, "desired_field": "보험계리사", "target_recognition": "전공선택"},
        ),
        (
            "/graduation/credit-drop",
            {**base, "concern": "조기졸업 영향"},
        ),
    ]

    for endpoint, payload in requests:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 200

    assert [call["task"] for call in calls] == ["early_graduation", "customized_major", "credit_drop"]
    assert calls[0]["extra"]["registered_semesters"] == 6
    assert calls[0]["extra"]["has_grade_waiver_history"] is True
    assert calls[1]["extra"]["desired_field"] == "보험계리사"
    assert calls[1]["extra"]["target_recognition"] == "전공선택"
    assert calls[2]["extra"]["concern"] == "조기졸업 영향"


def test_graduation_analysis_returns_503_when_not_ready(monkeypatch):
    class FakeGraduationService:
        def analyze(self, task, transcript, extra=None):
            raise GraduationServiceUnavailable("graduation_center_not_ready")

    monkeypatch.setattr(app_module, "graduation_service", FakeGraduationService())
    client = TestClient(app_module.app)

    response = client.post("/graduation/micro-degree", json={"transcript": _transcript_payload()})

    assert response.status_code == 503
    assert response.json()["detail"] == "graduation_center_not_ready"


def test_transcript_parser_rejects_non_pdf_without_optional_dependencies():
    result = parse_transcript_bytes(b"not-a-pdf", "transcript.txt", vision_ocr_consent=False, openai_api_key=None, model="gpt-4o")

    assert result.status == "failed"
    assert "PDF" in result.message


def test_graduation_output_sanitizer_masks_sensitive_values():
    sanitized = _sanitize_sensitive_output("학번 2020123456 / 연락처 01012345678 / GPA 3.9")

    assert "2020123456" not in sanitized
    assert "01012345678" not in sanitized
    assert "3.9" not in sanitized


def test_curated_customized_major_source_reflects_uploaded_notice():
    source = _customized_major_source()

    assert source["source_type"] == "user_provided_official_notice_image"
    assert "5차 학기 이상 재학생" in source["text"]
    assert "2026.06.01" in source["text"]
    assert "2026.06.08" in source["text"]
    assert "02-910-4043" in source["text"]


def test_credit_drop_source_uses_official_grade_waiver_rules():
    source = _credit_drop_source()

    assert source["source_type"] == "official_academic_guide"
    assert "7차 학기 재학생" in source["text"]
    assert "최대 6학점" in source["text"]
    assert "조기졸업 신청 또는 예정자" in source["text"]
    assert "W(Withdraw)" in source["text"]


def test_early_graduation_policy_sources_include_official_notice():
    sources = _official_policy_sources("early_graduation")

    assert any("조기졸업 승인 안내" in source["title"] for source in sources)


def test_graduation_policy_json_loads_new_policy_tasks():
    data = load_graduation_data()

    assert not data["missing_files"]
    for task in ["early_graduation", "customized_major", "credit_drop"]:
        sources = policy_sources_for_task(data, task)
        assert sources
        assert sources[0]["text"]


def test_service_sources_include_curated_policy_json_before_rag(monkeypatch):
    service = GraduationCenterService()
    monkeypatch.setattr(service, "_rag_search", lambda query, limit=6: [])
    data = load_graduation_data()

    sources = service._sources_for(
        "customized_major",
        _transcript_payload(),
        {"matched": False, "department": "소프트웨어학부"},
        {},
        data,
    )

    assert sources[1]["source_type"] == "user_provided_official_notice_image"
    assert sources[1]["id"] == "G2"


def test_early_graduation_policy_json_mentions_core_cautions():
    data = load_graduation_data()
    source = policy_sources_for_task(data, "early_graduation")[0]

    assert "6학기 이상" in source["text"]
    assert "졸업연기" in source["text"]
    assert "성적포기 내역" in source["text"]


def test_analysis_prompt_adds_answer_quality_rules():
    transcript = _transcript_payload()
    sources = [{"id": "G1", "title": "요람", "page": "195", "section": "별표5", "text": "근거"}]

    prompt = _analysis_prompt("credit_drop", transcript, {"matched": True}, sources, {"concern": "조기졸업 영향"})

    assert "summary는 한 문장" in prompt
    assert "마크다운 표는 만들지 마세요" in prompt
    assert "공식 용어 '성적포기'" in prompt
    assert "조기졸업 신청 또는 예정자 제한" in prompt
    assert "가능 여부, 충족 항목, 부족 항목" in prompt


def test_task_specific_rules_cover_customized_major():
    rules = "\n".join(_task_specific_rules("customized_major"))

    assert "자격" in rules
    assert "서류" in rules
    assert "승인 후 제한" in rules


# ---- P2 회귀: agent_product_planning.md §15.4 5섹션 통일 ----

import pytest


def _sample_sources():
    return [
        {"id": "G1", "title": "요람 별표5", "page": "195", "section": "졸업이수학점표"},
        {"id": "G2", "title": "요람", "page": "732", "section": "졸업요건"},
    ]


def _sample_payload():
    return {
        "summary": "총학점과 전공학점이 부족하여 졸업 요건을 충족하지 못합니다.",
        "findings": [
            {"label": "가능 여부", "detail": "졸업 불가능", "source_ids": ["G1"]},
            {"label": "부족 항목", "detail": "전공 16학점 부족", "source_ids": ["G1"]},
            {"label": "확인 필요", "detail": "캡스톤 이수 여부", "source_ids": ["G2"]},
        ],
        "recommendations": [
            {"action": "전공 16학점 학기별 계획", "reason": "졸업 위해", "source_ids": ["G1"]},
        ],
        "warnings": ["성적포기 처리 여부 확인 필요"],
    }


@pytest.mark.parametrize("task", [
    "audit", "early_graduation", "substitute_courses", "micro_degree",
    "customized_major", "credit_drop",
])
def test_build_answer_planning_tasks_use_semester_plan_label(task):
    """6 task: '[다음 학기 수강계획에 반영할 항목]' 라벨 (학기 계획 적용 가능)."""
    answer = _build_answer(task, _sample_payload(), _sample_sources())
    assert f"[{TASK_TITLES[task]}]" in answer
    assert "[자동 분석 결과]" in answer
    assert "[부족·불확실 항목]" in answer
    assert "[학과·교무팀에 확인할 질문]" in answer
    assert "[다음 학기 수강계획에 반영할 항목]" in answer
    assert "[다음 행동]" not in answer  # 학기 라벨이 우선
    assert "[최종 확인]" in answer
    assert "[근거]" in answer


@pytest.mark.parametrize("task", ["post_graduation_checklist", "career_translator"])
def test_build_answer_post_grad_and_career_use_action_label(task):
    """post_grad/career: 학기 계획 부적합 → '[다음 행동]' 라벨로 교체."""
    answer = _build_answer(task, _sample_payload(), _sample_sources())
    assert "[자동 분석 결과]" in answer
    assert "[부족·불확실 항목]" in answer
    assert "[학과·교무팀에 확인할 질문]" in answer
    assert "[다음 학기 수강계획에 반영할 항목]" not in answer  # 드롭
    assert "[다음 행동]" in answer
    assert "[최종 확인]" in answer
    assert "[근거]" in answer


def test_build_answer_always_has_final_confirmation_and_sources():
    """§15.4 binding — 모든 task에 [최종 확인]·[근거]·고정 문구 존재."""
    for task in TASK_TITLES:
        answer = _build_answer(task, _sample_payload(), _sample_sources())
        assert "[최종 확인]" in answer
        assert "최종 판정은 학과사무실/교무팀 확인" in answer
        assert "[근거]" in answer
        assert "[G1]" in answer  # citation 보존


def test_build_answer_fallback_when_findings_empty():
    """findings 비어있어도 [부족·불확실]과 [학과·교무팀 확인] 섹션은 fallback 문구로 채워짐."""
    payload = {"summary": "졸업 가능", "findings": [], "recommendations": [], "warnings": []}
    answer = _build_answer("audit", payload, _sample_sources())
    assert "[부족·불확실 항목]" in answer
    assert "부족·불확실 항목 없음" in answer
    assert "[학과·교무팀에 확인할 질문]" in answer
    assert "학과사무실/교무팀에서 검토받고" in answer
