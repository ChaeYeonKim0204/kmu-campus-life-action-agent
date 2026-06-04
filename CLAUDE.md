# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> ⚠️ **재설계 진행 중 (branch `feat/agentic-redesign-kcy`).** 교수 피드백 반영으로 방향을 전환했다: 캠퍼스라이프 `/ask` 곁다리 기능을 걷어내고 **졸업센터(졸업사정 컨설팅)를 메인 축**으로, 더 **agentic(ReAct)** 하게 재구성한다. 아래 문서에서 "현재"는 코드에 실재하는 것, "목표/계획"은 이 브랜치에서 만들어 갈 것이다. `main` 브랜치는 옛 구조 그대로 보존돼 있으니 옛 동작을 보려면 `git switch main`. 자세한 제거 범위·근거는 `docs/second_topic_workflow_candidates.md` 및 codex 2차 검토(아래 *재설계 개요*)를 따른다.

## What this project is

국민대(KMU) 학생의 **졸업 요건을 분석해 컨설팅 보고서**를 내주는 grounded 에이전트다. 업로드한 성적증명서를 요약(학번 뒷자리만 마스킹)으로 만들고, 공식 요람·규정을 RAG로 근거 삼아, 학생 **개인 데이터**에 기반한 졸업 진단·대체경로·학기별 액션플랜을 **결정론적 보고서** 형태로 제시한다. 여기에 졸업센터(RAG)와 **다른 워크플로우 archetype을 가진 두 번째 주제** 1개를 더해 "학교생활 도우미" 틀을 채운다(주제 미정 — `docs/second_topic_workflow_candidates.md` 참고). 사용자 노출 문자열은 한국어; 따로 지시 없으면 한국어 유지.

차별점(왜 상용 LLM이 아니라 이걸 써야 하나)을 코드로 증명하는 게 목표다: ① 공식 요람·규정 grounding(환각 차단) ② 상용 LLM이 못 보는 **개인 DB(성적표·학적)** ③ 결정론적 보고서 산출 ④ ReAct로 *도구를 골라 쓰는* 에이전트적 동작.

This is a course **team project**; the professor's grading rubric below is a binding design constraint — build to it and self-evaluate against it (presentation 2026-06-09, ≤15 min incl. live prototype demo).

**범위 = 프로토타입 (교수 명시):** 프로덕션 수준의 견고함(전체 라이브 크롤·스케일·모든 학과/엣지케이스 커버·운영 안정성)은 **목표가 아니다.** 발표 데모에서 매끄럽게 돌아가는 **happy path를 정형성 있게** 보여주면 된다. 구체적 함의: ① 데이터는 준비된 **seed/canned**로 충분 — 티어2 라이브 크롤 파이프라인을 새로 돌릴 필요 없음(동결 유지가 더 정당). ② 졸업센터 ReAct·컨설팅 보고서와 두 번째 주제는 **시연 가능한 좁은 슬라이스**로 구현(모든 케이스 X). ③ 단 "프로토타입 = 대충"이 아니다 — 위 루브릭(정형성·품질·결정론)은 그대로 적용되니 **좁되 매끄럽게**. 새 작업의 범위를 잡을 때 "이게 데모를 좋게 만드는가, 아니면 프로덕션 견고함에 과투자하는가"를 먼저 따진다.

## 평가 기준 = 설계 제약 (build & self-evaluate against this)

- **워크플로우 노드 분절 + 시각화** — 업무를 discrete node로 나눠 워크플로우로 표현한다. 복잡한 로직을 하나의 LLM 노드에 몰아넣지 말 것. **재설계 방향:** 졸업센터를 `parse → structured_check → 요람 RAG → (ReAct controller) → report build → validate` 노드로 구성한다. ReAct를 도입하되 **LLM은 "다음에 어떤 도구를 쓸지"만 추론**(Thought→Action 선택)하고, 실행(Action)은 **결정론적 도구 노드**가 한다. LLM이 답변·보고서를 통째로 생성하는 방향은 루브릭에 역행한다. (→ *ReAct 가드레일* 절)
  - **교수가 Dify처럼 노드가 분기된 workflow를 눈으로 보는 걸 선호한다 — 데모에서 노드 그래프를 시각화하는 것이 채점 포인트.** 따라서 노드를 코드로만 나누지 말고, **각 노드 실행을 구조화된 trace로 방출**한다: `{node, status, branch_taken, input_summary, output_summary, (ReAct step·tool명·observation 요약)}`. 프론트가 이 trace로 Dify식 그래프를 그리고 데모에서 노드가 순서대로 점등되게 한다(시각화는 프론트 파트지만 **trace 데이터는 모델/백엔드 책임**). ReAct 루프도 "도구 선택 → 해당 노드 점등 → observation → 다음 분기"가 그래프 위에 보이도록 trace를 설계할 것.
