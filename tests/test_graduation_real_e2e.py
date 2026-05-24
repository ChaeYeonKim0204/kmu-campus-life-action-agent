"""Opt-in E2E checks for a local real transcript PDF.

This file intentionally skips by default. It is meant for a developer's local
machine only, with a private transcript PDF that must never be committed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import app as app_module


RUN_FLAG = "RUN_REAL_TRANSCRIPT_E2E"
PDF_PATH_ENV = "REAL_TRANSCRIPT_PDF_PATH"


def _real_transcript_path() -> Path:
    if os.getenv(RUN_FLAG) != "1":
        pytest.skip(f"{RUN_FLAG}=1 이 설정된 경우에만 실제 성적증명서 E2E를 실행합니다.")
    load_dotenv(dotenv_path=Path("test/.env"), override=False)
    if not os.getenv("OPENAI_API_KEY", "").strip():
        pytest.skip("OPENAI_API_KEY가 없어 실제 성적증명서 E2E를 건너뜁니다.")
    raw_path = os.getenv(PDF_PATH_ENV, "").strip()
    if not raw_path:
        pytest.skip(f"{PDF_PATH_ENV}가 없어 실제 성적증명서 E2E를 건너뜁니다.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        pytest.skip(f"{PDF_PATH_ENV} 파일을 찾을 수 없어 실제 성적증명서 E2E를 건너뜁니다.")
    if path.suffix.lower() != ".pdf":
        pytest.skip(f"{PDF_PATH_ENV}는 PDF 파일이어야 합니다.")
    return path


def test_real_transcript_graduation_center_e2e_contract():
    pdf_path = _real_transcript_path()
    client = TestClient(app_module.app)
    status = client.get("/graduation/status").json()
    if not status.get("ready"):
        pytest.skip("졸업센터가 ready 상태가 아니어서 실제 성적증명서 E2E를 건너뜁니다.")

    parse_data = _parse_real_pdf(client, pdf_path, vision_ocr_consent=False)
    if parse_data["status"] == "needs_vision_consent":
        parse_data = _parse_real_pdf(client, pdf_path, vision_ocr_consent=True)

    assert parse_data["status"] == "parsed"
    _assert_parse_response_is_sanitized(parse_data)
    transcript = parse_data["transcript"]
    assert transcript

    for endpoint, body in _analysis_requests(transcript):
        response = client.post(endpoint, json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"completed", "blocked"}
        _assert_analysis_response_is_sanitized(data)


def _parse_real_pdf(client: TestClient, pdf_path: Path, *, vision_ocr_consent: bool) -> dict[str, Any]:
    with pdf_path.open("rb") as handle:
        response = client.post(
            "/graduation/transcript/parse",
            files={"file": ("real_transcript.pdf", handle, "application/pdf")},
            data={"vision_ocr_consent": "true" if vision_ocr_consent else "false", "store_result": "false"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"parsed", "needs_vision_consent"}
    _assert_no_raw_text_keys(data)
    return data


def _analysis_requests(transcript: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    course_name = _first_course_name(transcript) or "캡스톤디자인"
    return [
        ("/graduation/audit", {"transcript": transcript}),
        (
            "/graduation/early-graduation",
            {
                "transcript": transcript,
                "registered_semesters": None,
                "is_five_year_architecture": False,
                "has_transfer_or_readmission": False,
                "has_academic_warning": False,
                "has_repeated_semester": False,
                "has_grade_waiver_history": False,
                "has_disciplinary_record": False,
            },
        ),
        (
            "/graduation/customized-major",
            {
                "transcript": transcript,
                "desired_field": "데이터/AI 직무",
                "target_recognition": "전공선택",
            },
        ),
        (
            "/graduation/credit-drop",
            {"transcript": transcript, "concern": "성적포기 가능 여부와 졸업 영향"},
        ),
        (
            "/graduation/substitute-courses",
            {"transcript": transcript, "course_name": course_name},
        ),
        ("/graduation/micro-degree", {"transcript": transcript}),
        ("/graduation/post-graduation-checklist", {"transcript": transcript}),
        (
            "/graduation/career-translator",
            {"transcript": transcript, "target_job": "데이터 분석가"},
        ),
    ]


def _first_course_name(transcript: dict[str, Any]) -> str:
    for course in transcript.get("courses") or []:
        name = str(course.get("name", "")).strip()
        if name:
            return name
    return ""


def _assert_parse_response_is_sanitized(data: dict[str, Any]) -> None:
    _assert_no_raw_text_keys(data)
    transcript = data.get("transcript") or {}
    masked_name = transcript.get("masked_name")
    masked_student_id = transcript.get("masked_student_id")
    _assert_safe(masked_name is None or "*" in masked_name, "이름 마스킹 계약이 깨졌습니다.")
    _assert_safe(masked_student_id is None or "*" in masked_student_id, "학번 마스킹 계약이 깨졌습니다.")
    _assert_safe(transcript.get("gpa_minimum_met") in {"yes", "no", "unknown"}, "GPA 상태 계약이 깨졌습니다.")
    _assert_safe("gpa" not in transcript, "GPA 원시 필드가 응답에 포함되었습니다.")
    _assert_safe("gpa_value" not in transcript, "GPA 숫자 필드가 응답에 포함되었습니다.")
    for course in transcript.get("courses") or []:
        _assert_safe("grade" not in course, "과목별 성적 필드가 응답에 포함되었습니다.")
        _assert_safe(set(course).issubset({"name", "credits", "category"}), "과목 요약 허용 필드 계약이 깨졌습니다.")


def _assert_analysis_response_is_sanitized(data: dict[str, Any]) -> None:
    _assert_no_raw_text_keys(data)
    answer = str(data.get("answer", ""))
    _assert_safe(not re.search(r"\b20\d{6,8}\b", answer), "학번으로 보이는 값이 분석 응답에 포함되었습니다.")
    _assert_safe(not re.search(r"01[016789]-?\d{3,4}-?\d{4}", answer), "연락처로 보이는 값이 분석 응답에 포함되었습니다.")
    _assert_safe(
        not re.search(r"(GPA|평점평균)\s*[:：]?\s*\d+(?:\.\d+)?", answer, flags=re.IGNORECASE),
        "GPA 숫자가 분석 응답에 포함되었습니다.",
    )
    _assert_safe("raw OCR" not in answer, "raw OCR 문구가 분석 응답에 포함되었습니다.")
    _assert_safe("raw text" not in answer, "raw text 문구가 분석 응답에 포함되었습니다.")


def _assert_no_raw_text_keys(value: Any) -> None:
    raw = json.dumps(value, ensure_ascii=False)
    _assert_safe("raw_text" not in raw, "raw_text 키가 응답에 포함되었습니다.")
    _assert_safe("ocr_text" not in raw, "ocr_text 키가 응답에 포함되었습니다.")
    _assert_safe("raw_ocr_text" not in raw, "raw_ocr_text 키가 응답에 포함되었습니다.")


def _assert_safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)
