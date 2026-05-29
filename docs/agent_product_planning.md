# KMU 캠퍼스 생활 액션 에이전트 기획 문서

> 문서 목적: 현재 구현된 에이전트 동작을 기준으로 역할, 판단 흐름, 도구 호출, 안전 정책, 액션 설계, 평가 기준을 정리하기 위한 기획 문서  
> 작성일: 2026-05-24  
> 대상: 기획, 에이전트 설계, 백엔드, 프론트엔드, QA, RAG/데이터 담당자  
> 기준 범위: `agent/`, `tools/`, `retriever/`, `llm_client.py`, `app.py`의 에이전트 orchestration  
> 관련 문서: `docs/frontend_product_planning.md`, `docs/backend_product_planning.md`

---

## 1. 문서 요약

### 1.1 에이전트 한 줄 정의

국민대학교 학생의 학사·행정·생활지원 질문을 개인정보 없이 이해하고, 공식 근거를 검색한 뒤, 답변과 다음 행동 초안을 함께 제공하는 규칙 기반 RAG 액션 에이전트입니다.

### 1.2 에이전트가 해결하는 문제

학생은 보통 아래 방식으로 질문합니다.

- "이캠에 강의가 안 떠요"
- "국장 신청 뭐 확인해야 해?"
- "예비군 가면 출석 어떻게 돼?"
- "복학생인데 이번 주 뭐 해야 해?"
- "모바일학생증이 안 찍혀요"
- "졸업요건 부족한지 알고 싶어요"

이 질문들은 단순 검색어가 아닙니다. 에이전트는 질문 안의 상황, 학생식 표현, 학생 상태, 공식 근거 필요성, 다음 행동 필요성을 함께 판단해야 합니다.

### 1.3 에이전트의 제품 책임

- 학생 질문에서 민감정보를 감지하고 차단합니다.
- 학생식 표현을 공식 용어와 연결합니다.
- 질문을 이슈 타입으로 분류합니다.
- 공식 자료 chunk를 검색하고, 근거가 없으면 절차 안내를 만들지 않습니다.
- 답변 본문에 citation marker를 포함합니다.
- 학생 상황에 맞는 체크리스트, 문의처, 기한, 준비물, 주의사항을 조립합니다.
- 사용자가 이어서 실행할 수 있는 action을 추천합니다.
- action 수행 시 필요한 slot만 질문하고, 개인정보 입력을 다시 차단합니다.
- LLM을 사용하더라도 deterministic answer contract와 개인정보 guard를 우선합니다.

### 1.4 현재 에이전트의 핵심 성격

현재 에이전트는 완전 자율형 agent가 아니라, 안전한 절차 안내를 위한 deterministic orchestration agent입니다.

즉, 에이전트의 핵심은 자유 생성이 아니라 아래 세 가지입니다.

1. **판단**: 질문을 어떤 행정 이슈로 볼 것인가
2. **근거 선택**: 어떤 공식 chunk를 근거로 삼을 것인가
3. **행동 연결**: 학생이 다음에 무엇을 준비하도록 도울 것인가

---

## 2. 에이전트 범위

### 2.1 포함 범위

| 범위 | 설명 |
| --- | --- |
| 학사/행정 Q&A | 출석, 휴복학, 수강신청, 등록금, 증명서, 학생증, 장학, 학사일정 등 |
| 생활지원 Q&A | 통학버스, 주차, 생활관, 도서관, 식단, 학생보험 등 |
| 포털/eCampus 안내 | 로그인 이후 개인 화면 대신 공식 경로와 확인 순서 안내 |
| 문의처 라우팅 | 이슈별 기본 문의처와 chunk 기반 문의처 추천 |
| 문서/체크리스트 초안 | 출석인정신청서, 휴복학 체크리스트, 문의문 등 |
| 학생 상태 맞춤 안내 | 신입생, 재학생, 복학생, 휴학생, 졸업예정자 |
| 졸업요건 보조 | 비식별 학점 요약 기반 간이 진단과 수강계획 방향 |
| 공식 자료 최신성 보조 | optional live check와 ingest 결과 활용 |

### 2.2 제외 범위

| 제외 범위 | 이유 |
| --- | --- |
| ON국민 로그인 대행 | 로그인 정보 수집 금지 |
| eCampus 개인 강의 화면 조회 | post-login 개인 정보 접근 금지 |
| 성적표 원문 저장 | 개인정보·민감 학업정보 보호 |
| 실제 학번/전화번호/주민번호 처리 | guardrail 위반 |
| 최종 행정 승인 판단 | 학교 담당 부서 권한 |
| 공식 근거 없는 절차 조언 | hallucination 방지 |
| 에브리타임/비공식 커뮤니티 크롤링 | 출처 신뢰도와 정책 문제 |

### 2.3 에이전트가 항상 유지해야 하는 문장

학생이 실제 행정 처리를 해야 하는 경우, 답변은 항상 아래 메시지를 유지해야 합니다.

```text
최종 처리는 국민대학교 공식 포털, 담당 부서, 학과사무실 또는 담당 교강사 확인이 필요합니다.
실제 개인정보나 로그인 정보는 입력하지 마세요.
```

---

## 3. 에이전트 구조

### 3.1 전체 에이전트 지도

```text
User Question
  → Privacy Guard
  → Issue Classifier
  → Student Context / Student Playbook
  → Search Query Builder
  → Optional LLM Query Expansion
  → Optional Live Refresh
  → Hybrid Retriever
  → Issue-Matched Chunk Preference
  → Optional LLM Rerank
  → Source Guard
  → Action Planner
  → Answer Builder
      ├── Citation Builder
      ├── Checklist Tool
      ├── Contact Router
      ├── Deadline Tool
      ├── Student Playbook
      └── Student Context Guidance
  → Optional LLM Polish
  → Final Output Guard
  → API Response
```

### 3.2 주요 모듈

