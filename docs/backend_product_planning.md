# KMU 캠퍼스 생활 액션 에이전트 백엔드 기획 문서

> 문서 목적: 현재 FastAPI 백엔드 구현을 기준으로 API 역할, RAG 파이프라인, 데이터 수집 정책, 개인정보 보호, 운영/QA 기준을 공유하기 위한 기획 문서  
> 작성일: 2026-05-24  
> 대상: 기획, 백엔드, 프론트엔드, RAG/에이전트, 데이터 수집, QA 담당자  
> 기준 서버: `app.py` 중심의 FastAPI 앱  
> 개발 API 주소: `http://127.0.0.1:8001`  
> 프론트 개발 주소: `http://127.0.0.1:5173`

---

## 1. 문서 요약

### 1.1 백엔드 한 줄 정의

국민대학교 공식 공개 자료를 수집·검색·검증하고, 학생 질문에 대해 개인정보를 차단한 뒤 근거 기반 답변과 다음 행동 문서 초안을 반환하는 FastAPI 기반 RAG/액션 서버입니다.

### 1.2 백엔드의 제품 책임

- 학생 질문을 안전하게 받아 개인정보 입력을 차단합니다.
- 질문을 학사/행정 이슈 타입으로 분류합니다.
- 공식 자료 chunk에서 근거를 검색합니다.
- 근거가 없으면 절차성 답변을 만들지 않습니다.
- 답변에는 citation과 공식 출처를 함께 제공합니다.
- 답변 이후 가능한 다음 행동을 제안합니다.
- 출석인정신청서, 휴학/복학 체크리스트, 문의문 등 후속 문서 초안을 만듭니다.
- 학교 서버 보호 정책을 지키며 공식 자료를 수집합니다.
- Chroma vector 검색이 실패해도 JSONL keyword 검색으로 서비스를 계속 제공합니다.
- 졸업센터에서는 성적증명서 원문을 저장하지 않고 비식별 요약만 분석합니다.

### 1.3 현재 확인된 실행 상태

- FastAPI 앱은 `python -m uvicorn app:app --reload --host 127.0.0.1 --port 8001`로 프론트와 정상 연결됩니다.
- `GET /health`는 keyword chunk, vector 상태, LLM 상태, 졸업센터 상태, 최근 ingest 상태를 반환합니다.
- 일반 RAG 답변의 vector retriever는 optional accelerator입니다.
- 졸업센터는 별도 `data/graduation` 구조화 데이터와 졸업용 Chroma 인덱스를 사용합니다.
- 프론트 개발 서버는 현재 `8001`을 바라보지만 일부 문서에는 `8000`이 남아 있어 포트 정책 정리가 필요합니다.

---

## 2. 서비스 내 백엔드 위치

### 2.1 전체 서비스 구조

```text
사용자
→ React 프론트엔드
→ FastAPI 백엔드
   ├─ 개인정보 guard
   ├─ 이슈 classifier
   ├─ HybridRetriever
   │  ├─ KeywordRetriever
   │  └─ VectorRetriever
   ├─ action planner
   ├─ deterministic answer builder
   ├─ document drafter
   ├─ ingestion/crawler pipeline
   └─ graduation center service
→ JSON 응답
→ 프론트 UI 렌더링
```

### 2.2 백엔드가 제공하는 핵심 경험

| 경험 | 백엔드 책임 |
| --- | --- |
| 질문 답변 | `/ask`에서 guard, 분류, 검색, 답변 조립, 출처 반환 |
| 출처 확인 | citation과 source chunk metadata 반환 |
| 다음 행동 | 이슈별 `next_actions` 추천 |
| 서류 초안 | `/actions/start`, `/actions/continue` 상태 머신 제공 |
| 최신 자료 확인 | `/ingest/live-refresh`, `/ingest/run`으로 공식 공개 자료 갱신 |
| 운영 상태 확인 | `/health`, `/sources` 제공 |
| 졸업 진단 | `/graduation/*` API로 성적증명서 파싱/분석 |

### 2.3 백엔드가 하지 않는 일

- ON국민, SWELL 개인 화면, eCampus 로그인 후 화면을 자동 탐색하지 않습니다.
- 학생의 실제 학번, 주민번호, 연락처, 포털 ID/PW를 저장하지 않습니다.
- 일반 질문 답변에서 LLM이 자유롭게 절차를 생성하지 않습니다.
- 공식 근거가 없는 상태에서 행정 절차를 단정하지 않습니다.
- 실제 행정 신청 제출을 대행하지 않습니다.

---

## 3. 백엔드 모듈 지도

### 3.1 최상위

| 파일 | 역할 |
| --- | --- |
| `app.py` | FastAPI 엔드포인트, 서비스 객체 초기화, 프론트 정적 파일 서빙 |
| `llm_client.py` | 선택적 OpenAI 보조 기능. 일반 답변의 source of truth는 아님 |
| `requirements.txt` | Python 의존성 |

### 3.2 agent

| 파일 | 역할 |
| --- | --- |
| `agent/guard.py` | 개인정보 guard, source guard |
| `agent/classifier.py` | rule-based issue classifier |
| `agent/planner.py` | issue/chunk 기반 다음 action 추천 |
| `agent/answer_builder.py` | deterministic 답변 조립 |
| `agent/citation.py` | `[S1]`, `[S2]` citation label 생성 |
| `agent/action_state.py` | action start/continue 상태 머신 |
| `agent/answer_validator.py` | 답변 citation contract와 privacy output 검증 |
| `agent/student_context.py` | 학생 상태 기반 맞춤 확인 문구 |
| `agent/student_playbook.py` | 학생식 표현, 문의 전 확인, 흔한 착각 playbook |

