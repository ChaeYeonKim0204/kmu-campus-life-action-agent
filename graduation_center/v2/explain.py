"""규정 근거 해설 노드 — 보고서 내장형 RAG (챗 UI 없음).

audit의 주요 부족 항목 2~3개를 결정론으로 선정 → 요람 Chroma 검색 → LLM이
검색 chunk만 근거로 해설 생성(source_ids enum 강제) → 결정론 validator가 인용
해소·수치 정합·마스킹 검증 → 컨설팅 보고서의 '규정 근거 해설' 섹션으로 삽입.

판정은 결정론 본체가 source of truth — LLM은 규정 원문의 자연어 해설만 한다.
동일 입력 캐시(해시 키)로 데모 일관성·지연을 보장하고, 실패 시 해당 섹션만
graceful degrade(audit 응답은 정상 완료).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from graduation_center.v2.models_v2 import (
    AuditResult, ExplainLine, ExplainSection, NodeTraceEvent, RequirementProfile,
    Source, StudentContext,
)

CHROMA_DIR = "data/graduation/chroma"
COLLECTION = "kmu_graduation_yoram"
EMBEDDING_MODEL = "text-embedding-3-small"
CACHE_PATH = Path("data/graduation/v2/explain_cache.json")
MAX_ITEMS = 3
TOP_K = 4
_STUDENT_ID = re.compile(r"\b(20\d{2})\d{4}\b")


# ---------- 1) 해설 대상 선정 (결정론) ----------
def select_explain_items(audit: AuditResult, profile: RequirementProfile,
                         ctx: StudentContext) -> list[dict]:
    """부족 항목을 우선순위(필수 > 융합 > 영역 > 핵심교양 세부)로 최대 3개 선정."""
    items: list[dict] = []
    dept = profile.department_name_ko

    if audit.missing_required_names:
        names = ", ".join(audit.missing_required_names[:4])
        items.append({
            "key": "missing_required",
            "title": f"미이수 필수지정 과목 ({len(audit.missing_required_names)}과목)",
            "query": f"{dept} 전공 필수지정 과목 이수 졸업요건 {names}",
            "context": f"미이수 필수지정: {names}",
        })
    for cc in audit.convergence_checks:
        short_groups = [gc for gc in cc.get("group_checks", []) if gc["gap"] > 0]
        if cc.get("gap", 0) > 0 or short_groups:
            gtxt = ", ".join(f"{gc['group']} {gc['gap']:.0f}학점 부족" for gc in short_groups)
            items.append({
                "key": f"conv:{cc['program_id']}",
                "title": f"{cc['name']}({cc['track']}) 이수 요건",
                "query": f"연계 융합전공 {cc['name']} 이수 요건 학점 중복인정 한도 {cc['track']}",
                "context": f"{cc['name']} {cc['earned']:.0f}/{cc['required']:.0f}학점"
                           + (f" · {gtxt}" if gtxt else "")
                           + f" · 중복인정 {cc['double_used']:.0f}/{cc['double_cap']:.0f}",
            })
    for g in audit.area_gaps:
        if g.gap > 0 and g.area in ("전공", "기초교양", "핵심교양", "자유교양"):
            items.append({
                "key": f"area:{g.area}",
                "title": f"{g.area} 이수학점 부족 ({g.gap:.0f}학점)",
                "query": f"{dept} 졸업요건 {g.area} 최저 이수학점",
                "context": f"{g.area} {g.earned:.0f}/{g.required:.0f}학점 (부족 {g.gap:.0f})",
            })
    core_short = [g for g in audit.core_area_gaps if g.gap > 0]
    if core_short:
        areas = ", ".join(g.area for g in core_short)
        items.append({
            "key": "core_areas",
            "title": f"핵심교양 영역별 최저 미충족 ({areas})",
            "query": f"핵심교양 영역별 최저 이수 기준 {areas}",
            "context": "; ".join(f"{g.area} {g.earned:.0f}/{g.required:.0f}" for g in core_short),
        })
    return items[:MAX_ITEMS]


# ---------- 2) 요람 검색 (tool) ----------
def retrieve_yoram(query: str, client, top_k: int = TOP_K) -> list[dict]:
    import chromadb
    col = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    emb = client.embeddings.create(model=EMBEDDING_MODEL, input=[query]).data[0].embedding
    r = col.query(query_embeddings=[emb], n_results=top_k, include=["documents", "metadatas"])
    out = []
    for doc, meta in zip(r.get("documents", [[]])[0], r.get("metadatas", [[]])[0]):
        out.append({"page": (meta or {}).get("page"), "section": (meta or {}).get("section", "요람"),
                    "text": (doc or "")[:600]})
    return out


# ---------- 3) LLM 해설 생성 (llm) ----------
def _schema(item_keys: list[str], source_ids: list[str]) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "explanations": {
                "type": "array", "maxItems": MAX_ITEMS,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "item_key": {"type": "string", "enum": item_keys},
                        "lines": {
                            "type": "array", "maxItems": 4,
                            "items": {
                                "type": "object", "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string", "maxLength": 220},
                                    "source_ids": {"type": "array", "maxItems": 3,
                                                   "items": {"type": "string", "enum": source_ids}},
                                },
                                "required": ["text", "source_ids"],
                            },
                        },
                    },
                    "required": ["item_key", "lines"],
                },
            },
        },
        "required": ["explanations"],
    }


def _prompt(items: list[dict], chunks_by_item: dict[str, list[dict]],
            id_by_chunk: dict[int, str]) -> str:
    blocks = []
    for it in items:
        src = "\n".join(
            f"[{id_by_chunk[id(c)]}] 요람 p.{c['page']} ({c['section']})\n{c['text']}"
            for c in chunks_by_item.get(it["key"], []))
        blocks.append(f"### 항목 {it['key']} — {it['title']}\n진단 결과: {it['context']}\n근거 후보:\n{src}")
    body = "\n\n".join(blocks)
    return f"""졸업사정 컨설팅 보고서의 '규정 근거 해설' 섹션을 작성한다.