| 모듈 | 역할 |
| --- | --- |
| `agent/guard.py` | 개인정보 입력 차단, 공식 근거 부족 차단 |
| `agent/classifier.py` | 질문을 issue_type으로 분류 |
| `agent/student_playbook.py` | 학생식 표현, 실무 팁, 흔한 실수 제공 |
| `agent/student_context.py` | 비식별 학생 상태 기반 맞춤 확인 항목 생성 |
| `agent/planner.py` | 다음 action 후보 추천 |
| `agent/answer_builder.py` | 최종 답변 본문 deterministic 조립 |
| `agent/citation.py` | chunk별 `S1`, `S2` citation label 생성 |
| `agent/answer_validator.py` | citation/output privacy contract 검증 |
| `agent/action_state.py` | action start/continue 상태 전환 |
| `tools/document_drafter.py` | action별 slot schema와 초안 생성 |
| `tools/checklist.py` | 공식 chunk 기반 체크리스트 생성 |
| `tools/contact_router.py` | 이슈별 문의처 추천 |
| `tools/deadline.py` | 날짜 추출과 제출기한 계산 |
| `retriever/hybrid_retriever.py` | vector/keyword 검색 병합 |
| `llm_client.py` | optional query expansion/rerank/polish |

---

## 4. 에이전트 페르소나

### 4.1 서비스 안에서의 말투

에이전트는 국민대 학생에게 아래 톤으로 응답합니다.

- 한국어 우선
- 행정 문서처럼 딱딱하기보다 학생이 바로 실행할 수 있게 설명
- 단정적인 최종 판정 대신 확인 경로와 준비 항목 제시
- 개인정보 입력을 요청하지 않음
- 근거가 부족하면 부족하다고 말함
- "어디서 확인하면 되는지", "무엇을 준비하면 되는지", "누구에게 문의하면 되는지"를 분리해서 안내

### 4.2 에이전트의 제품적 위치

에이전트는 "행정 담당자"가 아니라 "공식 근거를 읽고 학생이 다음 행동을 준비하도록 돕는 안내자"입니다.

따라서 아래 표현은 피해야 합니다.

- "확정입니다"
- "승인됩니다"
- "반드시 처리됩니다"
- "제가 대신 확인했습니다"
- "학번을 알려주세요"
- "성적표를 올려주세요"
- "비밀번호를 입력하세요"

권장 표현은 아래와 같습니다.

- "공식 근거상 확인되는 내용은 다음과 같습니다."
- "개인 처리 상태는 ON국민에서 직접 확인해야 합니다."
- "담당 부서 확인이 필요합니다."
- "개인정보 없이 상황을 요약하면 다음 문의문을 사용할 수 있습니다."
- "공식 근거에서 제출서류가 확인되지 않아 담당 부서 확인이 필요합니다."

---

## 5. 입력 이해 정책

### 5.1 질문 입력

`POST /ask`의 핵심 입력은 아래와 같습니다.

| 필드 | 의미 |
| --- | --- |
| `question` | 학생 질문 원문 |
| `student_context` | 비식별 학생 상태, 대상 학기, 관심 항목 |
| `llm_assist` | LLM 보조 기능 사용 여부 |
| `live_check` | 공식 소스 live refresh 시도 여부 |

### 5.2 비식별 학생 맥락

에이전트는 아래 정도의 맥락만 personalization에 사용합니다.

| 필드 | 예시 | 허용 이유 |
| --- | --- | --- |
| `status` | 신입생, 재학생, 복학생, 휴학생, 졸업예정자 | 민감 개인식별 아님 |
| `term` | 2026-2학기 | 신청기간 안내에 필요 |
| `concern` | 수강신청, 등록금, 졸업 | 관심 항목 우선순위에 필요 |

사용하면 안 되는 맥락은 아래와 같습니다.

- 학번
- 주민번호
- 전화번호
- 실제 성적
- 포털 ID/PW
- 성적표 원본

### 5.3 학생식 표현 인식

학생은 공식 용어보다 생활 표현을 사용합니다. 에이전트는 `student_playbook`과 `classifier`를 통해 이를 해석합니다.

| 학생 표현 | 에이전트 해석 |
| --- | --- |
| 이캠, 이캠퍼스, 가대 | eCampus |
| 온국민, 포털, 종정시 | ON국민 포털 |
| 과사 | 학과사무실 |
| 케이카드, K-CARD | 모바일학생증/학생증 |
| 국장 | 국가장학금 |
| 장바구니, 담아두기 | 수강신청 장바구니 |
| 납부확인 | 등록금 납부 확인 |
| 훈련필증, 소집통지서 | 예비군 출석인정 증빙 |

이 표현은 답변에서 "알아들은 국민대식 표현"으로 보여줄 수 있습니다.

---

## 6. 이슈 분류 설계

### 6.1 issue_type 목록

현재 에이전트가 다루는 주요 issue_type은 아래와 같습니다.

| issue_type | 사용자 의도 |
| --- | --- |
| `attendance` | 출석인정, 공결, 결석, 예비군 출석 |
| `leave_return` | 휴학, 복학, 질병휴학, 군휴학 |
| `course_registration` | 수강신청, 수강정정, 폐강, 시간표 |
| `registration_tuition` | 등록금, 분납, 납부확인, 고지서 |
| `certificate` | 증명서 발급 |
| `student_id` | 학생증, 모바일학생증, K-CARD |
| `scholarship` | 장학금, 국가장학금, 근로장학, 학자금 |
| `portal_access` | ON국민, eCampus, 로그인, 계정 접근 |
| `campus_facility` | 통학버스, 주차, 생활관, 도서관, 식단 |
| `academic_record` | 학적부 정정, 이름/영문명/주소 변경 |
| `student_insurance` | 학생보험, 상해, 사고, 치료비 |
| `graduation` | 졸업요건, 이수학점, 요람 |
| `schedule` | 학사일정, 마감, 이번 주/이번 달 할 일 |
| `contact` | 문의처, 부서, 어디로 물어볼지 |
| `military` | 병무, 예비군 |
| `other` | 분류 불가 |

