"""Transcript PDF parsing with privacy-preserving output."""

from __future__ import annotations

import base64
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from graduation_center.data import category_from_code, load_graduation_data
from graduation_center.models import CourseSummary, TranscriptParseResponse, TranscriptSummary


FAILING_GRADES = {"F", "NP", "N", "U", "W"}


class NeedsVisionConsent(Exception):
    """Raised when an image transcript needs explicit OCR consent."""


def parse_transcript_bytes(
    content: bytes,
    filename: str,
    *,
    vision_ocr_consent: bool,
    openai_api_key: str | None,
    model: str,
) -> TranscriptParseResponse:
    """Parse a transcript PDF and return a sanitized summary."""
    if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
        return TranscriptParseResponse(status="failed", message="PDF 파일만 업로드할 수 있습니다.")
    if len(content) > 15 * 1024 * 1024:
        return TranscriptParseResponse(status="failed", message="15MB 이하의 PDF만 업로드할 수 있습니다.")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
            handle.write(content)
            tmp_path = Path(handle.name)

        text = _extract_text_pdf(tmp_path)
        if len(text.strip()) > 200:
            return TranscriptParseResponse(
                status="parsed",
                message="텍스트 기반 성적증명서를 파싱했습니다.",
                transcript=_parse_transcript_text(text, parse_method="text"),
            )

        if not vision_ocr_consent:
            return TranscriptParseResponse(
                status="needs_vision_consent",
                message="텍스트를 충분히 추출하지 못했습니다. 이미지 기반 PDF일 수 있어 Vision OCR 동의가 필요합니다.",
                warnings=["vision_ocr_consent_required"],
            )
        if not openai_api_key:
            return TranscriptParseResponse(
                status="failed",
                message="Vision OCR을 사용하려면 OPENAI_API_KEY가 필요합니다.",
                warnings=["openai_api_key_missing"],
            )
        img_b64 = _extract_pdf_image_b64(tmp_path)
        if not img_b64:
            return TranscriptParseResponse(status="failed", message="PDF에서 OCR용 이미지를 추출할 수 없습니다.")
        try:
            data = _parse_transcript_vision(img_b64, openai_api_key, model)
        except Exception:
            return TranscriptParseResponse(
                status="failed",
                message="Vision OCR 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                warnings=["vision_ocr_failed"],
            )
        return TranscriptParseResponse(
            status="parsed",
            message="이미지 기반 성적증명서를 Vision OCR로 파싱했습니다.",
            transcript=_summary_from_vision_data(data),
            warnings=["vision_ocr_used"],
        )
    except RuntimeError as exc:
        return TranscriptParseResponse(status="failed", message=str(exc))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _extract_text_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError("pdfplumber 패키지가 설치되어 있지 않습니다.") from exc
    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _parse_transcript_text(full_text: str, parse_method: str = "text") -> TranscriptSummary:
    """Parse text extracted from a transcript without returning raw sensitive values."""
    student_id = _extract(full_text, r"학\s*번[:\s]+(\d{7,10})", "")
    name = _extract(full_text, r"성\s*명[:\s]+([가-힣]{2,5})", "")
    department = _extract(full_text, r"학\s*(?:과|부|전공)[:\s]+([가-힣A-Za-z0-9·\s]+?)(?:\n|학번|성명)", "미확인")
    gpa = _to_float(_extract(full_text, r"(?:평점평균|GPA)[:\s]+([\d.]+)", ""))
    admission_year = _admission_year(student_id)
    courses: list[dict[str, Any]] = []
    total_credits = 0.0

    course_pattern = re.findall(
        r"([가-힣A-Za-z0-9&·\s\(\)\-/]+?)\s+(\d(?:\.\d)?)\s+([A-F][+0-]?|P|NP|N|S|U|W)\s+([A-Z]{1,2}|전공|교양|일반선택|기초교양|핵심교양|자유교양)?",
        full_text,
    )
    for course_name, credits_raw, grade, category in course_pattern:
        name_value = " ".join(course_name.split())
        if len(name_value) < 2 or any(token in name_value for token in ["평점", "학점", "성명", "학번"]):
            continue
        credits = _to_float(credits_raw)
        if credits <= 0:
            continue
        if grade not in FAILING_GRADES:
            total_credits += credits
        courses.append({"name": name_value[:120], "credits": credits, "grade": grade, "category": category or "미분류"})

    credits_match = re.search(r"(?:총\s*)?(?:취득|이수)\s*학점[:\s]+(\d+(?:\.\d+)?)", full_text)
    if credits_match:
        total_credits = _to_float(credits_match.group(1))

    return _build_summary(
        name=name,
        student_id=student_id,
        department=department.strip(),
        admission_year=admission_year,
        completed_credits=total_credits,
        gpa=gpa,
        courses=courses,
        parse_method=parse_method,
    )


