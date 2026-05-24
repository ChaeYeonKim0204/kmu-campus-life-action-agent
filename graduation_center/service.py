"""Graduation center analysis service."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from graduation_center.data import compute_structured_check, load_graduation_data, policy_sources_for_task
from graduation_center.models import GraduationAnalysisResponse, TranscriptSummary
from graduation_center.parser import parse_transcript_bytes


class GraduationServiceUnavailable(RuntimeError):
    """Raised when graduation center prerequisites are missing."""


class GraduationCenterService:
    """Service integrating transcript parsing, 요람 RAG, and GPT analysis."""

    def __init__(self, data_dir: str = "data/graduation", chroma_dir: str = "data/graduation/chroma"):
        self.data_dir = Path(data_dir)
        self.chroma_dir = Path(chroma_dir)
        self.collection_name = "kmu_graduation_yoram"
        self.legacy_collection_name = "kookmin_yoram"
        self.embedding_model = "text-embedding-3-small"
        self.model = os.getenv("OPENAI_GRADUATION_MODEL", "gpt-4o")
        self._client = None
        self._collection = None

    def status(self) -> dict[str, Any]:
        """Return readiness state for the graduation center."""
        data = load_graduation_data(str(self.data_dir))
        api_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
        chroma_status = self._chroma_status()
        ready = api_key and not data["missing_files"] and chroma_status["available"]
        return {
            "ready": ready,
            "openai_api_key_configured": api_key,
            "model": self.model if api_key else None,
            "data_dir": str(self.data_dir),
            "missing_files": data["missing_files"],
            "chroma": chroma_status,
            "privacy": {
                "pdf_storage": "temporary_only",
                "returns_raw_text": False,
                "returns_gpa_value": False,
                "returns_course_grades": False,
            },
        }

    def parse_transcript_upload(self, content: bytes, filename: str, *, vision_ocr_consent: bool) -> dict[str, Any]:
        """Parse a transcript upload into a sanitized summary."""
        response = parse_transcript_bytes(
            content,
            filename,
            vision_ocr_consent=vision_ocr_consent,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            model=self.model,
        )
        return response.model_dump()

    def analyze(self, task: str, transcript: TranscriptSummary | dict, extra: dict[str, Any] | None = None) -> GraduationAnalysisResponse:
        """Run a GPT-backed graduation analysis task."""
        self._require_ready()
        transcript_model = transcript if isinstance(transcript, TranscriptSummary) else TranscriptSummary.model_validate(transcript)
        public_transcript = _public_transcript(transcript_model)
        safety_flags = _input_safety_flags(public_transcript, extra or {})
        if safety_flags:
            return GraduationAnalysisResponse(
                status="blocked",
                task=task,
                answer="민감정보가 포함될 수 있어 졸업 센터 분석을 실행하지 않았습니다.",
                safety_flags=safety_flags,
                warnings=["sensitive_input_blocked"],
            )

        data = load_graduation_data(str(self.data_dir))
        structured_check = compute_structured_check(public_transcript, data)
        sources = self._sources_for(task, public_transcript, structured_check, extra or {}, data)
        llm_payload = self._call_llm(task, public_transcript, structured_check, sources, extra or {})
        answer = _build_answer(task, llm_payload, sources)
        answer = _sanitize_sensitive_output(answer)
        return GraduationAnalysisResponse(
            status="completed",
            task=task,
            answer=answer,
            sources=sources,
            structured_check=structured_check,
            safety_flags=[],
            llm={"used": True, "model": self.model},
            warnings=list(transcript_model.warnings),
        )

    def _require_ready(self) -> None:
        status = self.status()
        if not status["ready"]:
            raise GraduationServiceUnavailable("graduation_center_not_ready")

    def _client_instance(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            raise GraduationServiceUnavailable("openai_package_not_installed") from exc
        self._client = OpenAI()
        return self._client

    def _collection_instance(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
        except Exception as exc:  # pragma: no cover - depends on optional runtime package
            raise GraduationServiceUnavailable("chromadb_package_not_installed") from exc
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        try:
            self._collection = client.get_collection(self.collection_name)
        except Exception:
            self._collection = client.get_collection(self.legacy_collection_name)
        return self._collection

    def _chroma_status(self) -> dict[str, Any]:
        if not self.chroma_dir.exists():
            return {"available": False, "count": 0, "error": "chroma_dir_missing"}
        try:
            collection = self._collection_instance()
            return {"available": True, "count": int(collection.count()), "error": None}
        except Exception as exc:
            return {"available": False, "count": 0, "error": str(exc)}

    def _sources_for(
        self,
        task: str,
        transcript: dict,
        structured_check: dict,
        extra: dict[str, Any],
        data: dict[str, Any] | None = None,
    ) -> list[dict]:
        sources = [_structured_source(structured_check)]
        sources.extend(policy_sources_for_task(data or load_graduation_data(str(self.data_dir)), task))
        if task in {"early_graduation", "credit_drop"}:
            sources.extend(_official_policy_sources(task))
        query = _query_for_task(task, transcript, extra)
        sources.extend(self._rag_search(query, limit=6))
        for index, source in enumerate(sources, 1):
            source["id"] = f"G{index}"
        return sources

    def _rag_search(self, query: str, limit: int = 6) -> list[dict]:
        client = self._client_instance()
        collection = self._collection_instance()
        embedding_response = client.embeddings.create(model=self.embedding_model, input=[query])
        embedding = embedding_response.data[0].embedding
        response = collection.query(query_embeddings=[embedding], n_results=limit, include=["documents", "metadatas", "distances"])
        sources = []
        for doc, meta, distance in zip(
            response.get("documents", [[]])[0],
            response.get("metadatas", [[]])[0],
            response.get("distances", [[]])[0],
        ):
            sources.append(
                {
                    "title": "2025 국민대학교 요람",
                    "url": "data/graduation/chroma",
                    "page": meta.get("page", "?") if meta else "?",
                    "section": meta.get("section", "요람") if meta else "요람",
                    "text": _compact(doc, 520),
                    "relevance": round(1 - float(distance), 3),
                    "source_type": "graduation_yoram_rag",
                }
            )
        return sources

    def _call_llm(self, task: str, transcript: dict, structured_check: dict, sources: list[dict], extra: dict[str, Any]) -> dict:
        client = self._client_instance()
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "findings": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {
                                "type": "string",
                                "enum": ["가능 여부", "충족 항목", "부족 항목", "주의사항", "확인 필요", "제도 기준", "추천 경로", "행정 일정"],
                            },
                            "detail": {"type": "string", "maxLength": 320},
                            "source_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                        },
                        "required": ["label", "detail", "source_ids"],
                    },
                },
                "recommendations": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "action": {"type": "string", "maxLength": 140},
                            "reason": {"type": "string", "maxLength": 260},
                            "source_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                        },
                        "required": ["action", "reason", "source_ids"],
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            },
            "required": ["summary", "findings", "recommendations", "warnings"],
        }
        prompt = _analysis_prompt(task, transcript, structured_check, sources, extra)
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": "You analyze Korean university graduation requirements using only provided sanitized transcript summaries and sources."},
                {"role": "user", "content": prompt},
            ],
            text={"format": {"type": "json_schema", "name": "graduation_analysis", "schema": schema, "strict": True}},
            temperature=0.1,
        )
        output_text = getattr(response, "output_text", "") or _extract_output_text(response)
        return json.loads(output_text)


def _public_transcript(transcript: TranscriptSummary) -> dict[str, Any]:
    return {
        "department": transcript.department,
        "admission_year": transcript.admission_year,
        "total_credits": transcript.total_credits,
        "category_credits": transcript.category_credits,
        "gpa_minimum_met": transcript.gpa_minimum_met,
        "courses": [course.model_dump() for course in transcript.courses],
    }


def _structured_source(structured_check: dict) -> dict:
    text = "학과별 졸업 최저이수학점 구조화 데이터"
    if structured_check.get("matched"):
        req = structured_check.get("requirements", {})
        text = (
            f"{structured_check.get('department')} 기준: 총 {req.get('총학점')}학점, "
            f"전공 {req.get('전공')}학점, 기초교양 {req.get('기초교양')}학점, "
            f"핵심교양 {req.get('핵심교양')}학점, 자유교양 {req.get('자유교양')}학점."
        )
    return {
        "title": "2025 국민대학교 요람 별표5 졸업이수학점표",
        "url": "data/graduation/graduation_requirements.json",
        "page": "195-197",
        "section": "별표5 졸업이수학점표",
        "text": text,
        "relevance": 1.0,
        "source_type": "structured_json",
    }


def _customized_major_source() -> dict:
    """Return the curated Customized전공 source from structured policy data."""
    sources = policy_sources_for_task(load_graduation_data(), "customized_major")
    return sources[0] if sources else {}


def _credit_drop_source() -> dict:
    """Return the curated 성적포기 source from structured policy data."""
    sources = policy_sources_for_task(load_graduation_data(), "credit_drop")
    return sources[0] if sources else {}


def _official_policy_sources(task: str) -> list[dict]:
    """Pull relevant policy chunks already indexed from official KMU sources."""
    path = Path("data/processed/chunks.jsonl")
    if not path.exists():
        return []
    terms = {
        "early_graduation": ["조기졸업"],
        "credit_drop": ["성적포기", "학점포기", "수강포기"],
    }.get(task, [])
    matched_chunks = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                haystack = " ".join(str(chunk.get(key, "")) for key in ("title", "text", "keywords", "search_hints"))
                if not any(term in haystack for term in terms):
                    continue
                title = str(chunk.get("title", ""))
                score = 2 if any(term in title for term in terms) else 1
                matched_chunks.append((score, chunk))
    except Exception:
        return []
    sources = []
    for _, chunk in sorted(matched_chunks, key=lambda item: (-item[0], int(item[1].get("source_tier", 9))))[:3]:
        sources.append(
            {
                "title": chunk.get("title", "국민대학교 공식자료"),
                "url": chunk.get("url", ""),
                "page": chunk.get("posted_date", "공식자료"),
                "section": chunk.get("department", chunk.get("source_type", "공식자료")),
                "text": _compact(chunk.get("text", ""), 620),
                "relevance": 0.95,
                "source_type": chunk.get("source_type", "official_chunk"),
            }
        )
    return sources


def _query_for_task(task: str, transcript: dict, extra: dict[str, Any]) -> str:
    department = transcript.get("department", "")
    if task == "early_graduation":
        return f"{department} 조기졸업 승인 요건 졸업사정 성적포기 졸업연기"
    if task == "customized_major":
        return f"{department} Customized전공 인정 전공선택 일반선택 필수과목 대체 신청"
    if task == "credit_drop":
        return f"{department} 성적포기 학점포기 수강포기 졸업요건 조기졸업"
    if task == "substitute_courses":
        return f"{department} {extra.get('course_name', '')} 대체 이수 인정 과목 졸업요건"
    if task == "micro_degree":
        return f"{department} 마이크로디그리 소학위 이수요건 교과목"
    if task == "post_graduation_checklist":
        return "졸업예정증명서 학위수여 졸업식 학위복 졸업 후 증명서"
    if task == "career_translator":
        return f"{department} 교과목 개요 {extra.get('target_job', '')} 직무 역량"
    return f"{department} 졸업요건 필수과목 이수규정"


def _analysis_prompt(task: str, transcript: dict, structured_check: dict, sources: list[dict], extra: dict[str, Any]) -> str:
    task_labels = {
        "audit": "졸업 가능 여부 진단",
        "early_graduation": "조기졸업 가능 여부 및 조심할 점 안내",
        "customized_major": "Customized전공 인정 제도 안내",
        "credit_drop": "학점 드랍/성적포기 제도 확인",
        "substitute_courses": f"대체 이수 과목 탐색: {extra.get('course_name', '')}",
        "micro_degree": "마이크로디그리/소학위 가능성 분석",
        "post_graduation_checklist": "졸업 전후 행정 체크리스트",
        "career_translator": f"직무 역량 번역: {extra.get('target_job', '')}",
    }
    course_names = [
        {"name": course.get("name"), "credits": course.get("credits"), "category": course.get("category")}
        for course in transcript.get("courses", [])[:80]
    ]
    source_context = "\n\n".join(
        f"[{source['id']}] {source.get('title')} / {source.get('page')}p / {source.get('section')}\n{source.get('text')}"
        for source in sources
    )
    task_rules = "\n".join(f"- {rule}" for rule in _task_specific_rules(task))
    return f"""작업: {task_labels.get(task, task)}