### 6.2 분류 방식

현재 분류기는 rule-based keyword scoring 방식입니다.

```text
question
  → lowercase normalization
  → ISSUE_KEYWORDS score 계산
  → military/schedule special case 처리
  → meta issue 제외 후 대표 issue_type 선택
```

### 6.3 분류 설계 원칙

- 학생 경험에서 자주 겹치는 단어를 고려합니다.
- "예비군"만 있으면 `military`, "예비군 출석인정"이면 `attendance`로 볼 수 있어야 합니다.
- "이번 주 뭐 해야 해"처럼 일정 의도가 강하면 `schedule`을 우선합니다.
- `schedule`, `contact`, `student_support` 같은 meta issue는 더 구체적인 이슈가 있으면 보조 신호로 다룹니다.

### 6.4 분류 개선 과제

| 과제 | 필요 이유 |
| --- | --- |
| 복합 의도 분류 | "복학생인데 등록금 고지서 안 떠요"는 복학+등록금이 함께 있음 |
| confidence calibration | 현재 confidence는 단순 score 기반 |
| top-k issue 반환 | 프론트에서 "혹시 이 주제인가요?" 확인 가능 |
| 테스트 질문 corpus 확장 | 실제 학생식 표현 수집 필요 |
| 이슈별 negative keyword | 비슷한 표현의 오분류 감소 |

---

## 7. 개인정보 Guard 설계

### 7.1 입력 guard

`inspect_privacy`는 질문과 action slot 값에서 개인정보 패턴을 감지합니다.

차단 대상:

| flag | 예시 |
| --- | --- |
| `student_id` | 실제 학번 또는 "학번" 입력 |
| `resident_number` | 주민번호 |
| `portal_password` | 실제 비밀번호, 포털 PW |
| `grade_report` | 성적표 원본, 내 성적, GPA 등 |
| `phone` | 휴대전화번호, 연락처 |

차단 응답:

```text
실제 학번, 성적, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력받지 않습니다.
가상 사례나 사용자가 직접 요약한 비식별 정보로만 안내할 수 있습니다.
```

### 7.2 비밀번호 질문 처리

비밀번호 관련 질문은 모두 차단하지 않습니다.

허용:

- "비밀번호를 잊었어"
- "eCampus 비밀번호 찾기는 어디서 해?"

차단:

- "제 비밀번호는 abcd1234입니다"
- "내 포털 비밀번호로 로그인해줘"

### 7.3 출력 guard

`answer_validator.validate_output_privacy`는 최종 답변 또는 action 문서 초안에 민감한 실제 값이 포함되는지 다시 검사합니다.

출력 guard가 실패하면:

- LLM polish 결과를 폐기하고 deterministic 답변으로 fallback합니다.
- action 문서 초안이면 반환하지 않고 차단 메시지를 반환합니다.

### 7.4 기획상 안전 UX

프론트는 개인정보 차단 시 아래 UX를 제공해야 합니다.

- 무엇이 차단됐는지 flag를 너무 노골적으로 재노출하지 않습니다.
- "학번 대신 학년/상태만 입력해 주세요"처럼 대체 입력을 안내합니다.
- slot form에는 개인정보 입력 금지 helper text를 계속 표시합니다.
- 졸업센터는 원본 업로드 전 별도 privacy notice와 동의 UI를 둡니다.

---

## 8. Grounding 설계

### 8.1 공식 근거 우선 원칙

에이전트는 공식 chunk가 없으면 절차성 답변을 생성하지 않습니다.

```text
retriever.search(...)
  → chunks empty
  → require_sources blocked
  → "공식 문서 근거가 부족하므로 확인이 필요합니다."
```

### 8.2 retrieval source

일반 RAG의 기준 데이터는 `data/processed/chunks.jsonl`입니다.

검색은 `HybridRetriever`가 담당합니다.

```text
VectorRetriever.search
KeywordRetriever.search
→ chunk_id 기준 병합
→ score와 source_tier 기준 정렬
```

Vector retriever는 optional accelerator입니다. Chroma가 없어도 keyword path로 동작해야 합니다.

### 8.3 issue matched chunk preference

검색 후 `app.py`의 `_prefer_issue_matched_chunks`는 분류된 issue_type에 맞는 chunk를 우선합니다.

설계 의도:

- 일반 검색 결과가 비슷한 키워드로 흐트러지는 것을 줄입니다.
- `issue_types` metadata가 명시된 chunk를 우선합니다.
- ingest 전에도 crawler의 공식 URL-bound fallback chunk를 사용할 수 있습니다.
- `schedule`은 날짜 순 정렬을 우선합니다.

### 8.4 citation contract

답변의 사실/절차 주장은 citation marker와 연결되어야 합니다.

```text
본문: 출석인정 신청은 사유 발생 7일 이내 제출이 필요합니다.[S1]
근거: [S1] 학사안내 / official URL / excerpt
```

에이전트 계약:

- `S1`, `S2`는 unique chunk 기준으로 부여합니다.
- 본문 marker는 `[근거]` 블록의 citation id와 일치해야 합니다.
- `[None]` 같은 marker는 허용하지 않습니다.
- citation 목록이 있는데 inline marker가 없으면 guard flag를 반환합니다.

### 8.5 공식 근거와 학생 경험 팁의 구분

답변에는 공식 근거 기반 내용과 학생 경험 팁이 함께 들어갑니다.

구분 원칙:

- 절차, 서류, 기한, 제출처는 공식 chunk citation이 필요합니다.
- 학생 경험 팁은 실무적 안내지만 최종 판단으로 쓰면 안 됩니다.
- 학생 경험 팁은 문의 전 준비, 흔한 실수, 확인 순서 중심으로 제한합니다.

---

## 9. 답변 생성 Agent

### 9.1 답변 생성 방식

현재 `/ask`의 최종 답변은 LLM이 직접 작성하지 않고 `answer_builder.py`가 조립합니다.

답변 섹션:

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

