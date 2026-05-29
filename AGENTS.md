# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this project is

A grounded-RAG agent that answers Kookmin University (KMU) campus-life questions in Korean and drafts the next-step paperwork (출석인정신청서, 휴학/복학 체크리스트, 문의문 etc.). User-facing strings are Korean; keep them Korean unless told otherwise.

## Commands

Backend (FastAPI):
```bash
pip install -r requirements.txt
uvicorn app:app --reload          # http://127.0.0.1:8000
```

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

There is no linter or formatter wired into the repo.

## Architecture

The request pipeline is the spine — most files are nodes in it.

```
POST /ask question
  → agent.guard.inspect_privacy        # regex-block 학번/주민/연락처/PW/성적
  → agent.classifier.classify_issue    # rule-based, returns issue_type
  → retriever.HybridRetriever.search   # vector (Chroma) + keyword JSONL, merged by chunk_id
  → agent.guard.require_sources        # block if no chunks
  → agent.planner.suggest_actions      # propose next-step actions by issue_type + chunk.actions
  → agent.answer_builder.build_final_answer
        ├── tools.checklist.generate_checklist
        ├── tools.contact_router.route_contact
        ├── tools.deadline (extract_event_date + calculate_deadline)
        └── agent.citation (S1/S2 labels + cite())
```

Action drafting is a separate two-step flow with its own state machine:
`POST /actions/start` → `agent.action_state.start_action` returns required slot questions →
`POST /actions/continue` → re-runs `inspect_privacy` over slot values → `tools.document_drafter.draft_action_document` writes a grounded draft. Slot schemas live in `tools/document_drafter.py:ACTION_SCHEMAS`. The graduation-audit and course-plan actions dispatch from `document_drafter` into `tools.graduation.audit_graduation_requirements` and `tools.course_planner.recommend_course_plan` respectively — those tools are reached only through the action flow, not through `/ask`.

### Data plane

`data/processed/chunks.jsonl` is the **source of truth** for retrieval, written by `ingestion.pipeline.run_ingestion` from raw crawler output in `data/raw/`. Chroma at `data/vector/chroma` is an optional accelerator indexed in the same pipeline — `VectorRetriever` degrades silently (sets `available=False`, populates `.error`) and the keyword path keeps serving answers. Do not gate features on Chroma being up. After ingest, `HybridRetriever.reload()` must be called so the in-memory keyword index picks up new chunks (the `/ingest/run` handler does this).

Chunk metadata is rich and load-bearing: `source_tier` (1=규정 … 8=SWELL, sorted lower-tier-wins ties), `issue_types`, `keywords`, `search_hints`, `application_path`, `required_documents`, `submit_to`, `contacts`, `schedule`, `deadline_rule`, `actions`. The retriever, planner, checklist, contact router, and deadline calculator all read different subsets of these fields, so when adding a new chunk shape make sure every downstream consumer can still find what it needs.

### Crawl/ingest

`POST /ingest/run` → `ingestion.pipeline.run_ingestion`. The crawler base in `crawler/base.py` enforces school-server-protection rules that must not be relaxed:

- per-host random delay (`min_delay_seconds`/`max_delay_seconds`, default 8–18s)
- `max_pages_per_run` cap (default 3) and `INGEST_COOLDOWN_SECONDS = 300` between runs
- module-level `_INGEST_LOCK` prevents concurrent ingest
- `If-None-Match` / `If-Modified-Since` from stored `ETag`/`Last-Modified` for conditional GET
- if network fails or is empty, the curated `SourcePage.fallback_text` is used and the chunk is tagged `used_fallback: true`; the API response always exposes `network_success`/`fallback_used`/`network_failed`/`failed_urls` so callers see the real fetch status

Crawler state lives in `data/state/crawler_state.json` (per-doc content_hash + cache headers). Each `BaseCrawler` subclass is essentially `source_type` + `pages: list[SourcePage]`.

## Guardrails that must hold

These are project requirements, not preferences — see `project_plan.md` §7:

- Never collect or echo back: 학번, 주민번호, 연락처, 성적표 원본, 포털 ID/PW. `PRIVACY_PATTERNS` in `agent/guard.py` is the canonical list; both `/ask` and `/actions/continue` run it.
- Never fabricate procedural advice without an official chunk backing it — `require_sources` blocks the answer if retrieval returns nothing.
- Never auto-crawl post-login portals (ON국민, SWELL personal screens) or 에브리타임. Only the public sources tier-listed in the README.
- LLM generation is deliberately stubbed (`llm_client.GuardedLLMClient.generate` returns `""`); the answer is assembled deterministically in `answer_builder`. If you wire a real model, it must still consume only retrieved chunks and preserve citation markers.

## Citation contract

`agent/citation.build_citations` assigns `S1`, `S2`, … to each unique retrieved chunk and `cite()` produces the `[S1]` markers embedded in the answer text. Anywhere you add a procedural claim to the answer, append `cite(chunk, labels)` for the chunk that supports it — readers and tests rely on every factual line carrying a marker that resolves to a citation in the `[근거]` block.
