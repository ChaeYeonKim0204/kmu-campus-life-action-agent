# KMU 캠퍼스 생활 에이전트 — 신규 구축 기획 문서

> **문서 목적:** 팀 내부 작업 지시서 (처음부터 새로 구축)
> **작성일:** 2026-05-21
> **대상:** 프론트엔드 담당자 / 백엔드 담당자 / 에이전트·모델 담당자
> **버전:** v1.0

---

## 목차

1. [서비스 정의 & 구축 목표](#1-서비스-정의--구축-목표)
2. [아키텍처 & 기술 스택](#2-아키텍처--기술-스택)
3. [핵심 사용자 여정](#3-핵심-사용자-여정)
4. [역할별 구축 태스크](#4-역할별-구축-태스크)
   - 4-1. 프론트엔드 (FE)
   - 4-2. 백엔드 (BE)
   - 4-3. 에이전트·모델 (AG)
5. [역할 간 인터페이스 계약](#5-역할-간-인터페이스-계약)
6. [마일스톤 & 의존성 맵](#6-마일스톤--의존성-맵)

---

## 1. 서비스 정의 & 구축 목표

### 1-1. 무엇을 만드는가

국민대학교 학생이 캠퍼스 생활 관련 질문을 하면 **공식 문서를 근거로 한국어 답변**을 제공하고, 필요 시 **출석인정신청서 등 다음 단계 서류 초안**을 작성해주는 RAG 기반 에이전트 서비스.

**커버하는 질문 유형 (16개 이슈 카테고리)**

출석 인정 / 휴학·복학 / 수강신청 / 등록금 / 증명서 발급 / 학생증 / 장학금 / 포털·eCampus 접근 / 캠퍼스 시설 / 학적부 정정 / 학생보험 / 졸업요건 / 학사일정 / 문의처 안내 / 예비군·병무 / 수강계획

### 1-2. 왜 처음부터 새로 짓는가

기존 서비스에서 **UI/UX 전면 재설계**가 필요하다는 결론이 났고, 기존 코드에 덧대어 고치는 것보다 처음부터 깔끔하게 짓는 것이 낫다고 판단했다. 동시에 기존에 stubbed 상태였던 LLM을 처음부터 실제로 연결하여 답변 품질을 높인다.

**기존 서비스에서 가져올 자산 (레퍼런스)**

| 자산 | 활용 방법 |
|---|---|
| `data/processed/chunks.jsonl` | 초기 청크 데이터 — 새 파이프라인에서 재활용 |
| `agent/guard.py`의 `PRIVACY_PATTERNS` | 개인정보 차단 패턴 — 새 구현의 레퍼런스 |
| `agent/classifier.py`의 `ISSUE_KEYWORDS` | 이슈 분류 키워드 — 새 분류기 레퍼런스 |
| `crawler/` 8개 파일 | 공식 출처 URL 목록과 fallback_text — 새 크롤러 레퍼런스 |
| `tools/document_drafter.py`의 `ACTION_SCHEMAS` | 신청서 슬롯 스키마 — 새 액션 플로우 레퍼런스 |

### 1-3. 이번 구축 범위 외

- 학생 로그인·인증 (개인 맞춤 이력 저장)
- 모바일 앱
- 다국어 지원

---

## 2. 아키텍처 & 기술 스택

### 2-1. 전체 구조

```
[사용자 브라우저]
      ↕  HTTP/JSON
[FastAPI 서버]
  ├─ /ask          → Agent Pipeline
  ├─ /actions/*    → Action State Machine
  ├─ /health       → 상태 확인
  └─ /admin/*      → 관리자 전용 (인증 필요)
         ↕
[Agent Pipeline]
  Guard → Classifier → Retriever → Planner → LLM → Answer Builder
         ↕                   ↕
    [LLM API]          [Vector DB + JSONL]
         ↕
[Data Pipeline]
  Crawler → Parser → Chunker → Indexer
```

### 2-2. 기술 스택

| 레이어 | 기술 | 비고 |
|---|---|---|
| **프론트엔드** | React 18 + TypeScript | Vite 빌드 |
| **UI 라이브러리** | shadcn/ui + Tailwind CSS | 컴포넌트 기반 |
| **상태 관리** | TanStack Query | API 캐싱 및 로딩 상태 |
| **백엔드** | FastAPI (Python 3.11) | pydantic-settings로 환경변수 관리 |
| **프로덕션 서버** | Gunicorn + Uvicorn workers | |
| **LLM** | Claude API (Anthropic) | 쿼리 확장 / 재랭킹 / 답변 polish |
| **벡터 DB** | ChromaDB | 로컬 persistent 모드 |
| **컨테이너** | Docker + docker-compose | |
| **CI** | GitHub Actions | pytest 자동 실행 |

### 2-3. 폴더 구조 가이드라인

```
project-root/
├── frontend/                  # FE 전담
│   ├── src/
│   │   ├── components/        # UI 컴포넌트
│   │   ├── pages/             # 라우트별 페이지 (/, /admin)
│   │   ├── hooks/             # 커스텀 훅 (useAsk, useAction)
│   │   ├── api/               # API 통신 레이어
│   │   └── types/             # TypeScript 타입 정의
│   └── ...
│
├── app/                       # BE 전담
│   ├── main.py                # FastAPI 진입점
│   ├── config.py              # pydantic-settings 환경변수
│   ├── routers/               # 엔드포인트별 라우터
│   ├── middleware/            # CORS, 로깅, 인증
│   └── schemas/               # Pydantic 요청/응답 모델
│
├── agent/                     # AG 전담
│   ├── guard.py
│   ├── classifier.py
│   ├── planner.py
│   ├── answer_builder.py
│   ├── citation.py
│   └── action_state.py
│
├── retriever/                 # AG 전담
├── tools/                     # AG 전담
├── crawler/                   # AG 전담
├── ingestion/                 # AG 전담
├── llm_client/                # AG 전담 (실제 LLM 연결)
│
├── data/                      # 공유 (gitignore 일부)
├── tests/                     # 공유
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 3. 핵심 사용자 여정

> FE·BE·AG 세 담당자가 **같은 화면을 목표로** 작업하기 위한 공통 기준선.

### 여정 A — 질문 → 답변

```
진입    서비스 첫 화면 로드
         └─ 질문 입력창에 자동 포커스

입력    질문 작성 (예: "수강신청 기간이 언제야?")
         └─ [선택] 학생 상태 설정 펼치기 (기본 접힘)

제출    질문 버튼 클릭

대기    처리 단계 순차 표시
         이슈 분류 중... → 공식 자료 검색 중... → 답변 생성 중...

결과    답변 카드 렌더링 (5종)
         ┌─ [요약] 핵심 답변 + 근거 출처 [S1]    ← 항상 펼침
         ├─ [체크리스트] 해야 할 일 N개
         ├─ [기한] 날짜·일정 (있는 경우)
         ├─ [문의처] 담당 부서 + 연락처
         └─ [근거 출처] 공식 문서 링크           ← 기본 접힘

후속    다음 행동 버튼 → 여정 B 진입
```

**화면 요구사항**
- 질문 입력창 : 화면 상단 고정, 진입 시 자동 포커스
- 학생 상태 설정 : Accordion (기본 접힘, 설정값 있으면 헤더에 요약 표시)
- 로딩 : 단계별 텍스트 순차 전환
- 에러 : "잠시 후 다시 시도해주세요. 급한 문의는 [학교 공식 포털](https://www.kookmin.ac.kr)을 이용해주세요."
- 개인정보 차단 : 붉은 인라인 메시지 (차단 이유 한 줄)

---

### 여정 B — 신청서 초안 작성

```
진입    여정 A 답변 화면의 [다음 행동] 버튼 클릭
         예: "출석인정신청서 작성하기"

슬롯    필요 항목 채팅 형식으로 한 개씩 표시
         예: "결석 날짜는 언제인가요?" → "사유를 선택해주세요."
         ※ 학번·주민번호·성적 입력 시 즉시 인라인 차단

초안    완성된 신청서 초안 렌더링
         └─ 사용된 공식 근거 출처 표시

완료    [복사하기] 버튼 + 면책 고정 문구
         "이 초안은 참고용입니다. 제출 전 담당 부서에 확인하세요."
```

---

## 4. 역할별 구축 태스크

> **태스크 크기:** 1~2일 이내 완료 단위
> **우선순위:** P1 (다른 역할 블로킹) / P2 (MVP 필수) / P3 (MVP 이후)
> **완료 기준(DoD):** 각 태스크마다 명시된 조건을 충족해야 완료로 인정

---

### 4-1. 프론트엔드 (FE)

#### FE-001 | 프로젝트 초기 설정

| | |
|---|---|
| **설명** | Vite + React 18 + TypeScript 프로젝트 생성. Tailwind CSS, shadcn/ui, TanStack Query 설치. ESLint + Prettier 설정. `VITE_API_URL` 환경변수 구조 잡기 |
| **완료 기준** | `npm run dev` 실행 시 빈 화면 정상 로드. `npm run build` 성공. `.env.example`에 `VITE_API_URL` 명시 |
| **우선순위** | P1 |
| **의존성** | 없음 |

---

#### FE-002 | API 통신 레이어

| | |
|---|---|
| **설명** | `src/api/` 폴더에 `/ask`, `/actions/start`, `/actions/continue`, `/health` 호출 함수 작성. TypeScript 타입 정의 포함. 응답 에러 코드(`privacy_blocked`, `no_source`, `server_error`) 분기 처리 |
| **완료 기준** | 각 API 함수 호출 시 정상/에러 응답 타입 추론 가능. Mock 서버 또는 실제 백엔드와 통신 테스트 통과 |
| **우선순위** | P1 |
| **의존성** | BE-004 (API 응답 스키마 확정) |

---

#### FE-003 | 레이아웃 & 기본 화면 구조

| | |
|---|---|
| **설명** | 전체 레이아웃 구성. 상단 헤더 / 메인 채팅 영역 / 우측 정보 패널(다음 행동, 출처). 반응형 고려(최소 너비 360px). 라우터 설정(`/` 학생 화면, `/admin` 관리자 화면) |
| **완료 기준** | `/` 접속 시 레이아웃 정상 렌더링. `/admin` 접속 시 별도 페이지 렌더링. 모바일(375px) 기준 레이아웃 깨지지 않음 |
| **우선순위** | P1 |
| **의존성** | FE-001 |

---

#### FE-004 | 질문 입력 컴포넌트

| | |
|---|---|
| **설명** | 질문 텍스트 입력창 + 전송 버튼. 페이지 로드 시 자동 포커스. Enter 키 전송(Shift+Enter 줄바꿈). 전송 중 버튼 비활성화 및 로딩 스피너 표시 |
| **완료 기준** | 텍스트 입력 후 전송 시 `useAsk` 훅 호출. 로딩 중 재전송 불가. 빈 입력 전송 방지 |
| **우선순위** | P1 |
| **의존성** | FE-002, FE-003 |

---

#### FE-005 | 학생 상태 설정 Accordion

| | |
|---|---|
| **설명** | "학생 상태 / 대상 학기 / 관심 항목" 설정을 Accordion UI로 구성. 기본 접힘. 설정값이 있으면 헤더에 요약 표시 (예: "재학생 · 2026-1학기"). `/ask` 요청 시 `student_context` 필드에 포함 |
| **완료 기준** | 첫 진입 시 Accordion 접힘 상태. 학생 상태 선택 후 헤더 요약 텍스트 갱신. 설정값이 API 요청 body에 포함되는 것 확인 |
| **우선순위** | P2 |
| **의존성** | FE-004 |

---

#### FE-006 | 로딩 상태 컴포넌트

| | |
|---|---|
| **설명** | 질문 제출 후 처리 단계를 순차 텍스트로 표시. "이슈 분류 중..." → "공식 자료 검색 중..." → "답변 생성 중..." 각 단계 1.5초 간격 전환. 실제 응답 수신 시 즉시 답변 카드로 교체 |
| **완료 기준** | 3단계 텍스트가 순차 전환됨. 응답 수신 시 로딩 컴포넌트 unmount 확인 |
| **우선순위** | P2 |
| **의존성** | FE-004 |

---

#### FE-007 | 답변 카드 컴포넌트 (5종)

| | |
|---|---|
| **설명** | API 응답을 섹션별 카드로 렌더링. ① 요약 카드(항상 펼침, 인용 마커 [S1] 포함) ② 체크리스트 카드 ③ 기한 카드(deadline 없으면 숨김) ④ 문의처 카드 ⑤ 근거 출처 카드(기본 접힘, 클릭 시 펼침). 인용 마커 클릭 시 출처 카드로 스크롤 |
| **완료 기준** | 5종 카드 정상 렌더링. deadline 없을 때 기한 카드 미표시. 인용 마커 클릭 → 출처 카드 스크롤 동작 |
| **우선순위** | P2 |
| **의존성** | FE-002 |

---

#### FE-008 | 에러 상태 컴포넌트

| | |
|---|---|
| **설명** | 에러 코드별 메시지 분기. `privacy_blocked` → 붉은 인라인 경고 (차단 이유 표시). `no_source` → "공식 자료에서 관련 내용을 찾지 못했습니다. 담당 부서에 직접 문의해주세요." `server_error` / 네트워크 오류 → "잠시 후 다시 시도해주세요." + 포털 링크 |
| **완료 기준** | 3종 에러 케이스 각각에 맞는 UI 렌더링 확인. 백엔드 미실행 상태에서도 `server_error` 메시지 정상 노출 |
| **우선순위** | P1 |
| **의존성** | FE-002 |

---

#### FE-009 | 예시 질문 버튼

| | |
|---|---|
| **설명** | AG-011에서 제공하는 대표 질문 6개를 버튼으로 표시. 클릭 시 입력창에 자동 입력 후 전송. 개인정보 포함 질문 버튼 없음 |
| **완료 기준** | 6개 버튼 표시. 클릭 시 해당 질문으로 `/ask` 호출 및 정상 답변 반환 확인 |
| **우선순위** | P2 |
| **의존성** | AG-011 |

---

#### FE-010 | 신청서 작성 플로우 (여정 B)

| | |
|---|---|
| **설명** | 다음 행동 버튼 클릭 → `/actions/start` 호출 → 슬롯 입력 채팅 UI (한 개씩 순차 표시) → `/actions/continue` 호출 → 초안 렌더링. 개인정보 차단 인라인 표시. 완료 화면에 [복사하기] 버튼 + 면책 고정 문구 |
| **완료 기준** | 여정 B 전체 플로우 E2E 동작. 복사 버튼 클릭 시 클립보드에 초안 텍스트 저장. 면책 문구 항상 노출 |
| **우선순위** | P2 |
| **의존성** | FE-007, BE-006 |

---

#### FE-011 | 관리자 페이지 (/admin)

| | |
|---|---|
| **설명** | `/admin` 경로에 관리자 전용 페이지 구성. 기능: 청크 수 / Chroma 상태 / LLM 상태 확인, 수집·인덱싱 실행 버튼, 이슈별 최신 확인 드롭다운. Admin Token 입력 후 잠금 해제 방식 |
| **완료 기준** | 토큰 없이 기능 버튼 비활성화. 올바른 토큰 입력 후 수집 실행 API 호출 가능. 학생 화면(`/`)에는 관리자 UI 완전히 미노출 |
| **우선순위** | P2 |
| **의존성** | FE-003, BE-008 |

---

#### FE-012 | 프로덕션 빌드 & 정적 파일 서빙

| | |
|---|---|
| **설명** | `npm run build` → `dist/` 생성. FastAPI가 `dist/index.html`과 `dist/assets/`를 서빙하는 흐름 검증. `.env.production`에 실제 API URL 설정 |
| **완료 기준** | `docker compose up` 후 `/` 접속 시 프론트 UI 로드 및 질문 동작 확인 |
| **우선순위** | P2 |
| **의존성** | BE-009 |

---

### 4-2. 백엔드 (BE)

#### BE-001 | 프로젝트 초기 설정

| | |
|---|---|
| **설명** | FastAPI 프로젝트 구조 생성. `pyproject.toml` 또는 `requirements.txt` 의존성 정의. `pydantic-settings`로 환경변수 로드 (`config.py`). `.env.example` 작성. 필수 환경변수: `ALLOWED_ORIGINS`, `ADMIN_TOKEN`, `LLM_API_KEY`, `DATA_DIR` |
| **완료 기준** | `uvicorn app.main:app` 실행 성공. `.env` 누락 시 시작 시 명확한 오류 메시지 출력 |
| **우선순위** | P1 |
| **의존성** | 없음 |

---

#### BE-002 | FastAPI 앱 기본 설정

| | |
|---|---|
| **설명** | CORS 미들웨어 (`ALLOWED_ORIGINS` 환경변수 기반). 전역 예외 핸들러 (`HTTPException`, `Exception`). 요청 로깅 미들웨어 (요청 ID, 처리 시간). 정적 파일 서빙 (`frontend/dist/`) |
| **완료 기준** | 허용되지 않은 origin 요청 시 CORS 오류 반환. 처리되지 않은 예외 발생 시 표준 에러 JSON 반환 (500). 요청마다 로그에 요청 ID 포함 |
| **우선순위** | P1 |
| **의존성** | BE-001 |

---

#### BE-003 | 에러 응답 표준화

| | |
|---|---|
| **설명** | 모든 API 에러를 통일된 구조로 반환. 에러 코드 정의: `privacy_blocked`, `no_source`, `server_error`, `unauthorized`. 운영 환경에서는 `detail` 필드 생략 (보안) |
| **완료 기준** | 개인정보 차단 / 소스 없음 / 서버 오류 / 인증 실패 각각에 대해 표준 에러 JSON 반환 확인 |
| **우선순위** | P1 |
| **의존성** | BE-001 |
| **참고** | FE-002, FE-008이 이 결과물을 사용함. **1주차 목요일까지 FE와 공유 필요** |

---

#### BE-004 | API 응답 스키마 확정 및 공유

| | |
|---|---|
| **설명** | `/ask`, `/actions/start`, `/actions/continue` 응답 Pydantic 모델 작성. FE 담당자에게 공유하여 TypeScript 타입 정의 작성에 사용. Swagger UI(`/docs`)에서 자동 문서화 확인 |
| **완료 기준** | `/docs` 접속 시 3개 엔드포인트 응답 스키마 렌더링. FE 담당자 확인 및 승인 |
| **우선순위** | P1 |
| **의존성** | BE-001, BE-003 |
| **참고** | FE-002가 이 결과물을 기다림. **1주차 수요일까지 완료 목표** |

---

#### BE-005 | POST /ask 엔드포인트 구현

| | |
|---|---|
| **설명** | `/ask` 요청을 받아 AG 파이프라인 호출 후 응답 반환. 흐름: `inspect_privacy` → `classify_issue` → `retriever.search` → `require_sources` → `suggest_actions` → `build_final_answer`. `tool_logs` 포함 |
| **완료 기준** | 정상 질문에 대해 `answer`, `citations`, `next_actions`, `checklist`, `contacts` 포함 응답 반환. 개인정보 포함 질문 시 `privacy_blocked` 에러 반환 |
| **우선순위** | P1 |
| **의존성** | BE-003, BE-004, AG-001 ~ AG-006 완료 후 통합 |

---

#### BE-006 | POST /actions/start, /actions/continue 엔드포인트

| | |
|---|---|
| **설명** | 신청서 작성 2단계 엔드포인트 구현. `/actions/start`: action_id → 슬롯 목록 반환. `/actions/continue`: 슬롯값 개인정보 검사 → 청크 검색 → 초안 생성 |
| **완료 기준** | 여정 B 전체 플로우(start → continue 반복 → completed) API 레벨에서 정상 동작. 개인정보 포함 슬롯 입력 시 `privacy_blocked` 반환 |
| **우선순위** | P2 |
| **의존성** | BE-005, AG-007 |

---

#### BE-007 | GET /health 엔드포인트

| | |
|---|---|
| **설명** | 서비스 상태 반환. 포함 항목: `keyword_chunks` 수, `vector_available` 여부, `llm_status`, `last_ingest` 시간 |
| **완료 기준** | `/health` 응답에 4개 항목 포함. LLM API key 유효 여부 확인값 포함 |
| **우선순위** | P1 |
| **의존성** | BE-001 |

---

#### BE-008 | 관리자 엔드포인트 (인증 포함)

| | |
|---|---|
| **설명** | `/admin/ingest`, `/admin/live-refresh`, `/admin/sources` 엔드포인트 구현. Bearer 토큰 인증 (`ADMIN_TOKEN` 환경변수). 토큰 없으면 401 반환 |
| **완료 기준** | 토큰 없이 호출 시 401 반환. 올바른 토큰으로 인제스트 실행 및 결과 반환 확인 |
| **우선순위** | P2 |
| **의존성** | BE-002, AG-008 |

---

#### BE-009 | Docker 설정

| | |
|---|---|
| **설명** | `Dockerfile` 작성 (Python 3.11 slim 베이스, Gunicorn + Uvicorn workers). `docker-compose.yml`로 백엔드 + 볼륨 마운트(`data/`) 구성. `.env` 파일 주입 방식 |
| **완료 기준** | `docker compose up` 으로 서버 기동. `/health` 정상 응답. `data/` 볼륨 마운트로 청크 데이터 유지 확인 |
| **우선순위** | P2 |
| **의존성** | BE-001, BE-002 |

---

#### BE-010 | 구조화 로깅

| | |
|---|---|
| **설명** | Python `logging` 모듈로 통일. 로그 레벨: INFO(요청 처리), WARNING(소스 없음), ERROR(예외). 로그 항목: 요청 ID, issue_type, 처리 시간, LLM 사용 여부 |
| **완료 기준** | `/ask` 처리 시 구조화 로그 출력. ERROR 레벨 로그 별도 확인 가능 |
| **우선순위** | P2 |
| **의존성** | BE-002 |

---

### 4-3. 에이전트·모델 (AG)

#### AG-001 | LLM 클라이언트 구현 (실제 연결)

| | |
|---|---|
| **설명** | `llm_client/` 모듈 구현. Claude API (Anthropic SDK) 연결. 기능별 메서드: `expand_search_query()` (쿼리 확장), `rerank_chunks()` (청크 재랭킹), `polish_answer()` (답변 다듬기). API key 없거나 오류 시 graceful fallback (기존 비LLM 결과 유지) |
| **완료 기준** | API key 설정 후 3개 메서드 호출 시 실제 LLM 응답 반환. API key 없으면 fallback 모드로 동작 (오류 없이) |
| **우선순위** | P1 |
| **의존성** | 없음 |

---

#### AG-002 | Privacy Guard 구현

| | |
|---|---|
| **설명** | 입력 텍스트에서 개인정보 탐지. 차단 패턴: 학번, 주민번호, 포털 비밀번호(실제 제공 시), 성적 원본, 연락처. 레퍼런스: 기존 `agent/guard.py`의 `PRIVACY_PATTERNS`. 오탐 방지 로직 포함 (예: "비밀번호 찾는 방법" → 차단 안 함) |
| **완료 기준** | 경계 케이스 10개 이상 단위 테스트 통과. "포털 비밀번호 찾는 방법" → 허용, "내 비밀번호: abc123" → 차단 |
| **우선순위** | P1 |
| **의존성** | 없음 |

---

#### AG-003 | Issue Classifier 구현

| | |
|---|---|
| **설명** | 질문을 16개 이슈 카테고리로 분류. 1단계: 키워드 매칭 (레퍼런스: 기존 `classifier.py`의 `ISSUE_KEYWORDS`). 2단계: 키워드 점수 낮을 때 LLM 보조 분류. 결과: `issue_type`, `confidence`, `scores` 반환 |
| **완료 기준** | 대표 질문 30개 샘플 테스트 정확도 85% 이상. `other` 분류 케이스 원인 문서화 |
| **우선순위** | P1 |
| **의존성** | AG-001 (LLM 보조 분류) |

---

#### AG-004 | Hybrid Retriever 구현

| | |
|---|---|
| **설명** | Vector(ChromaDB) + Keyword(JSONL) 검색 결과 병합. Vector 미사용 시 Keyword 단독으로 degraded 동작. `source_tier`(1=규정, 숫자 낮을수록 신뢰도 높음) 기준 정렬. 청크 로드 경로: `data/processed/chunks.jsonl` |
| **완료 기준** | Chroma 미설치 시 Keyword 검색만으로 정상 답변 반환. Chroma 설치 시 Vector 검색 결과 포함 여부 확인. `/health`에서 `vector_available` 상태 반영 |
| **우선순위** | P1 |
| **의존성** | 없음 |

---

#### AG-005 | Answer Builder 구현

| | |
|---|---|
| **설명** | 검색된 청크 + LLM을 조합하여 최종 답변 조립. 구성: 요약 문장 (LLM 생성) + 체크리스트 + 기한 + 문의처. 인용 마커 ([S1], [S2]) 자동 삽입. LLM 오류 시 템플릿 fallback. 레퍼런스: 기존 `answer_builder.py`, `citation.py` |
| **완료 기준** | 이슈 유형별 답변 구조 확인 (출석, 휴학, 수강신청 등 5개 이상). LLM API 오류 시 템플릿 방식으로 답변 반환 확인 |
| **우선순위** | P1 |
| **의존성** | AG-001, AG-004 |

---

#### AG-006 | Planner & Tools 구현

| | |
|---|---|
| **설명** | `planner.py`: 이슈 유형 + 청크 액션 필드 기반 다음 행동 추천. `tools/checklist.py`: 이슈별 체크리스트 생성. `tools/contact_router.py`: 청크 contacts 필드에서 담당 부서 추출. `tools/deadline.py`: 날짜 계산. 레퍼런스: 기존 동명 파일들 |
| **완료 기준** | 출석 이슈 질문에 "출석인정신청서 작성하기" 액션 포함 답변 반환. 체크리스트 1개 이상 포함. 문의처 1개 이상 포함 |
| **우선순위** | P1 |
| **의존성** | AG-004 |

---

#### AG-007 | Action State Machine & Document Drafter

| | |
|---|---|
| **설명** | `action_state.py`: start_action (슬롯 질문 반환) → continue_action (슬롯 수집 → 완료 시 초안 생성). `tools/document_drafter.py`: 슬롯값 + 청크 기반 신청서 초안 작성. 슬롯 스키마 레퍼런스: 기존 `ACTION_SCHEMAS`. 출석 / 휴학 / 복학 / 졸업 4종 우선 구현 |
| **완료 기준** | 출석인정신청서 슬롯 입력 → 초안 생성 E2E 테스트 통과. 초안에 공식 근거 출처 포함 확인 |
| **우선순위** | P2 |
| **의존성** | AG-005 |

---

#### AG-008 | 데이터 파이프라인 구현

| | |
|---|---|
| **설명** | `crawler/`: 8개 공식 출처 크롤러 구현 (레퍼런스: 기존 크롤러). 학교 서버 보호 규칙 준수 (요청 간 랜덤 딜레이 8~18초, 최대 페이지 수 제한). `ingestion/`: HTML 파싱 → 청크 분할 → `chunks.jsonl` 저장 → ChromaDB 인덱싱. 네트워크 실패 시 `fallback_text` 사용 |
| **완료 기준** | `/admin/ingest` 호출 후 `chunks.jsonl` 업데이트 및 ChromaDB 인덱싱 확인. `used_fallback: true` 청크 비율 20% 이하 |
| **우선순위** | P2 |
| **의존성** | AG-004 |

---

#### AG-009 | 초기 청크 데이터 구축

| | |
|---|---|
| **설명** | 기존 서비스의 `chunks.jsonl` (103개)을 기반으로 새 파이프라인 포맷에 맞게 변환 및 검수. 확인 항목: `issue_types` 매핑 정확성, `contacts` 연락처 유효성, `fallback_text` 충실도 |
| **완료 기준** | 새 포맷 청크 100개 이상 `data/processed/chunks.jsonl`에 저장. 이슈 유형 16개 카테고리에 최소 2개 이상 청크 매핑 확인 |
| **우선순위** | P1 |
| **의존성** | AG-004 |

---

#### AG-010 | 대표 예시 질문 6개 선정

| | |
|---|---|
| **설명** | FE 예시 버튼에 쓸 대표 질문 6개 선정 및 검증. 기준: 이슈 유형 다양하게 커버 / 정상 답변 반환 확인 / 개인정보 미포함 |
| **완료 기준** | 6개 질문과 각 예상 issue_type 목록 FE 담당자에게 전달. 모든 질문 `/ask` 호출 시 정상 답변 반환 확인 |
| **우선순위** | P1 |
| **의존성** | AG-005, AG-009 |
| **참고** | FE-009가 이 결과물을 사용함 |

---

#### AG-011 | 테스트 스위트 구성 & CI 설정

| | |
|---|---|
| **설명** | `tests/` 폴더에 단위 테스트 작성. 대상: Guard (경계 케이스 10개), Classifier (30개 샘플), Answer Builder (이슈별 5개), Action State (E2E 1개). GitHub Actions에 `pytest` 자동 실행 설정 |
| **완료 기준** | `pytest` 전체 통과. CI 파이프라인에서 push 시 자동 실행 확인. 테스트 실패 시 PR 머지 불가 |
| **우선순위** | P2 |
| **의존성** | AG-002 ~ AG-007 |

---

## 5. 역할 간 인터페이스 계약

> BE 담당자가 아래 구조를 확정하면 FE는 Mock 데이터로 독립 개발 가능.
> **계약 확정 기한: 1주차 수요일**

### 5-1. POST /ask

**요청**
```jsonc
{
  "question": "string",
  "student_context": {           // optional
    "status": "재학생",
    "term": "2026-1학기",
    "concern": "수강신청"
  },
  "llm_assist": true,
  "live_check": false
}
```

**성공 응답 (200)**
```jsonc
{
  "answer": "string",
  "issue_type": "course_registration",
  "citations": [
    { "id": "S1", "title": "string", "url": "string", "text": "string" }
  ],
  "next_actions": [
    { "action_id": "string", "label": "string", "description": "string" }
  ],
  "checklist": {
    "tasks": ["string"],
    "required_documents": ["string"],
    "application_paths": ["string"]
  },
  "contacts": [
    { "name": "string", "label": "string", "phone": "string" }
  ],
  "deadline": null,              // 또는 { "deadline": "YYYY-MM-DD", "description": "string" }
  "tool_logs": ["string"]
}
```

### 5-2. 에러 응답 (공통)

```jsonc
{
  "error_code": "privacy_blocked" | "no_source" | "server_error" | "unauthorized",
  "message": "string",           // 사용자에게 보여줄 한국어 메시지
  "detail": "string"             // 개발용 (운영 환경 생략)
}
```

### 5-3. POST /actions/start

**요청**
```jsonc
{ "action_id": "attendance_approval" }
```

**응답**
```jsonc
{
  "action_id": "string",
  "title": "출석인정신청서 작성",
  "slots": [
    { "key": "event_date", "question": "결석 날짜는 언제인가요?", "required": true },
    { "key": "reason", "question": "사유를 선택해주세요.", "required": true }
  ]
}
```

### 5-4. POST /actions/continue

**요청**
```jsonc
{
  "action_id": "attendance_approval",
  "slots": { "event_date": "2026-05-10", "reason": "예비군 훈련" }
}
```

**응답**
```jsonc
// 완료 시
{
  "status": "completed",
  "document": "string",          // 초안 전문
  "checklist": ["string"],
  "citations": []
}

// 추가 슬롯 필요 시
{
  "status": "pending",
  "next_slot": { "key": "string", "question": "string" }
}

// 차단 시
{
  "status": "blocked",
  "error_code": "privacy_blocked",
  "message": "string"
}
```

---

## 6. 마일스톤 & 의존성 맵

### 주차별 마일스톤

| 주차 | 마일스톤 | 완료 조건 |
|---|---|---|
| **1주차** | 기반 구축 & 계약 확정 | BE-001~004, BE-007 완료 / AG-001~003, AG-009 완료 / FE-001 완료 / API 계약 FE 공유 완료 |
| **2주차** | 핵심 기능 구현 | BE-005~006 완료 / AG-004~007, AG-010 완료 / FE-002~009 완료 |
| **3주차** | 통합 & 안정화 | 여정 A, B E2E 통합 테스트 통과 / BE-008~010 완료 / FE-010~012 완료 / AG-008, AG-011 완료 |
| **4주차** | 배포 & 운영 준비 | Docker 배포 완료 / `/health` 모니터링 연결 / CI 파이프라인 통과 |

---

### 의존성 맵

```
[1주차 우선 착수]
BE-001 ──→ BE-002 ──→ BE-003 ──→ BE-004 ──→ (FE-002 착수 가능)
                                 └──→ BE-007

AG-001 ──→ AG-003 (LLM 보조 분류)
AG-002 (독립)
AG-009 (독립, 데이터 준비)
FE-001 (독립)

[2주차]
BE-004 + AG-001~006 ──→ BE-005 ──→ BE-006
AG-004 + AG-005 ──→ AG-006
AG-005 ──→ AG-007 ──→ BE-006

FE-002 ──→ FE-004 ──→ FE-005, FE-006, FE-007, FE-008
FE-003 ──→ FE-004

AG-010 ──→ FE-009

[3주차]
BE-005 + FE-004~008 ──→ E2E 통합 테스트
BE-006 + FE-010 ──→ 여정 B E2E 테스트
BE-009 ──→ FE-012

AG-002~007 ──→ AG-011 (테스트 스위트)
BE-008 ──→ FE-011 (관리자 페이지)
```

---

### 역할 간 블로킹 요약

| 완료 필요 | 기다리는 작업 | 완료 목표 |
|---|---|---|
| BE-004 (API 스키마) | FE-002 착수 | 1주차 수요일 |
| AG-010 (예시 질문) | FE-009 착수 | 2주차 초 |
| BE-006 (actions API) | FE-010 착수 | 2주차 말 |
| BE-009 (Docker) | FE-012 (빌드 검증) | 3주차 |
| AG-002~007 | AG-011 (테스트 스위트) | 3주차 |

---

## 부록 A — 기존 서비스 레퍼런스 파일 위치

새 코드베이스 구현 시 아래 파일들을 레퍼런스로 활용.

| 레퍼런스 파일 | 활용 목적 |
|---|---|
| `agent/guard.py` | Privacy guard 패턴 (AG-002) |
| `agent/classifier.py` | 이슈 키워드 목록 (AG-003) |
| `agent/answer_builder.py` | 답변 섹션 구조 (AG-005) |
| `agent/citation.py` | 인용 마커 로직 (AG-005) |
| `agent/action_state.py` | 액션 상태 머신 구조 (AG-007) |
| `tools/document_drafter.py` | ACTION_SCHEMAS 슬롯 정의 (AG-007) |
| `tools/checklist.py` | 체크리스트 생성 로직 (AG-006) |
| `tools/contact_router.py` | 문의처 라우팅 (AG-006) |
| `crawler/` (8개 파일) | 공식 출처 URL 및 fallback_text (AG-008) |
| `data/processed/chunks.jsonl` | 초기 청크 데이터 (AG-009) |

## 부록 B — 공통 약속

- **태스크 완료 보고:** 완료 시 태스크 ID와 완료 기준 충족 여부를 팀 채널에 공유
- **블로킹 발생 시:** 즉시 공유. 의존 관계상 다른 담당자에게 영향이 있을 때는 당일 공유
- **API 계약 변경 시:** BE가 변경 내용을 FE·AG에 즉시 공지 후 문서 업데이트
- **테스트 기준:** 주요 기능은 단위 테스트 후 PR 제출. `pytest` 통과 필수
