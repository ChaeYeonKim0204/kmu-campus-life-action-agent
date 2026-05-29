# 작업 현황 및 폴더/파일 역할 정리 (팀원 공유용)

> **KMU Campus Life Action Agent** — 국민대 학생생활 관련 한국어 RAG 에이전트
> 작성일: 2026-05-19 / 대상 독자: 코드 배경이 없는 팀원 포함

---

## 0. 이 프로젝트가 한 줄로 무엇을 하는지

> "**국민대 학생이 학사·휴복학·수강신청·증명서·졸업·문의처에 대해 물어보면, 학교 공식 문서를 근거로 한국어 답변을 주고, 필요하면 출석인정신청서·휴학 체크리스트·문의문 초안까지 자동으로 만들어 주는 챗봇.**"

- 학생이 자연어로 묻는다: "예비군 훈련으로 결석했는데 어떻게 해요?"
- 시스템은 **국민대 학칙·학사안내·SWELL 등 공식 페이지**에서 미리 수집·인덱싱한 자료에서 근거 문단을 찾고
- 그 근거를 **`[S1]` 형태의 인용 마커**와 함께 9개 섹션의 정형 답변으로 조립한다
- 필요하면 학생에게 추가 정보를 묻고 (예: 결석일, 수업명) **출석인정신청서 초안**을 만들어 준다
- **개인정보(학번/주민/연락처/PW/성적)는 절대 받지 않는다** — 정규식으로 입력을 사전 차단한다

## 1. 핵심 용어집 (먼저 읽어주세요)

| 용어 | 의미 |
|------|------|
| **RAG** (Retrieval-Augmented Generation) | LLM이 마음대로 말하지 않고, 미리 모아 둔 문서를 검색해서 그걸 근거로 답하게 하는 방식. 환각(hallucination) 방지가 목적 |
| **Grounded** | 모든 답변 문장에 "어느 문서의 몇 번째 청크가 근거인지" 매핑되어 있는 상태 |
| **Chunk** | 크롤한 긴 문서를 의미 단위로 자른 작은 조각. 한 조각이 검색·인용의 최소 단위 |
| **`chunks.jsonl`** | 청크들이 한 줄에 하나씩 저장된 파일. **이 프로젝트의 검색 진실의 원천** |
| **Source tier** | 문서 신뢰도 등급 (1=학칙, 8=학생 게시판). 검색 점수가 같으면 **낮은 티어가 우선** |
| **Issue type** | 질문 분류 카테고리 10종 (attendance, leave_return, course_registration, certificate, graduation, schedule, contact, military, student_support, other) |
| **Citation (`[S1]`, `[S2]`)** | 답변 본문에 붙는 인용 마커. 마지막 `[근거]` 블록의 출처 목록과 1:1 매칭됨 |
| **Action** | 답변과 별개로 **서류 초안·체크리스트를 만들어 주는 작업**. 8종 정의됨 |
| **Slot** | 액션을 완성하기 위해 학생에게 추가로 물어볼 항목 (예: 결석일, 수업명) |
| **Vector / Chroma** | 의미 기반 검색을 위한 벡터 DB. 로컬에서 동작, 없어도 키워드 검색으로 대체 가능 |
| **Hybrid retriever** | 벡터 검색 + 키워드 검색을 합쳐서 더 정확한 검색을 만드는 컴포넌트 |
| **Guardrail** | "절대 하면 안 되는 일"을 강제하는 코드 (개인정보 차단, 근거 없는 답변 금지 등) |
| **LLM** (Large Language Model) | GPT 같은 거대 언어모델. **현재 이 프로젝트는 LLM 호출을 의도적으로 안 한다** — 답변은 결정론적 템플릿으로 조립됨 |

## 2. 현재까지 작업 완료 상태 (2026-05-19 기준)

