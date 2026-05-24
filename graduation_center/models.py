"""Pydantic models for the graduation center."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


GpaMinimumStatus = Literal["yes", "no", "unknown"]


class CourseSummary(BaseModel):
    """Non-sensitive course summary used for graduation analysis."""

    name: str = Field(..., min_length=1, max_length=120)
    credits: float = Field(..., ge=0, le=30)
    category: str = Field(default="미분류", max_length=40)


class TranscriptSummary(BaseModel):
    """Sanitized transcript summary returned to the UI."""

    masked_name: str | None = None
    masked_student_id: str | None = None
    department: str = Field(default="미확인", max_length=120)
    admission_year: int | None = Field(default=None, ge=1900, le=2100)
    total_credits: float = Field(default=0, ge=0, le=300)
    category_credits: dict[str, float] = Field(default_factory=dict)
    gpa_minimum_met: GpaMinimumStatus = "unknown"
    courses: list[CourseSummary] = Field(default_factory=list, max_length=300)
    parse_method: str = "text"
    warnings: list[str] = Field(default_factory=list)


class TranscriptParseResponse(BaseModel):
    """Response for transcript parsing."""

    status: Literal["parsed", "needs_vision_consent", "failed"]
    message: str
    transcript: TranscriptSummary | None = None
    warnings: list[str] = Field(default_factory=list)


class GraduationAnalysisRequest(BaseModel):
    """Base request for graduation analysis endpoints."""

    transcript: TranscriptSummary


class SubstituteCoursesRequest(GraduationAnalysisRequest):
    """Request for substitute course search."""

    course_name: str = Field(..., min_length=1, max_length=120)


class CareerTranslatorRequest(GraduationAnalysisRequest):
    """Request for career translation."""

    target_job: str = Field(..., min_length=1, max_length=120)


class EarlyGraduationRequest(GraduationAnalysisRequest):
    """Request for early graduation eligibility checks."""

    registered_semesters: int | None = Field(default=None, ge=1, le=20)
    is_five_year_architecture: bool = False
    has_transfer_or_readmission: bool = False
    has_academic_warning: bool = False
    has_repeated_semester: bool = False
    has_grade_waiver_history: bool = False
    has_disciplinary_record: bool = False


class CustomizedMajorRequest(GraduationAnalysisRequest):
    """Request for Customized major recognition checks."""

    desired_field: str = Field(default="", max_length=120)
    target_recognition: str = Field(default="전공선택", max_length=40)


class CreditDropRequest(GraduationAnalysisRequest):
    """Request for credit-drop / grade-waiver guidance."""

    concern: str = Field(default="성적포기 가능 여부", max_length=160)


class GraduationAnalysisResponse(BaseModel):
    """Common response for graduation center analysis."""

    status: Literal["completed", "blocked"]
    task: str
    answer: str
    sources: list[dict] = Field(default_factory=list)
    structured_check: dict = Field(default_factory=dict)
    safety_flags: list[str] = Field(default_factory=list)
    llm: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