### 3.3 retriever

| 파일 | 역할 |
| --- | --- |
| `retriever/keyword_retriever.py` | JSONL 기반 keyword 검색 |
| `retriever/vector_retriever.py` | Chroma 기반 vector 검색, optional |
| `retriever/hybrid_retriever.py` | vector + keyword merge, score 정렬 |

### 3.4 ingestion/crawler

| 폴더 | 역할 |
| --- | --- |
| `crawler/` | 공식 공개 출처별 crawler adapter |
| `ingestion/parser.py` | HTML visible text 추출 |
| `ingestion/file_extractors.py` | 첨부 파일 추출 |
| `ingestion/chunker.py` | 긴 문서 chunk 분리 |
| `ingestion/pipeline.py` | 수집, chunk 생성, JSONL 저장, vector upsert |
| `ingestion/live_refresh.py` | issue-scoped 최신 확인 |

### 3.5 tools

| 파일 | 역할 |
| --- | --- |
| `tools/checklist.py` | 해야 할 일, 필요서류, 신청경로 생성 |
| `tools/contact_router.py` | 문의처 추천 |
| `tools/deadline.py` | 이벤트 날짜 추출, 마감일 계산 |
| `tools/document_drafter.py` | action schema와 문서 초안 생성 |
| `tools/graduation.py` | 일반 action용 졸업요건 간이 진단 |
| `tools/course_planner.py` | 일반 action용 수강계획 방향 추천 |

### 3.6 graduation_center

| 파일 | 역할 |
| --- | --- |
| `graduation_center/models.py` | 성적증명서 비식별 요약과 분석 요청/응답 모델 |
| `graduation_center/parser.py` | PDF 성적증명서 파싱 |
| `graduation_center/data.py` | 요람 구조화 데이터 로드/계산 |
| `graduation_center/service.py` | 졸업센터 readiness, RAG, GPT 분석, privacy sanitize |

---

## 4. API 개요

### 4.1 공개 사용자 API

| Method | Path | 목적 |
| --- | --- | --- |
| `GET` | `/` | 빌드된 프론트가 있으면 `frontend/dist/index.html` 서빙, 없으면 API 안내 |
| `GET` | `/health` | 서비스 상태 확인 |
| `POST` | `/ask` | 질문 답변, 출처, tool log, 다음 행동 반환 |
| `POST` | `/actions/start` | action 시작, 필요한 slot 질문 반환 |
| `POST` | `/actions/continue` | slot 입력 후 문서 초안 또는 추가 질문 반환 |

### 4.2 졸업센터 API

| Method | Path | 목적 |
| --- | --- | --- |
| `GET` | `/graduation/status` | 졸업센터 준비 상태와 privacy policy 반환 |
| `POST` | `/graduation/transcript/parse` | PDF 업로드를 비식별 성적 요약으로 파싱 |
| `POST` | `/graduation/audit` | 졸업 가능 여부 진단 |
| `POST` | `/graduation/substitute-courses` | 대체 이수 후보 탐색 |
| `POST` | `/graduation/micro-degree` | 마이크로디그리/소학위 가능성 분석 |
| `POST` | `/graduation/post-graduation-checklist` | 졸업 전후 행정 체크리스트 |
| `POST` | `/graduation/career-translator` | 이수 과목 기반 직무 역량 번역 |
| `POST` | `/graduation/early-graduation` | 조기졸업 가능 여부와 제한 조건 확인 |
| `POST` | `/graduation/customized-major` | Customized전공 인정 가능성 안내 |
| `POST` | `/graduation/credit-drop` | 성적포기/학점 드랍 제도 확인 |

### 4.3 운영/관리 API

| Method | Path | 목적 | 운영 주의 |
| --- | --- | --- | --- |
| `POST` | `/ingest/run` | 공식자료 전체/소스별 수집 및 인덱싱 | 인증 필요 |
| `POST` | `/ingest/live-refresh` | 이슈별 공식 공개 소스 최신 확인 | 인증/쿨다운 필요 |
| `GET` | `/sources` | 현재 keyword source chunk 목록 반환 | 운영에서는 노출 제한 권장 |

---

## 5. POST /ask 기획

### 5.1 목적

학생의 자연어 질문을 받아 공식 근거 기반 답변, 출처, 다음 행동, 처리 상태를 반환합니다.

### 5.2 요청 스키마