| 영역 | 상태 | 비고 |
|------|------|------|
| 크롤링 어댑터 | **8개 소스 / 11개 문서** | 학칙·학사안내·학생지원·일정·공지·요람·조직도·SWELL |
| 인덱싱된 청크 | **46개** | `data/processed/chunks.jsonl` |
| 벡터 DB | **Chroma 로컬 인덱스** | 외부 모델 없이 SHA256 기반 64차원 결정론 임베딩 |
| 답변 파이프라인 | 완성 (9개 섹션 결정론 조립) | `[답변요약]/[해야할일]/[필요서류]/[신청경로]/[기한]/[문의처]/[다음행동]/[근거]/[주의]` |
| 액션 종류 | **8종** | 출석/휴학/복학/증명서/수강신청/졸업감사/이수계획/문의 |
| 가드레일 | 개인정보 5종 차단 + 근거 없으면 응답 금지 | `agent/guard.py` |
| API 엔드포인트 | **7개** | `/`, `/health`, `/ask`, `/actions/start`, `/actions/continue`, `/ingest/run`, `/sources` |
| 프런트엔드 | Vite + React SPA | Chat / ActionForm / Source / ToolLog / Admin 패널 |
| 테스트 | **pytest 18개 전부 통과** | `tests/test_*.py` 8개 파일 |
| LLM 연동 | **의도적 스텁 상태** | `llm_client.GuardedLLMClient.generate()` 가 `""` 반환 |
| 학사공지 크롤러 | 프로브 단계 | `scripts/` 의 Playwright 스크립트로 페이지네이션·본문 추출 디버깅 중 |

---

## 3. 전체 그림 — 시스템 아키텍처

```
┌────────────────────────────────────────────────────────────────────┐
│  사용자 (브라우저, http://127.0.0.1:5173)                          │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ 자연어 질문
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  React 프런트엔드 (frontend/)                                       │
│  ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌──────────────┐         │
│  │ChatPanel │ │ActionForm  │ │SourcePanel│ │AdminDashboard│         │
│  └──────────┘ └────────────┘ └───────────┘ └──────────────┘         │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTP (FastAPI)
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI 백엔드 (app.py)                                            │
│                                                                      │
│  /ask 요청 시:                                                       │
│    1. guard.inspect_privacy   → 개인정보 입력 차단                   │
│    2. classifier.classify_issue → 10개 카테고리로 질문 분류           │
│    3. retriever.search        → Hybrid (벡터+키워드) 검색            │
│    4. guard.require_sources   → 근거 없으면 차단                    │
│    5. planner.suggest_actions → 다음 행동 제안                       │
│    6. answer_builder          → 9개 섹션 답변 조립                   │
│         ├── checklist        (해야 할 일·필요 서류·신청 경로)         │
│         ├── contact_router   (문의처 부서·전화)                       │
│         ├── deadline         (한국어 날짜 파싱 + 기한 계산)            │
│         └── citation         (S1/S2 라벨 부착)                       │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ 검색
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  데이터 계층 (data/)                                                │
│  ┌─────────────────────┐    ┌────────────────────────┐              │
│  │ chunks.jsonl        │ ←  │ Chroma 벡터 인덱스      │              │
│  │ (검색의 진실 원천)   │    │ (의미 기반 가속기)       │              │
│  └─────────────────────┘    └────────────────────────┘              │
└──────────────────────────────▲─────────────────────────────────────┘
                               │ POST /ingest/run 으로 트리거
                               │
┌────────────────────────────────────────────────────────────────────┐
│  인제스션 파이프라인 (ingestion/ + crawler/)                         │
│                                                                      │
│  BaseCrawler (학교 서버 보호 규칙 강제):                              │
│    - 호스트별 8~18초 랜덤 지연                                       │
│    - 1회 실행당 최대 3페이지                                          │
│    - 실행 간 5분 쿨다운                                              │
│    - ETag/Last-Modified 조건부 GET (변경 없으면 304 → 스킵)           │
│    - 네트워크 실패 시 사전 정의된 fallback_text 사용                  │
│                                                                      │
│  → 8개 소스 어댑터 (kmu_rule, kmu_academic_guide, kmu_org 등)         │
│  → parser → chunker → chunks.jsonl 기록 → Chroma upsert              │
└────────────────────────────────────────────────────────────────────┘
```

## 4. 실제 사용 시나리오 — 데이터가 어떻게 흐르는가