def _extract_pdf_image_b64(path: Path) -> str | None:
    try:
        import numpy as np
        import pypdf
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        raise RuntimeError("Vision OCR에 필요한 pypdf, pillow, numpy 패키지가 설치되어 있지 않습니다.") from exc

    reader = pypdf.PdfReader(str(path))
    for page in reader.pages:
        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        for _, obj in xobjects.items():
            xobj = obj.get_object()
            if xobj.get("/Subtype") != "/Image":
                continue
            width = int(xobj["/Width"])
            height = int(xobj["/Height"])
            data = xobj.get_data()
            color_space = xobj.get("/ColorSpace", "/DeviceRGB")
            if color_space == "/DeviceRGB":
                arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
                image = Image.fromarray(arr, "RGB")
            elif color_space == "/DeviceGray":
                arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
                image = Image.fromarray(arr, "L").convert("RGB")
            else:
                continue
            from io import BytesIO

            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    return None


def _parse_transcript_vision(img_b64: str, api_key: str, model: str) -> dict:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise RuntimeError("openai 패키지가 설치되어 있지 않습니다.") from exc

    client = OpenAI(api_key=api_key)
    prompt = """국민대학교 성적증명서 이미지에서 졸업 진단에 필요한 정보만 JSON으로 추출하세요.
민감정보도 파싱에는 필요하지만, 응답 JSON 외 다른 텍스트는 절대 쓰지 마세요.

반환 형식:
{
  "이름": "",
  "학번": "",
  "학부_전공": "",
  "입학연도": 2020,
  "총_취득학점": 0.0,
  "총_평점평균": 0.0,
  "과목목록": [
    {"이수구분": "D", "교과목명": "과목명", "학점": 3.0, "성적": "A0"}
  ]
}

규칙:
- 학번은 학생 정보란의 숫자만 사용하고 증명서번호와 혼동하지 마세요.
- 과목목록에는 교과목명, 학점, 성적, 이수구분을 원본 그대로 추출하세요.
- JSON만 반환하세요."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=4096,
        temperature=0,
    )
    raw = (response.choices[0].message.content or "").strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _summary_from_vision_data(data: dict) -> TranscriptSummary:
    courses = []
    total_from_courses = 0.0
    for item in data.get("과목목록", []) or []:
        grade = str(item.get("성적", "")).strip()
        credits = _to_float(item.get("학점"))
        if grade not in FAILING_GRADES:
            total_from_courses += credits
        courses.append(
            {
                "name": str(item.get("교과목명", "")).strip(),
                "credits": credits,
                "grade": grade,
                "category": str(item.get("이수구분", "미분류")).strip(),
            }
        )
    total = _to_float(data.get("총_취득학점")) or total_from_courses
    student_id = str(data.get("학번", "")).strip()
    return _build_summary(
        name=str(data.get("이름", "")).strip(),
        student_id=student_id,
        department=str(data.get("학부_전공", data.get("대학", "미확인"))).strip(),
        admission_year=int(data.get("입학연도") or _admission_year(student_id) or 0) or None,
        completed_credits=total,
        gpa=_to_float(data.get("총_평점평균")),
        courses=courses,
        parse_method="vision",
    )


def _build_summary(
    *,
    name: str,
    student_id: str,
    department: str,
    admission_year: int | None,
    completed_credits: float,
    gpa: float,
    courses: list[dict[str, Any]],
    parse_method: str,
) -> TranscriptSummary:
    codes = load_graduation_data().get("codes")
    category_credits: dict[str, float] = {}
    safe_courses: list[CourseSummary] = []
    for course in courses[:300]:
        course_name = str(course.get("name", "")).strip()
        credits = _to_float(course.get("credits"))
        if not course_name or credits <= 0:
            continue
        mapped_category = category_from_code(str(course.get("category", "미분류")), codes)
        safe_courses.append(CourseSummary(name=course_name, credits=credits, category=mapped_category))
        if str(course.get("grade", "")).strip() not in FAILING_GRADES:
            category_credits[mapped_category] = round(category_credits.get(mapped_category, 0.0) + credits, 2)
    if not completed_credits:
        completed_credits = round(sum(item.credits for item in safe_courses), 2)
    warnings = []
    if not safe_courses:
        warnings.append("course_list_empty")
    if department == "미확인":
        warnings.append("department_unconfirmed")
    return TranscriptSummary(
        masked_name=_mask_name(name),
        masked_student_id=_mask_student_id(student_id),
        department=department or "미확인",
        admission_year=admission_year,
        total_credits=round(float(completed_credits or 0), 2),
        category_credits=category_credits,
        gpa_minimum_met=_gpa_minimum(gpa),
        courses=safe_courses,
        parse_method=parse_method,
        warnings=warnings,
    )


def _extract(text: str, pattern: str, default: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else default


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(re.sub(r"[^\d.]", "", str(value)) or 0)
    except Exception:
        return 0.0


def _admission_year(student_id: str) -> int | None:
    student_id = student_id.strip()
    if len(student_id) >= 4 and student_id[:4].isdigit():
        return int(student_id[:4])
    if len(student_id) >= 2 and student_id[:2].isdigit():
        return int("20" + student_id[:2])
    return None


def _gpa_minimum(gpa: float) -> str:
    if not gpa:
        return "unknown"
    return "yes" if gpa >= 2.0 else "no"


def _mask_name(name: str) -> str | None:
    name = name.strip()
    if not name:
        return None
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def _mask_student_id(student_id: str) -> str | None:
    digits = re.sub(r"\D", "", student_id or "")
    if not digits:
        return None
    if len(digits) <= 4:
        return "*" * len(digits)
    return digits[:4] + "*" * (len(digits) - 4)