```json
{
  "question": "공결 신청 절차가 어떻게 돼?",
  "student_context": {
    "status": "enrolled",
    "term": "2026-1학기",
    "concern": "출석"
  },
  "llm_assist": true,
  "live_check": false
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `question` | string | 필수. 한국어 자연어 질문 |
| `student_context` | object | 선택. 상태, 학기, 관심 항목 |
| `llm_assist` | boolean | 선택. OpenAI 보조 기능 요청 여부 |
| `live_check` | boolean | 선택. 관련 공식 공개 소스 최신 확인 여부 |

### 5.3 처리 흐름

```text
POST /ask
→ inspect_privacy(question)
→ classify_issue(question)
→ augment_query_with_context(question, student_context)
→ optional LLM query expansion
→ optional live_refresh
→ HybridRetriever.search
→ prefer_issue_matched_chunks
→ optional LLM rerank
→ require_sources
→ suggest_actions
→ build_final_answer
→ optional polish_answer
→ validate_answer_contract
→ validate_output_privacy
→ JSON response
```

### 5.4 응답 스키마 핵심

| 필드 | 설명 |
| --- | --- |
| `answer` | 한국어 최종 답변. `[S1]` citation marker 포함 |
| `issue_type` | 분류된 이슈 타입 |
| `classification` | classifier confidence와 score |
| `tool_logs` | 처리 단계 로그 |
| `sources` | 검색된 원본 chunk 목록 |
| `citations` | UI가 표시할 출처 목록 |
| `next_actions` | 추천 후속 action |
| `safety_flags` | guard/validation flag |
| `answer_validation` | citation marker 검증 결과 |
| `output_privacy` | 최종 답변 privacy 검증 결과 |
| `llm` | LLM 보조 사용/실패/fallback metadata |
| `live_check` | 최신 확인 시도/성공/fallback/실패 정보 |

### 5.5 차단 응답

개인정보가 감지되면 검색과 live check를 실행하지 않고 바로 차단합니다.

```json
{
  "answer": "실제 학번, 성적, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력받지 않습니다. 가상 사례나 사용자가 직접 요약한 비식별 정보로만 안내할 수 있습니다.",
  "issue_type": "privacy_blocked",
  "tool_logs": ["guard.inspect_privacy 호출됨"],
  "sources": [],
  "citations": [],
  "next_actions": [],
  "safety_flags": ["student_id", "grade_report"],
  "llm": {
    "used": false,
    "reason": "privacy_blocked"
  },
  "live_check": {
    "attempted": false,
    "reason": "privacy_blocked"
  }
}
```

### 5.6 기획상 성공 기준

- 공식 근거가 있으면 답변, citation, next action이 함께 반환됩니다.
- 공식 근거가 없으면 `no_official_source`로 차단성 안내를 반환합니다.
- 답변의 절차성 문장은 citation marker를 유지해야 합니다.
- LLM 보조가 실패해도 기본 deterministic 답변이 정상 반환되어야 합니다.
- live check가 실패해도 기존 근거 사용 여부가 응답 metadata에 드러나야 합니다.

---

## 6. 개인정보 guard 정책

### 6.1 차단 대상

| flag | 감지 대상 | 예 |
| --- | --- | --- |
| `student_id` | 학번 | `20`으로 시작하는 학번 패턴, `학번` |
| `resident_number` | 주민번호 | `000000-0000000`, `주민` |
| `portal_password` | 포털 ID/PW, 비밀번호 | `내 비밀번호`, `password=...` |
| `grade_report` | 성적표 원본, GPA, 개인 성적 | `성적표`, `내 성적`, `gpa` |
| `phone` | 연락처/전화번호 | 휴대폰 번호, `연락처`, `전화번호` |

### 6.2 적용 위치

| 위치 | 적용 함수 | 목적 |
| --- | --- | --- |
| `/ask` | `inspect_privacy(question)` | 질문 단계 차단 |
| `/actions/continue` | `inspect_privacy(slot values)` | 서류 slot 값 차단 |
| `/ask` 최종 답변 | `validate_output_privacy(answer)` | polish 등 후처리 결과 검증 |
| `/actions/continue` 최종 문서 | `validate_output_privacy(document + checklist)` | 초안에 민감정보가 포함될 가능성 차단 |
| 졸업센터 분석 | `_input_safety_flags`, `_sanitize_sensitive_output` | 비식별 요약만 분석/출력 |

### 6.3 기획 원칙

- 개인정보는 "필요하면 넣어도 된다"가 아니라 "절대 입력하지 않는다"가 기본입니다.
- action 문서 미리보기에도 이름/학번은 placeholder로 유지합니다.
- 졸업센터는 PDF 업로드를 허용하지만 원문 저장 없이 임시 파싱 후 비식별 요약만 반환해야 합니다.
- GPT 보조 기능이 켜져도 개인정보가 prompt나 output에 들어가지 않아야 합니다.

---

## 7. 이슈 분류 정책

### 7.1 현재 issue_type

| issue_type | 대표 주제 |
| --- | --- |
| `attendance` | 출석, 출석인정, 공결, 예비군 결석 |
| `leave_return` | 휴학, 복학, 질병휴학, 군휴학 |
| `course_registration` | 수강신청, 수강정정, 수변, 폐강, 시간표 |
| `registration_tuition` | 등록금, 분납, 납부확인, 고지서 |
| `certificate` | 증명서, 졸업예정증명서, 성적증명서 |
| `student_id` | 학생증, 모바일학생증, K-Card, 재발급 |
| `scholarship` | 장학, 국가장학금, 근로장학, 학자금 |
| `portal_access` | ON국민, eCampus, 로그인, 비밀번호 |
| `campus_facility` | 통학버스, 주차, 기숙사, 도서관, 식단 |
| `academic_record` | 학적부 정정, 개명, 영문명, 주소 변경 |
| `student_insurance` | 학생보험, 상해, 사고, 치료비 |
| `graduation` | 졸업요건, 요람, 전공필수, 이수학점 |
| `schedule` | 일정, 기간, 마감, 이번 주, 오늘 |
| `contact` | 문의처, 부서, 전화, 학과사무실 |
| `military` | 병무, 예비군, 군 관련 |
| `student_support` | 학생증, 보험, 상담, IT, 도서관 |
| `other` | 미분류 |

### 7.2 분류 원칙

- rule-based keyword classifier로 동작합니다.
- `schedule`, `contact`, `student_support`는 meta issue로 취급되어 구체 이슈가 있으면 구체 이슈가 우선됩니다.
- 예비군 단독 질문은 `military`, 출석/공결 맥락이 함께 있으면 `attendance`로 분류될 수 있습니다.
- "이번 주", "오늘", "다가오는", "뭐 해야"처럼 일정 의도가 강하면 `schedule`로 분류될 수 있습니다.

### 7.3 개선 필요

- keyword 충돌에 대한 regression test를 지속 추가해야 합니다.
- 신조어/학생식 표현은 `student_playbook`과 classifier keyword 양쪽에 반영해야 합니다.
- FE 추천 질문은 classifier가 높은 confidence로 분류할 수 있는 표현을 우선 사용해야 합니다.

---

## 8. RAG 검색/근거 정책

### 8.1 데이터 source of truth

`data/processed/chunks.jsonl`이 일반 RAG 검색의 기준 데이터입니다.

Chroma vector store는 같은 chunk를 인덱싱한 optional accelerator입니다. Chroma가 설치되지 않았거나 깨져도 keyword retriever로 답변이 가능해야 합니다.

### 8.2 HybridRetriever 원칙

```text
VectorRetriever.search(query)
KeywordRetriever.search(query)
→ chunk_id 기준 merge
→ 더 높은 score 채택
→ score desc, source_tier asc 정렬
→ top N 반환
```

### 8.3 source tier

| tier | 출처 | 기획상 의미 |
| --- | --- | --- |
| 1 | 규정관리시스템 | 제도적 최상위 근거 |
| 2 | 학사안내 | 절차, 서류, 신청경로 핵심 근거 |
| 3 | 학생지원/대학생활 안내 | 학생증, 증명서, 병무, 상담 |
| 4 | 학사일정 | 기간, 일정, 마감일 |
| 5 | 공지사항 | 학기별 변경/모집/신청 공지 |
| 6 | 요람/규정집 | 졸업요건, 교육과정 |
| 7 | 대학조직 | 문의처/부서 라우팅 |
| 8 | SWELL 공개 게시판 | 공개 비교과/신청 안내 |

### 8.4 chunk metadata 계약

각 chunk는 아래 metadata를 가질 수 있으며, 여러 downstream 모듈이 의존합니다.

| metadata | 사용처 |
| --- | --- |
| `source_tier` | 검색 tie-break, 출처 신뢰도 표시 |
| `issue_types` | 이슈별 검색/우선순위 |
| `keywords`, `search_hints` | keyword relevance |
| `application_path` | 신청 경로 안내 |
| `required_documents` | 필요 서류 안내 |
| `submit_to` | 제출처 안내 |
| `contacts` | 문의처 라우팅 |
| `schedule` | 학사일정/기간 표시 |
| `deadline_rule` | 마감일 계산 |
| `actions` | next action 추천 |
| `published_at`, `posted_date` | 공지/출처 freshness 표시 |
| `fetched_from_network`, `used_fallback`, `fetch_status` | 최신성/수집 상태 표시 |

### 8.5 근거 부족 정책

`require_sources`는 검색된 chunk가 없으면 답변 생성을 차단합니다.

기획 원칙:

- "모르겠다"는 답변은 허용됩니다.
- 공식 근거 없는 절차 안내는 허용되지 않습니다.
- fallback chunk도 공식 URL에 연결된 curated fallback이어야 합니다.

---

## 9. 답변 조립과 citation 계약

### 9.1 답변 생성 방식

일반 `/ask` 답변은 LLM 자유 생성이 아니라 `answer_builder.py`에서 deterministic하게 조립됩니다.

구성:

```text
[답변 요약]
[해야 할 일]
[학생 경험 팁]
[학생 맞춤 확인]
[문의 전 준비]
[필요 서류]
[신청 경로]
[기한]
[문의처 추천]
[다음 행동]
[근거]
[주의]
```

### 9.2 citation label

`agent/citation.py`는 검색된 unique chunk에 `S1`, `S2`, ...를 부여합니다.

기획상 계약:

- 절차성 주장은 가능한 한 근거 chunk의 citation marker를 포함합니다.
- `[근거]` 블록의 citation id는 본문 marker와 대응해야 합니다.
- 프론트는 `[S1]` marker를 클릭 가능한 "근거 S1" pill로 렌더링할 수 있습니다.
- `answer_validator`는 marker와 citation 목록의 일치 여부를 검증합니다.

### 9.3 LLM polish 정책

`OPENAI_POLISH_ENABLED=true`일 때만 deterministic 답변 본문을 문장 단위로 다듬을 수 있습니다.

제약:

- 새 절차, 날짜, 부서명, 전화번호, 서류명, 신청 경로 추가 금지
- citation marker 보존
- 섹션 구조 보존
- guard 실패 시 원래 deterministic 답변으로 fallback

---

## 10. Action flow 기획

### 10.1 목적

답변 이후 "무엇을 해야 하는지"를 실제 작성 가능한 문서 초안이나 체크리스트로 전환합니다.

### 10.2 상태 흐름

```text
POST /actions/start
→ action_id 확인
→ required_slots 계산
→ needs_input 응답

