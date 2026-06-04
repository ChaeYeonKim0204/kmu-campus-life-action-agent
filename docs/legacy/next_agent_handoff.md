# Next Agent Handoff Prompt

You are continuing work in `/Users/moondh/Desktop/genai_proj`, a KMU campus-life grounded RAG/action agent. User-facing strings should remain Korean unless explicitly requested otherwise.

Read `AGENTS.md` first. The project requirements there are binding: no sensitive personal data collection, no fabricated procedural advice without official chunks, no post-login portal crawling, and citation markers must resolve to the `[근거]` block.

## Current Goal

The recent work upgraded the service from a static local-RAG demo into a safer, more observable RAG system with:

- optional OpenAI API assistance,
- issue-scoped live refresh against official public KMU pages,
- final answer validation,
- output privacy checks,
- UI controls/status panels,
- admin controls for manual issue refresh.

The next useful work is mostly operational polish, smoke testing with real keys/network, and securing admin surfaces.

## Important Existing Behavior

`POST /ask` now follows this approximate flow:

```text
privacy guard
→ rule classifier
→ optional OpenAI query expansion
→ optional live refresh for issue_type
→ hybrid retriever
→ optional OpenAI rerank
→ require official sources
→ deterministic answer_builder
→ optional OpenAI polish
→ final citation contract validation
→ final output privacy validation
```

`POST /actions/continue` now follows this approximate flow:

```text
slot privacy guard
→ optional live refresh by action issue_type
→ retrieve official chunks
→ deterministic action draft
→ final output privacy validation
```

OpenAI remains optional. The deterministic answer builder is still the source of truth.

## Major Files Changed or Added

### OpenAI assistance

- `llm_client.py`
  - Implements `GuardedLLMClient`.
  - Uses OpenAI Responses API structured outputs for:
    - `expand_search_query`
    - `rerank_chunks`
    - `polish_answer`
  - Fails closed when disabled, when API key is missing, or when API calls fail.
  - Tracks `api_key_configured`, `polish_enabled`, and `error`.
  - Default model: `gpt-4o-mini`.

- `requirements.txt`
  - Added `openai>=1.68.0`.

Environment variables:

```bash
OPENAI_API_KEY=...
OPENAI_ENABLED=true
OPENAI_MODEL=gpt-4o-mini
OPENAI_POLISH_ENABLED=true
```

`OPENAI_ENABLED=false` is the safe default. `OPENAI_POLISH_ENABLED=true` only matters when OpenAI is enabled and key is configured.

### Live refresh

- `ingestion/live_refresh.py`
  - Adds `refresh_sources_for_issue`.
  - Selects pages by `issue_type`.
  - Checks only public official `SourcePage`s from registered crawlers.
  - Updates `chunks.jsonl` only for documents fetched from network.
  - Does not let fallback text overwrite existing chunks.
  - Uses per-issue cooldown, default 60s.
  - Writes `last_live_refresh` into `data/state/crawler_state.json`.

- `app.py`
  - `AskRequest.live_check`
  - `ActionContinueRequest.live_check`
  - `LiveRefreshRequest`
  - `POST /ingest/live-refresh`
  - `/health.live_refresh` summary.

### Final validation and privacy

- `agent/answer_validator.py`
  - `validate_answer_contract(answer, citations)`
    - checks unresolved `[S1]`-style markers,
    - `[None]`,
    - missing `[근거]`,
    - missing inline markers when citations exist.
  - `validate_output_privacy(answer)`
    - detects concrete sensitive values:
      - student-id-like values,
      - resident registration numbers,
      - mobile phone numbers,
      - explicit password values.
    - intentionally allows generic text like “비밀번호 찾기”.

- `app.py`
  - Uses final guards after answer polish.
  - If polish breaks citation contract or introduces sensitive output, falls back to deterministic answer.
  - Adds `answer_validation`, `output_privacy`, and final `safety_flags` to `/ask`.
  - Applies `output_privacy` to action drafts before returning them.

### Citations and source provenance

- `agent/citation.py`
  - Citation metadata now includes:
    - `published_at`,
    - `fetched_from_network`,
    - `used_fallback`,
    - `fetch_status`,
    - `http_status`.

### Frontend

- `frontend/src/App.jsx`
  - Sends `live_check` and `llm_assist`.
  - Propagates `live_check`, `llm`, `answer_validation`, `output_privacy` into status UI.
  - Sends `live_check` on `actions/continue`.
  - Handles `blocked` action output without displaying sensitive draft text.

- `frontend/src/components/ChatPanel.jsx`
  - Added toggles:
    - `공식 사이트 최신 확인`,
    - `GPT 보조`.

