"""FastAPI server for KMU Campus Life Action Agent."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agent.action_state import continue_action, start_action
from agent.answer_builder import build_final_answer
from agent.citation import build_citations
from tools.menu_parser import is_menu_chunk, is_menu_query
from agent.answer_validator import validate_answer_contract, validate_output_privacy
from agent.classifier import classify_issue
from agent.guard import inspect_privacy, require_sources
from agent.intent_scope import (
    build_out_of_scope_answer,
    detect_out_of_scope,
    suggested_questions,
)
from agent.planner import suggest_actions
from agent.student_playbook import detect_student_terms
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
from graduation_center.v2.catalog import load_programs
from graduation_center.v2.excel_parser import fail_fast_columns as v2_fail_fast_columns
from ingestion.live_refresh import refresh_sources_for_issue
from ingestion.pipeline import CRAWLERS, load_state, run_ingestion
from llm_client import GuardedLLMClient
from retriever.hybrid_retriever import HybridRetriever


class AskRequest(BaseModel):
    """Request body for a user question."""

    question: str = Field(..., min_length=1)
    student_context: dict[str, Any] = Field(default_factory=dict)
    llm_assist: bool = True
    live_check: bool = False


class ActionStartRequest(BaseModel):
    """Request body for starting a follow-up action."""

    action_id: str


class ActionContinueRequest(BaseModel):
    """Request body for continuing a follow-up action."""

    action_id: str
    slots: dict[str, Any] = Field(default_factory=dict)
    live_check: bool = False
    query: str = ""


class IngestRequest(BaseModel):
    """Request body for an ingestion run."""

    source: str = "seed"
    limit: int = 20
    force_rebuild: bool = False


class LiveRefreshRequest(BaseModel):
    """Request body for issue-scoped live refresh."""

    issue_type: str = Field(..., min_length=1)
    query: str = ""
    max_pages: int = Field(default=3, ge=1, le=5)


app = FastAPI(title="KMU Campus Life Action Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_local_environment() -> None:
    """Load local environment files without overriding shell-provided values."""
    for env_path in (Path(".env"), Path("test/.env")):
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)


_load_local_environment()

retriever = HybridRetriever()
llm_client = GuardedLLMClient()
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
        "message": "KMU Campus Life Action Agent API",
        "frontend": "Run `cd frontend && npm install && npm run dev`, then open http://127.0.0.1:5173",
    }


@app.get("/health")
def health() -> dict:
    """Return service health and optional vector-store availability."""
    status = retriever.status()
    state = load_state()
    return {
        "status": "ok",
        "keyword_chunks": status["keyword_chunks"],
        "vector_retriever_available": status["vector_available"],
        "vector_indexed_count": status["vector_indexed_count"],
        "vector_error": status["vector_error"],
        "llm": llm_client.status(),
        "graduation_center": graduation_service.status(),
        "last_ingest": state.get("last_ingest"),
        "live_refresh": _summarize_live_refresh_state(state),
        "agent_metrics": _summarize_agent_usage(),
    }


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


_EMPTY_ANSWER_VALIDATION = {"ok": True, "flags": [], "markers": [], "citation_ids": []}
_EMPTY_OUTPUT_PRIVACY = {"ok": True, "flags": []}
_ACTION_LLM_DEFAULT = {"used": False, "reason": "not_applicable"}

# B6 (§20): per-/ask operational telemetry. Mirrors llm_client._record_usage —
# no raw question/answer/slots are ever written, and file IO fails silently so a
# logging problem never breaks an answer.
AGENT_USAGE_LOG_PATH = Path("data/state/agent_usage.jsonl")


def _llm_usage_flags(llm_metadata: dict) -> dict:
    """Derive boolean LLM-assist flags from /ask llm metadata for usage logging."""
    qe = llm_metadata.get("query_expansion", {}) or {}
    rr = llm_metadata.get("rerank", {}) or {}
    pol = llm_metadata.get("polish", {}) or {}
    return {
        "llm_query_expansion_used": bool(qe.get("used")),
        "llm_rerank_used": bool(rr.get("used")),
        "llm_polish_used": bool(pol.get("used")),
        "llm_fallback": bool(
            qe.get("error") or rr.get("error") or pol.get("error") or pol.get("rejected_reason")
        ),
    }


def _record_agent_usage(record: dict) -> None:
    """Append one /ask telemetry line (no raw text) — silent on any failure."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "route": "/ask", **record}
    try:
        AGENT_USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AGENT_USAGE_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_recent_agent_usage(limit: int = 1000) -> list[dict]:
    """Return up to the last ``limit`` usage records; tolerate missing/corrupt lines."""
    try:
        with AGENT_USAGE_LOG_PATH.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return []
    records: list[dict] = []
    for raw in lines[-limit:]:
        text = raw.strip()
        if not text:
            continue
        try:
            records.append(json.loads(text))
        except Exception:
            continue
    return records


