"""FastAPI server — KMU 졸업사정 컨설팅 에이전트 (졸업센터 전용).

재설계(2026-06)로 옛 캠퍼스라이프 /ask·/actions·/ingest·/sources 파이프라인은 제거됨.
원본 코드는 unused/ 보관(unused/legacy_app_with_ask.py = 슬림화 전 전체본 1075줄).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from graduation_center import GraduationCenterService
from graduation_center.models import (
    CreditDropRequest,
    CustomizedMajorRequest,
    EarlyGraduationRequest,
    CareerTranslatorRequest,
    GraduationAnalysisRequest,
    SubstituteCoursesRequest,
)
from graduation_center.service import GraduationServiceUnavailable
from graduation_center.v2 import pipeline as v2_pipeline
from graduation_center.v2 import whatif as v2_whatif
from graduation_center.v2.catalog import load_programs
from graduation_center.v2.excel_parser import fail_fast_columns as v2_fail_fast_columns

app = FastAPI(title="KMU Graduation Consulting Agent", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_local_environment() -> None:
    """Load local .env without overriding shell-provided values."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


_load_local_environment()

graduation_service = GraduationCenterService()

frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")
dist_assets = Path("frontend/dist/assets")
if dist_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_assets)), name="frontend_assets")


@app.get("/", response_model=None)
def index():
    """Serve the local demo UI when available."""
    html = Path("frontend/dist/index.html")
    if html.exists():
        return FileResponse(html)
    return {
        "message": "KMU Graduation Consulting Agent API",
        "frontend": "Run `cd frontend && npm install && npm run dev`, then open http://127.0.0.1:5173",
    }


@app.get("/health")
def health() -> dict:
    """Service health — 졸업센터 준비 상태만(옛 retriever/llm 텔레메트리는 unused/ 보관)."""
    return {
        "status": "ok",
        "graduation_center": graduation_service.status(),
    }


# --- 졸업센터 v1 (PDF 성적증명서 기반 분석 과제) ---