- **데이터 관리** — 사용자 입력 양식을 구체적으로 정의하고(성적표 → `TranscriptSummary`, 과제별 입력 슬롯), 노드 간 데이터 흐름이 또렷할 것(앞 노드 출력이 뒤 노드에서 실제로 쓰이고 추적 가능). 개인 DB를 쓸수록 프라이버시 가드(아래)를 더 강하게.
- **결과의 정형성·품질** — 출력이 즉시 업무에 쓸 수 있는 수준일 것: 텍스트 나열이 아니라 **섹션형 컨설팅 보고서**(현황진단 / 부족요건 / 대체경로 시나리오 / 학기별 액션플랜 / 근거) + citation. LLM 출력의 무작위성을 통제해(결정론적 조립·구조화 출력·낮은 temperature) 매번 일관된 결과를 낼 것 — 교수가 구두로 강조한 포인트.
- **실무 유용성·문제 해결력** — 실제 학생 경험 개선에 기여하는가. 상용 LLM 대비 필요성이 드러나는가.

새 기능이나 추가 LLM 사용을 설계할 때 위 4개 기준에 비춰 판단한다.

## 재설계 개요 (제거 범위 + 순서)

곁다리(캠퍼스라이프 `/ask` 파이프라인)와 메인 축(졸업센터)을 분리해 3티어로 정리한다. codex 2차 검토 반영:

- **티어1 — ✅ 정리 완료 (2026-06-04, `unused/` 보관):** `agent/`, `tools/`, `llm_client.py`, `app.py`의 `/ask`·`/actions/*` 라우트와 관련 헬퍼, 테스트 18종 — 전부 `unused/`로 git mv(이력 보존, 슬림화 전 app.py 전체본은 `unused/legacy_app_with_ask.py`). 복구 절차는 `unused/README.md`.
- **티어2 — ✅ 노출 종료·코드 보관 (2026-06-04):** `crawler/`, `ingestion/`, `retriever/`는 `unused/`로 이동(삭제 아님 — 상호 import라 묶음 보관, 두 번째 주제 시 묶음 복구), `/ingest/*`·`/sources` 라우트 제거. **`data/raw·processed·vector·state`는 루트 유지** — `graduation_center/service.py`가 `data/processed/chunks.jsonl`을 런타임에 읽는다.
- **티어3 — 유지 (메인 축):** `graduation_center/`, `data/graduation/`, `/graduation/*`, `/health`, `/`(정적), `tests/test_graduation_*`.

**선행 의존 이관 (중요):** `graduation_center/service.py:_official_policy_sources()`가 `data/processed/chunks.jsonl`(티어2 데이터)을 **직접 읽는다**(early_graduation·credit_drop 공식 근거용). 졸업센터는 import 레벨에선 독립이지만 이 **런타임 파일 의존**이 있으므로, 티어2 데이터를 건드리기 전에 해당 정책 chunk를 `data/graduation/policies.json`으로 이관하고 이 함수를 고쳐야 근거가 조용히 빠지지 않는다.

**권장 순서:** ① 위 chunks.jsonl 의존 이관 → ② `app.py`를 졸업센터 전용으로 슬림화(`/ask`·`/actions`·일반 `/ingest`·`/sources` 제거 or flag) → ③ (프론트 파트) 첫 화면을 졸업센터 중심으로, 기존 채팅/퀘스트/Admin ingest 숨김 → ④ `graduation_center`에 ReAct controller 추가 → ⑤ 두 번째 주제 확정 후 티어2 재사용 vs 삭제 결정. **프론트는 `/ask`·`/actions/start`·`/ingest/run`에 강결합돼 있어, 백엔드만 지우면 데모 첫 화면이 깨진다 — 프론트 정보구조 전환과 함께 진행할 것.**

## Commands

Backend (FastAPI):
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8001   # frontend dev expects the API on 8001
```
The frontend dev build hardcodes the API base as `http://127.0.0.1:8001` (`frontend/src/App.jsx`), so run the backend on `--port 8001` when developing against the Vite dev server. Bare `uvicorn app:app --reload` listens on 8000, which the served-from-dist deployment uses (it calls `window.location.origin`). 실행 환경은 conda `kmu-agent`(3.11).

Frontend (Vite + React):
```bash
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173
cd frontend && npm run build                # builds frontend/dist; FastAPI serves dist/index.html at / and mounts dist/assets at /assets when present
```