### 시나리오 A. "예비군 훈련으로 결석했는데 어떻게 해요?"

| 단계 | 처리 | 결과 |
|------|------|------|
| 1 | 프런트엔드에서 `POST /ask`로 질문 전송 | — |
| 2 | `inspect_privacy()` | 학번·주민·연락처 등 정규식 매치 없음 → 통과 |
| 3 | `classify_issue()` | "예비군"·"훈련"·"결석" 키워드 매치 → `issue_type = "attendance"` (또는 military) |
| 4 | `retriever.search(query, issue_type)` | 키워드+벡터로 학칙 제303조, 학사안내(출석), 조직도(교무팀) 청크 매치 |
| 5 | `require_sources()` | 청크가 있으니 통과 |
| 6 | `suggest_actions()` | `draft_attendance_recognition_form` 액션 추천 |
| 7 | `build_final_answer()` | 9개 섹션 답변 조립, `[S1]` 인용 마커 부착 |
| 8 | 응답 반환 | 학생이 "출석인정신청서 작성" 버튼 누르면 액션 흐름 시작 |

답변 결과 형식 (실제 텍스트):

```
[답변 요약]
출석인정 관련 공식 근거를 확인했습니다. 예비군 훈련은 출석인정 신청
가능 사유에 해당할 수 있으며[S2], 사유 발생 7일 이내 신청서와 증빙
서류 제출이 필요합니다.[S1]

[해야 할 일]
1. 결석 사유 발생일과 대상 수업을 확인합니다.
2. 출석인정 신청서를 작성합니다.
...

[필요 서류]
- 예비군 소집통지서 또는 훈련필증
...

[신청 경로]
- 담당 교강사에게 직접 제출
...

[기한]
- 사유 발생 7일 이내

[문의처 추천]
- 출석·성적 문의: 교무팀 (02-910-XXXX)

[다음 행동]
- 출석인정신청서 초안 작성: 결석일·수업명을 받아서 초안을 만들어 드립니다.

[근거]
- [S1] 국민대학교 학사규정 - 출석/성적 관련 조항 / https://rule.kookmin.ac.kr/... / "…"
- [S2] 국민대학교 학사안내 - 출석인정 / https://... / "…"

[주의]
최종 처리는 국민대학교 공식 포털, 담당 부서, 학과사무실 또는 담당
교강사 확인이 필요합니다. 실제 개인정보나 로그인 정보는 입력하지 마세요.
```

### 시나리오 B. 학생이 "출석인정신청서 초안 작성" 버튼을 누르면

| 단계 | 처리 |
|------|------|
| 1 | `POST /actions/start { action_id: "draft_attendance_recognition_form" }` |
| 2 | 시스템이 6개 슬롯 질문을 반환: 결석일/사유/수업명/교강사명/증빙서류/제출예정일 |
| 3 | 학생이 폼을 채워서 `POST /actions/continue { action_id, slots }` |
| 4 | `inspect_privacy()` 가 슬롯 값들을 다시 검사 (학번 등 포함 시 차단) |
| 5 | `draft_action_document()` → `_attendance_document()` 가 템플릿에 슬롯 값을 채워 초안 텍스트 + 5단계 체크리스트 반환 |

### 시나리오 C. "내 학번은 20210123인데..." 라고 물으면

→ `inspect_privacy()` 가 `\b20\d{6,8}\b` 패턴에 매치 → `blocked=True` 로 즉시 차단.
응답: **"실제 학번, 성적, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력받지 않습니다. 가상 사례나 사용자가 직접 요약한 비식별 정보로만 안내할 수 있습니다."**

---

## 5. 폴더·파일 상세 (전체)

### 5.1 루트 파일

