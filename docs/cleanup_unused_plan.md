# 작업계획: 미사용 코드 정리 — 루트=졸업센터 / unused/=무관 보관 (rev.2)

> 상태: codex 라운드1 반영(MUST 2·SHOULD 3·NICE 2), 라운드2 확인 대기. **선행 시도의 교훈 반영**(2026-06-04 1차 시도를 계획·검증 없이 실행했다가
> conftest 전역 fixture의 llm_client import로 전 테스트 ERROR → git reset 원복. 본 계획은 그 사고 분석 포함).
> 원칙(사용자 지시): **삭제 금지 — `unused/` 폴더로 이동(보관)**. 루트에는 졸업센터 관련만 남긴다.

## 0. 범위·비범위

- **이동(→ `unused/`)**: 티어1(`agent/`, `tools/`, `llm_client.py`) · 티어2(`crawler/`, `ingestion/`, `retriever/`, `scripts/crawl_notice.py`·`probe_notice_*.py`) · 티어1·2 테스트 18종 · `test/`(단수, 졸업RAG 프로토타입 18MB) · `frontend/src/components/AdminDashboard.jsx` · 슬림화 전 `app.py` 사본(`unused/legacy_app_with_ask.py`).
- **불변**: `kmu-career-agent/`(팀원 작업 — 절대 미관여) · v1 졸업센터(`graduation_center/` 전체 + `/graduation/*` 라우트 — 동작 기능·회귀 테스트 연결) · **`data/` 전체**(티어2 데이터 동결 — `graduation_center/service.py:296`이 `data/processed/chunks.jsonl`을 런타임에 읽음 → CLAUDE.md 선행의존 경고 사항, 데이터는 절대 이동 금지) · `frontend/src/App.jsx`의 RPG UI 본체(내장 코드라 파일 이동 불가 — 프론트 파트 영역, AdminDashboard import/사용 2줄만 주석化).
- **티어2를 unused/로 옮기는 근거**: CLAUDE.md "동결=삭제 금지·노출 끄기"와 양립 — 이동은 삭제가 아니고(git mv, 이력 보존), 코드를 import하는 곳이 티어1 라우트·테스트뿐이라(조사 완료: graduation_center는 0건) 함께 이동하면 깨질 참조가 없다. 단 crawler↔ingestion↔retriever는 상호 absolute import라 **반드시 묶음 이동**(unused/ 안에서는 실행 불가 — 복구 시 묶음 원위치, README에 명시).

## 1. 실행 단계 (전부 repo 루트 절대경로 — 1차 시도의 cwd 함정 방지)