Tests:
```bash
pytest                                       # tests/conftest.py injects repo root onto sys.path
pytest tests/test_graduation_center.py       # 졸업센터 단위 테스트
```
`tests/` (plural) is the real pytest suite — 정리(2026-06-04) 후 잔존 6종: `test_graduation_*` 3종(졸업센터 회귀) + `test_v2_*` 3종(v2 파이프라인·해설·상담 Agent). 티어1·2 테스트 18종은 `unused/tests_tier1/`에 보관(수집 경로 밖). 옛 `test/` (singular) graduation-RAG 프로토타입은 `unused/prototype_test/`로 이동 — `scripts/build_graduation_index.py`의 요람 PDF 경로가 그곳을 가리킨다.

There is no linter or formatter wired into the repo.

## Architecture

### Graduation center (졸업센터) — 메인 축

`graduation_center/`는 자체 `/graduation/*` 엔드포인트를 가진 독립 서브시스템이다(`/graduation/status`, `/transcript/parse`, `/audit`, `/substitute-courses`, `/micro-degree`, `/post-graduation-checklist`, `/career-translator`, `/early-graduation`, `/customized-major`, `/credit-drop`).

**현재 흐름:** 업로드한 성적증명서 PDF → `TranscriptSummary`(`graduation_center/parser.py`) → `compute_structured_check`(`data/graduation/graduation_requirements.json` 대조) → 요람 RAG(자체 Chroma `data/graduation/chroma`) → GPT 분석(`service._call_llm`) → **학번 뒷자리만 마스킹**한 뒤 반환. 출력 보고서는 `G1`/`G2` citation 체계를 쓴다(`service._build_answer`).

**전제조건:** 졸업센터는 `/ask`와 달리 OpenAI + 인덱싱된 요람 Chroma를 **요구**한다. 없으면 keyword-only로 degrade하지 않고 `GraduationServiceUnavailable`을 던지며 `app.py`가 HTTP 503으로 매핑한다.

**프라이버시(최소 적용):** 입력이 학생 본인의 성적증명서라 주민번호가 없으므로, 본인이 올린 성적·GPA·과목은 자문 보고서에 **그대로 활용·표시**한다. 출력에서 **학번 뒷자리만 마스킹**(예: `2020XXXX`)하면 된다 — 자세한 결정·코드 정리 방향은 *Guardrails* 절 참고.

**의존 주의:** `_official_policy_sources()`(service.py)가 `data/processed/chunks.jsonl`을 직접 읽는다 — *재설계 개요*의 선행 이관 참고.

**목표 (이 브랜치에서 구축):**
- 직선 파이프라인 → **ReAct controller** 도입. LLM이 갭을 보고 *필요한 도구만 골라 반복 호출*(compute_check / 요람 RAG / 대체과목·마이크로디그리 탐색 / 학점 갭 계산).
- 출력을 **섹션형 컨설팅 보고서**로(현황진단·부족요건·대체경로 시나리오·학기별 액션플랜·근거).

### 두 번째 주제 — 미정 (RAG와 다른 workflow)

졸업센터(RAG=검색·근거제시)와 **대비되는 워크플로우 archetype** 1개. 후보: 플래닝/최적화형(제약충족), 능동·상태형(event-driven), what-if 시뮬형. 비교·다이어그램은 `docs/second_topic_workflow_candidates.md`. 팀 확정 후 본 문서에 구조를 채운다.

### 제거 대상 (옛 `/ask` 파이프라인 — 티어1)

> 아래는 `main`에 남아있는 옛 구조이며 이 브랜치에서 걷어내는 중이다. 참고용으로만 둔다.

`app.py`의 `POST /ask`가 `guard.inspect_privacy → classifier.classify_issue → (llm_client.expand) → (live_refresh) → retriever.HybridRetriever.search → (llm_client.rerank) → guard.require_sources → planner.suggest_actions → answer_builder.build_final_answer(checklist/contact_router/deadline/citation) → (llm_client.polish) → answer_validator` 순으로 돌던 캠퍼스라이프 Q&A 파이프라인. `/actions/start`·`/actions/continue`는 `document_drafter`로 문서를 초안하던 별도 상태머신. 이들과 `agent/`, `tools/`, `llm_client.py`가 티어1 제거 대상이다.

## ReAct 가드레일 (도입 시 필수)

ReAct를 잘못 잡으면 "노드 분절·결정론" 루브릭과 정면 충돌한다. controller를 추가할 때 다음을 반드시 지킨다(codex 검토 반영):