| 파일 | 역할 | 비개발자가 알아야 할 점 |
|------|------|--------------------------|
| `app.py` | FastAPI 서버 진입점. 7개 라우트 정의 | "서버를 실행하면 이 파일이 먼저 실행된다" |
| `llm_client.py` | LLM 호출 인터페이스 (현재 빈 문자열 반환) | "지금은 LLM을 안 쓰고 결정론 템플릿으로 답한다. 추후 모델 연결 지점" |
| `requirements.txt` | Python 의존성 (FastAPI, Pydantic, requests, BeautifulSoup4, ChromaDB, pytest) | `pip install -r requirements.txt` 만 실행하면 됨 |
| `README.md` | 일반 소개·실행법·소스 티어 설명 | 처음 보는 사람에게 보내는 문서 |
| `PROGRESS.md` | 진행 로그 (어디까지 했는지 일자별 메모) | 현재 진행 상태 확인용 |
| `STRUCTURE.md` | 폴더 맵 (모듈 단위 설명) | 이 문서의 축소판 |
| `project_plan.md` | 4주 MVP 계획서 (목표·범위·역할 분담) | 프로젝트 기획 문서 |
| `CLAUDE.md` | Claude Code 작업 시 지켜야 할 룰 (가드레일, 인용 계약) | AI 협업할 때만 의미 있음 |

### 5.2 `agent/` — 답변 생성 파이프라인 노드 6개

요청이 들어오면 이 폴더의 파일들이 **차례대로** 호출된다.

| 파일 | 무엇을 하는가 | 입력 | 출력 |
|------|---------------|------|------|
| `guard.py` | **개인정보 차단 + 근거 없으면 응답 금지** 강제. 5종 정규식(`student_id`, `resident_number`, `portal_password`, `grade_report`, `phone`) | 사용자 질문 텍스트 / 검색된 청크 목록 | `GuardResult(blocked, flags, message)` |
| `classifier.py` | 질문을 10개 카테고리 중 하나로 룰 기반 분류 | 질문 텍스트 | `{issue_type, confidence, scores}` |
| `planner.py` | 분류 결과 + 청크 메타데이터로 **다음 행동(액션)** 추천 | `issue_type`, 청크 목록 | `[{action_id, label, description}, ...]` |
| `answer_builder.py` | **9개 섹션 답변을 결정론적으로 조립**. checklist/contact/deadline/citation 도구를 호출 | 질문, `issue_type`, 청크 목록, 액션 목록 | `{answer, citations, checklist, contacts, deadline}` |
| `citation.py` | 청크별 고유 라벨 `S1`, `S2` 부여 + 본문에 `[S1]` 마커 삽입 | 청크 목록 | 라벨 사전 + 인용 목록 |
| `action_state.py` | **액션(서류 작성)의 상태 머신**. 슬롯이 부족하면 추가 질문, 다 채워지면 초안 작성 | `action_id`, 슬롯 dict, 청크 | `{status: needs_input \| completed, ...}` |

### 5.3 `retriever/` — 검색 엔진 3개

| 파일 | 역할 |
|------|------|
| `hybrid_retriever.py` | **상위 인터페이스**. 벡터 결과 + 키워드 결과를 `chunk_id` 기준 머지, 점수와 source_tier로 랭킹. `/ask` 와 `/actions/continue` 가 이걸 호출 |
| `vector_retriever.py` | Chroma DB 기반 의미 검색. **외부 LLM/임베딩 모델 없이** SHA256 해시 기반 64차원 벡터를 직접 만들어 사용 (학교 환경에서 외부 API 호출 없이 동작하는 게 목적). 초기화 실패해도 조용히 다운그레이드 |
| `keyword_retriever.py` | JSONL 파일을 메모리에 올려놓고 토큰 매칭으로 검색. 키워드 완전일치는 2배 가중, `issue_type` 일치는 +2, source_tier 낮을수록 보너스 |

> **왜 둘 다 두는가?** 벡터 DB가 깨지거나 안 떠도 키워드 검색만으로 답이 나가야 하니까. 학교 데모 환경 안정성 우선.

### 5.4 `tools/` — 답변 풍성하게 만들어 주는 도구 6개

`answer_builder.py` 가 이 도구들을 조합해서 답변의 각 섹션을 채운다.