① `unused/` 생성 + `cp app.py unused/legacy_app_with_ask.py`(참조 보관)
② `git mv`: `agent/` `tools/` `llm_client.py` `crawler/` `ingestion/` `retriever/` → `unused/`; `test/` → `unused/prototype_test/`; `scripts/{crawl_notice,probe_notice_page,probe_notice_view}.py` → `unused/`; 테스트 18종(`test_actions·answer_validator·api_contract·app_live_check·citation·classifier·contact_router·deadline·demo_scenarios·guard·ingestion·intent_scope·live_refresh·llm_client·menu_parser·retriever·student_context·student_playbook`) → `unused/tests_tier1/`; `AdminDashboard.jsx` → `unused/frontend_components/`
③ **`tests/conftest.py` 수정 (1차 시도 사고 지점)**: `_isolate_llm_usage_log`·`usage_log_path` fixture 제거 — `monkeypatch.setattr("llm_client...", raising=False)`의 문자열 타깃이 모듈 import를 유발해 llm_client 이동 시 **전 테스트 ERROR**. 잔존 테스트 6종의 두 fixture 사용 0건 확인 완료(grep). `live_llm` 로직·`_isolate_explain`은 유지.
④ **`app.py` 슬림화**: 티어1 임포트(18-31·46-49행)·요청 모델(AskRequest~LiveRefreshRequest)·`retriever`/`llm_client` 인스턴스·`/ask`(485-)·`/actions/*`·`/ingest/*`·`/sources` 라우트·텔레메트리/메뉴 헬퍼 제거. **유지**: index·mounts·`_load_local_environment`(`test/.env` 항목만 제거 — test/ 이동)·v1 라우트 10종+`_graduation_analysis_response`·`_truthy_form_value`·v2 라우트 4종. `/health`는 `{status, graduation_center}`로 축소(레거시 `llm.enabled` 혼동도 해소 — 상담 e2e LOW). title "KMU Graduation Consulting Agent", version 0.2.0.
⑤ **`App.jsx` 최소 수정 2곳**: AdminDashboard import(4행)·사용부(1141행 부근 lab-section) 주석化. RPG UI의 `/ask`·`/actions` fetch는 잔존(숨김 화면 — 열면 404, README에 명시).
⑥ `unused/README.md`: 보관물↔원위치↔정체 표 + 복구 절차(**티어2는 상호 absolute import — crawler/base.py↔ingestion.parser, ingestion/pipeline.py↔crawler.* — 보관 전용·root 직접 실행 불가·복구 시 묶음 원위치**, codex 확인) + 불변 목록(kmu-career-agent·data/·v1).
⑦ **CLAUDE.md 갱신**: 재설계 개요의 "제거 대상/동결" 서술 → "정리 완료(unused/ 보관)" 반영, Tests 절의 티어1 테스트 **"19종"→"이동 18종·잔존 6종" 숫자 정정**(codex), `test/`(단수) 설명을 unused/prototype_test로 갱신.
⑧ **[codex MUST-1] `test/` 잔존 참조 2곳 갱신**: `scripts/build_graduation_index.py:17`의 요람 PDF 경로(`test/2025...pdf` → `unused/prototype_test/...pdf`, untracked 로컬 자산이라 폴더와 함께 이동됨) + `tests/test_graduation_real_e2e.py:29`의 `test/.env` 로드(`unused/prototype_test/.env`로 — 둘 다 경로 상수 1줄).
⑨ **[codex SHOULD] README.md 갱신**: `/health` 필드·`/ask`·`/actions/*`·`/ingest/*`·`/sources` 운영 문서를 "legacy — unused/ 보관" 표기 + 졸업센터 전용 API 표로 교체(484·721행 부근).
⑩ **[codex NICE] `.gitignore`**: `unused/prototype_test/*.pdf`·`.env`·`chroma_db/`·`index_stats.json` 패턴 추가(기존 `test/...` 패턴은 이동 후 무효 — 함께 갱신). untracked 로컬 자산이 status에 튀어나오는 것 방지.

## 2. 검증 (실행 직후, 전부 통과해야 커밋)

1. **[codex MUST-2 정정]** 기준 = 잔존 6종의 이동 전 베이스라인: 실행 직전 `pytest tests/test_graduation_center.py tests/test_graduation_8_tasks.py tests/test_graduation_real_e2e.py tests/test_v2_*.py`로 pass/skip 수를 측정·기록하고, 이동 후 `pytest tests/`가 **그 수치와 동일**해야 통과(18종 이동으로 전체 236은 당연히 감소 — 잘못된 기준이었음).
2. `python -c "import app"` + uvicorn 기동(:8077) → `/health`·`/graduation/v2/status` 200, 즉시 kill
3. `cd frontend && npm run build` 성공 (cwd 복귀 주의)
4. `git status` — 전부 R(rename)/M/A인지, 의도치 않은 D 없는지
5. 데모 경로 무영향 확인: GraduationV2가 호출하는 `/graduation/v2/*` 3종 라우트 잔존 grep

## 3. 리스크·롤백

- 발표 D-5에 구조 변경 — 위 검증 5종 + 커밋 1개로 원자화(`git revert` 1회로 전체 롤백 가능). 데모가 쓰는 코드 경로(graduation_center·v2 라우트·GraduationV2·WorkflowGraph)는 한 줄도 변경하지 않음.
- `frontend/dist`는 빌드 산출물(gitignore) — 데모가 dist 폴백을 쓸 수 있으므로 검증 3에서 재빌드.
- 알려진 잔존 결합(의도·codex SHOULD-2 수용): App.jsx RPG UI의 죽은 fetch(/ask·/actions)와 그 전용 컴포넌트(SourcePanel·ProcessingStatusPanel·QuestBoard 등)는 App.jsx에 내장 결합돼 있어 이번 범위에서 제외 — 기본 화면이 GraduationV2라 데모 무영향이며, **프론트 파트의 추출 리팩터 대상으로 unused/README에 명시**. `unused/` 내 코드는 import 불가 상태(보관 전용).

## 4. 커밋

단일 커밋 `chore: 졸업센터 외 미사용 코드 unused/ 보관 — 티어1 제거·티어2 노출 종료(app.py 슬림화)` — 이동(R)·app.py·conftest·App.jsx·README·CLAUDE.md 포함.