### 9.2 답변 요약 정책

`_build_summary`는 issue_type별 고정 템플릿을 사용합니다.

예시:

| issue_type | 요약 방향 |
| --- | --- |
| `attendance` | 출석인정 가능성, 증빙, 7일 이내 제출 |
| `leave_return` | 휴복학 유형별 경로와 서류 차이 |
| `course_registration` | 나의 시간표/개인수업시간표 확인 |
| `registration_tuition` | 고지서, 납부 상태, 장학/학적 영향 |
| `portal_access` | 개인 화면은 사용자가 직접 확인 |
| `schedule` | 오늘 기준 진행/예정 일정 |
| `graduation` | 요람/학과 기준과 최종 확인 필요 |

### 9.3 체크리스트 생성

`tools/checklist.py`는 두 종류의 정보를 합칩니다.

1. issue_type별 기본 task
2. 공식 chunk metadata의 required_documents, application_path, submit_to

기획상 checklist는 "학생이 지금 할 일"이어야 하며, 설명형 문장보다 실행형 문장을 우선합니다.

### 9.4 문의처 추천

`tools/contact_router.py`는 아래 순서로 문의처를 구성합니다.

1. chunk metadata의 `contacts`
2. issue_type별 default contact

프론트는 문의처를 별도 카드나 answer section으로 보여줄 수 있습니다.

주의:

- 연락처가 있으면 표시합니다.
- 연락처가 없으면 부서명/역할만 표시합니다.
- 개인 처리가 필요한 문의는 "사용자가 직접 포털 확인"을 함께 안내합니다.

### 9.5 기한 계산

`tools/deadline.py`는 질문에서 날짜를 추출하고 chunk의 `deadline_rule.days`로 제출기한을 계산합니다.

지원 입력:

- `YYYY-MM-DD`
- `2026년 5월 15일`
- `5월 15일`은 기본 연도 2026 사용

기획상 개선 필요:

- 현재 기본 연도가 고정되어 있어 운영 시 현재 연도 기준으로 바꿔야 합니다.
- 마감일이 공휴일/주말일 때 처리 정책이 필요합니다.
- "다음 주 월요일" 같은 상대 날짜 파싱은 아직 제한적입니다.

### 9.6 학생 맞춤 확인

`student_context_guidance`는 학생 상태별로 추가 확인 항목을 제공합니다.

예시:

| 상태 | 추가 확인 |
| --- | --- |
| 신입생 | 포털 사용자등록, eCampus 로그인, 모바일학생증 발급 시점 |
| 복학생 | 복학 승인, 수강신청 가능 상태, 등록금 고지서 반영 |
| 휴학생 | 휴학 중 가능한 절차와 복학 예정 학기 일정 |
| 졸업예정자 | 필수과목, 졸업인증, 증명서 발급 가능 시점 |

---

## 10. Student Playbook 설계

### 10.1 목적

`student_playbook.py`는 공식 근거 검색만으로는 부족한 "학생이 실제로 헷갈리는 흐름"을 보완합니다.

단, playbook은 공식 절차를 대체하지 않습니다.

### 10.2 playbook 구성

| 필드 | 의미 |
| --- | --- |
| `scenario` | 현재 상황을 학생 언어로 요약 |
| `prechecks` | 문의 전 확인할 항목 |
| `evidence` | 준비할 정보와 캡처 |
| `common_mistakes` | 흔한 착각 |
| `student_terms` | 질문에서 감지한 학생식 표현 |

### 10.3 override scenario

일부 질문은 같은 issue_type 안에서도 더 구체적인 상황으로 override합니다.

| 조건 | override |
| --- | --- |
| eCampus에 강의가 안 보임 | 수강신청 완료 여부와 강의 공개 시점 확인 |
| 등록금 냈는데 납부확인 안 보임 | 은행 납부와 포털 반영 시간 분리 |
| 모바일학생증 인식 안 됨 | 실물 카드 문제와 모바일 인증 문제 분리 |

### 10.4 playbook 관리 원칙

- 공식 근거가 아닌 생활 팁임을 명확히 둡니다.
- 민감정보 입력을 유도하지 않습니다.
- 학생의 다음 문의를 더 잘 준비시키는 방향이어야 합니다.
- "대신 처리"가 아니라 "확인 항목 정리"에 머뭅니다.

---

## 11. Action Planner 설계

### 11.1 다음 행동의 의미

다음 행동은 답변 이후 학생이 바로 이어서 할 수 있는 보조 작업입니다.

예시:

- 출석인정신청서 초안 작성
- 휴학/복학 준비 체크리스트 생성
- 등록금 문의문 초안 작성
- 졸업요건 간이 진단
- 수강계획 방향 추천

### 11.2 추천 방식

`suggest_actions(issue_type, chunks)`는 아래 정보를 조합합니다.

1. issue_type별 기본 action
2. chunk metadata의 `actions`
3. contact-ready issue일 경우 문의문 초안 action 추가
4. 중복 action 제거

### 11.3 action 목록

| action_id | 목적 | issue_type |
| --- | --- | --- |
| `draft_attendance_recognition_form` | 출석인정신청서 초안 | `attendance` |
| `draft_leave_checklist` | 휴학 준비 체크리스트 | `leave_return` |
| `draft_return_checklist` | 복학 준비 체크리스트 | `leave_return` |
| `course_registration_checklist` | 수강신청/폐강 확인 | `course_registration` |
| `certificate_issue_guide` | 증명서 발급 경로 | `certificate` |
| `student_id_issue_guide` | 학생증 발급 체크리스트 | `student_id` |
| `scholarship_notice_checklist` | 장학공지 확인 | `scholarship` |
| `portal_access_checklist` | 포털/eCampus 접근 체크리스트 | `portal_access` |
| `academic_schedule_digest` | 학사일정 체크리스트 | `schedule` |
| `campus_facility_guide` | 생활지원 이용 체크리스트 | `campus_facility` |
| `academic_record_correction_checklist` | 학적부 정정 체크리스트 | `academic_record` |
| `student_insurance_checklist` | 학생보험 청구 체크리스트 | `student_insurance` |
| `military_service_checklist` | 병무/예비군 체크리스트 | `military` |
| `graduation_audit` | 졸업요건 간이 진단 | `graduation` |
| `recommend_course_plan` | 수강계획 방향 추천 | `graduation` |
| `draft_contact_message` | 문의문 초안 | `contact` |