| 파일 | 무엇을 만드는가 |
|------|----------------|
| `checklist.py` | "해야 할 일" 작업 목록 + "필요 서류" + "신청 경로". `issue_type` 별로 분기 |
| `contact_router.py` | "문의처 추천" — 청크에 있는 부서 연락처를 추출하고, 없으면 디폴트 부서 정보로 폴백 |
| `deadline.py` | 한국어 날짜("5월 15일", "2026-05-15") 파싱 + "사유 발생 N일 이내" 같은 규칙으로 마감일 계산 |
| `document_drafter.py` | **8종 액션의 초안 생성 엔진**. `ACTION_SCHEMAS` 에 슬롯 정의가 있고, 액션별 핸들러(`_attendance_document`, `_leave_checklist` 등)가 템플릿에 슬롯을 채워 넣음 |
| `graduation.py` | 졸업학점 부족분 계산 (현재 학점 vs 목표 학점). `graduation_audit` 액션에서만 호출됨 |
| `course_planner.py` | 졸업 부족분과 학생 관심사로 수강 방향 추천. `recommend_course_plan` 액션에서만 호출됨 |

#### 액션 8종 (`ACTION_SCHEMAS`) 한눈에 보기

| Action ID | 라벨 | 필요한 슬롯 |
|-----------|------|-------------|
| `draft_attendance_recognition_form` | 출석인정신청서 초안 작성 | 결석일, 사유, 수업명, 교강사, 증빙서류, 제출예정일 |
| `draft_leave_checklist` | 휴학 준비 체크리스트 | 휴학 유형, 대상 학기, 증빙서류(선택) |
| `draft_return_checklist` | 복학 준비 체크리스트 | 대상 학기, 현재 휴학 유형(선택) |
| `course_registration_checklist` | 수강신청/폐강 확인 체크리스트 | 대상 학기, 확인 내용 |
| `certificate_issue_guide` | 증명서 발급 경로 확인 | 증명서 종류, 사용 목적(선택) |
| `graduation_audit` | 졸업요건 간이 진단 | 현재 총학점, 전공학점, 목표 총학점, 목표 전공학점 |
| `recommend_course_plan` | 수강계획 방향 추천 | 관심 분야, 총학점 부족분, 전공학점 부족분 |
| `draft_contact_message` | 문의문 초안 작성 | 주제, 문의 부서(선택), 질문 요약 |

### 5.5 `ingestion/` — 크롤러가 가져온 문서를 청크로 만드는 파이프라인

| 파일 | 역할 |
|------|------|
| `pipeline.py` | **핵심 오케스트레이터**. `run_ingestion()` 이 크롤러를 디스패치 → content_hash 로 중복 제거 → chunks.jsonl 기록 → Chroma upsert. **300초(5분) 쿨다운** 강제 |
| `parser.py` | BeautifulSoup으로 HTML에서 script/style/nav/footer 제거하고 본문 텍스트만 추출 |
| `chunker.py` | 추출된 텍스트를 700자 이하의 단락 단위 청크로 자름 |
| `file_extractors.py` | 첨부파일 지원 상태 선언 (현재 PDF/DOCX만 인지, HWP/OCR은 추후) |

### 5.6 `crawler/` — 소스별 크롤링 어댑터 8개

**`base.py` 의 BaseCrawler 가 학교 서버 보호 규칙을 모든 어댑터에 강제한다:**
- 호스트별 **랜덤 8~18초 지연**
- 1회 실행당 **최대 3페이지** (`max_pages_per_run = 3`)
- 실행 간 **5분 쿨다운** (`INGEST_COOLDOWN_SECONDS = 300`)
- 모듈 레벨 `_INGEST_LOCK` 으로 **동시 실행 차단**
- `ETag` / `Last-Modified` **조건부 GET** (변경 없으면 304 → 재청크 스킵)
- 네트워크 실패 시 어댑터에 미리 정의된 **`fallback_text` 사용** + `used_fallback: true` 태깅