- `frontend/src/components/ProcessingStatusPanel.jsx`
  - New panel showing:
    - answer validation,
    - output privacy check,
    - live refresh status,
    - GPT query expansion/rerank/polish usage.

- `frontend/src/components/SourcePanel.jsx`
  - Shows provenance badge:
    - `네트워크 확인`,
    - `fallback`,
    - `저장 근거`.

- `frontend/src/components/AdminDashboard.jsx`
  - Shows:
    - GPT assist status,
    - API key status,
    - polish status,
    - latest live refresh summary,
    - manual issue-scoped live refresh controls.

## New or Updated API Surface

### `/ask`

Accepts:

```json
{
  "question": "...",
  "student_context": {},
  "llm_assist": true,
  "live_check": false
}
```

Returns additional metadata:

- `llm`
- `live_check`
- `answer_validation`
- `output_privacy`

### `/actions/continue`

Accepts:

```json
{
  "action_id": "...",
  "slots": {},
  "live_check": false
}
```

Returns `output_privacy`, and `live_check` when applicable.

### `/ingest/live-refresh`

Admin/manual refresh endpoint:

```json
{
  "issue_type": "certificate",
  "query": "졸업예정증명서",
  "max_pages": 2
}
```

Runs issue-scoped refresh and reloads retriever if chunks were updated.

### `/health`

Now includes:

- `llm.enabled`
- `llm.api_key_configured`
- `llm.polish_enabled`
- `llm.error`
- `live_refresh.count`
- `live_refresh.latest`
- `live_refresh.recent`

## Tests Added

Notable new test files:

- `tests/test_llm_client.py`
- `tests/test_live_refresh.py`
- `tests/test_app_live_check.py`
- `tests/test_citation.py`
- `tests/test_answer_validator.py`
- `tests/test_api_contract.py`

Latest verification completed:

```bash
pytest
# 63 passed

cd frontend && npm run build
# build successful
```

Note: Vite prints a CJS deprecation warning during build, but the build succeeds.

## Current Worktree Notes

The worktree was already dirty before these changes. Do not assume every modified/untracked file was created in the recent sequence. In particular, there were pre-existing modifications in many core files and untracked directories such as `test/`.

Use `git status --short` before making further changes. Do not revert unrelated user changes.

## Recommended Next Steps

1. Create `.env.example`
   - Include:
     - `OPENAI_API_KEY`
     - `OPENAI_ENABLED`
     - `OPENAI_MODEL`
     - `OPENAI_POLISH_ENABLED`
   - Include notes about keeping OpenAI disabled by default.

2. Add smoke scripts
   - Suggested files:
     - `scripts/smoke_api.py`
     - `scripts/smoke_live_refresh.py`
   - Should test:
     - `/health`,
     - `/ask` with `llm_assist=false`,
     - `/ask` with `live_check=true` but avoid repeated runs,
     - `/ingest/live-refresh` for a small issue like `certificate`.

3. Real OpenAI API smoke test
   - Only if `OPENAI_API_KEY` is provided.
   - Confirm query expansion/rerank/polish metadata.
   - Confirm fallback if polish changes citations.

4. Real KMU live refresh smoke test
   - Use low max pages.
   - Respect cooldown.
   - Check `network_success`, `fallback_used`, `network_failed`, `failed_urls`.

5. Protect admin endpoints
   - `/ingest/run` and `/ingest/live-refresh` are currently open.
   - Add a simple admin token header for non-local/public deployments.
   - Recommended env:
     - `ADMIN_API_TOKEN`
   - Keep local demo convenient if token is not set.

6. Add timing metadata
   - Add duration fields:
     - OpenAI expansion/rerank/polish duration,
     - live refresh duration,
     - total `/ask` duration.
   - Display in `ProcessingStatusPanel` or admin panel.

7. Browser QA
   - Start backend:
     - `uvicorn app:app --reload`
   - Start frontend:
     - `cd frontend && npm run dev`
   - Verify:
     - toggles,
     - source provenance badges,
     - processing status panel,
     - action blocked response,
     - admin manual live refresh.

8. Frontend polish
   - The app is functional but dense.
   - Keep it utilitarian, not marketing-like.
   - Avoid decorative cards inside cards.
   - Check narrow viewport wrapping for status badges and admin metrics.

## Caution Areas

- Do not let OpenAI generate new procedural facts.
- Do not let fallback live refresh overwrite network-backed chunks.
- Do not relax crawler delays/cooldowns.
- Do not crawl login-required ON국민/SWELL personal pages.
- Do not expose sensitive draft text if output privacy check fails.
- Keep Korean user-facing copy.

## Useful Commands

```bash
pytest
cd frontend && npm run build
uvicorn app:app --reload
cd frontend && npm run dev
```

For one-off API checks:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"졸업예정증명서 어디서 뽑아?","llm_assist":false}'
```