POST /actions/continue
→ slot values privacy guard
→ action_issue_type 확인
→ optional live_refresh
→ action 관련 official chunks 검색
→ missing_slots 계산
→ needs_input 또는 completed 응답
→ output_privacy 검증
```

### 10.3 지원 action

| action_id | label | issue_type |
| --- | --- | --- |
| `draft_attendance_recognition_form` | 출석인정신청서 초안 작성 | `attendance` |
| `draft_leave_checklist` | 휴학 준비 체크리스트 생성 | `leave_return` |
| `draft_return_checklist` | 복학 준비 체크리스트 생성 | `leave_return` |
| `course_registration_checklist` | 수강신청/폐강 확인 체크리스트 생성 | `course_registration` |
| `certificate_issue_guide` | 증명서 발급 경로 확인 | `certificate` |
| `student_id_issue_guide` | 학생증 발급 체크리스트 생성 | `student_id` |
| `scholarship_notice_checklist` | 장학공지 확인 체크리스트 생성 | `scholarship` |
| `portal_access_checklist` | 포털/eCampus 접근 체크리스트 생성 | `portal_access` |
| `academic_schedule_digest` | 오늘 기준 학사일정 체크리스트 생성 | `schedule` |
| `campus_facility_guide` | 생활지원 이용 체크리스트 생성 | `campus_facility` |
| `academic_record_correction_checklist` | 학적부 정정 체크리스트 생성 | `academic_record` |
| `student_insurance_checklist` | 학생보험 청구 체크리스트 생성 | `student_insurance` |
| `military_service_checklist` | 병무/예비군 체크리스트 생성 | `military` |
| `graduation_audit` | 졸업요건 간이 진단 | `graduation` |
| `recommend_course_plan` | 수강계획 방향 추천 | `graduation` |
| `draft_contact_message` | 문의문 초안 작성 | `contact` |

### 10.4 action response

#### needs_input

```json
{
  "status": "needs_input",
  "action_id": "draft_attendance_recognition_form",
  "label": "출석인정신청서 초안 작성",
  "issue_type": "attendance",
  "missing_slots": ["event_date", "absence_reason"],
  "questions": ["결석일 또는 훈련일은 언제인가요?", "결석 사유를 적어주세요."],
  "privacy_notice": "학번, 실명, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력하지 마세요."
}
```

#### completed

```json
{
  "status": "completed",
  "action_id": "draft_attendance_recognition_form",
  "document": "[출석인정신청서 초안]...",
  "checklist": ["공식 양식 확인", "증빙서류 준비"],
  "output_privacy": {
    "ok": true,
    "flags": []
  },
  "live_check": {
    "attempted": false,
    "requested": false
  }
}
```

### 10.5 기획상 주의

- slot에는 학번/실명/연락처를 요구하지 않습니다.
- "담당 교강사" 같은 비식별 placeholder를 허용합니다.
- 실제 제출 가능한 최종 서식이 아니라 공식 근거 기반 초안입니다.
- 최종 제출 여부는 학교 포털/담당 부서에서 학생이 직접 확인해야 합니다.

---

## 11. 수집/ingestion 기획

### 11.1 수집 대상

| source | crawler |
| --- | --- |
| `academic_guide` | `KMUAcademicGuideCrawler` |
| `notice` | `KMUNoticeCrawler` |
| `schedule` | `KMUScheduleCrawler` |
| `student_support` | `KMUStudentSupportCrawler` |
| `organization` | `KMUOrgCrawler` |
| `cradle` | `KMUCradleCrawler` |
| `university_rule` | `KMURuleCrawler` |
| `swell_public` | `SWELLPublicCrawler` |

### 11.2 학교 서버 보호 정책

| 정책 | 현재 구현 |
| --- | --- |
| per-host delay | host별 8-18초 random delay |
| 첫 요청 delay | 1.5-4초 random delay |
| source별 페이지 제한 | crawler당 `max_pages_per_run = 3` |
| 전체 ingest cooldown | 300초 |
| 동시 실행 방지 | module-level `_INGEST_LOCK` |
| 조건부 요청 | ETag, Last-Modified 사용 |
| timeout | 기본 12초 |
| User-Agent | 낮은 빈도의 학생 demo checker로 명시 |
| network 실패 | 공식 URL-bound fallback text 사용 |

### 11.3 ingestion 결과

`run_ingestion`은 다음 정보를 반환해야 합니다.

| 필드 | 설명 |
| --- | --- |
| `status` | `completed` 또는 `skipped` |
| `message` | 사용자/운영자 안내 |
| `documents_seen` | 수집 문서 수 |
| `new_documents` | 신규 문서 수 |
| `changed_documents` | 변경 문서 수 |
| `skipped_documents` | hash 동일 문서 수 |
| `chunks_written` | JSONL 총 chunk 수 |
| `vector_available` | vector retriever 사용 가능 여부 |
| `vector_indexed` | vector upsert 수 |
| `vector_error` | vector 오류 |
| `network_success` | 실제 fetch 성공 |
| `fallback_used` | fallback 사용 |
| `network_failed` | 실패/빈 응답 |
| `failed_urls` | 실패 URL 목록 |
| `last_ingest` | 마지막 수집 상태 |

### 11.4 data/state

| 경로 | 역할 |
| --- | --- |
| `data/processed/chunks.jsonl` | 일반 RAG source of truth |
| `data/state/crawler_state.json` | 문서별 content hash, cache header, last_seen 저장 |
| `data/vector/chroma` | 일반 RAG vector index |
| `data/graduation` | 졸업센터 구조화 데이터 |
| `data/graduation/chroma` | 졸업센터 요람 RAG index |

---

## 12. live refresh 기획

### 12.1 목적

질문 또는 action 흐름에서 사용자가 최신 확인을 요청했을 때, 전체 수집이 아니라 해당 issue_type과 관련된 공식 공개 소스만 즉시 재확인합니다.

### 12.2 적용 위치

| API | 조건 |
| --- | --- |
| `/ask` | `live_check=true`이고 privacy guard를 통과한 경우 |
| `/actions/continue` | `live_check=true`이고 slot privacy guard를 통과한 경우 |
| `/ingest/live-refresh` | 운영자가 특정 issue_type을 지정한 경우 |

### 12.3 기획상 원칙

- 로그인 후 개인 화면은 확인하지 않습니다.
- 네트워크 fetch가 성공한 문서만 로컬 chunk에 반영합니다.
- fallback이 사용된 문서는 기존 chunk를 덮어쓰지 않습니다.
- 응답에 `network_success`, `fallback_used`, `network_failed`, `failed_urls`를 반드시 드러냅니다.

---

## 13. 졸업센터 백엔드 기획

### 13.1 일반 RAG와의 차이

일반 `/ask`는 공식 웹 chunk 중심 deterministic 답변입니다. 졸업센터는 성적증명서 비식별 요약, 구조화 요람 JSON, 졸업용 Chroma RAG, GPT 분석을 결합합니다.

### 13.2 readiness 조건

`GET /graduation/status`의 `ready`는 다음 조건을 모두 만족해야 true입니다.

- `OPENAI_API_KEY`가 설정되어 있음
- `data/graduation` 필수 JSON 파일이 존재함
- `data/graduation/chroma` collection이 사용 가능함

### 13.3 privacy policy

응답의 `privacy`는 다음 약속을 반환합니다.

| 항목 | 값 |
| --- | --- |
| `pdf_storage` | `temporary_only` |
| `returns_raw_text` | `false` |
| `returns_gpa_value` | `false` |
| `returns_course_grades` | `false` |

### 13.4 transcript summary

`TranscriptSummary`는 원문 성적증명서가 아니라 분석 가능한 비식별 요약입니다.

| 필드 | 설명 |
| --- | --- |
| `masked_name` | 마스킹된 이름 |
| `masked_student_id` | 마스킹된 학번 |
| `department` | 학과 |
| `admission_year` | 입학연도 |
| `total_credits` | 총 이수학점 |
| `category_credits` | 이수구분별 학점 |
| `gpa_minimum_met` | 기준 충족 여부. GPA 숫자는 반환하지 않음 |
| `courses` | 과목명, 학점, 이수구분. 과목별 성적 없음 |
| `parse_method` | text 또는 vision 등 |
| `warnings` | 파싱 주의사항 |

### 13.5 분석 task

| task | API | 목적 |
| --- | --- | --- |
| `audit` | `/graduation/audit` | 졸업 가능 여부 진단 |
| `early_graduation` | `/graduation/early-graduation` | 조기졸업 조건 확인 |
| `customized_major` | `/graduation/customized-major` | Customized전공 인정 안내 |
| `credit_drop` | `/graduation/credit-drop` | 성적포기/학점 드랍 제도 확인 |
| `substitute_courses` | `/graduation/substitute-courses` | 대체 이수 후보 |
| `micro_degree` | `/graduation/micro-degree` | 마이크로디그리 가능성 |
| `post_graduation_checklist` | `/graduation/post-graduation-checklist` | 졸업 전후 행정 체크리스트 |
| `career_translator` | `/graduation/career-translator` | 직무 역량 번역 |

### 13.6 졸업센터 응답

| 필드 | 설명 |
| --- | --- |
| `status` | `completed` 또는 `blocked` |
| `task` | 분석 task |
| `answer` | 한국어 분석 결과 |
| `sources` | `G1`, `G2` 형태의 졸업센터 source |
| `structured_check` | 구조화 요람 기준 계산 결과 |
| `safety_flags` | 민감정보 차단 flag |
| `llm` | GPT 사용 metadata |
| `warnings` | 파싱/분석 주의사항 |

---

## 14. LLM 사용 정책

### 14.1 일반 질문

일반 `/ask`에서 LLM은 선택적 보조 기능입니다.

| 기능 | 조건 | 실패 시 |
| --- | --- | --- |
| 검색어 확장 | `OPENAI_ENABLED=true`, `llm_assist=true` | 원 질문 사용 |
| chunk rerank | 검색 결과가 있고 LLM 사용 가능 | 기존 검색 순서 사용 |
| 답변 polish | `OPENAI_POLISH_ENABLED=true` | deterministic 답변 사용 |
| 자유 답변 생성 | 현재 사용하지 않음 | 항상 deterministic builder |

### 14.2 졸업센터

졸업센터는 GPT 분석을 사용합니다. 다만 입력은 비식별 transcript summary와 제공된 source로 제한합니다.

제약:

- 이름, 학번, GPA 숫자, 과목별 성적 생성/언급 금지
- 제공된 source 기반으로 분석
- structured JSON과 요람 RAG source를 함께 사용
- output sanitize 적용

### 14.3 환경변수

| 변수 | 의미 |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_ENABLED` | 일반 질문 LLM 보조 활성화 |
| `OPENAI_MODEL` | 일반 질문 보조 모델 |
| `OPENAI_POLISH_ENABLED` | 답변 polish 활성화 |
| `OPENAI_GRADUATION_MODEL` | 졸업센터 분석 모델 |