| 어댑터 파일 | 대상 | 소스 티어 | 페이지 수 |
|-------------|------|-----------|-----------|
| `kmu_rule.py` | 학칙 제303조 (출석·성적) | **1 (최우선)** | 1 |
| `kmu_academic_guide.py` | 출석·휴복학 가이드 | 2 | 2 |
| `kmu_student_support.py` | 증명서 발급 안내 | 3 | 1 |
| `kmu_schedule.py` | 휴복학·수강신청 일정 | 4 | 2 |
| `kmu_notice.py` | 2026-1 수강신청 공지 | 5 | 1 |
| `kmu_cradle.py` | 졸업 요람 | 6 | 1 |
| `kmu_org.py` | 학사·학생처 조직도 | 7 | 2 |
| `swell_public.py` | SWELL 공개 게시판 | 8 | 1 |

> **검색 점수가 같을 때는 티어 낮은(=더 공식적인) 청크가 위로 올라간다.**

### 5.7 `data/` — 데이터 저장소

| 하위 폴더 / 파일 | 역할 |
|---|---|
| `raw/` | 크롤러가 가져온 원본 HTML/JSON |
| **`processed/chunks.jsonl`** | **검색의 진실의 원천** — 한 줄에 청크 하나, JSON 형식. 메타데이터: `source_tier`, `issue_types`, `keywords`, `search_hints`, `application_path`, `required_documents`, `submit_to`, `contacts`, `schedule`, `deadline_rule`, `actions` |
| `processed/notices_crawled.jsonl` | `scripts/crawl_notice.py` 프로브 출력 |
| `vector/chroma/` | Chroma SQLite 인덱스 (의미 검색 가속용) |
| `vector_db/` | 대체 벡터 저장소 슬롯 (정리 필요) |
| `state/crawler_state.json` | 문서별 `content_hash` + `ETag`/`Last-Modified` 캐시 (조건부 GET용) |
| `actions/` | 액션 폼 스키마 정의 |

#### `chunks.jsonl` 한 줄 실제 예시 (학칙 청크)

```json
{
  "chunk_id": "rule_academic_303_001",
  "doc_id": "rule_academic_303",
  "title": "국민대학교 학사규정 - 출석/성적 관련 조항",
  "url": "https://rule.kookmin.ac.kr/lmxsrv/law/lawFullView.do?SEQ=303",
  "source_type": "university_rule",
  "source_tier": 1,
  "department": "교무팀",
  "issue_types": ["attendance", "course_registration", "grade"],
  "keywords": ["학사규정", "출석", "성적", "결시", "제도"],
  "search_hints": ["출석인정 제도 근거", "결석 성적 처리", "학사 규정 출석"],
  "text": "(여기에 본문 텍스트가 들어감)",
  "fetched_from_network": true,
  "used_fallback": false,
  "http_status": 200,
  "content_hash": "cbf14279...d764d5c6329-1"
}
```

> 이 메타데이터 필드들이 어디서 쓰이는지 알아 두면 유용:
> - `issue_types`, `keywords`, `search_hints` → 검색 점수
> - `source_tier` → 검색 결과 랭킹 동률 시 우선순위
> - `application_path`, `required_documents`, `submit_to` → 답변의 "신청 경로/필요 서류" 섹션
> - `contacts` → 답변의 "문의처" 섹션
> - `schedule`, `deadline_rule` → 답변의 "기한" 섹션
> - `actions` → 답변의 "다음 행동" 섹션

### 5.8 `tests/` — pytest 18개 (전부 통과)

| 파일 | 무엇을 검증하는가 |
|------|-------------------|
| `conftest.py` | repo 루트를 `sys.path`에 주입 (테스트가 `agent.*`, `tools.*` 임포트 가능하게) |
| `test_guard.py` | 학번·주민·PW·성적·연락처가 입력으로 들어오면 차단되는지 |
| `test_classifier.py` | "예비군 결석" → attendance, "휴학" → leave_return 등 분류 정확도 |
| `test_retriever.py` | "수강신청 완료 확인", "증명서" 질문 시 올바른 청크가 검색되는지 |
| `test_deadline.py` | 한국어 날짜("5월 15일") 파싱 + N일 이내 기한 계산 |
| `test_contact_router.py` | issue_type 별로 올바른 부서가 매핑되는지 |
| `test_actions.py` | 출석인정 액션의 슬롯 질문이 정확한지, 슬롯 채워지면 초안이 나오는지 |
| `test_ingestion.py` | 문서가 청크로 변환될 때 메타데이터가 보존되는지, 쿨다운 로직 |