중요 규칙:
- 제공된 비식별 성적 요약과 출처만 사용하세요.
- 이름, 학번, GPA 숫자, 과목별 성적을 만들거나 언급하지 마세요.
- 한국어로 답하고, 사용자가 바로 행동할 수 있게 간결하게 작성하세요.
- summary는 한 문장으로 작성하고 80자 안팎을 넘기지 마세요.
- findings.label은 가능 여부, 충족 항목, 부족 항목, 주의사항, 확인 필요, 제도 기준, 추천 경로, 행정 일정 중 하나만 사용하세요.
- recommendations는 사용자가 다음에 실제로 할 수 있는 행동으로 쓰세요.
- 마크다운 표는 만들지 마세요.
- 출처나 비식별 요약에서 판단할 수 없는 내용은 단정하지 말고 '확인 필요'로 표시하세요.
- 조기졸업에서는 GPA 숫자를 표시하지 말고 '평점 기준 충족/미충족/확인 필요'로만 말하세요.
- 학점 드랍은 국민대학교 공식 표현 '성적포기'와 함께 설명하세요.
- source_ids에는 반드시 아래 출처 ID 중 직접 근거가 되는 ID만 넣으세요.
- 최종 확인은 교학팀/학과사무실이 필요하다는 경고를 포함하세요.