---

## 15. 프론트엔드 연동 계약

### 15.1 포트 계약

현재 프론트 개발 서버는 `5173`에서 실행될 때 `8001`로 API를 호출합니다.

운영 전 결정 필요:

- README/AGENTS의 기본 백엔드 포트를 `8001`로 바꿀지
- 프론트 `API_BASE` fallback을 `8000`으로 맞출지
- `.env`의 `VITE_API_BASE_URL`을 우선하도록 바꿀지

권장:

```text
개발 기본: VITE_API_BASE_URL=http://127.0.0.1:8001
운영 기본: window.location.origin
문서: 8001로 통일 또는 환경변수 중심으로 통일
```

### 15.2 응답 안정성

프론트는 아래 필드가 없어도 안전하게 fallback해야 하지만, 백엔드는 가능하면 항상 같은 shape를 반환해야 합니다.

| API | 항상 유지할 필드 |
| --- | --- |
| `/ask` | `answer`, `issue_type`, `tool_logs`, `sources`, `citations`, `next_actions`, `safety_flags`, `llm`, `live_check` |
| `/actions/start` | `status`, `action_id`, `label`, `missing_slots`, `questions`, `privacy_notice` |
| `/actions/continue` | `status`, `action_id`, `document/checklist` 또는 `missing_slots/questions` |
| `/graduation/status` | `ready`, `openai_api_key_configured`, `model`, `data_dir`, `missing_files`, `chroma`, `privacy` |

