# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A grounded-RAG agent that answers Kookmin University (KMU) campus-life questions in Korean and drafts the next-step paperwork (출석인정신청서, 휴학/복학 체크리스트, 문의문 etc.). It also runs a deeper, transcript-based graduation analysis subsystem (졸업센터). User-facing strings are Korean; keep them Korean unless told otherwise.

## Commands

Backend (FastAPI):
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8001   # frontend dev expects the API on 8001
```
The frontend dev build hardcodes the API base as `http://127.0.0.1:8001` (`frontend/src/App.jsx`), so run the backend on `--port 8001` when developing against the Vite dev server. Bare `uvicorn app:app --reload` listens on 8000, which the served-from-dist deployment uses (it calls `window.location.origin`).

Frontend (Vite + React, served separately during dev):
```bash
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173
cd frontend && npm run build                # builds frontend/dist; FastAPI serves dist/index.html at / and mounts dist/assets at /assets when present
```

Tests:
```bash
pytest                            # runs all tests; tests/conftest.py injects repo root onto sys.path
pytest tests/test_actions.py -k attendance   # single test
```

`tests/` (plural) is the real pytest suite for the running app. `test/` (singular) is a **separate, standalone graduation-RAG prototype** with its own `requirements.txt`, `.env`, and scripts (`0_extract_structured_data.py`, `1_build_index.py`, …) — it is not part of the app's test run and predates the `graduation_center/` package that productized it. Don't conflate the two.

There is no linter or formatter wired into the repo.

## Architecture

The `/ask` request pipeline is the spine — most files are nodes in it.

```
POST /ask question
  → agent.guard.inspect_privacy        # regex-block 학번/주민/연락처/PW/성적
  → agent.classifier.classify_issue    # rule-based, returns issue_type
  → llm_client.expand_search_query     # OPTIONAL (env-gated); else passthrough
  → ingestion.live_refresh.refresh_sources_for_issue  # OPTIONAL (live_check=true)
  → retriever.HybridRetriever.search   # vector (Chroma) + keyword JSONL, merged by chunk_id
  → llm_client.rerank_chunks           # OPTIONAL (env-gated); else identity
  → agent.guard.require_sources        # block if no chunks
  → agent.planner.suggest_actions      # propose next-step actions by issue_type + chunk.actions
  → agent.answer_builder.build_final_answer
        ├── tools.checklist.generate_checklist
        ├── tools.contact_router.route_contact
        ├── tools.deadline (extract_event_date + calculate_deadline)
        └── agent.citation (S1/S2 labels + cite())
  → llm_client.polish_answer           # OPTIONAL (env-gated); else deterministic text
  → agent.answer_validator             # final output guard; reverts to deterministic answer on failure
```

`app.py` is the FastAPI server holding all routes plus the retrieval-shaping helpers (`_prefer_issue_matched_chunks`, `_curated_fallback_chunks`, `_query_relevance_score`, …). The `_curated_fallback_chunks` path lets the API answer from each crawler's `SourcePage.fallback_text` even before any ingest run has indexed chunks — useful to know when retrieval "works" on a fresh checkout.

`agent/student_context.py` normalizes the optional non-sensitive `student_context` (status/term/concern) used to personalize answers; `agent/student_playbook.py` holds `STUDENT_TERM_ALIASES` (이캠→eCampus, 과사→학과사무실, 종정시→포털 …) and per-issue playbooks. Term aliasing feeds both query relevance scoring and answer "학생 경험 팁" sections — it is deliberately separate from official-source retrieval.

### Action drafting flow

A separate two-step flow with its own state machine:
`POST /actions/start` → `agent.action_state.start_action` returns required slot questions →
`POST /actions/continue` → re-runs `inspect_privacy` over slot values → `tools.document_drafter.draft_action_document` writes a grounded draft, then `agent.answer_validator.validate_output_privacy` guards the returned text. Slot schemas live in `tools/document_drafter.py:ACTION_SCHEMAS`. The graduation-audit and course-plan actions dispatch from `document_drafter` into `tools.graduation.audit_graduation_requirements` (an MVP credit-gap calculator) and `tools.course_planner.recommend_course_plan` — those tools are reached only through the action flow, not through `/ask`, and are distinct from the `graduation_center/` subsystem below.

### Graduation center (졸업센터)

`graduation_center/` is a separate, deeper subsystem with its own `/graduation/*` endpoints (`/graduation/status`, `/transcript/parse`, `/audit`, `/substitute-courses`, `/micro-degree`, `/post-graduation-checklist`, `/career-translator`, `/early-graduation`, `/customized-major`, `/credit-drop`). Flow: parse an uploaded transcript PDF into a **sanitized, non-identifying** `TranscriptSummary` (`graduation_center/parser.py`) → `compute_structured_check` against `data/graduation/graduation_requirements.json` → 요람 RAG over its own Chroma collection at `data/graduation/chroma` → GPT analysis (`service._call_llm`) → `_sanitize_sensitive_output` masks any student ID / 주민번호 / phone / GPA before returning.

Unlike the main `/ask` pipeline, the graduation center **requires** OpenAI + an indexed 요람 Chroma collection. When prerequisites are missing it raises `GraduationServiceUnavailable`, which `app.py` maps to HTTP 503 — it does not degrade to keyword-only. Never return raw transcript text, GPA numbers, or per-course grades from this subsystem (`status().privacy` documents the contract).