규칙:
- 각 항목마다 2~4줄. 제공된 근거 chunk의 내용만 사용해 해당 규정/요건을 해설한다.
- 줄마다 직접 근거가 된 chunk ID만 source_ids에 넣는다(근거 없는 줄 금지).
- 진단 결과의 숫자는 인용 가능. 근거 chunk에 없는 새 수치·요건을 만들지 않는다.
- 졸업 가능/불가 판정은 하지 않는다 — 판정은 시스템이 이미 했고, 너는 규정 해설만 한다.
- 학생이 다음에 할 행동(학과사무실 확인 등)으로 끝맺어도 좋다. 한국어, 존댓말.

{body}"""


def _call_llm(client, model: str, items: list[dict], chunks_by_item: dict,
              id_by_chunk: dict) -> dict:
    sids = sorted(id_by_chunk.values())
    kwargs = {
        "model": model,
        "input": [
            {"role": "system",
             "content": "You write grounded Korean explanations of university regulations using only provided yoram chunks."},
            {"role": "user", "content": _prompt(items, chunks_by_item, id_by_chunk)},
        ],
        "text": {"format": {"type": "json_schema", "name": "explain_sections",
                            "schema": _schema([i["key"] for i in items], sids), "strict": True}},
    }
    if model.startswith(("gpt-5", "o")):
        kwargs["reasoning"] = {"effort": "minimal"}
    try:
        resp = client.responses.create(**kwargs, temperature=0.1)
    except Exception as exc:
        if "temperature" in str(exc).lower():
            resp = client.responses.create(**kwargs)
        else:
            raise
    return json.loads(getattr(resp, "output_text", "") or "")


# ---------- 4) 인용 검증 (validator, 결정론) ----------
def validate_explanations(raw: dict, items: list[dict], chunks_by_item: dict,
                          id_by_chunk: dict) -> list[ExplainSection]:
    chunk_text_by_id = {}
    allowed_by_item: dict[str, set] = {}
    for it in items:
        ids = set()
        for c in chunks_by_item.get(it["key"], []):
            cid = id_by_chunk[id(c)]
            ids.add(cid)
            chunk_text_by_id[cid] = c["text"]
        allowed_by_item[it["key"]] = ids
    title_by_key = {i["key"]: i["title"] for i in items}
    ctx_by_key = {i["key"]: i["context"] for i in items}

    sections: list[ExplainSection] = []
    for ex in raw.get("explanations", []):
        key = ex.get("item_key")
        if key not in title_by_key:
            continue
        lines: list[ExplainLine] = []
        for ln in ex.get("lines", [])[:4]:
            text = _STUDENT_ID.sub(r"\1XXXX", str(ln.get("text", "")).strip())[:220]
            if not text:
                continue
            sids = [s for s in ln.get("source_ids", []) if s in allowed_by_item[key]]
            cited = " ".join(chunk_text_by_id.get(s, "") for s in sids) + " " + ctx_by_key[key]
            # 새 수치 생성 가드: 2자리 이상 숫자는 인용 chunk나 진단 결과에 있어야 함
            grounded = bool(sids) and all(n in cited for n in re.findall(r"\d{2,}", text))
            if not grounded:
                text += " ※ 공식 출처 미확인 — 학과사무실 확인 권장"
            lines.append(ExplainLine(text=text, source_ids=sids, grounded=grounded))
        if lines:
            sections.append(ExplainSection(key=key, title=title_by_key[key], lines=lines))
    return sections


# ---------- 캐시 (동일 입력 = 동일 해설 · 데모 지연 0) ----------
def _cache_key(model: str, items: list[dict]) -> str:
    return hashlib.sha256(json.dumps({"m": model, "i": items}, ensure_ascii=False,
                                     sort_keys=True).encode()).hexdigest()[:24]


def _cache_get(key: str):
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8")).get(key)
    except Exception:
        return None


def _cache_put(key: str, value: dict) -> None:
    try:
        data = {}
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        data[key] = value
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # 캐시 실패는 침묵 — 해설 생성 자체를 막지 않음


def _get_client():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None
    try:
        from openai import OpenAI
        return OpenAI(timeout=20)
    except Exception:
        return None


# ---------- 오케스트레이션 ----------
def run_explain(audit: AuditResult, profile: RequirementProfile, ctx: StudentContext,
                client=None) -> tuple[list[ExplainSection], list[Source], list[NodeTraceEvent], str | None]:
    """반환: (sections, Y-sources, trace 2노드, fallback_reason)."""
    items = select_explain_items(audit, profile, ctx)
    model = os.getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini")
    if not items:
        return [], [], [
            NodeTraceEvent(node="요람 RAG 해설", kind="llm", status="skip",
                           summary="부족 항목 없음 — 해설 생략", branch_taken="해설 불필요"),
        ], None

    ck = _cache_key(model, items)
    cached = _cache_get(ck)
    if cached:
        sections = [ExplainSection.model_validate(s) for s in cached["sections"]]
        sources = [Source.model_validate(s) for s in cached["sources"]]
        trace = [
            NodeTraceEvent(node="요람 RAG 해설", kind="llm",
                           summary=f"{len(sections)}개 항목 해설 (캐시 — 동일 입력 동일 결과)",
                           branch_taken=f"{len(sections)}개 항목 해설"),
            NodeTraceEvent(node="해설 검증", kind="validator",
                           summary="인용 해소·수치 정합·마스킹 통과(캐시)", branch_taken="통과"),
        ]
        return sections, sources, trace, None

    client = client or _get_client()
    if client is None:
        return [], [], [
            NodeTraceEvent(node="요람 RAG 해설", kind="llm", status="skip",
                           summary="LLM 미설정 — 결정론 진단·G 근거는 유효", branch_taken="해설 생략(키 없음)"),
        ], "LLM 미설정(OPENAI_API_KEY 없음)"

    try:
        chunks_by_item: dict[str, list[dict]] = {}
        id_by_chunk: dict[int, str] = {}
        n = 0
        for it in items:
            chunks = retrieve_yoram(it["query"], client)
            chunks_by_item[it["key"]] = chunks
            for c in chunks:
                n += 1
                id_by_chunk[id(c)] = f"Y{n}"
        raw = _call_llm(client, model, items, chunks_by_item, id_by_chunk)
        sections = validate_explanations(raw, items, chunks_by_item, id_by_chunk)
        # 실제 인용된 chunk만 근거 목록에 노출
        used = {sid for sec in sections for ln in sec.lines for sid in ln.source_ids}
        sources = []
        for it in items:
            for c in chunks_by_item[it["key"]]:
                cid = id_by_chunk[id(c)]
                if cid in used:
                    sources.append(Source(id=cid, doc="2025 국민대학교 요람",
                                          page=c.get("page"), source_type="yoram_rag",
                                          ref=c.get("section")))
        ungrounded = sum(1 for sec in sections for ln in sec.lines if not ln.grounded)
        trace = [
            NodeTraceEvent(node="요람 RAG 해설", kind="llm",
                           summary=f"{len(items)}개 항목 · 요람 chunk {n}건 검색 · {model}",
                           branch_taken=f"{len(sections)}개 항목 해설"),
            NodeTraceEvent(node="해설 검증", kind="validator",
                           status="ok" if ungrounded == 0 else "warn",
                           summary=("인용 해소·수치 정합·마스킹 통과" if ungrounded == 0
                                    else f"근거 미확인 {ungrounded}줄 표시"),
                           branch_taken=("통과" if ungrounded == 0 else "일부 미확인 표시")),
        ]
        _cache_put(ck, {"sections": [s.model_dump() for s in sections],
                        "sources": [s.model_dump() for s in sources]})
        return sections, sources, trace, None
    except Exception as exc:
        return [], [], [
            NodeTraceEvent(node="요람 RAG 해설", kind="llm", status="fail",
                           summary=f"해설 생성 불가({type(exc).__name__}) — 결정론 진단·G 근거는 유효",
                           branch_taken="해설 실패(degrade)"),
        ], f"해설 생성 불가: {type(exc).__name__}"