def _graduation_analysis_response(task: str, transcript, extra: dict[str, Any] | None = None) -> dict:
    """Run graduation service analysis and map readiness failures to HTTP 503."""
    try:
        return graduation_service.analyze(task, transcript, extra).model_dump()
    except GraduationServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _truthy_form_value(value) -> bool:
    """Parse boolean-ish multipart form values."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@app.get("/graduation/status")
def graduation_status() -> dict:
    """Return graduation center readiness and privacy policy details."""
    return graduation_service.status()


@app.post("/graduation/transcript/parse")
async def graduation_transcript_parse(request: Request) -> dict:
    """Parse an uploaded transcript PDF into a sanitized summary."""
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="python-multipart 패키지가 필요합니다.") from exc

    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="file 필드에 PDF 성적증명서를 업로드해 주세요.")
    filename = str(getattr(upload, "filename", "") or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    content = await upload.read()
    response = graduation_service.parse_transcript_upload(
        content,
        filename,
        vision_ocr_consent=_truthy_form_value(form.get("vision_ocr_consent")),
    )
    if response.get("status") == "failed":
        raise HTTPException(status_code=400, detail=response.get("message", "성적증명서 파싱에 실패했습니다."))
    return response


@app.post("/graduation/audit")
def graduation_audit(request: GraduationAnalysisRequest) -> dict:
    """Run transcript-based graduation audit."""
    return _graduation_analysis_response("audit", request.transcript)


@app.post("/graduation/substitute-courses")
def graduation_substitute_courses(request: SubstituteCoursesRequest) -> dict:
    """Find substitute course options from sanitized transcript summary."""
    return _graduation_analysis_response("substitute_courses", request.transcript, {"course_name": request.course_name})


@app.post("/graduation/micro-degree")
def graduation_micro_degree(request: GraduationAnalysisRequest) -> dict:
    """Analyze micro-degree opportunities."""
    return _graduation_analysis_response("micro_degree", request.transcript)


@app.post("/graduation/post-graduation-checklist")
def graduation_post_graduation_checklist(request: GraduationAnalysisRequest) -> dict:
    """Generate post-graduation administrative checklist."""
    return _graduation_analysis_response("post_graduation_checklist", request.transcript)


@app.post("/graduation/career-translator")
def graduation_career_translator(request: CareerTranslatorRequest) -> dict:
    """Translate completed courses into job competency language."""
    return _graduation_analysis_response("career_translator", request.transcript, {"target_job": request.target_job})


@app.post("/graduation/early-graduation")
def graduation_early_graduation(request: EarlyGraduationRequest) -> dict:
    """Check early graduation eligibility and cautions."""
    extra = {
        "registered_semesters": request.registered_semesters,
        "is_five_year_architecture": request.is_five_year_architecture,
        "has_transfer_or_readmission": request.has_transfer_or_readmission,
        "has_academic_warning": request.has_academic_warning,
        "has_repeated_semester": request.has_repeated_semester,
        "has_grade_waiver_history": request.has_grade_waiver_history,
        "has_disciplinary_record": request.has_disciplinary_record,
    }
    return _graduation_analysis_response("early_graduation", request.transcript, extra)


@app.post("/graduation/customized-major")
def graduation_customized_major(request: CustomizedMajorRequest) -> dict:
    """Guide Customized major recognition checks."""
    return _graduation_analysis_response(
        "customized_major",
        request.transcript,
        {"desired_field": request.desired_field, "target_recognition": request.target_recognition},
    )


@app.post("/graduation/credit-drop")
def graduation_credit_drop(request: CreditDropRequest) -> dict:
    """Guide credit-drop / grade-waiver policy checks."""
    return _graduation_analysis_response("credit_drop", request.transcript, {"concern": request.concern})


# --- 졸업센터 v2 (Bounded Audit Agent) — 엑셀 수강내역 기반, Chroma 비의존 ---

@app.get("/graduation/v2/status")
def graduation_v2_status() -> dict:
    """v2 준비 상태 (프로그램 목록·LLM 키 유무). Chroma와 무관."""
    import os
    from graduation_center.v2.catalog import program_total_min, regular_term_cap
    progs = load_programs()
    # 학사규정 제32조 학기당 이수학점 상한을 프로그램별로 미리 계산해 노출(프론트 기본값).
    for pid, p in progs.items():
        total = program_total_min(pid)
        p["total_credits_min"] = total
        p["max_credits_per_term"] = regular_term_cap(total) if total else None
    # 전체 학과 목록(다전공·부전공 선택 UI용 검색 목록). 데모 분석 지원은 convergence 프로그램만.
    departments = []
    try:
        import json as _json
        from pathlib import Path as _Path
        dept = _json.loads(_Path("data/graduation/graduation_requirements.json").read_text(encoding="utf-8"))["departments"]
        seen = set()
        for v in dept.values():
            nm = v.get("학과_전공명") or ""
            if nm and nm not in seen:
                seen.add(nm); departments.append({"name": nm, "college": v.get("대학", "")})
        departments.sort(key=lambda d: (d["college"], d["name"]))
    except Exception:
        pass
    return {
        "programs": progs,
        "departments": departments,
        "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "note": "엑셀 수강내역 업로드 기반. 진단·로드맵·리스크는 결정론(키 불필요), LLM은 요람 Q&A 근거 답변에만 사용.",
    }


@app.post("/graduation/v2/verify")
async def graduation_v2_verify(request: Request) -> dict:
    """수강내역 엑셀(여러 학기) → 매칭 → 편집 가능한 검증 테이블(HITL)."""
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="python-multipart 패키지가 필요합니다.") from exc
    uploads = form.getlist("files") or ([form.get("file")] if form.get("file") else [])
    files: list[tuple[bytes, str]] = []
    for up in uploads:
        if up is None or not hasattr(up, "read"):
            continue
        fn = str(getattr(up, "filename", "") or "")
        if not fn.lower().endswith((".xls", ".xlsx")):
            raise HTTPException(status_code=400, detail=f"엑셀(.xls/.xlsx)만 업로드할 수 있습니다: {fn}")
        content = await up.read()
        try:
            missing = v2_fail_fast_columns(content, fn)
        except Exception as exc:  # 손상/위장 엑셀(xlrd·openpyxl 파싱 실패) → 422
            raise HTTPException(status_code=422, detail={"file": fn, "error": "엑셀 파일을 읽을 수 없습니다(손상 또는 지원하지 않는 형식)."}) from exc
        if missing:
            raise HTTPException(status_code=422, detail={"file": fn, "missing_columns": missing})
        files.append((content, fn))
    if not files:
        raise HTTPException(status_code=400, detail="files 필드에 수강내역 엑셀을 1개 이상 업로드해 주세요.")
    context_raw = form.get("context")
    try:
        context = json.loads(context_raw) if context_raw else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="context 필드가 유효한 JSON이 아닙니다.") from exc
    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context 필드는 JSON 객체여야 합니다.")
    if "program_id" not in context:
        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다 (예: ai_bigdata, mirae_mobility).")
    # 연계·융합전공은 verify 단계부터 차단 — audit에서만 막으면 첫 단계가 성공해 흐름이 끊김
    prog = load_programs().get(context["program_id"])
    if prog is not None and prog.get("track_type") != "primary":
        raise HTTPException(status_code=400,
                            detail=f"'{context['program_id']}'는 제1전공으로 선택할 수 없습니다(연계·융합전공은 다전공/부전공으로 추가).")
    try:
        return v2_pipeline.run_verify(files, context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc


@app.post("/graduation/v2/audit")
def graduation_v2_audit(payload: dict) -> dict:
    """사용자 확정 테이블 → 진단 → 로드맵(결정론 배치+검증) → 리스크 → 컨설팅 응답."""
    ctx = payload.get("context")
    if not isinstance(ctx, dict) or "program_id" not in ctx:
        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다.")
    try:
        return v2_pipeline.run_audit(payload).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc


@app.post("/graduation/v2/whatif")
def graduation_v2_whatif(payload: dict) -> dict:
    """졸업 시나리오 상담 Agent — 자연어 질문 → 매개변수 추출(LLM) → 조건 가드 →
    졸업사정 재실행(결정론, before/after) → 비교·다음 행동. 해석·재실행 실패는
    500이 아니라 status="unsupported"로 degrade(데모 중 에러 화면 금지)."""
    ctx = payload.get("context")
    if not isinstance(ctx, dict) or "program_id" not in ctx:
        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다.")
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 이 필요합니다 (1~200자).")
    if len(question) > 200:
        raise HTTPException(status_code=400, detail="question 은 200자 이내여야 합니다.")
    try:
        return v2_whatif.run_whatif(payload).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc
