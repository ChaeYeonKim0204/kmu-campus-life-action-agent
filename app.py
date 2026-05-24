"""FastAPI server for KMU Campus Life Action Agent."""

from __future__ import annotations

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
from agent.answer_validator import validate_answer_contract, validate_output_privacy
from agent.classifier import classify_issue
from agent.guard import inspect_privacy, require_sources
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


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    """Answer a campus-life question with grounded sources and next actions."""
    tool_logs: list[str] = []
    privacy = inspect_privacy(request.question)
    tool_logs.append("guard.inspect_privacy 호출됨")
    if privacy.blocked:
        return {
            "answer": privacy.message,
            "issue_type": "privacy_blocked",
            "tool_logs": tool_logs,
            "sources": [],
            "citations": [],
            "next_actions": [],
            "safety_flags": privacy.flags,
            "llm": {"used": False, "reason": "privacy_blocked"},
            "live_check": {"attempted": False, "reason": "privacy_blocked"},
        }

    classification = classify_issue(request.question)
    issue_type = classification["issue_type"]
    tool_logs.append("classify_issue 호출됨")

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
        return {
            "answer": (
                f"{source_guard.message}\n"
                "국민대학교 공식 포털, 관련 부서, 학과사무실 또는 담당 교강사에게 확인해 주세요."
            ),
            "issue_type": issue_type,
            "tool_logs": tool_logs,
            "sources": [],
            "citations": [],
            "next_actions": [],
            "safety_flags": source_guard.flags,
            "llm": llm_metadata,
            "live_check": live_check_result,
        }

    actions = suggest_actions(issue_type, chunks)
    tool_logs.append("suggest_actions 호출됨")
    built = build_final_answer(request.question, issue_type, chunks, actions, request.student_context)
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
    privacy_text = " ".join(str(value) for value in request.slots.values())
    privacy = inspect_privacy(privacy_text)
    if privacy.blocked:
        return {
            "status": "blocked",
            "message": privacy.message,
            "safety_flags": privacy.flags,
        }
    from tools.document_drafter import action_issue_type

    issue_type = action_issue_type(request.action_id)
    action_live_check: dict[str, Any] = {"attempted": False, "requested": request.live_check}
    if request.live_check:
        action_live_check = refresh_sources_for_issue(
            issue_type,
            query=request.action_id,
            vector_retriever=retriever.vector,
        )
        if action_live_check.get("updated"):
            retriever.reload()
    chunks = retriever.search(request.action_id, issue_type=issue_type, limit=4)
    chunks = _prefer_issue_matched_chunks(chunks, issue_type, request.action_id)
    result = continue_action(request.action_id, request.slots, chunks)
    if result.get("status") != "completed":
        return {**result, "live_check": action_live_check}

    output_text = " ".join(
        [
            str(result.get("document", "")),
            " ".join(str(item) for item in result.get("checklist", []) or []),
        ]
    )
    output_privacy = validate_output_privacy(output_text)
    if not output_privacy["ok"]:
        return {
            "status": "blocked",
            "message": "초안에 민감정보 값이 포함될 가능성이 있어 반환하지 않았습니다. 개인정보를 제거한 뒤 다시 시도해 주세요.",
            "safety_flags": output_privacy["flags"],
            "output_privacy": output_privacy,
            "live_check": action_live_check,
        }
    return {**result, "output_privacy": output_privacy, "live_check": action_live_check}


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