### 11.4 action 추천 UX 원칙

- action은 "지금 할 수 있는 일"로 표현합니다.
- action 시작 전 개인정보 입력 금지 안내를 보여줍니다.
- action 결과는 최종 제출본이 아니라 초안임을 표시합니다.
- 공식 양식이 필요한 경우 "학교 양식에 맞게 최종 확인" 문구를 포함합니다.

---

## 12. Action State Machine

### 12.1 기본 흐름

```text
POST /actions/start
  → action_id 검증
  → required_slots 확인
  → missing_slots 질문 반환

POST /actions/continue
  → slot privacy guard
  → policy chunk 검색
  → missing_slots 재확인
  → draft_action_document
  → output privacy guard
  → completed response
```

### 12.2 상태

| 상태 | 의미 |
| --- | --- |
| `unsupported` | 지원하지 않는 action_id |
| `needs_input` | 필수 slot이 부족함 |
| `completed` | 초안 또는 체크리스트 생성 완료 |
| `blocked` | 개인정보 또는 출력 guard에 의해 차단 |

### 12.3 slot 설계 원칙

slot은 행정 문서 초안에 필요한 최소 정보만 받아야 합니다.

허용 slot 예시:

- 결석일
- 수업명
- 결석 사유
- 증빙서류 종류
- 대상 학기
- 문의 주제
- 개인정보 없는 질문 요약
- 부족한 총 학점 숫자
- 부족한 전공 학점 숫자

금지 slot 예시:

- 학번
- 실제 이름
- 전화번호
- 주민번호
- 포털 ID/PW
- 성적표 원문
- 구체적인 성적 목록

### 12.4 action document 품질 기준

초안은 아래 조건을 만족해야 합니다.

- 제목이 명확해야 합니다.
- 학생이 직접 수정 가능한 문장이어야 합니다.
- 공식 절차의 최종 판단을 대신하지 않아야 합니다.
- 개인정보 입력을 요구하지 않아야 합니다.
- 준비물과 확인 순서가 checklist로 분리되어야 합니다.
- 문의문은 정중하고 짧아야 합니다.

---

## 13. LLM 보조 정책

### 13.1 현재 위치

LLM은 에이전트의 주 판단자가 아니라 보조자입니다.

가능한 역할:

- 검색어 확장
- 검색 chunk rerank
- deterministic 답변 문장 다듬기

불가능한 역할:

- 공식 근거 없는 절차 생성
- citation 없는 사실 추가
- 개인정보 처리
- 최종 행정 판단
- 로그인 후 개인 화면 대체 확인

### 13.2 query expansion

LLM이 활성화된 경우, 질문과 issue_type, student_context를 바탕으로 검색어를 확장할 수 있습니다.

fallback:

- LLM 실패 시 원래 검색어를 사용합니다.
- tool_logs에는 fallback 여부를 남깁니다.

### 13.3 rerank

LLM rerank는 검색된 chunk 중 답변에 더 적합한 chunk를 고르는 보조 역할입니다.

제약:

- 새 chunk를 생성하지 않습니다.
- official source chunk 밖의 정보를 추가하지 않습니다.
- 실패하면 기존 chunk 순서를 사용합니다.

### 13.4 polish

LLM polish는 deterministic 답변의 문장 표현만 다듬습니다.

제약:

- 새 절차, 날짜, 부서명, 전화번호, 서류명, 신청 경로 추가 금지
- citation marker 유지
- output privacy와 citation validation 실패 시 폐기

### 13.5 LLM 메타데이터

응답의 `llm` 필드는 아래 상태를 프론트와 QA에 제공합니다.

| 필드 | 의미 |
| --- | --- |
| `enabled` | LLM 클라이언트 활성화 여부 |
| `polish_enabled` | polish 기능 활성화 여부 |
| `assist_requested` | 사용자/API 요청 여부 |
| `query_expansion.used` | 검색어 확장 사용 여부 |
| `rerank.used` | rerank 사용 여부 |
| `polish.used` | polish 사용 여부 |
| `rejected_reason` | guard로 polish 폐기된 이유 |

---

## 14. Live Check Agent

### 14.1 목적

`live_check`는 특정 질문이나 action에 대해 공식 소스를 짧게 새로 확인하는 기능입니다.

사용 위치:

- `/ask`
- `/actions/continue`
- `/ingest/live-refresh`

### 14.2 동작

```text
issue_type + query
  → refresh_sources_for_issue
  → public official sources only
  → updated이면 retriever.reload
  → response.live_check에 결과 포함
```

### 14.3 정책

- 로그인 페이지나 개인 화면은 수집하지 않습니다.
- 에브리타임 등 비공식 커뮤니티는 사용하지 않습니다.
- issue 범위 내에서 제한적으로만 새로 확인합니다.
- 학교 서버 보호 정책은 crawler layer에서 유지해야 합니다.

### 14.4 UX 원칙

프론트는 live check를 "최신 공식 자료 확인"으로 표현할 수 있습니다.

다만 아래 메시지를 유지해야 합니다.

- live check는 최종 행정 승인 확인이 아닙니다.
- network 실패 시 fallback 자료를 사용할 수 있습니다.
- 최신 공지는 사용자가 공식 페이지에서 한 번 더 확인해야 합니다.

---

## 15. 졸업 에이전트

### 15.1 일반 RAG와의 차이

졸업센터는 일반 `/ask`와 별도 도메인입니다.

일반 RAG:

- 공식 chunk 검색 기반 답변
- `data/processed/chunks.jsonl`
- `HybridRetriever`

졸업센터:

- 비식별 transcript summary 기반 분석
- `graduation_center` 서비스
- `data/graduation` 구조화 데이터
- 졸업용 인덱스와 분석 task

### 15.2 졸업센터 입력 원칙

원본 성적표는 저장하지 않는 것이 원칙입니다.

허용 입력:

- 파싱된 비식별 학점 요약
- 영역별 이수학점
- 과목명 중심의 sanitized course summary
- 등록 학기 수 같은 비식별 조건

주의 입력:

- PDF 업로드는 parsing을 위한 일시 처리여야 합니다.
- OCR consent가 필요한 경우 명시해야 합니다.
- 결과에는 최종 졸업 판정이 아니라 "확인 필요"가 남아야 합니다.

### 15.3 졸업 task

| endpoint/task | 목적 |
| --- | --- |
| `/graduation/audit` | 졸업요건 분석 |
| `/graduation/substitute-courses` | 대체과목 후보 확인 |
| `/graduation/micro-degree` | 마이크로디그리 기회 분석 |
| `/graduation/post-graduation-checklist` | 졸업 이후 행정 체크리스트 |
| `/graduation/career-translator` | 수강 이력을 직무 역량 언어로 변환 |
| `/graduation/early-graduation` | 조기졸업 가능성 및 주의사항 |
| `/graduation/customized-major` | 자기설계/맞춤형 전공 인정 확인 |
| `/graduation/credit-drop` | 학점 포기/성적 관련 정책 확인 |

### 15.4 졸업 에이전트 UX

졸업 결과는 항상 아래를 분리해야 합니다.

- 자동 분석 결과
- 부족하거나 불확실한 항목
- 학생이 학과/교무팀에 확인할 질문
- 다음 학기 수강계획에 반영할 항목
- 최종 판정은 학교 담당 부서 확인 필요

---

## 16. 응답 계약

### 16.1 `/ask` 응답

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `answer` | 최종 한국어 답변 |
| `issue_type` | 분류된 이슈 |
| `classification` | confidence와 score |
| `tool_logs` | 내부 tool 호출 trace |
| `sources` | 검색된 chunk |
| `citations` | UI용 citation 목록 |
| `next_actions` | 추천 action |
| `safety_flags` | guard/validator flag |
| `answer_validation` | citation contract 검증 결과 |
| `output_privacy` | 출력 개인정보 검증 결과 |
| `llm` | LLM 보조 사용 여부 |
| `live_check` | live refresh 결과 |

### 16.2 `/actions/start` 응답

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `status` | `needs_input` 또는 `unsupported` |
| `action_id` | action 식별자 |
| `label` | 사용자 표시 이름 |
| `issue_type` | 관련 이슈 |
| `missing_slots` | 필요한 slot |
| `questions` | 사용자에게 물어볼 문장 |
| `privacy_notice` | 개인정보 입력 금지 안내 |

### 16.3 `/actions/continue` 응답

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `status` | `needs_input`, `completed`, `blocked` |
| `document` | 생성된 문서 초안 |
| `checklist` | 실행 체크리스트 |
| `audit` | 졸업 간이 진단 결과, 해당 action에서만 |
| `output_privacy` | 초안 개인정보 검증 결과 |
| `live_check` | live refresh 결과 |

### 16.4 tool_logs 활용

`tool_logs`는 사용자에게 전부 노출하기보다 개발/QA/관리자 모드에서 유용합니다.

예시:

```text
guard.inspect_privacy 호출됨
classify_issue 호출됨
search_official_sources 호출됨
guard.require_sources 호출됨
suggest_actions 호출됨
generate_checklist 호출됨
route_contact 호출됨
build_final_answer 호출됨
guard.final_output_guard 호출됨
```

기획상 활용:

- QA가 agent decision path를 확인
- LLM fallback 여부 추적
- live check 실행 여부 추적
- guard 차단 위치 확인

---

## 17. 에이전트 시나리오

### 17.1 예비군 출석인정

입력:

```text
예비군 훈련 때문에 수업 빠지면 출석인정 어떻게 해?
```

흐름:

```text
privacy ok
→ issue_type attendance
→ attendance/military 관련 official chunks 검색
→ 출석인정 checklist 생성
→ 담당 교강사/교무팀 문의처 추천
→ draft_attendance_recognition_form action 추천
```

답변이 포함해야 할 내용:

- 출석인정 가능 사유일 수 있음
- 증빙서류 확인
- 제출기한 확인
- 담당 교강사 제출 여부 확인
- 개인정보 입력 금지

### 17.2 eCampus 강의 미표시

입력:

```text
이캠에 강의가 안 떠요
```

흐름:

```text
issue_type portal_access
→ student term eCampus 감지
→ playbook override: 강의 미표시 상황
→ 공식 로그인/포털/eCampus 근거 검색
→ portal_access_checklist 추천
→ draft_contact_message 추천
```

답변이 포함해야 할 내용:

- 수강신청 완료 여부 확인
- 개강 직후 강의 공개 시점 확인
- 포털/eCampus 서비스 구분
- 비밀번호/학번 입력 금지
- 문제 화면, 과목명, 분반, 발생 시간 준비

### 17.3 복학생 이번 주 할 일

입력:

```text
복학생인데 이번 주 뭐 해야 해?
```

student_context:

```json
{
  "status": "returning",
  "term": "2026-2학기",
  "concern": "수강신청"
}
```

흐름:

```text
issue_type schedule
→ student_context_guidance returning
→ schedule chunks 날짜순 정렬
→ 진행/예정 일정 표시
→ academic_schedule_digest action 추천
```

답변이 포함해야 할 내용:

- 복학 승인 상태 확인
- 수강신청 가능 상태 확인
- 등록금 고지서 반영 여부 확인
- 대상 학기 기준 일정 확인
- 개인 신청 상태는 ON국민에서 직접 확인

### 17.4 등록금 납부확인 지연

입력:

```text
등록금 냈는데 납부확인이 안 떠요
```