def _summarize_agent_usage(limit: int = 1000) -> dict:
    """Aggregate recent /ask telemetry into operational rates for /health (B6 §20)."""
    records = _read_recent_agent_usage(limit)
    count = len(records)
    summary = {
        "count": count,
        "window": limit,
        "privacy_block_rate": 0.0,
        "no_source_rate": 0.0,
        "citation_validation_fail_rate": 0.0,
        "output_privacy_fail_rate": 0.0,
        "live_check_success_rate": 0.0,
        "llm_fallback_rate": 0.0,
        "avg_latency_ms": 0.0,
    }
    if not count:
        return summary

    def _rate(predicate) -> float:
        return round(sum(1 for r in records if predicate(r)) / count, 4)

    summary["privacy_block_rate"] = _rate(lambda r: bool(r.get("privacy_blocked")))
    summary["no_source_rate"] = _rate(lambda r: bool(r.get("no_source")))
    summary["citation_validation_fail_rate"] = _rate(lambda r: r.get("citation_validation_ok") is False)
    summary["output_privacy_fail_rate"] = _rate(lambda r: r.get("output_privacy_ok") is False)
    summary["llm_fallback_rate"] = _rate(lambda r: bool(r.get("llm_fallback")))

    # Success rate is measured only over attempts so non-live answers don't dilute it.
    attempts = [r for r in records if r.get("live_check_attempted")]
    if attempts:
        succeeded = sum(1 for r in attempts if r.get("live_check_success"))
        summary["live_check_success_rate"] = round(succeeded / len(attempts), 4)

    latencies = [r.get("latency_ms") for r in records if isinstance(r.get("latency_ms"), (int, float))]
    if latencies:
        summary["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
    return summary


def _action_response(result: dict, **overrides: Any) -> dict:
    """Merge action-specific fields onto the A1 common-field contract.

    Every /actions/continue return path goes through here so the response shape
    matches /ask: action-specific keys (status/message/document/checklist/
    missing_slots/...) are preserved, and any missing common field is filled with
    a safe default. Overrides set to None are ignored so callers only pass the
    fields they actually computed.
    """
    response: dict[str, Any] = {
        "answer": "",
        "issue_type": "",
        "classification": {"issue_type": "", "confidence": 0.0, "scores": {}},
        "tool_logs": [],
        "sources": [],
        "citations": [],
        "next_actions": [],
        "safety_flags": [],
        "answer_validation": dict(_EMPTY_ANSWER_VALIDATION),
        "output_privacy": dict(_EMPTY_OUTPUT_PRIVACY),
        "llm": dict(_ACTION_LLM_DEFAULT),
        "live_check": {"attempted": False, "requested": False},
    }
    response.update(result)
    response.update({key: value for key, value in overrides.items() if value is not None})
    return response


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    """Answer a campus-life question with grounded sources and next actions."""
    start = time.perf_counter()
    tool_logs: list[str] = []
    privacy = inspect_privacy(request.question)
    tool_logs.append("guard.inspect_privacy 호출됨")
    if privacy.blocked:
        _record_agent_usage(
            {
                "issue_type": "privacy_blocked",
                "status": "privacy_blocked",
                "safety_flags": privacy.flags,
                "chunk_count": 0,
                "citation_count": 0,
                "privacy_blocked": True,
                "no_source": False,
                "output_privacy_ok": True,
                "citation_validation_ok": True,
                "live_check_attempted": False,
                "live_check_success": False,
                "llm_query_expansion_used": False,
                "llm_rerank_used": False,
                "llm_polish_used": False,
                "llm_fallback": False,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
        return {
            "answer": privacy.message,
            "issue_type": "privacy_blocked",
            "classification": {"issue_type": "privacy_blocked", "confidence": 0.0, "scores": {}},
            "tool_logs": tool_logs,
            "sources": [],
            "citations": [],
            "next_actions": [],
            "safety_flags": privacy.flags,
            "answer_validation": dict(_EMPTY_ANSWER_VALIDATION),
            "output_privacy": dict(_EMPTY_OUTPUT_PRIVACY),
            "llm": {"used": False, "reason": "privacy_blocked"},
            "live_check": {"attempted": False, "reason": "privacy_blocked"},
        }

    classification = classify_issue(request.question)
    issue_type = classification["issue_type"]
    tool_logs.append("classify_issue 호출됨")

    scope = detect_out_of_scope(request.question)
    tool_logs.append("intent_scope.detect_out_of_scope 호출됨")
    if scope["out_of_scope"]:
        suggestions = suggested_questions()
        _record_agent_usage(
            {
                "issue_type": "out_of_scope",
                "status": "out_of_scope",
                "safety_flags": ["out_of_scope"],
                "chunk_count": 0,
                "citation_count": 0,
                "privacy_blocked": False,
                "no_source": False,
                "output_privacy_ok": True,
                "citation_validation_ok": True,
                "live_check_attempted": False,
                "live_check_success": False,
                "llm_query_expansion_used": False,
                "llm_rerank_used": False,
                "llm_polish_used": False,
                "llm_fallback": False,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
        return {
            "answer": build_out_of_scope_answer(scope["category"], suggestions),
            "issue_type": "out_of_scope",
            "classification": {
                "issue_type": "out_of_scope",
                "confidence": 1.0,
                "scores": classification.get("scores", {}),
            },
            "tool_logs": tool_logs,
            "sources": [],
            "citations": [],
            "next_actions": [],
            "safety_flags": ["out_of_scope"],
            "answer_validation": dict(_EMPTY_ANSWER_VALIDATION),
            "output_privacy": dict(_EMPTY_OUTPUT_PRIVACY),
            "llm": {"used": False, "reason": "out_of_scope"},
            "live_check": {"attempted": False, "reason": "out_of_scope"},
            "scope": {
                "out_of_scope": True,
                "category": scope["category"],
                "matched_terms": scope["matched_terms"],
                "suggested_questions": suggestions,
            },
        }

    search_query = _augment_query_with_context(request.question, request.student_context)
    llm_metadata: dict[str, Any] = {
        "enabled": llm_client.enabled,
        "polish_enabled": llm_client.polish_enabled,
        "assist_requested": request.llm_assist,
        "query_expansion": {"used": False, "expanded_query": search_query, "keywords": [], "error": None},
        "rerank": {"used": False, "selected_chunk_ids": [], "error": None},
        "polish": {"used": False, "error": None, "rejected_reason": None},
    }
    live_check_result: dict[str, Any] = {"attempted": False, "requested": request.live_check}
    if request.llm_assist and llm_client.enabled:
        expansion = llm_client.expand_search_query(search_query, issue_type, request.student_context)
        llm_metadata["query_expansion"] = expansion
        if expansion.get("used"):
            search_query = expansion["expanded_query"]
            tool_logs.append("llm.expand_search_query 호출됨")
        else:
            tool_logs.append("llm.expand_search_query fallback됨")

    if request.live_check:
        live_check_result = refresh_sources_for_issue(
            issue_type,
            query=search_query,
            vector_retriever=retriever.vector,
        )
        if live_check_result.get("updated"):
            retriever.reload()
        tool_logs.append("live_refresh.official_sources 호출됨")

    chunks = retriever.search(search_query, issue_type=issue_type, limit=8)
    chunks = _prefer_issue_matched_chunks(chunks, issue_type, search_query)
    if issue_type == "campus_facility" and is_menu_query(search_query):
        chunks = _merge_menu_doc_fragments(chunks, search_query)
    tool_logs.append("search_official_sources 호출됨")

    if request.llm_assist and llm_client.enabled and chunks:
        chunks, rerank = llm_client.rerank_chunks(request.question, issue_type, chunks, limit=6)
        llm_metadata["rerank"] = rerank
        if rerank.get("used"):
            tool_logs.append("llm.rerank_chunks 호출됨")
        else:
            tool_logs.append("llm.rerank_chunks fallback됨")

    source_guard = require_sources(chunks)
    tool_logs.append("guard.require_sources 호출됨")
    if source_guard.blocked:
        _record_agent_usage(
            {
                "issue_type": issue_type,
                "status": "no_source",
                "safety_flags": source_guard.flags,
                "chunk_count": 0,
                "citation_count": 0,
                "privacy_blocked": False,
                "no_source": True,
                "output_privacy_ok": True,
                "citation_validation_ok": True,
                "live_check_attempted": bool(live_check_result.get("attempted")),
                "live_check_success": bool(live_check_result.get("network_success", 0) > 0),
                **_llm_usage_flags(llm_metadata),
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
        return {
            "answer": (
                f"{source_guard.message}\n"
                "국민대학교 공식 포털, 관련 부서, 학과사무실 또는 담당 교강사에게 확인해 주세요."
            ),
            "issue_type": issue_type,
            "classification": classification,
            "tool_logs": tool_logs,
            "sources": [],
            "citations": [],
            "next_actions": [],
            "safety_flags": source_guard.flags,
            "answer_validation": dict(_EMPTY_ANSWER_VALIDATION),
            "output_privacy": dict(_EMPTY_OUTPUT_PRIVACY),
            "llm": llm_metadata,
            "live_check": live_check_result,
        }

    actions = suggest_actions(issue_type, chunks)
    tool_logs.append("suggest_actions 호출됨")
    built = build_final_answer(
        request.question,
        issue_type,
        chunks,
        actions,
        request.student_context,
        live_check_result=live_check_result,
    )
    tool_logs.extend(["generate_checklist 호출됨", "route_contact 호출됨", "build_final_answer 호출됨"])
    answer = built["answer"]
    if request.llm_assist and llm_client.polish_enabled:
        polish = llm_client.polish_answer(answer)
        llm_metadata["polish"] = {
            "used": polish.get("used", False),
            "error": polish.get("error"),
            "rejected_reason": polish.get("rejected_reason"),
        }
        if polish.get("used"):
            answer = polish["answer"]
            tool_logs.append("llm.polish_answer 호출됨")
        else:
            tool_logs.append("llm.polish_answer fallback됨")

    answer_validation = validate_answer_contract(answer, built["citations"])
    output_privacy = validate_output_privacy(answer)
    if (not answer_validation["ok"] or not output_privacy["ok"]) and answer != built["answer"]:
        answer = built["answer"]
        answer_validation = validate_answer_contract(answer, built["citations"])
        output_privacy = validate_output_privacy(answer)
        llm_metadata["polish"]["used"] = False
        llm_metadata["polish"]["rejected_reason"] = "final_output_guard_failed"
        tool_logs.append("guard.final_output_guard fallback됨")
    else:
        tool_logs.append("guard.final_output_guard 호출됨")

    final_safety_flags = [*answer_validation["flags"], *output_privacy["flags"]]

    _record_agent_usage(
        {
            "issue_type": issue_type,
            "status": "answered",
            "safety_flags": final_safety_flags,
            "chunk_count": len(chunks),
            "citation_count": len(built["citations"]),
            "privacy_blocked": False,
            "no_source": False,
            "output_privacy_ok": bool(output_privacy["ok"]),
            "citation_validation_ok": bool(answer_validation["ok"]),
            "live_check_attempted": bool(live_check_result.get("attempted")),
            "live_check_success": bool(live_check_result.get("network_success", 0) > 0),
            **_llm_usage_flags(llm_metadata),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    )

    return {
        "answer": answer,
        "issue_type": issue_type,
        "classification": classification,
        "tool_logs": tool_logs,
        "sources": chunks,
        "citations": built["citations"],
        "next_actions": actions,
        "safety_flags": final_safety_flags,
        "answer_validation": answer_validation,
        "output_privacy": output_privacy,
        "llm": llm_metadata,
        "live_check": live_check_result,
    }


@app.post("/actions/start")
def action_start(request: ActionStartRequest) -> dict:
    """Start a document/action drafting flow."""
    return start_action(request.action_id)


@app.post("/actions/continue")
def action_continue(request: ActionContinueRequest) -> dict:
    """Continue a document/action drafting flow with user-provided non-sensitive slots."""
    tool_logs: list[str] = []
    privacy_text = " ".join(str(value) for value in request.slots.values())
    privacy = inspect_privacy(privacy_text)
    tool_logs.append("guard.inspect_privacy 호출됨")
    if privacy.blocked:
        return _action_response(
            {"status": "blocked", "message": privacy.message},
            tool_logs=tool_logs,
            safety_flags=privacy.flags,
            live_check={"attempted": False, "requested": request.live_check},
        )
    from tools.document_drafter import action_grounding, action_issue_type, action_label

    issue_type = action_issue_type(request.action_id)
    tool_logs.append(f"document_drafter.action_issue_type → {issue_type}")
    classification = {"issue_type": issue_type, "confidence": 1.0, "scores": {}}
    grounding = action_grounding(request.action_id)
    # B3: enrich the grounding search beyond the bare action_id so official source
    # chunks are more likely to surface (original query + human label + issue type).
    search_terms = " ".join(
        filter(None, [request.query, action_label(request.action_id), issue_type])
    ).strip() or request.action_id
    action_live_check: dict[str, Any] = {"attempted": False, "requested": request.live_check}
    if request.live_check:
        action_live_check = refresh_sources_for_issue(
            issue_type,
            query=request.query or request.action_id,
            vector_retriever=retriever.vector,
        )
        tool_logs.append("live_refresh.refresh_sources_for_issue 호출됨")
        if action_live_check.get("updated"):
            retriever.reload()
    chunks = retriever.search(search_terms, issue_type=issue_type, limit=4)
    chunks = _prefer_issue_matched_chunks(chunks, issue_type, search_terms)
    tool_logs.append(f"retriever.search 호출됨 (chunks={len(chunks)})")
    _, action_citations = build_citations(chunks)
    result = continue_action(request.action_id, request.slots, chunks)
    tool_logs.append(f"action_state.continue_action 호출됨 (status={result.get('status')})")
    if result.get("status") != "completed":
        return _action_response(
            result,
            tool_logs=tool_logs,
            issue_type=issue_type,
            classification=classification,
            sources=chunks,
            citations=action_citations,
            live_check=action_live_check,
            grounding=grounding,
        )

    # B3 (§11.4·§12.4): an action whose policy demands an official source must not
    # return a finished draft when retrieval found nothing to ground it on.
    if grounding == "official_chunk_required" and not chunks:
        tool_logs.append("grounding.official_chunk_required → 공식 근거 없음으로 차단")
        return _action_response(
            {
                "status": "blocked",
                "action_id": request.action_id,
                "message": "관련 공식 근거 문서를 찾지 못해 초안을 생성하지 않았습니다. 질문을 더 구체적으로 적거나 live_check를 사용해 최신 공식 자료를 받아 주세요.",
                "grounding": grounding,
            },
            tool_logs=tool_logs,
            issue_type=issue_type,
            classification=classification,
            sources=[],
            citations=[],
            safety_flags=["no_official_source"],
            live_check=action_live_check,
        )

    output_text = " ".join(
        [
            str(result.get("document", "")),
            " ".join(str(item) for item in result.get("checklist", []) or []),
        ]
    )
    output_privacy = validate_output_privacy(output_text)
    tool_logs.append("answer_validator.validate_output_privacy 호출됨")
    if not output_privacy["ok"]:
        return _action_response(
            {
                "status": "blocked",
                "message": "초안에 민감정보 값이 포함될 가능성이 있어 반환하지 않았습니다. 개인정보를 제거한 뒤 다시 시도해 주세요.",
            },
            tool_logs=tool_logs,
            issue_type=issue_type,
            classification=classification,
            sources=chunks,
            citations=action_citations,
            safety_flags=output_privacy["flags"],
            output_privacy=output_privacy,
            live_check=action_live_check,
            grounding=grounding,
        )
    return _action_response(
        result,
        tool_logs=tool_logs,
        issue_type=issue_type,
        classification=classification,
        sources=chunks,
        citations=action_citations,
        output_privacy=output_privacy,
        live_check=action_live_check,
        grounding=grounding,
    )


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


def _merge_menu_doc_fragments(chunks: list[dict], query: str) -> list[dict]:
    """Give the menu chunk the full menu text for 학식/메뉴 questions.

    The 오늘의 메뉴 page is stored as many chunks sharing one doc_id, but
    `_unique_chunks_by_doc_id` collapses them to a single (often nav-only) fragment
    before answer assembly — so menu_parser only sees part of the menu, or none.
    Here we concatenate every fragment of that doc (from the full index) into the one
    retrieved menu chunk so the parser sees the complete menu. Citations stay clean
    (still one menu source). No new facts are introduced — all fragments are the same
    official page already in the index.
    """
    all_sources = retriever.all_sources()
    # 메뉴 텍스트를 품은 doc(생활관/도서관/오늘의 메뉴는 한 doc_id에 섞임)을 식별한다.
    # 검색이 같은 doc의 비-메뉴 조각(예: 도서관 안내)만 물어왔어도 doc_id로 잡아낸다.
    menu_doc_ids = {chunk.get("doc_id") for chunk in all_sources if is_menu_chunk(chunk) and chunk.get("doc_id")}
    if not menu_doc_ids:
        return chunks
    target_idx = next((i for i, chunk in enumerate(chunks) if chunk.get("doc_id") in menu_doc_ids), None)
    if target_idx is None:
        return chunks
    doc_id = chunks[target_idx].get("doc_id")
    fragments = [chunk for chunk in all_sources if chunk.get("doc_id") == doc_id]
    if len(fragments) <= 1:
        return chunks
    merged_text = "\n".join(fragment.get("text") or "" for fragment in fragments)
    merged_chunk = {**chunks[target_idx], "text": merged_text}
    new_chunks = list(chunks)
    new_chunks[target_idx] = merged_chunk
    return new_chunks


def _prefer_issue_matched_chunks(chunks: list[dict], issue_type: str | None, query: str = "") -> list[dict]:
    """Prefer official chunks explicitly tagged for the classified issue."""
    if not issue_type or issue_type == "other":
        return chunks
    matched = [chunk for chunk in chunks if issue_type in (chunk.get("issue_types") or [])]
    fallback_chunks = _curated_fallback_chunks(issue_type, query=query)
    if issue_type == "schedule":
        return _sort_schedule_chunks(_unique_chunks_by_doc_id([*matched, *fallback_chunks])) or chunks
    if matched:
        return _unique_chunks_by_doc_id(_sort_chunks_by_query([*matched, *fallback_chunks], query))[:4]
    return fallback_chunks or chunks


def _augment_query_with_context(question: str, student_context: dict | None) -> str:
    """Add non-sensitive context terms to retrieval without changing user wording."""
    terms = [question]
    for key in ("term", "concern"):
        value = str((student_context or {}).get(key, "")).strip()
        if value and value not in question:
            terms.append(value)
    return " ".join(terms)


def _curated_fallback_chunks(issue_type: str, query: str = "", limit: int = 4) -> list[dict]:
    """Use official URL-bound fallback pages before an ingest run has indexed them."""
    chunks: list[dict] = []
    for crawler_name, crawler_cls in CRAWLERS.items():
        for page in crawler_cls.pages:
            if issue_type not in page.issue_types:
                continue
            if issue_type == "schedule" and not page.schedule:
                continue
            chunks.append(
                {
                    "chunk_id": f"curated_{page.doc_id}",
                    "doc_id": page.doc_id,
                    "source_tier": page.source_tier or crawler_cls.source_tier,
                    "source_type": crawler_name,
                    "title": page.title,
                    "url": page.url,
                    "text": page.fallback_text,
                    "department": page.department,
                    "keywords": page.keywords,
                    "search_hints": page.search_hints,
                    "issue_types": page.issue_types,
                    "application_path": page.application_path,
                    "required_documents": page.required_documents,
                    "submit_to": page.submit_to,
                    "contacts": page.contacts,
                    "schedule": page.schedule,
                    "deadline_rule": page.deadline_rule,
                    "actions": page.actions,
                    "published_at": page.published_at,
                    "used_fallback": True,
                    "fetched_from_network": False,
                }
            )
    if query:
        scored_chunks = [(chunk, _query_relevance_score(chunk, query)) for chunk in chunks]
        if any(score > 0 for _, score in scored_chunks):
            chunks = [chunk for chunk, score in scored_chunks if score > 0]
    chunks = _sort_chunks_by_query(chunks, query)
    return [_compact_chunk(chunk) for chunk in chunks[:limit]]


def _sort_chunks_by_query(chunks: list[dict], query: str) -> list[dict]:
    return sorted(
        chunks,
        key=lambda chunk: (
            -_query_relevance_score(chunk, query),
            int(chunk.get("source_tier", 9)),
            str(chunk.get("title", "")),
        ),
    )


def _query_relevance_score(chunk: dict, query: str) -> int:
    normalized = (query or "").lower()
    expanded_terms = [normalized, *[term.lower() for term in detect_student_terms(query)]]
    haystacks = [
        str(chunk.get("title", "")).lower(),
        str(chunk.get("text", "")).lower(),
        " ".join(str(item).lower() for item in chunk.get("keywords", []) or []),
        " ".join(str(item).lower() for item in chunk.get("search_hints", []) or []),
    ]
    score = 0
    for term in expanded_terms:
        if not term:
            continue
        for haystack in haystacks:
            if term in haystack or any(len(piece) >= 2 and piece in haystack for piece in term.split()):
                score += 1
    for keyword in chunk.get("keywords", []) or []:
        if str(keyword).lower() in normalized:
            score += 3
    return score


def _compact_chunk(chunk: dict) -> dict:
    return {key: value for key, value in chunk.items() if value not in (None, [], {})}


def _unique_chunks_by_doc_id(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for chunk in chunks:
        key = chunk.get("doc_id") or chunk.get("chunk_id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def _sort_schedule_chunks(chunks: list[dict]) -> list[dict]:
    def sort_key(chunk: dict) -> tuple[str, str]:
        schedule = chunk.get("schedule") or {}
        return (str(schedule.get("start_date", "9999-12-31")), str(chunk.get("title", "")))

    return sorted(chunks, key=sort_key)


def _summarize_live_refresh_state(state: dict[str, Any]) -> dict[str, Any]:
    """Summarize last per-issue live refreshes for admin health output."""
    entries = []
    for issue_type, record in (state.get("last_live_refresh") or {}).items():
        fetch_summary = record.get("fetch_summary") or {}
        entries.append(
            {
                "issue_type": issue_type,
                "completed_at": record.get("completed_at"),
                "documents_seen": record.get("documents_seen", 0),
                "updated_documents": record.get("updated_documents", 0),
                "network_success": fetch_summary.get("network_success", 0),
                "fallback_used": fetch_summary.get("fallback_used", 0),
                "network_failed": fetch_summary.get("network_failed", 0),
                "failures": record.get("failures", []),
            }
        )
    entries.sort(key=lambda item: str(item.get("completed_at") or ""), reverse=True)
    return {
        "count": len(entries),
        "latest": entries[0] if entries else None,
        "recent": entries[:5],
    }


@app.post("/ingest/run")
def ingest_run(request: IngestRequest) -> dict:
    """Run official-source ingestion and vector indexing."""
    result = run_ingestion(
        source=request.source,
        limit=request.limit,
        force_rebuild=request.force_rebuild,
        vector_retriever=retriever.vector,
    )
    retriever.reload()
    return result


@app.post("/ingest/live-refresh")
def ingest_live_refresh(request: LiveRefreshRequest) -> dict:
    """Run issue-scoped official-source live refresh for admin use."""
    result = refresh_sources_for_issue(
        request.issue_type,
        query=request.query or request.issue_type,
        max_pages=request.max_pages,
        vector_retriever=retriever.vector,
    )
    if result.get("updated"):
        retriever.reload()
    return result


@app.get("/sources")
def sources() -> dict:
    """List available official source chunks."""
    chunks = retriever.all_sources()
    return {"count": len(chunks), "sources": chunks}