### 15.3 에러 응답 개선 방향

현재 일부 API는 `HTTPException` 또는 일반 JSON 응답이 혼재합니다. 프론트 UX 안정성을 위해 표준 error envelope을 권장합니다.

```json
{
  "status": "error",
  "error_code": "graduation_center_not_ready",
  "message": "졸업 센터 준비가 필요합니다.",
  "detail": {
    "missing_files": [],
    "chroma": {
      "available": false
    }
  }
}
```

---

## 16. 운영/보안 기획

### 16.1 현재 운영 리스크

| 리스크 | 설명 | 우선순위 |
| --- | --- | --- |
| CORS 전체 허용 | `allow_origins=["*"]` | P0 |
| 관리자 API 인증 없음 | `/ingest/run`, `/ingest/live-refresh`, `/sources` | P0 |
| 포트 문서 불일치 | 문서 8000, 프론트 8001 | P0 |
| reload 운영 위험 | 개발용 `uvicorn --reload` | P1 |
| source dump 노출 | `/sources`가 전체 chunk를 노출 | P1 |
| 졸업센터 비용/민감도 | GPT + 성적증명서 처리 | P1 |

### 16.2 운영 전 필수 조치

- 관리자 API에 인증 또는 내부망 제한을 적용합니다.
- CORS를 실제 프론트 도메인으로 제한합니다.
- `/sources`는 운영자용으로 분리하거나 pagination/redaction을 적용합니다.
- ingestion 실행은 rate limit과 권한 검사를 모두 통과해야 합니다.
- 성적증명서 업로드 파일 크기 제한, content-type 검증, audit logging 정책을 정의합니다.
- 환경변수 문서를 정리합니다.