작업별 규칙:
{task_rules}

[비식별 성적 요약]
{json.dumps({**transcript, "courses": course_names}, ensure_ascii=False, indent=2)}

[구조화 졸업요건 계산]
{json.dumps(structured_check, ensure_ascii=False, indent=2)}

[사용자 확인 항목]
{json.dumps(extra, ensure_ascii=False, indent=2)}

[출처]
{source_context}
"""


def _task_specific_rules(task: str) -> list[str]:
    rules = {
        "audit": [
            "졸업 가능성은 총학점, 이수구분별 부족 학점, 확인 필요 항목 순서로 정리하세요.",
            "부족 학점이 0이어도 졸업인증, 논문, 학부별 인증 등 요람 밖 확인 항목을 분리하세요.",
        ],
        "early_graduation": [
            "조기졸업은 평점 기준, 등록학기, 성적포기/성적경고/편입 등 제외 사유, 졸업연기 불가를 분리해 말하세요.",
            "학생의 실제 GPA 숫자는 절대 쓰지 말고 gpa_minimum_met 값만 평점 기준 충족/미충족/확인 필요로 번역하세요.",
        ],
        "customized_major": [
            "신청 가능 여부를 단정하기보다 자격, 과목 적합성, 서류, 신청 기간, 승인 후 제한을 분리해 안내하세요.",
            "타전공 과목과 진로/소속 전공의 연관성은 사용자가 작성해야 할 판단 근거 관점으로 제안하세요.",
        ],
        "credit_drop": [
            "사용자의 '학점 드랍' 표현은 괄호로 받고 공식 용어 '성적포기'를 중심으로 설명하세요.",
            "조기졸업 신청 또는 예정자 제한, 철회 불가, 취득학점 제외, W 표기를 반드시 확인 항목으로 넣으세요.",
        ],
        "substitute_courses": [
            "대체 이수는 후보 과목을 확정하지 말고 유사성, 학점 수, 소속 학과 승인 필요성을 기준으로 안내하세요.",
        ],
        "micro_degree": [
            "마이크로디그리는 성적표 과목명 기반 가능성만 제시하고, 실제 이수요건은 최신 개설/운영 기준 확인으로 남기세요.",
        ],
        "post_graduation_checklist": [
            "졸업 전, 졸업사정 후, 졸업 이후 순서로 행정 체크리스트를 정리하세요.",
        ],
        "career_translator": [
            "과목명은 성적 없이 역량 키워드로만 번역하고, 포트폴리오/이력서에 쓸 수 있는 행동을 추천하세요.",
        ],
    }
    return rules.get(task, ["확인 가능한 근거와 확인 필요 항목을 분리해 답하세요."])


def _build_answer(task: str, payload: dict, sources: list[dict]) -> str:
    source_ids = {source["id"] for source in sources}
    title = {
        "audit": "졸업 진단",
        "early_graduation": "조기졸업 가능 여부 및 조심할 점",
        "customized_major": "커스터마이징 전공 제도",
        "credit_drop": "학점 드랍/성적포기 제도",
        "substitute_courses": "대체 이수 과목 탐색",
        "micro_degree": "마이크로디그리 발굴",
        "post_graduation_checklist": "졸업 전후 체크리스트",
        "career_translator": "직무 역량 번역",
    }.get(task, "졸업 센터 분석")
    lines = [f"[{title}]", f"{payload.get('summary', '')} {_markers(['G1'], source_ids)}", "", "[주요 확인]"]
    for item in payload.get("findings", []):
        markers = _markers(item.get("source_ids") or ["G1"], source_ids)
        lines.append(f"- {item.get('label')}: {item.get('detail')} {markers}")
    lines.extend(["", "[추천 행동]"])
    for item in payload.get("recommendations", []):
        markers = _markers(item.get("source_ids") or ["G1"], source_ids)
        lines.append(f"- {item.get('action')}: {item.get('reason')} {markers}")
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["", "[주의]"])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(["", "[근거]"])
    for source in sources:
        lines.append(f"- [{source['id']}] {source.get('title')} / {source.get('page')}p / {source.get('section')}")
    return "\n".join(lines)


def _markers(values: list[str], source_ids: set[str]) -> str:
    valid = [value for value in values if value in source_ids]
    if not valid:
        valid = ["G1"]
    return "".join(f"[{value}]" for value in valid[:3])


def _input_safety_flags(transcript: dict, extra: dict[str, Any]) -> list[str]:
    text = json.dumps({"transcript": transcript, "extra": extra}, ensure_ascii=False)
    flags = []
    if re.search(r"\d{6}-\d{7}|주민", text):
        flags.append("resident_number")
    if re.search(r"01[016789]-?\d{3,4}-?\d{4}|연락처|전화번호", text):
        flags.append("phone")
    if re.search(r"비밀번호|패스워드|password|pw", text, re.IGNORECASE):
        flags.append("portal_password")
    return flags


def _sanitize_sensitive_output(text: str) -> str:
    text = re.sub(r"\b20\d{6,8}\b", "[학번 마스킹]", text)
    text = re.sub(r"\d{6}-\d{7}", "[주민번호 마스킹]", text)
    text = re.sub(r"01[016789]-?\d{3,4}-?\d{4}", "[연락처 마스킹]", text)
    text = re.sub(r"(GPA|평점평균)\s*[:：]?\s*\d+(?:\.\d+)?", r"\1 기준 비공개", text, flags=re.IGNORECASE)
    return text


def _compact(value: str, limit: int) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _extract_output_text(response: Any) -> str:
    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts)