### 5.9 `frontend/` — Vite + React SPA

- **스택**: Vite 5 + React 18.2 + 순수 CSS (TailwindCSS 등 없음)
- **빌드 산출물**: `npm run build` → `frontend/dist/` → FastAPI 가 `/` 와 `/assets`로 정적 서빙
- **개발 모드**: `npm run dev` → `http://127.0.0.1:5173` (백엔드는 `http://127.0.0.1:8000`)

| 컴포넌트 | 역할 |
|----------|------|
| `App.jsx` | 라우팅·전체 레이아웃 |
| `ChatPanel.jsx` | 사용자 질문 입력 → `POST /ask` → 답변 9개 섹션 렌더링 |
| `ActionForm.jsx` | 액션 시작 시 슬롯 질문 폼 → `POST /actions/start` → `POST /actions/continue` |
| `SourcePanel.jsx` | 검색된 청크와 인용 출처 노출 (S1, S2 매핑) |
| `ToolLogPanel.jsx` | classifier/retriever/guard/checklist/contact 같은 도구 호출 로그 표시 (디버깅·시연용) |
| `AdminDashboard.jsx` | `/health` 상태, `/ingest/run` 수동 트리거 |

### 5.10 `scripts/` — 학사공지 크롤러 프로브 3종 (Playwright 기반)

> ⚠ 이 스크립트들은 **본 파이프라인과 별개**의 실험·디버깅 용도. `data/processed/notices_crawled.jsonl`에 결과를 남김.

| 스크립트 | 용도 |
|----------|------|
| `crawl_notice.py` | 학사공지 페이지네이션을 워크하여 본문 추출, 옵션으로 `chunks.jsonl` 머지 |
| `probe_notice_page.py` | `?currentPageNo=N` 페이지네이션 동작 확인 |
| `probe_notice_view.py` | 공지 #11798 본문이 잘리는 문제 디버그 (`.view_cont`) |

---

## 6. API 레퍼런스 (백엔드 7개 라우트)

| 메서드 | 경로 | 요청 본문 | 응답 핵심 필드 |
|--------|------|-----------|----------------|
| GET | `/` | — | 데모 UI 또는 안내 메시지 |
| GET | `/health` | — | `status`, `keyword_chunks`, `vector_retriever_available`, `vector_indexed_count`, `last_ingest` |
| POST | `/ask` | `{question, student_context}` | `answer`, `issue_type`, `classification`, `tool_logs`, `sources`, `citations`, `next_actions`, `safety_flags` |
| POST | `/actions/start` | `{action_id}` | `{status, action_id, label, issue_type, missing_slots, questions, privacy_notice}` |
| POST | `/actions/continue` | `{action_id, slots}` | `{status, message, draft}` (개인정보 슬롯 들어오면 `status=blocked`) |
| POST | `/ingest/run` | `{source, limit, force_rebuild}` | `{network_success, chunks_written, vector_indexed, fallback_used, network_failed, failed_urls}` |
| GET | `/sources` | — | `{count, sources[]}` (전체 청크 덤프) |

---

## 7. 반드시 지켜야 할 가드레일 (협업 시 절대 깨면 안 됨)

`project_plan.md` §7 + `CLAUDE.md`의 규칙. **이 5개는 제품 요구사항** 이다.

1. **개인정보 절대 수집·반향 금지**: 학번, 주민번호, 연락처, 성적표 원본, 포털 ID/PW
   - 정규식은 `agent/guard.py:PRIVACY_PATTERNS` 가 유일한 진실의 원천
   - `/ask` 와 `/actions/continue` **둘 다** 이 검사를 통과해야 함