### 16.3 로그 정책

기획상 로그에 남겨도 되는 것:

- endpoint path
- status code
- issue_type
- source count
- network_success/fallback/network_failed count
- action_id
- safety flag 종류

로그에 남기면 안 되는 것:

- 질문 원문 중 개인정보 가능성이 있는 값
- action slot 원문
- PDF raw text
- OpenAI prompt 전문
- API key, 포털 계정, 연락처

---

## 17. QA 체크리스트

### 17.1 기본 API

- [ ] `GET /health`가 200을 반환합니다.
- [ ] `GET /`는 `frontend/dist`가 있으면 HTML을 반환합니다.
- [ ] `POST /ask`는 정상 질문에 answer/citations/next_actions를 반환합니다.
- [ ] `POST /ask`는 개인정보 질문을 `privacy_blocked`로 차단합니다.
- [ ] `GET /sources`는 JSONL chunk count와 sources를 반환합니다.

### 17.2 RAG 답변

- [ ] 공결 질문이 `attendance`로 분류됩니다.
- [ ] 휴학 질문이 `leave_return`으로 분류됩니다.
- [ ] 수변 질문이 `course_registration`으로 분류됩니다.
- [ ] 공식 근거가 없으면 no source 안내로 차단됩니다.
- [ ] 답변 본문 marker와 `citations` id가 일치합니다.
- [ ] `output_privacy.ok`가 true인 경우만 polish 답변을 유지합니다.

### 17.3 action flow

- [ ] 지원하지 않는 action은 `unsupported`를 반환합니다.
- [ ] `/actions/start`는 required slot 질문을 반환합니다.
- [ ] slot 일부 누락 시 `/actions/continue`는 `needs_input`을 반환합니다.
- [ ] 모든 slot 입력 시 `completed`와 document/checklist를 반환합니다.
- [ ] slot 값에 학번/연락처/성적이 있으면 `blocked`를 반환합니다.
- [ ] 완료 문서에 민감정보 flag가 있으면 초안을 반환하지 않습니다.

### 17.4 ingestion

- [ ] 동시 ingest 요청 중 하나는 skipped됩니다.
- [ ] cooldown 중 `force_rebuild=false`이면 skipped됩니다.
- [ ] fetch 실패 시 fallback count가 응답에 표시됩니다.
- [ ] Chroma 오류가 있어도 JSONL 저장은 실패하지 않습니다.
- [ ] ingest 완료 후 `retriever.reload()`가 호출되어 keyword index가 최신화됩니다.

### 17.5 live refresh

- [ ] `/ask`에서 privacy blocked이면 live refresh가 실행되지 않습니다.
- [ ] `live_check=true`이면 관련 official source refresh 결과가 응답에 포함됩니다.
- [ ] 네트워크 실패와 fallback 사용 여부가 숨겨지지 않습니다.
- [ ] fallback 문서는 기존 chunk를 덮어쓰지 않습니다.

### 17.6 졸업센터