흐름:

```text
issue_type registration_tuition
→ playbook override: 납부 반영 지연 상황
→ 등록금/납부 공식 chunk 검색
→ 재무팀/등록 담당 부서 문의처 추천
→ draft_contact_message action 추천
```

답변이 포함해야 할 내용:

- 은행 납부 완료와 포털 반영은 다를 수 있음
- 납부 방식, 납부 일시, 영수증을 준비
- 개인 고지서와 납부 상태는 ON국민에서 직접 확인
- 장학/휴복학 상태가 고지 금액에 영향을 줄 수 있음

### 17.5 졸업요건 간이 진단

입력:

```text
졸업요건 부족한지 알고 싶어요
```

흐름:

```text
issue_type graduation
→ official graduation chunks 검색
→ graduation_audit action 추천
→ action slot으로 total/major credits만 요청
→ 부족 학점 계산
→ 최종 판정은 학과/교무팀 확인 안내
```

주의:

- 성적표 원본 입력 금지
- 실제 성적/GPA 입력 금지
- 간이 진단은 공식 판정이 아님

---

## 18. 실패와 Fallback

### 18.1 개인정보 차단

상황:

```text
내 학번은 2026xxxx이고 성적으로 처리해줘
```

응답:

- `issue_type`: `privacy_blocked`
- `sources`: empty
- `next_actions`: empty
- `safety_flags`: detected flags
- `llm.used`: false

### 18.2 근거 없음

상황:

```text
공식 chunk 검색 결과 없음
```

응답:

- 공식 문서 근거 부족 메시지
- 담당 부서/학과사무실 확인 안내
- sources/citations/next_actions empty

### 18.3 LLM 실패

상황:

- query expansion 실패
- rerank 실패
- polish 실패

정책:

- deterministic path로 계속 진행
- metadata에 fallback 기록
- 답변 생성 자체를 LLM 실패에 의존하지 않음

### 18.4 LLM polish guard 실패

상황:

- citation marker 누락
- 새 개인정보 값 포함
- `[None]` marker 발생

정책:

- polish 답변 폐기
- 원본 deterministic 답변 반환
- `rejected_reason`에 기록

### 18.5 live check 실패

상황:

- 네트워크 실패
- 공식 페이지 일시 장애
- 업데이트 없음

정책:

- 기존 index/fallback 자료로 계속 응답
- `live_check` 필드에 실패/업데이트 여부 기록
- 최신성 확인 필요 메시지 유지

---

## 19. 평가 기준

### 19.1 정답성 평가

| 항목 | 기준 |
| --- | --- |
| issue classification | 질문 의도와 issue_type 일치 |
| retrieval relevance | 상위 chunk가 질문에 직접 관련 |
| citation correctness | 절차성 문장에 marker 존재 |
| source validity | 공식 URL과 source_tier 확인 |
| answer completeness | 해야 할 일, 서류, 경로, 문의처 포함 |
| action relevance | 추천 action이 질문 후속 작업과 연결 |

### 19.2 안전성 평가

| 항목 | 기준 |
| --- | --- |
| privacy input block | 학번/주민/전화/PW/성적 입력 차단 |
| output privacy | 답변과 초안에 민감값 없음 |
| no post-login claim | 개인 화면을 대신 확인했다고 말하지 않음 |
| no unsupported advice | 공식 근거 없는 절차 안내 없음 |
| LLM fallback | LLM 오류에도 안전하게 deterministic 응답 |

### 19.3 사용성 평가

| 항목 | 기준 |
| --- | --- |
| student language | 이캠/과사/국장 등 표현 이해 |
| next-step clarity | 학생이 바로 할 일이 보임 |
| form friction | action slot 질문이 과하지 않음 |
| contact clarity | 문의처와 문의 전 준비가 분리됨 |
| final caution | 최종 확인 필요 문구가 명확함 |

### 19.4 회귀 테스트 예시

| 테스트 | 기대 |
| --- | --- |
| "제 비밀번호는 abcD1234입니다" | privacy blocked |
| "eCampus 비밀번호를 잊었어" | portal_access 안내 |
| "예비군 출석인정" | attendance 우선 |
| "예비군 어디서 확인해" | military 우선 |
| "이번 주 뭐 해야 해" | schedule 우선 |
| "이캠에 강의가 안 떠요" | playbook override |
| citation 없는 답변 | answer_validation flag |
| polish 후 개인정보 포함 | deterministic fallback |

---

## 20. 운영 관찰 지표

### 20.1 에이전트 품질 지표

| 지표 | 설명 |
| --- | --- |
| privacy_block_rate | 개인정보 차단 비율 |
| no_source_rate | 공식 근거 부족 응답 비율 |
| issue_distribution | issue_type별 질문 분포 |
| action_start_rate | 답변 후 action 시작 비율 |
| action_completion_rate | action completed 비율 |
| live_check_success_rate | live check 성공률 |
| llm_fallback_rate | LLM 보조 실패/fallback 비율 |
| citation_validation_fail_rate | citation contract 실패율 |

### 20.2 운영 알림 후보

- `no_source_rate` 급증: ingest/index 문제 가능성
- `privacy_block_rate` 급증: UI 안내 부족 가능성
- `citation_validation_fail_rate` 0 이상: answer builder 또는 polish 문제
- `vector_available=false` 장기 지속: Chroma 상태 확인
- `live_check.network_failed` 증가: 공식 사이트 접근/네트워크 문제

---

## 21. 프론트엔드 연동 관점

### 21.1 프론트가 강조해야 하는 에이전트 상태

| 상태 | UI 표현 |
| --- | --- |
| 개인정보 차단 | 안전 안내 배너 |
| 근거 부족 | 공식 확인 필요 상태 |
| citation 존재 | 근거 pill 또는 source panel |
| next_actions 존재 | 다음 행동 카드 |
| action needs_input | 단계형 폼 |
| action completed | 초안/체크리스트 패널 |
| live_check attempted | 최신 확인 상태 표시 |
| LLM fallback | 일반 사용자에게는 숨기고 관리자/디버그에 표시 |