- **LLM은 `next_tool`만 고른다** — 답변·보고서 본문을 LLM이 생성하지 않는다. 최종 보고서는 결정론적 builder가 조립한다.
- **tool allowlist** — 호출 가능한 도구를 명시적으로 제한. 임의 코드/네트워크 금지.
- **구조화 출력(JSON schema)** — controller의 매 step 출력은 schema 강제(도구명 enum + 인자).
- **max step budget** — 무한 루프 방지 상한.
- **deterministic tool execution** — 도구 자체는 결정론적 노드(낮은 temp·고정 로직).
- **observation sanitization** — 도구 결과를 LLM에 다시 넣기 전 학번 뒷자리만 마스킹(최소 적용 — *Guardrails* 참고).
- **final report validator** — 최종 보고서의 citation 정합·출력 안전(학번 뒷자리 마스킹)을 재검증, 실패 시 안전 출력으로 폴백.
- **citation coverage check** — 모든 사실 줄에 근거 마커(내부 검증용; 화면 표시는 토글로 접음 — *Citation contract* 참고).
- **Thought 원문 비노출** — 추론 원문을 로그/화면에 그대로 드러내지 않는다(개인정보·환각 설명 누출 위험).

## Guardrails that must hold

These are project requirements, not preferences — see `project_plan.md` §7:

- **프라이버시 — 최소 적용 (2026-06 결정):** 입력은 학생 본인의 **성적증명서**라 주민번호가 없으므로 주민번호 마스킹은 비해당. 출력에서 **학번 뒷자리만 마스킹**한다(예: `2020XXXX`). 본인이 업로드한 성적·GPA·과목은 자문 도구 특성상 보고서에 **활용·표시 허용**. 따라서 기존의 GPA/성적/이메일/연락처 출력 마스킹, 입력측 차단(과거 `inspect_privacy`류), false-positive 유발 패턴은 **제거**한다(`graduation_center`의 `SENSITIVE_PATTERNS`를 학번 1종으로 축소). ⚠️ 데모·공유는 **본인 또는 더미 성적증명서**로 할 것 — 타인의 실제 증명서를 공개 화면에 띄우면 이름·성적이 노출된다. 다중 사용자/외부 배포로 가면 이 결정을 재검토.
- **근거 우선 + graceful degrade (2026-06 결정, 완화):** 공식 근거(요람·규정 RAG·정책 데이터)가 있으면 근거를 달아 단정적으로 답한다. 근거가 얇거나 없으면 **차단하지 말고** 일반 가이드를 주되 `※ 공식 출처 미확인 — 학과사무실/교무팀 확인 권장`처럼 확신도를 표시한다. "몰라요"로 회피하지 않되(루브릭 4: 실무 유용성), 근거 없는 내용을 근거 있는 것처럼 단정하지도 않는다. 과거의 hard-block(`require_sources`로 답 자체를 막던 방식)은 쓰지 않는다.
- Never auto-crawl post-login portals (ON국민, SWELL personal screens) or 에브리타임. Only the public sources tier-listed in the README. (티어2 크롤러를 동결·재사용하더라도 이 규칙과 `crawler/base.py`의 학교서버 보호 규칙 — 8~18s 딜레이, `max_pages_per_run`, `INGEST_COOLDOWN_SECONDS`, 조건부 GET, `_INGEST_LOCK` — 은 절대 완화 금지.)
- LLM 사용은 grounded·결정론 우선. 보고서 본문은 결정론적 builder가 source of truth이고, LLM 산출은 final validator가 citation/프라이버시 위반 시 되돌린다.

## Citation contract

졸업센터는 `G1`/`G2` 체계를 쓴다(`graduation_center/service.py:_build_answer`): 유니크 근거마다 `G1`, `G2`, … 라벨을 부여하고 보고서 본문의 사실 줄마다 해당 마커를 단다. 절차적·요건 주장에는 반드시 그것을 뒷받침하는 근거 마커를 붙이고, `[근거]` 블록에서 해소되게 한다 — validator와 테스트가 마커 해소를 검사한다. (옛 `/ask`는 `S1`/`S2` 체계를 썼고 `agent/citation.py`에 있었으나 티어1과 함께 제거된다.)

**표시 — 토글 (2026-06 결정):** 화면 기본 뷰에서는 `[G1]` 인라인 마커와 `[근거]` 블록을 **접어 숨기고**, "근거 보기" 토글로 펼친다 — 텍스트 덤프처럼 보이지 않는 컨설팅 보고서 룩을 위해(교수 피드백: "텍스트만 뿌리지 마라"). 단 **내부적으로는 마커를 계속 생성·검증**한다(grounding 무결성·validator·환각 차단). 즉 계약을 *없애는* 게 아니라 *표시만 접는* 것. (마커 숨김은 프론트 표시 레이어에서, 데이터·검증 레이어는 그대로.)