- [ ] `/graduation/status`가 privacy policy를 반환합니다.
- [ ] PDF가 아니면 `/graduation/transcript/parse`가 400을 반환합니다.
- [ ] 이미지 기반 PDF는 동의 없을 때 `needs_vision_consent`를 반환합니다.
- [ ] transcript response에 raw text, GPA 숫자, 과목별 성적이 없습니다.
- [ ] readiness 조건이 부족하면 분석 API가 503을 반환합니다.
- [ ] 민감 입력이 감지되면 `blocked`를 반환합니다.
- [ ] 분석 응답 source id는 `G1`, `G2` 형태로 부여됩니다.

---

## 18. 릴리즈 판단 기준

### 18.1 데모 릴리즈 가능 조건

- `/health`가 정상이고 keyword chunk가 1개 이상입니다.
- 대표 질문 5개가 `/ask`에서 정상 응답합니다.
- citation contract가 통과합니다.
- 출석인정신청서 action flow가 완료됩니다.
- 개인정보 차단 시나리오가 정상 동작합니다.
- 졸업센터가 ready이거나 준비 필요 메시지가 명확합니다.
- live refresh 실패 시에도 fallback/기존 근거 사용 상태가 응답에 표시됩니다.

### 18.2 학생 대상 베타 조건

- 관리자 API가 학생에게 노출되지 않습니다.
- CORS가 개발/운영 도메인으로 제한됩니다.
- 포트/API base 정책이 문서와 코드에서 일치합니다.
- 에러 응답 shape가 표준화됩니다.
- `/sources` 노출 범위가 제한됩니다.
- 졸업센터 privacy QA가 통과합니다.
- 주요 API regression test가 자동화됩니다.

### 18.3 운영 배포 조건

- 관리자 인증/권한 체계가 적용됩니다.
- 수집/인덱싱 작업에 rate limit, cooldown, lock이 모두 적용됩니다.
- 로그에서 민감정보가 제거됩니다.
- OpenAI 비용/timeout/fallback 정책이 명확합니다.
- 성적증명서 업로드 보안 정책이 확정됩니다.
- 공식 출처 최신성 및 fallback 사용 정책이 사용자에게 설명됩니다.
- 배포 서버는 reload가 아닌 production server 설정을 사용합니다.

---

## 19. 향후 개선 로드맵

### 19.1 P0

| 과제 | 이유 |
| --- | --- |
| API 포트/환경변수 정리 | 프론트-백엔드 연결 혼선 제거 |
| 관리자 API 인증 | ingest/source 노출 보호 |
| CORS 제한 | 운영 보안 기본 요건 |
| 에러 envelope 표준화 | 프론트 오류 UX 안정화 |
| 졸업센터 업로드 제한 | 민감 파일 처리 안정화 |

### 19.2 P1

| 과제 | 기대 효과 |
| --- | --- |
| API response model 명시 | OpenAPI 문서와 FE 계약 강화 |
| `/sources` pagination/redaction | 응답 크기와 정보 노출 감소 |
| classifier regression suite 확장 | 학생식 표현 대응 |
| live refresh 결과 cache 정책 | 학교 서버 부담 완화 |
| citation coverage report | 근거 없는 문장 탐지 |

### 19.3 P2

| 과제 | 기대 효과 |
| --- | --- |
| admin page 분리용 token auth | 운영자 UX 정리 |
| background ingest job queue | API timeout/동시성 안정화 |
| chunk quality dashboard | 수집 품질 관리 |
| structured API for answer sections | 프론트 카드 UI 구현 용이 |
| OpenTelemetry 또는 structured logging | 운영 모니터링 강화 |

---

## 20. 부록: 파일 기준 매핑

| 파일 | 백엔드 기획 영역 |
| --- | --- |
| `app.py` | API gateway, service orchestration |
| `agent/guard.py` | privacy/source guard |
| `agent/classifier.py` | issue classification |
| `agent/planner.py` | next action recommendation |
| `agent/answer_builder.py` | deterministic grounded answer |
| `agent/answer_validator.py` | citation/privacy output validation |
| `agent/action_state.py` | action state machine |
| `tools/document_drafter.py` | action schema and document drafting |
| `retriever/hybrid_retriever.py` | search merge policy |
| `retriever/keyword_retriever.py` | JSONL keyword retrieval |
| `retriever/vector_retriever.py` | optional Chroma retrieval |
| `ingestion/pipeline.py` | official source ingestion |
| `ingestion/live_refresh.py` | issue-scoped refresh |
| `crawler/base.py` | official crawler safety policy |
| `graduation_center/models.py` | graduation request/response contract |
| `graduation_center/service.py` | graduation RAG/GPT service |
| `llm_client.py` | optional LLM helper |
| `data/processed/chunks.jsonl` | general RAG source of truth |
| `data/state/crawler_state.json` | crawl state |
| `data/graduation` | graduation structured data |

---

## 21. 결론

이 백엔드는 단순 API 서버가 아니라 공식 근거, 개인정보 보호, 다음 행동 생성을 함께 책임지는 학사 행정 RAG 오케스트레이터입니다.

운영 전 핵심은 세 가지입니다.

1. 공식 근거와 citation contract를 깨지 않는 안정적인 답변 파이프라인을 유지합니다.
2. 개인정보와 성적증명서 처리 범위를 명확히 제한합니다.
3. 수집/관리 API를 학생용 API와 분리하고 권한을 적용합니다.

이 기준을 지키면 프론트엔드의 메타버스 캠퍼스 경험은 단순한 화면 연출이 아니라, 백엔드의 공식 근거 검색과 안전한 행정 액션 생성 능력을 학생이 이해하기 쉬운 방식으로 드러내는 제품 경험이 됩니다.