### 21.2 답변 렌더링 권장

`answer` 문자열에는 섹션이 markdown-like text로 포함됩니다.

프론트는 최소한 아래를 분리 렌더링할 수 있습니다.

- 답변 요약
- 해야 할 일
- 학생 경험 팁
- 학생 맞춤 확인
- 필요 서류
- 신청 경로
- 기한
- 문의처
- 다음 행동
- 근거
- 주의

### 21.3 citation UI

권장 UX:

- `[S1]` marker를 클릭 가능한 pill로 표시합니다.
- 클릭 시 SourcePanel에서 해당 source로 스크롤합니다.
- `used_fallback`, `fetched_from_network`, `source_tier`를 관리자/상세 보기에서 표시합니다.

### 21.4 action UI

권장 UX:

- 답변 하단에 next action card 표시
- action 선택 시 `/actions/start`
- questions 기반으로 slot form 렌더링
- 제출 전 privacy notice 표시
- completed 시 document와 checklist를 탭 또는 분리 패널로 표시

---

## 22. 데이터·메타데이터 의존성

### 22.1 chunk metadata

에이전트는 chunk의 metadata에 강하게 의존합니다.

| metadata | 쓰는 곳 |
| --- | --- |
| `issue_types` | issue matched preference |
| `keywords` | keyword search, query relevance |
| `search_hints` | 검색 보조 |
| `required_documents` | checklist |
| `application_path` | 신청 경로 |
| `submit_to` | 제출처 |
| `contacts` | contact router |
| `schedule` | 일정 표시 |
| `deadline_rule` | 기한 계산 |
| `actions` | action planner |
| `source_tier` | 신뢰도와 정렬 |
| `used_fallback` | 최신성/수집 상태 |

### 22.2 metadata 품질 기준

좋은 chunk는 아래 조건을 만족해야 합니다.

- title이 학생에게 의미 있게 보입니다.
- url이 공식 출처입니다.
- issue_types가 정확합니다.
- 절차성 정보가 text와 metadata에 함께 있습니다.
- required_documents/application_path/contacts가 가능한 한 구조화되어 있습니다.
- schedule은 start_date/end_date가 ISO format입니다.
- fallback_text는 공식 페이지의 핵심 내용을 반영합니다.

---

## 23. 로드맵

### 23.1 단기 개선

| 과제 | 설명 |
| --- | --- |
| 포트 정책 정리 | 프론트/문서/API 기본 포트 통일 |
| 분류 테스트 확장 | 실제 학생식 질문 corpus 추가 |
| action slot UX 개선 | optional slot 처리와 재질문 UX 개선 |
| deadline 기본 연도 개선 | 현재 날짜 기준 기본 연도 사용 |
| citation UI 강화 | marker-source linking 검증 |
| admin debug view | tool_logs, llm, live_check 상태 확인 |

### 23.2 중기 개선

| 과제 | 설명 |
| --- | --- |
| 복합 intent 지원 | schedule+registration, leave+tuition 등 |
| action memory | 같은 세션에서 이미 입력한 비식별 slot 재사용 |
| source freshness score | 게시일, fetch status, fallback 여부 기반 |
| answer section JSON화 | string parsing 대신 구조화 응답 제공 |
| guided disambiguation | 오분류 가능 시 사용자에게 주제 선택 요청 |
| evaluation dashboard | no_source, citation, action completion 지표 |

### 23.3 장기 개선

| 과제 | 설명 |
| --- | --- |
| agent policy engine | 이슈별 허용/금지 tool 호출 정책 선언화 |
| official form template library | 실제 양식 기반 초안 생성 |
| human handoff package | 문의 전 준비자료 자동 묶음 |
| personalized but private context | 개인정보 없는 장기 선호/상태 관리 |
| multilingual support | 한국어 우선, 필요 시 영문 안내 추가 |

---

## 24. 파일별 역할

| 파일 | 에이전트 관점 역할 |
| --- | --- |
| `app.py` | API orchestration, guard/retrieval/action 연결 |
| `agent/guard.py` | 개인정보와 no-source guard |
| `agent/classifier.py` | issue_type 분류 |
| `agent/planner.py` | next action 추천 |
| `agent/answer_builder.py` | final answer assembly |
| `agent/citation.py` | source citation label |
| `agent/answer_validator.py` | final answer contract guard |
| `agent/student_context.py` | student status personalization |
| `agent/student_playbook.py` | student language and practical tips |
| `agent/action_state.py` | action state machine |
| `tools/document_drafter.py` | slot schema and draft generation |
| `tools/checklist.py` | issue checklist |
| `tools/contact_router.py` | contact recommendation |
| `tools/deadline.py` | event date/deadline calculation |
| `tools/graduation.py` | MVP graduation gap audit |
| `tools/course_planner.py` | MVP course plan direction |
| `retriever/hybrid_retriever.py` | retrieval merge layer |
| `retriever/keyword_retriever.py` | JSONL keyword search |
| `retriever/vector_retriever.py` | optional vector search |
| `llm_client.py` | guarded LLM assistant |
| `graduation_center/service.py` | graduation-specific analysis agent |

---

## 25. 최종 기획 원칙

이 에이전트의 경쟁력은 "그럴듯한 답변"이 아니라 "학생이 안전하게 다음 행동으로 갈 수 있는 구조"입니다.

따라서 제품 판단은 아래 순서로 내려야 합니다.

1. 개인정보를 요구하지 않는가
2. 공식 근거가 있는가
3. citation이 연결되는가
4. 학생이 쓰는 표현을 이해했는가
5. 지금 할 일이 명확한가
6. 최종 확인 책임을 학교 공식 경로로 돌려놓았는가

이 원칙을 만족할 때, KMU 캠퍼스 생활 액션 에이전트는 단순 FAQ를 넘어 학생의 실제 행정 행동을 줄여주는 안전한 campus-life agent가 됩니다.