### Optional LLM assist

LLM use is **off by default and fails closed** to the deterministic path. `llm_client.GuardedLLMClient` reads `OPENAI_ENABLED` (query expansion + reranking) and `OPENAI_POLISH_ENABLED` (answer polishing); both also need `OPENAI_API_KEY`. The legacy `generate()` method is still a hard stub returning `""` — the answer is assembled deterministically in `answer_builder`. The three live helpers are retrieval/presentation-only and grounded:

- `expand_search_query` — adds official KMU synonyms to the retrieval query; never adds facts.
- `rerank_chunks` — reorders *already-retrieved* chunks via a `chunk_id` enum schema; cannot introduce new sources.
- `polish_answer` — rewrites prose between section headers only; `_polish_rejection_reason` rejects the result if citation markers, section headers, or the `[근거]` block change, or if it grows too long.

Even when polish succeeds, `agent.answer_validator` re-checks the final text and reverts to the deterministic `built["answer"]` if the citation contract or output-privacy check fails. If you wire any further model use, it must consume only retrieved chunks and preserve citation markers.

### Data plane

`data/processed/chunks.jsonl` is the **source of truth** for `/ask` retrieval, written by `ingestion.pipeline.run_ingestion` from raw crawler output in `data/raw/`. Chroma at `data/vector/chroma` is an optional accelerator indexed in the same pipeline — `VectorRetriever` degrades silently (sets `available=False`, populates `.error`) and the keyword path keeps serving answers. Do not gate `/ask` features on Chroma being up. (The `graduation_center/` Chroma at `data/graduation/chroma` is a *different* store with the opposite policy — it is required, not optional.) After ingest, `HybridRetriever.reload()` must be called so the in-memory keyword index picks up new chunks (the `/ingest/run` and live-refresh handlers do this).

Chunk metadata is rich and load-bearing: `source_tier` (1=규정 … 8=SWELL, sorted lower-tier-wins ties), `issue_types`, `keywords`, `search_hints`, `application_path`, `required_documents`, `submit_to`, `contacts`, `schedule`, `deadline_rule`, `actions`. The retriever, planner, checklist, contact router, deadline calculator, and `_curated_fallback_chunks` all read different subsets of these fields, so when adding a new chunk shape make sure every downstream consumer can still find what it needs.

### Crawl/ingest

`POST /ingest/run` → `ingestion.pipeline.run_ingestion` (full crawl). `POST /ingest/live-refresh` and the `live_check=true` flag on `/ask` and `/actions/continue` → `ingestion.live_refresh.refresh_sources_for_issue`, a narrower per-issue refresh that only touches pages relevant to the classified issue and rewrites chunks only when a network fetch actually succeeds (its own `_LIVE_REFRESH_LOCK` + 60s cooldown). The crawler base in `crawler/base.py` enforces school-server-protection rules that must not be relaxed:

- per-host random delay (`min_delay_seconds`/`max_delay_seconds`, default 8–18s)
- `max_pages_per_run` cap (default 3) and `INGEST_COOLDOWN_SECONDS = 300` between runs
- module-level `_INGEST_LOCK` prevents concurrent ingest
- `If-None-Match` / `If-Modified-Since` from stored `ETag`/`Last-Modified` for conditional GET
- if network fails or is empty, the curated `SourcePage.fallback_text` is used and the chunk is tagged `used_fallback: true`; the API response always exposes `network_success`/`fallback_used`/`network_failed`/`failed_urls` so callers see the real fetch status

Crawler state lives in `data/state/crawler_state.json` (per-doc content_hash + cache headers, plus `last_live_refresh` per issue). Each `BaseCrawler` subclass is essentially `source_type` + `pages: list[SourcePage]`.

## Guardrails that must hold

These are project requirements, not preferences — see `project_plan.md` §7:

- Never collect or echo back: 학번, 주민번호, 연락처, 성적표 원본, 포털 ID/PW. `PRIVACY_PATTERNS` in `agent/guard.py` is the canonical input list (`/ask` and `/actions/continue` run `inspect_privacy`); `agent/answer_validator.OUTPUT_PRIVACY_PATTERNS` guards the *output*, and `graduation_center` masks sensitive values in its own `_sanitize_sensitive_output`.
- Never fabricate procedural advice without an official chunk backing it — `require_sources` blocks the answer if retrieval returns nothing.
- Never auto-crawl post-login portals (ON국민, SWELL personal screens) or 에브리타임. Only the public sources tier-listed in the README.
- LLM assist is optional, env-gated, and grounded (see *Optional LLM assist*). The deterministic `answer_builder` output is the source of truth; the final `answer_validator` guard reverts any LLM-polished answer that breaks the citation contract or output-privacy check.

## Citation contract

`agent/citation.build_citations` assigns `S1`, `S2`, … to each unique retrieved chunk and `cite()` produces the `[S1]` markers embedded in the answer text. Anywhere you add a procedural claim to the answer, append `cite(chunk, labels)` for the chunk that supports it — readers, the `answer_validator` (which flags `unresolved_citation_marker` / `missing_inline_citation_marker`), and tests all rely on every factual line carrying a marker that resolves to a citation in the `[근거]` block. The graduation center uses a parallel `G1`/`G2` scheme (`graduation_center/service.py:_build_answer`).
