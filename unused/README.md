# unused/ — 졸업센터 데모와 무관한 보관 코드 (삭제 아님)

> 2026-06-04 정리(계획: `docs/plans/cleanup_unused_plan.md`, codex 2라운드 검증 후 실행).
> **루트 = 졸업센터(메인 축) 관련만, 여기는 그 외 전부.**
> git mv로 이동해 이력 보존 — 복구는 `git mv unused/<것> <원위치>` 후 app.py 임포트 복원.

| 보관물 | 원위치 | 정체 | 비고 |
|---|---|---|---|
| `agent/`, `tools/`, `llm_client.py` | 루트 | **티어1** — 옛 캠퍼스라이프 `/ask`·`/actions` 파이프라인 | CLAUDE.md 재설계 개요의 제거 대상 |
| `legacy_app_with_ask.py` | `app.py` | 슬림화 전 app.py 전체본(1075줄) | /ask·/actions·/ingest·/sources 라우트+텔레메트리 원본 참조용 |
| `crawler/`, `ingestion/`, `retriever/` | 루트 | **티어2** — 공식 소스 수집·검색 인프라 | **동결 보존**(두 번째 주제 재사용 후보). **보관 전용 — repo root에서 직접 실행 불가**(crawler↔ingestion 상호 absolute import — 복구 시 셋을 묶음 원위치). 데이터(`data/raw·processed·vector·state`)는 루트 그대로 — `graduation_center/service.py:296`이 `data/processed/chunks.jsonl`을 런타임에 읽음 |
| `crawl_notice.py`, `probe_notice_*.py` | `scripts/` | 티어2 크롤러 보조 스크립트 | 〃 |
| `tests_tier1/` (18종) | `tests/` | 티어1·2 테스트 | pytest 수집 경로 밖. 복구 시 `tests/conftest.py`의 `_isolate_llm_usage_log`·`usage_log_path` fixture(제거됨 — git 이력 참조)도 함께 복원 |
| `prototype_test/` | `test/`(단수) | 졸업RAG 독립 프로토타입(요람 PDF·로컬 .env 포함, ~18MB) | `graduation_center/`로 제품화되기 전 버전. `scripts/build_graduation_index.py`의 요람 PDF 경로가 이 폴더를 가리킴 |
| `frontend_components/AdminDashboard.jsx` | `frontend/src/components/` | `/ingest` 관리 UI | 백엔드 라우트 정리로 비활성 |

## 이동하지 않은 것 (주의)

- **`kmu-career-agent/`** — 팀원 작업(HITL 학업·커리어 에이전트 뼈대, 두 번째 주제 후보). 미관여.
- **v1 졸업센터** (`graduation_center/service.py` 등 + `/graduation/*` 8개 task 라우트) — 동작 기능·회귀 테스트(`test_graduation_*` 3종) 연결, 유지.
- **`data/` 전체** — 티어2 데이터 동결 + v1 런타임 의존(위 표 참조). 절대 이동 금지.
- **`frontend/src/App.jsx`의 옛 RPG 채팅 UI와 그 전용 컴포넌트**(SourcePanel·ProcessingStatusPanel·QuestBoard·CampusMap 등) — `/ask`·`/actions` fetch가 App.jsx에 내장돼 있어 파일 단위 이동 불가(추출 리팩터 필요). 기본 화면은 GraduationV2라 데모 무영향이나 **해당 UI를 열면 404** — 프론트 파트가 정리 시 이 폴더로 추출 권장.

## 복구 절차

- 티어1: `agent/`+`tools/`+`llm_client.py`+`tests_tier1/*` 원위치 + `legacy_app_with_ask.py`의 라우트·임포트·요청모델·텔레메트리를 app.py에 이식 + conftest fixture 복원.
- 티어2: `crawler/`+`ingestion/`+`retriever/`+크롤러 스크립트 **묶음** 원위치 + `/ingest`·`/sources` 라우트 이식.
