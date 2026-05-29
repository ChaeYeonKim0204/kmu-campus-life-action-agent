# KMU Campus Life Action Agent 작업계획

## 1. 목표

국민대학교 학생이 학교생활 중 마주치는 학사 행정, 학생지원, 일정, 증명서, 졸업요건, 문의처 질문에 대해 공식 근거 기반으로 답하고, 필요한 다음 행동까지 이어주는 Agent를 만든다.

핵심은 단순 챗봇이 아니라 다음 흐름을 수행하는 실행 보조 Agent다.

```text
질문 이해
→ 공식 근거 검색
→ 기한/서류/경로/문의처 Tool 실행
→ 출처 포함 답변
→ 신청서/체크리스트/문의문 초안 작성
```

## 2. MVP 범위

깊게 구현하는 기능:

- 출석인정 안내 및 출석인정신청서 초안 작성
- 휴학/복학 절차 안내
- 수강신청/폐강 확인 안내
- 증명서 발급 안내
- 학사일정 기반 기간 안내
- 문의처 추천
- 문장별 citation
- 개인정보 guard
- 근거 부족 질문 처리

확장 기능:

- 졸업요건 진단
- 수강계획 추천
- Chroma Vector DB 실연동
- 학사공지/규정관리시스템 자동 크롤링
- PDF/DOCX/OCR/HWP 처리
- 캘린더/리마인더
- 관리자 대시보드 고도화

## 3. 공식 데이터 계층

| Tier | 출처 | 역할 |
| --- | --- | --- |
| 1 | 규정관리시스템 | 제도적 가능 여부 |
| 2 | 학사안내 | 절차, 신청경로, 서류 |
| 3 | 학생지원/대학생활 안내 | 증명서, 학생증, 병무, 상담 |
| 4 | 학사일정 | 신청기간, 마감일 |
| 5 | 공지사항 | 최신 학기별 변경사항 |
| 6 | 요람/규정집 | 졸업요건, 교육과정 |
| 7 | 대학조직 | 문의처 라우팅 |
| 8 | SWELL 공개 게시판 | 공개 신청 안내 |

## 4. 시스템 구조

```text
국민대 공식 사이트
→ crawler adapter
→ parser/chunker
→ JSONL/Vector DB
→ hybrid retriever
→ agent tools
→ guard/citation
→ FastAPI
→ frontend
```

MVP는 `data/processed/chunks.jsonl`과 keyword retriever로 안정성을 우선한다. `VectorRetriever`는 Chroma 연결 지점을 제공하고, 실제 인덱싱은 2차 확장으로 둔다.

## 5. Tool Calling 설계

- `classify_issue`: 질문 유형 분류
- `search_official_sources`: 공식 chunk 검색
- `calculate_deadline`: 날짜 계산
- `generate_checklist`: 해야 할 일/서류/신청경로 생성
- `route_contact`: 문의처 추천
- `draft_action_document`: 신청서/사유문 초안 작성
- `audit_graduation_requirements`: 졸업요건 간이 진단
- `recommend_course_plan`: 수강계획 방향 추천
- `build_final_answer`: citation 포함 최종 답변 생성

## 6. Action Flow

출석인정 예시:

1. 사용자가 예비군 결석 질문
2. Agent가 출석인정/예비군 공식 근거 검색
3. 필요서류, 제출대상, 제출기한 안내
4. 다음 행동으로 출석인정신청서 초안 작성 제안
5. 결석일, 사유, 수업명, 교강사명, 증빙서류, 제출 예정일 입력 요청
6. 개인정보 없이 신청서 초안 생성
7. 제출 전 체크리스트 제공

## 7. Guardrails

- 학번, 주민번호, 연락처, 성적표 원본, 포털 ID/PW는 입력받지 않는다.
- 공식 근거가 없으면 절차 답변을 생성하지 않는다.
- 로그인 이후 ON국민/SWELL 개인 화면에는 접근하지 않는다.
- 에브리타임 등 비공식 서비스 자동 크롤링은 하지 않는다.
- 실제 제출은 사용자가 직접 수행한다.

## 8. 4주 작업계획

### 1주차

- 공식 source 목록 확정
- chunk schema/action schema 확정
- 핵심 공식 문서 수동 검증
- crawler adapter 구조 구현

### 2주차

- `/ask` API 구현
- 질문 분류, 검색, citation, guard 구현
- Tool Calling 로그 구현
- keyword fallback과 Chroma interface 구현

### 3주차

- 출석인정신청서 action flow 구현
- 휴학/복학, 수강신청, 증명서, 문의처 flow 구현
- 프론트 채팅 UI, source panel, tool log panel 구현

### 4주차

- 졸업요건 데모 기능 보강
- 학사일정 기반 마감 안내 보강
- 테스트와 발표 시나리오 정리
- 데모 데이터 정리

## 9. 팀 역할

- PM/Product: 기능 우선순위, 발표 스토리, 사용자 시나리오
- Data/RAG: 공식 소스 수집, chunking, Vector DB, citation 품질
- Backend/Agent: FastAPI, Tool pipeline, action state machine, Guarded LLM
- Frontend: 채팅 UI, action form, source panel, tool log panel
- QA/Integration: 테스트, 실패 케이스, 데모 안정화