2. **근거 없는 절차 답변 금지**: `require_sources()`가 청크 없으면 무조건 차단
3. **로그인 필요 페이지 자동 크롤 금지**: ON국민 포털, SWELL 개인 화면, 에브리타임 등
4. **공개 페이지에도 학교 서버 보호 규칙 강제**: 8~18초 지연, 3페이지 캡, 5분 쿨다운
5. **LLM 도입 시에도 인용 마커 보존**: 검색된 청크만 소비, `cite(chunk, labels)` 부착 유지

---

## 8. 빠른 시작 가이드 (팀원이 처음 실행할 때)

### 8.1 백엔드 실행

```bash
pip install -r requirements.txt
uvicorn app:app --reload
# → http://127.0.0.1:8000
```

### 8.2 프런트엔드 실행 (별도 터미널)

```bash
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

### 8.3 첫 크롤·인덱싱 실행

```bash
# 백엔드가 떠 있는 상태에서
curl -X POST http://127.0.0.1:8000/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"source": "seed", "limit": 20}'

# 또는 프런트엔드 AdminDashboard에서 버튼 클릭
```

### 8.4 테스트

```bash
pytest                          # 전체
pytest tests/test_actions.py    # 특정 파일
pytest -k attendance            # 키워드로 필터
```

> 린터·포매터는 현재 wiring 안 되어 있음.

### 8.5 데모 질문 예시 (README 기준)

- "예비군 훈련으로 결석했는데 어떻게 해요?"
- "휴학하려면 어떻게 해요?"
- "졸업예정증명서는 어디서 발급해요?"
- "2026-1학기 수강신청 일정 알려주세요"
- "졸업까지 학점이 몇 학점 남았나 확인하고 싶어요"

---

## 9. 알려진 다음 단계 / 미해결 이슈

| 항목 | 상태 | 우선순위 |
|------|------|----------|
| 실제 LLM 모델 연결 (`llm_client.py`) | 스텁만 존재 | 중 — 결정론 템플릿으로도 데모는 가능 |
| HWP 첨부파일 / OCR 지원 | 미지원 선언만 (`file_extractors.py`) | 낮음 |
| 학사공지 본문 절단 (공지 #11798) | 디버그 중 (`scripts/probe_notice_view.py`) | 중 |
| `data/vector_db/` 와 `data/vector/` 중복 | 정리 필요 | 낮음 |
| 린터·포매터 도입 (ruff, black) | 미설정 | 낮음 |
| 실제 학생 5인 사용성 테스트 | 미진행 | 높음 |

---

## 10. 자주 묻는 질문 (팀원용)

**Q. LLM을 왜 안 쓰나요?**
A. 의도적 결정입니다. 학교 환경에서 외부 LLM API 호출 의존성을 만들지 않으려고, 답변을 **결정론 템플릿 + 검색된 청크**로 조립합니다. `llm_client.py` 에 인터페이스만 만들어 두었으니 추후 Ollama/Qwen 등을 같은 인터페이스로 끼울 수 있습니다.

**Q. Chroma 벡터 DB가 깨지면 답변이 안 나오나요?**
A. 나옵니다. `VectorRetriever` 가 초기화에 실패하면 `available=False` 로 조용히 다운그레이드되고, 키워드 검색이 단독으로 동작합니다. **검색의 진실의 원천은 `chunks.jsonl`**, Chroma 는 가속기일 뿐입니다.

**Q. 새 학교 페이지를 추가하려면?**
A. `crawler/` 에 새 어댑터 파이썬 파일을 만들고, `BaseCrawler` 를 상속해서 `source_type` + `pages: list[SourcePage]` 만 정의하면 됩니다. `ingestion/pipeline.py` 가 자동으로 디스패치합니다.

**Q. 답변에 인용 마커가 빠지면 안 되나요?**
A. 안 됩니다. 모든 절차적 사실 문장에는 `cite(chunk, labels)` 가 붙어 `[근거]` 블록의 출처와 매칭되어야 합니다. 인용이 없는 사실 문장은 PR 리뷰에서 거부합니다.

**Q. 개인정보 차단 정규식을 수정하려면?**
A. `agent/guard.py:PRIVACY_PATTERNS` 만 수정하세요. 다른 곳에서 별도 검사 로직을 만들면 안 됩니다 (이중 진실 방지).
