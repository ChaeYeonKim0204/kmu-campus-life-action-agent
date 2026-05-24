# KMU 캠퍼스 생활 액션 에이전트 프론트엔드 기획 문서

> 문서 목적: 현재 React 프론트엔드 구현을 기준으로 화면 구조, 사용자 여정, 기능 범위, API 연결, 개선 과제를 공유하기 위한 기획 문서  
> 작성일: 2026-05-24  
> 대상: 기획, 프론트엔드, 백엔드, RAG/에이전트, QA 담당자  
> 기준 화면: `frontend/src/App.jsx` 중심의 Vite + React 단일 페이지 앱  
> 개발 주소: `http://127.0.0.1:5173/`  
> API 주소: 프론트 개발 서버 기준 `http://127.0.0.1:8001`

---

## 1. 문서 요약

### 1.1 프론트엔드 한 줄 정의

국민대학교 학생이 메타버스 캠퍼스 화면에서 건물과 NPC를 탐색하고, 학사 행정 질문부터 공식 근거 확인, 서류 초안 작성, 졸업 진단까지 이어갈 수 있는 한국어 기반 캠퍼스 생활 액션 UI입니다.

### 1.2 현재 프론트엔드의 핵심 방향

- 단순 챗봇이 아니라 **캠퍼스 탐색형 학사 행정 도우미**로 구성합니다.
- 답변만 제공하지 않고 **다음 행동**으로 이어지는 버튼, 서류함, 체크리스트, 졸업센터를 제공합니다.
- 답변의 신뢰성을 위해 **출처, 처리 로그, 최신 확인 상태, 개인정보 검사 결과**를 화면에서 볼 수 있게 합니다.
- 학생이 민감정보를 입력하지 않도록 질문 입력 단계와 서버 응답 단계에서 모두 경고합니다.
- 데모/운영자가 상태를 확인할 수 있도록 관리자 기능을 제공하되, 학생용 주 화면과 운영용 패널은 점진적으로 분리해야 합니다.

### 1.3 현재 확인된 실행 상태

- Vite 프론트엔드 개발 서버는 `5173` 포트에서 동작합니다.
- 현재 `API_BASE`는 개발 서버 포트가 `5173`이면 `http://127.0.0.1:8001`을 호출합니다.
- FastAPI 백엔드는 `8001` 포트에 띄웠을 때 프론트와 정상 연결됩니다.
- `frontend/dist`가 있으면 FastAPI 루트(`/`)에서도 빌드된 프론트엔드를 서빙할 수 있습니다.

---

## 2. 서비스 콘셉트

### 2.1 제품 콘셉트

**"국민대 캠퍼스를 돌아다니며 학사 행정 퀘스트를 해결하는 액션형 RAG 에이전트"**

기존 FAQ/챗봇 UI는 학생이 이미 정확한 질문을 알고 있어야 합니다. 이 서비스는 캠퍼스 건물, NPC, 퀘스트, 추천 질문을 통해 학생이 상황을 고르고 질문으로 진입하도록 돕습니다.

### 2.2 프론트엔드 디자인 키워드

| 키워드 | 설명 |
| --- | --- |
| 메타버스 캠퍼스 | 지도와 건물 선택을 통해 주제별 행정 업무를 탐색 |
| NPC 상담 | 건물별 담당자 캐릭터가 질문 진입을 안내 |
| 퀘스트 | 학생이 해야 할 행정 업무를 미션처럼 표시 |
| 공식 근거 | 답변의 citation을 클릭해 대백과/출처 패널로 이동 |
| 서류함 | 답변 이후 실제 작성해야 하는 초안과 체크리스트 제공 |
| 연구소 | 실시간 확인, GPT 보조, 처리 로그, 관리자 상태 확인 |
| 졸업센터 | 성적증명서 기반 졸업/진로 분석 기능을 별도 고급 모듈로 제공 |

### 2.3 해결하려는 사용자 문제

- 학사 행정 정보를 어디서 찾아야 할지 모른다.
- 공식 안내는 읽었지만 실제로 무엇을 준비해야 하는지 모르겠다.
- 출석인정, 휴학/복학, 수강신청, 장학, 증명서 등 업무별 담당 부서를 구분하기 어렵다.
- 답변이 맞는지 근거를 확인하고 싶다.
- 질문 이후 신청서, 문의문, 체크리스트 작성까지 바로 이어가고 싶다.
- 학번, 성적, 연락처 같은 민감정보를 입력해야 할지 헷갈린다.

---

## 3. 대상 사용자

### 3.1 주요 사용자

| 사용자 | 대표 니즈 | 프론트엔드 대응 |
| --- | --- | --- |
| 신입생 | eCampus, 학생증, 수강신청, 장학, 등록금 등 기본 절차 파악 | 학적 카드에서 `신입생` 선택, 건물별 추천 질문 제공 |
| 재학생 | 출석인정, 증명서, 수강정정, 장학금, 도서관 이용 문제 해결 | 채팅 답변, 출처 패널, 서류함 액션 제공 |
| 복학생 | 복학 후 일정, 수강신청, 등록금, 학생증/포털 접근 확인 | `복학생` 상태 기반 맞춤 확인 문구 제공 |
| 휴학생 | 휴학 연장, 복학 신청, 질병/군휴학 서류 확인 | 복지관 퀘스트와 휴학/복학 체크리스트 연결 |
| 졸업예정자 | 졸업요건, 조기졸업, 대체 이수, 직무 역량 확인 | 공학관 퀘스트와 졸업센터 모달 연결 |

### 3.2 보조 사용자

| 사용자 | 대표 니즈 | 프론트엔드 대응 |
| --- | --- | --- |
| 서비스 운영자 | 수집 상태, Chroma, GPT 보조, live refresh 확인 | 연구소 모달 내 관리자 대시보드 |
| 데모 담당자 | 짧은 시간 안에 전체 기능을 시연 | 추천 질문, 퀘스트, 서류함, 졸업센터 CTA |
| QA 담당자 | API 응답과 UI 상태를 빠르게 검증 | 처리 상태 패널, Tool Calling 로그, 출처 패널 |

---

## 4. 정보 구조

### 4.1 단일 페이지 구조

현재 프론트엔드는 별도 라우팅 없이 `App.jsx` 하나의 큰 화면 안에서 모달과 슬라이딩 패널을 전환합니다.

```text
App
├─ 배경/메타버스 프레임
├─ CampusMap
├─ 상단 HUD
├─ 좌측 메뉴
│  ├─ 홈
│  ├─ 퀘스트
│  ├─ 학적카드
│  └─ 대화기록
├─ 우측 메뉴
│  ├─ 서류함
│  ├─ 대백과
│  ├─ 졸업센터
│  └─ 연구소
├─ 미니맵
├─ 마스코트 말풍선 채팅
├─ 상세 대화 기록 슬라이딩 패널
├─ 서류함 모달
├─ 졸업센터 모달
├─ 퀘스트 보드 모달
├─ 학적 카드 모달
├─ 대백과 모달
└─ 연구소 모달
```

### 4.2 주요 화면 목록

| 화면/모달 | 역할 | 주요 컴포넌트 |
| --- | --- | --- |
| 메인 캠퍼스 | 서비스 첫 화면, 건물 탐색, 질문 진입 | `CampusMap`, `MascotSVG`, `RadarMinimapSVG` |
| 말풍선 채팅 | 빠른 질문 입력과 최근 대화 표시 | `App.jsx` 내부 말풍선 UI |
| 상세 대화 기록 | 전체 답변, 추천 질문, citation 클릭 | `RPGMessageConsole` |
| 퀘스트 보드 | 레벨/XP, 건물별 퀘스트, NPC 안내 | `QuestBoard` |
| 서류함 | 액션 선택, slot 입력, A4 미리보기 | `ActionForm` |
| 대백과 | 답변 citation의 공식 출처 확인 | `SourcePanel` |
| 연구소 | live check, GPT 보조, 처리 로그, 관리자 상태 | `ProcessingStatusPanel`, `ToolLogPanel`, `AdminDashboard` |
| 졸업센터 | 성적증명서 업로드, 졸업/진로 분석 | `GraduationCenter` |
| 학적 카드 | 학생 상태, 대상 학기, 관심 항목 설정 | `App.jsx` 내부 profile modal |
| 레벨업/퀘스트 완료 | 수행 보상 피드백 | `App.jsx` 내부 notification/modal |

---

## 5. 캠퍼스 맵 기획

### 5.1 건물별 주제 매핑

| 건물 ID | 화면명 | 담당 역할 | 대표 질문/업무 |
| --- | --- | --- | --- |
| `admin` | 본부관 | 학사지원 조교 | 공결, 출석인정신청서, 예비군 출석 |
| `union` | 복지관 | 종합민원실 | 휴학, 복학, 군휴학, 질병휴학 |
| `library` | 성곡도서관 | 도서관 사서 | 모바일 학생증, 도서관 좌석, 연체 |
| `ecampus` | 이캠퍼스 센터 | eCampus 헬프데스크 | 강의 목록 누락, 로그인, 앱 연동 |
| `bugak` | 북악관 | 행정 규정 상담 | 수강정정, 장학금, 증명서, 학기 중 휴학 |
| `engineering` | 공학관 | 공학관 행정직원 | 졸업요건, 폐강, 대체 이수, 졸업센터 |

### 5.2 맵 상호작용

- 건물 클릭 시 `activeBuilding`이 변경됩니다.
- 선택된 건물에 따라 추천 질문 목록이 바뀝니다.
- 건물별 퀘스트가 있으면 지도 위 quest pin과 퀘스트 보드 상태가 함께 바뀝니다.
- 아바타 위치와 미니맵 위치가 선택 건물 좌표에 맞춰 이동합니다.

### 5.3 기획 의도

학생은 행정 업무를 부서명보다 "장소"로 기억하는 경우가 많습니다. 따라서 건물 기반 UI는 질문 진입 전 맥락을 제공합니다.

예:

- "출석인정은 본부관"
- "휴학/복학은 복지관"
- "학생증은 성곡도서관"
- "이캠 문제는 이캠퍼스 센터"
- "졸업요건은 공학관/졸업센터"

---

## 6. 핵심 사용자 여정

### 6.1 여정 A: 빠른 질문 → 근거 기반 답변

```text
서비스 접속
→ 메인 캠퍼스 확인
→ 말풍선 입력창 또는 추천 질문 클릭
→ POST /ask 호출
→ 로딩 표시
→ 답변 수신
→ 최근 대화 말풍선에 요약 표시
→ 상세 대화 기록 패널 자동 오픈
→ citation 클릭 시 대백과 출처로 이동
```

#### 성공 기준

- 사용자는 첫 화면에서 질문 입력 위치를 바로 발견할 수 있어야 합니다.
- 답변에는 citation pill이 표시되어야 합니다.
- 답변에 `next_actions`가 있으면 서류함/액션 흐름으로 이어질 수 있어야 합니다.
- 개인정보 질문은 서버 응답 기준으로 차단되고, 프론트 입력 단계에서도 경고가 보여야 합니다.

### 6.2 여정 B: 건물 선택 → 추천 질문 → 답변

```text
지도에서 건물 선택
→ 해당 건물 추천 질문 노출
→ 추천 질문 클릭
→ POST /ask 호출
→ 답변 및 출처 확인
→ 퀘스트 조건과 일치하면 XP 획득
```

#### 성공 기준

- 건물별 추천 질문이 현재 행정 주제와 일치해야 합니다.
- 학생이 질문을 직접 작성하지 않아도 주요 데모 시나리오를 경험할 수 있어야 합니다.
- 퀘스트 완료 상태가 localStorage에 저장되어 새로고침 후에도 유지되어야 합니다.

### 6.3 여정 C: 답변 → 서류 초안 작성

```text
답변 수신
→ next_actions 확인
→ 서류함 열기
→ 액션 선택
→ POST /actions/start 호출
→ 필요한 slot 질문 표시
→ slot 입력
→ POST /actions/continue 호출
→ 문서 초안과 제출 전 체크리스트 표시
→ 관련 퀘스트 완료 처리
```

#### 성공 기준

- `ActionForm`은 액션 목록과 현재 action state를 분리해서 보여줘야 합니다.
- 필수 slot이 비어 있으면 인라인 에러를 표시해야 합니다.
- 완료 후 문서 초안은 대화 기록에 추가되어 사용자가 다시 확인할 수 있어야 합니다.
- 미리보기는 A4 문서처럼 보이되, 실제 개인정보는 넣지 않아야 합니다.

### 6.4 여정 D: 출처 확인

```text
답변 안 citation pill 클릭
→ 대백과 모달 열림
→ 해당 S번호 source card로 scroll
→ 네트워크 확인/fallback/저장 근거 상태 확인
→ 공식 문서 링크 열기
```

#### 성공 기준

- 사용자는 답변의 사실 주장과 출처를 연결할 수 있어야 합니다.
- `fetched_from_network`, `used_fallback`, `source_tier`, `source_type`, `department`가 보조 정보로 보여야 합니다.

### 6.5 여정 E: 졸업센터

```text
우측 메뉴에서 졸업센터 열기
→ /graduation/status 확인
→ 성적증명서 PDF 업로드
→ 텍스트 PDF 파싱 또는 Vision OCR 동의 필요 상태 표시
→ parsed transcript 저장
→ 졸업 진단/조기졸업/대체이수/마이크로디그리/직무역량 등 탭 실행
→ 결과 확인 또는 TXT 다운로드
```

#### 성공 기준

- 업로드 전에는 분석 버튼이 disabled되어야 합니다.
- Vision OCR이 필요한 경우 명시 동의 체크가 있어야 합니다.
- 응답에는 이름, 학번, GPA 숫자, 과목별 성적이 노출되지 않아야 합니다.
- 졸업센터는 일반 질문 답변보다 민감도가 높으므로 UI에서 임시 사용/비저장 정책을 명확히 보여야 합니다.

### 6.6 여정 F: 연구소/관리자 확인

```text
연구소 열기
→ 학생 상태 및 연동 설정 확인
→ live_check, GPT 보조 토글 설정
→ 처리 상태 패널 확인
→ Tool Calling 로그 확인
→ 관리자 대시보드에서 health/ingest/live-refresh 확인
```

#### 성공 기준

- 일반 학생이 보아도 위험한 정보가 노출되지 않아야 합니다.
- 운영용 기능인 ingest 실행은 향후 별도 관리자 페이지나 인증 뒤로 분리해야 합니다.
- 데모 환경에서는 시스템 상태를 보여주는 기능으로 활용할 수 있어야 합니다.

---

## 7. 주요 기능 명세

### 7.1 질문 입력

| 항목 | 내용 |
| --- | --- |
| 입력 위치 | 메인 말풍선, 상세 대화 기록 패널 |
| 전송 방식 | Enter 또는 전송 버튼 |
| 호출 API | `POST /ask` |
| 요청값 | `question`, `student_context`, `live_check`, `llm_assist` |
| 성공 처리 | 사용자 메시지 추가, 에이전트 답변 추가, tool logs/citations/actions/status 갱신 |
| 실패 처리 | `요청 실패: {error.message}` 표시 |

### 7.2 개인정보 실시간 경고

프론트는 사용자가 질문을 입력하는 동안 다음 항목을 감지합니다.

| 감지 항목 | 감지 예 |
| --- | --- |
| 학번 | `20`으로 시작하는 숫자 패턴, `학번` |
| 주민번호 | `000000-0000000`, `주민` |
| 비밀번호 | `비밀번호`, `패스워드`, `password`, `pw` |
| 성적 | `성적표`, `평점`, `gpa`, `내 성적`, `성적으로 처리` |
| 연락처 | 휴대폰 번호 패턴, `연락처`, `전화번호` |

서버도 동일한 guard를 실행하므로 프론트 경고는 UX 보조 역할입니다.

### 7.3 학생 학적 카드

| 항목 | 내용 |
| --- | --- |
| 상태값 | 기본, 신입생, 재학생, 복학생, 휴학생, 졸업예정 |
| 추가 입력 | 대상 학기, 관심 항목 |
| 저장 위치 | `localStorage.studentContext` |
| 사용처 | `/ask` 요청의 `student_context`, 퀘스트 보드 HUD, 맞춤 확인 문구 |

### 7.4 퀘스트/레벨 시스템

| 항목 | 내용 |
| --- | --- |
| 레벨 저장 | `localStorage.studentLevel` |
| XP 저장 | `localStorage.studentXp` |
| 퀘스트 저장 | `localStorage.studentQuests` |
| 완료 조건 | 특정 action 완료 또는 특정 trigger message 질문 |
| 보상 | 퀘스트별 XP |
| 피드백 | Quest completed banner, level-up modal |

초기 퀘스트:

| 퀘스트 | 조건 | 보상 |
| --- | --- | --- |
| 공결 신청서 작성 | `draft_attendance_recognition_form` 완료 | 40 XP |
| 휴학/복학 신청 마스터 | `draft_leave_checklist` 완료 | 40 XP |
| 도서관 학생증 오류 해결 | `모바일 학생증 안 찍힘` 질문 | 20 XP |
| E-Campus 클래스룸 동기화 | `이캠에 강의가 안 떠요` 질문 | 20 XP |
| 졸업 센터 종합 진단 | `graduation_audit` 액션 | 60 XP |

### 7.5 서류함

| 항목 | 내용 |
| --- | --- |
| 역할 | 답변 이후 추천 action을 실제 초안 작성 흐름으로 연결 |
| 주요 상태 | `actions`, `actionState`, `slots` |
| 시작 API | `POST /actions/start` |
| 계속 API | `POST /actions/continue` |
| 완료 출력 | `document`, `checklist`, `output_privacy`, `live_check` |
| UI 특징 | 좌측 slot 입력, 우측 A4 문서 미리보기, 모바일 탭 전환 |

### 7.6 대백과/출처

| 항목 | 내용 |
| --- | --- |
| 입력 데이터 | `/ask` 응답의 `citations` |
| 식별자 | `S1`, `S2`, ... |
| 상태 배지 | 네트워크 확인, fallback, 저장 근거 |
| 주요 메타 | source tier, source type, department, published_at, fetch status |
| 외부 이동 | 공식 문서 링크 새 창 열기 |

### 7.7 연구소

| 항목 | 내용 |
| --- | --- |
| 학생 설정 | 학적 상태, 대상 학기, 관심 항목 |
| 토글 | 공식 사이트 실시간 대조, GPT 보조 |
| 처리 상태 | 답변 검증, 민감정보 검사, live check, GPT 보조 |
| 로그 | Tool Calling 단계 |
| 관리자 | health, ingest, issue live refresh |

---

## 8. API 연결 기획

### 8.1 API Base 정책

현재 구현:

```javascript
const API_BASE = window.location.port === "5173"
  ? "http://127.0.0.1:8001"
  : window.location.origin;
```

기획상 권장:

- 개발 환경에서는 `.env`의 `VITE_API_BASE_URL`을 우선 사용합니다.
- 값이 없으면 현재 구현처럼 `5173 -> 8001` fallback을 사용할 수 있습니다.
- README와 실행 스크립트의 백엔드 포트를 `8001`로 맞추거나, 프론트 기본값을 `8000`으로 되돌리는 결정을 해야 합니다.

### 8.2 POST /ask

#### 요청

```json
{
  "question": "공결 신청 절차가 어떻게 돼?",
  "student_context": {
    "status": "enrolled",
    "term": "2026-1학기",
    "concern": "출석"
  },
  "live_check": false,
  "llm_assist": true
}
```

#### 프론트에서 사용하는 응답 필드

| 필드 | 사용처 |
| --- | --- |
| `answer` | 말풍선/상세 대화 기록 |
| `issue_type` | 향후 UI 분기 가능 |
| `tool_logs` | ToolLogPanel |
| `citations` | SourcePanel, citation pill |
| `next_actions` | ActionForm 시작 목록 |
| `live_check` | ProcessingStatusPanel, 연구소 상태 |
| `llm` | GPT 보조 상태 |
| `answer_validation` | 답변 검증 상태 |
| `output_privacy` | 민감정보 검사 상태 |
| `safety_flags` | 경고/차단 UI 분기 |

### 8.3 POST /actions/start

#### 요청

```json
{
  "action_id": "draft_attendance_recognition_form"
}
```

#### 프론트에서 사용하는 응답 필드

| 필드 | 사용처 |
| --- | --- |
| `status` | `needs_input` 여부 |
| `action_id` | 이후 continue 호출 |
| `label` | 서류함 제목 |
| `missing_slots` | 필수 입력 필드 렌더링 |
| `questions` | slot 질문 문구 |
| `privacy_notice` | 서류함 안내 |

### 8.4 POST /actions/continue

#### 요청

```json
{
  "action_id": "draft_attendance_recognition_form",
  "slots": {
    "event_date": "2026-05-20",
    "absence_reason": "예비군 훈련",
    "course_name": "자료구조",
    "instructor_name_optional": "담당 교강사",
    "evidence_document_type": "훈련필증",
    "planned_submission_date": "2026-05-22"
  },
  "live_check": false
}
```

#### 상태별 처리

| 상태 | 프론트 처리 |
| --- | --- |
| `completed` | 문서 초안과 체크리스트를 대화 기록에 추가, 모달 닫기, 퀘스트 완료 |
| `blocked` | 민감정보 차단 메시지 표시, action state 초기화 |
| 그 외 | 새 action state로 갱신하고 부족 slot 재입력 |

### 8.5 졸업센터 API

| API | 프론트 사용처 |
| --- | --- |
| `GET /graduation/status` | 모달 진입 시 준비 상태 확인 |
| `POST /graduation/transcript/parse` | PDF 업로드/파싱 |
| `POST /graduation/audit` | 졸업 가능 여부 진단 |
| `POST /graduation/early-graduation` | 조기졸업 가능 여부 |
| `POST /graduation/customized-major` | Customized전공 인정 확인 |
| `POST /graduation/credit-drop` | 성적포기/학점 드랍 정책 확인 |
| `POST /graduation/substitute-courses` | 대체 이수 과목 탐색 |
| `POST /graduation/micro-degree` | 마이크로디그리 분석 |
| `POST /graduation/post-graduation-checklist` | 졸업 전후 체크리스트 |
| `POST /graduation/career-translator` | 직무 역량 번역 |

### 8.6 관리자 API

| API | 프론트 사용처 | 운영 주의 |
| --- | --- | --- |
| `GET /health` | 관리자 metrics | 학생 화면 노출 범위 조정 필요 |
| `POST /ingest/run` | 전체 수집/인덱싱 실행 | 인증 필요 |
| `POST /ingest/live-refresh` | 이슈별 최신 확인 | 인증/쿨다운 안내 필요 |

---

## 9. 상태 관리 설계

### 9.1 주요 React 상태

| 상태 | 역할 |
| --- | --- |
| `question` | 현재 입력 중인 질문 |
| `studentContext` | 학적 상태/학기/관심 항목 |
| `messages` | 사용자/에이전트 대화 이력 |
| `toolLogs` | 처리 단계 로그 |
| `citations` | 답변 출처 목록 |
| `actions` | 다음 행동 목록 |
| `actionState` | 현재 서류 작성 플로우 상태 |
| `slots` | 서류 작성 slot 값 |
| `loading` | 질문 처리 중 여부 |
| `liveCheck` | 공식 사이트 실시간 대조 토글 |
| `llmAssist` | GPT 보조 토글 |
| `liveCheckStatus` | live check 결과 |
| `llmStatus` | GPT 보조 상태 |
| `answerValidation` | citation/답변 검증 결과 |
| `outputPrivacy` | 최종 출력 개인정보 검사 결과 |
| `level`, `xp`, `quests` | 퀘스트/보상 상태 |
| `activeBuilding` | 현재 선택 건물 |
| `show*Modal` | 각 모달 표시 상태 |

### 9.2 localStorage 저장 항목

| key | 값 | 목적 |
| --- | --- | --- |
| `studentContext` | JSON | 학적 카드 설정 유지 |
| `studentLevel` | number | 레벨 유지 |
| `studentXp` | number | XP 유지 |
| `studentQuests` | JSON | 퀘스트 완료 상태 유지 |

### 9.3 향후 리팩터링 권장

현재 `App.jsx`에 화면 상태와 비즈니스 흐름이 집중되어 있습니다. 기능이 커질수록 아래처럼 분리하는 것을 권장합니다.

```text
src/
├─ api/
│  ├─ client.js
│  ├─ ask.js
│  ├─ actions.js
│  └─ graduation.js
├─ hooks/
│  ├─ useAskFlow.js
│  ├─ useActionDraft.js
│  ├─ useQuestState.js
│  └─ useStudentContext.js
├─ components/
├─ screens/
│  ├─ CampusScreen.jsx
│  ├─ GraduationCenterScreen.jsx
│  └─ AdminScreen.jsx
└─ constants/
   ├─ buildings.js
   ├─ quests.js
   └─ examples.js
```

---

## 10. 컴포넌트별 역할

| 컴포넌트 | 현재 역할 | 기획상 책임 |
| --- | --- | --- |
| `App.jsx` | 전체 상태, API 호출, 모달 전환, 메인 레이아웃 | 화면 조립자. 향후 flow/hook 분리 필요 |
| `CampusMap.jsx` | SVG 캠퍼스 지도, 건물 클릭, 아바타 이동 | 주제 탐색 진입점 |
| `RPGMessageConsole.jsx` | 상세 대화 기록, 추천 질문, citation pill | 긴 답변 소비와 재질문 |
| `QuestBoard.jsx` | 퀘스트 목록, NPC 안내, XP/레벨 HUD | 행정 업무를 게임형 미션으로 전환 |
| `ActionForm.jsx` | action 선택, slot 입력, A4 미리보기 | 다음 행동/서류 초안 작성 |
| `SourcePanel.jsx` | citation 리스트, 공식 문서 링크 | 신뢰성 확인 |
| `ProcessingStatusPanel.jsx` | live check, LLM, validation 상태 | 처리 투명성 제공 |
| `ToolLogPanel.jsx` | tool log 리스트 | RAG/에이전트 처리 과정 표시 |
| `AdminDashboard.jsx` | health, ingest, live refresh | 운영/데모 상태 확인 |
| `GraduationCenter.jsx` | PDF 업로드, 졸업 관련 분석 탭 | 고급 졸업 진단 모듈 |
| `ChatPanel.jsx` | 기존 채팅 패널 | 현재 메인 플로우에서는 보조/레거시 성격 |

---

## 11. 화면별 콘텐츠 기획

### 11.1 메인 화면

#### 필수 요소

- 서비스 타이틀
- 학생 프로필 HUD
- AI 도우미 HUD
- 캠퍼스 지도
- 건물별 퀘스트 표시
- 미니맵
- 말풍선형 질문 입력
- 최근 대화 1-2개 요약
- 상세 로그/대화 기록 열기 링크

#### 첫 진입 메시지

현재 톤:

```text
안녕하세요! 학사지원 AI 국민이입니다. 지도의 건물을 클릭하여 각 구역의 조교를 만난 뒤 퀘스트를 수행해보세요! 무엇이든 물어보셔도 좋습니다.
```

기획상 요구:

- 학생이 무엇을 입력해야 하는지 즉시 이해할 수 있어야 합니다.
- "학번/성적/연락처는 입력하지 말라"는 경고가 부담스럽지 않게 노출되어야 합니다.
- 추천 질문은 첫 화면에 2개만 노출하고, 상세 패널에는 최대 5개까지 노출합니다.

### 11.2 상세 대화 기록

#### 필수 요소

- 대화 전체 이력
- 사용자/에이전트 발화 구분
- citation pill
- 추천 질문 버튼
- 하단 질문 입력창
- 개인정보 경고

#### 개선 기획

- 긴 답변은 섹션 접기/펼치기 또는 카드형 구조로 소비성을 높입니다.
- citation 클릭 후 출처 모달이 열릴 때 현재 답변 맥락이 유지되어야 합니다.

### 11.3 서류함

#### 필수 요소

- 추천 action 목록
- 현재 action의 입력 필드
- 필수값 누락 표시
- 개인정보 입력 금지 안내
- A4 문서 미리보기
- 완료 후 문서/체크리스트 대화 기록 추가

#### 개선 기획

- 완료 문서에는 복사 버튼, TXT 다운로드, 다시 수정 버튼을 제공합니다.
- 학번/이름은 "미기입" placeholder로 유지합니다.
- 실제 제출 버튼은 제공하지 않습니다.

### 11.4 졸업센터

#### 필수 요소

- 준비 상태 안내
- PDF 업로드
- Vision OCR 동의 checkbox
- 파싱 결과 요약
- 분석 탭
- 결과 출력
- TXT 다운로드

#### 개선 기획

- 성적증명서 업로드는 민감도가 높으므로 일반 챗봇보다 강한 privacy 안내가 필요합니다.
- 업로드 전 샘플 데이터 체험 모드를 제공하면 데모 안정성이 좋아집니다.
- 과목별 성적이나 GPA 숫자가 노출되지 않는지 UI 자동 검증이 필요합니다.

### 11.5 연구소

#### 필수 요소

- 학생 상태 및 연동 설정
- live check 토글
- GPT 보조 토글
- 처리 상태 패널
- Tool Calling 로그
- 관리자 대시보드

#### 개선 기획

- 운영 배포 시 연구소 안의 관리자 기능은 `/admin` 또는 인증 뒤로 이동합니다.
- 학생용 화면에서는 "공식 근거 최신 확인"과 "답변 검증" 정도만 남깁니다.

---

## 12. 콘텐츠 정책

### 12.1 사용자-facing 언어

- 모든 학생용 문구는 한국어를 기본으로 합니다.
- 행정 용어는 국민대 학생이 실제로 쓰는 표현과 공식 표현을 함께 보여줍니다.
- 예: `수변`을 입력해도 `수강정정`으로 이해하고 답변합니다.

### 12.2 개인정보 금지 문구

입력창, 서류함, 졸업센터에는 다음 취지의 안내가 필요합니다.

```text
학번, 주민번호, 연락처, 포털 ID/PW, 성적표 원본 등 개인정보는 입력하지 마세요.
필요한 경우 직접 요약한 비식별 정보만 사용해 주세요.
```

### 12.3 citation 표현

학생에게는 `[S1]` 같은 원본 마커보다 "근거 S1" 형태의 클릭 가능한 pill이 이해하기 쉽습니다.

단, 백엔드 답변 원문에는 `[S1]` marker가 유지되어야 합니다. 프론트는 이를 렌더링 단계에서 pill로 변환합니다.

### 12.4 데모용 콘텐츠와 운영용 콘텐츠 구분

현재 추천 질문에는 개인정보 guard 테스트용 질문이 포함되어 있습니다.

```text
내 학번이랑 성적으로 처리해줘.
```

이 질문은 데모에서 guard를 보여주는 용도라면 유용하지만, 실제 학생용 운영 화면에서는 숨기는 것이 좋습니다.

권장:

- `VITE_DEMO_MODE=true`일 때만 guard 테스트 예시 노출
- 운영 모드에서는 안전한 질문만 노출

---

## 13. 반응형/접근성 기획

### 13.1 현재 반응형 방향

- 데스크톱에서는 캠퍼스 지도와 말풍선 챗봇을 동시에 보여줍니다.
- 1140px 이하에서는 말풍선 영역을 하단 dock처럼 배치합니다.
- 768px 이하에서는 HUD, 메뉴, 미니맵, 말풍선을 축소합니다.
- 520px 이하에서는 타이틀 텍스트를 줄이고 아이콘 중심으로 전환합니다.
- 서류함은 1024px 이하에서 입력/미리보기 탭 전환을 지원합니다.

### 13.2 접근성 개선 필요

| 항목 | 현재 상태 | 개선 방향 |
| --- | --- | --- |
| 아이콘 버튼 | `data-title`, `title` 중심 | `aria-label` 추가 |
| 모달 | overlay click 닫기 | ESC 닫기, focus trap 필요 |
| 키보드 탐색 | 일부 입력 Enter 처리 | 메뉴/모달/탭 키보드 이동 보강 |
| 색 대비 | 다크 모달과 색상 배지 혼재 | 주요 텍스트 대비 점검 |
| 긴 답변 | 말풍선/콘솔에 raw text 표시 | 섹션 카드/heading 구조화 |
| 파일 업로드 | 기본 input | 업로드 상태/오류 aria-live 필요 |

---

## 14. MVP 범위

### 14.1 MVP 포함

- 메타버스 캠퍼스 메인 화면
- 건물 선택과 추천 질문
- 질문 입력 및 `/ask` 연결
- 답변/출처/로그 표시
- 개인정보 경고
- 출석인정신청서와 휴학/복학 체크리스트 액션
- 퀘스트 보드와 XP 저장
- 졸업센터 상태 확인과 PDF 업로드/분석 탭
- 관리자 health 표시

### 14.2 MVP 제외

- 실제 ON국민/포털 로그인
- 실제 행정 신청 제출
- 학생 개인 계정 저장
- 학번/성적/연락처 수집
- 에브리타임 또는 로그인 후 포털 크롤링
- 모바일 앱 네이티브 구현
- 실시간 다중 사용자 동기화

---

## 15. 운영 전 개선 과제

### 15.1 P0: 운영 전 반드시 결정

| 과제 | 이유 |
| --- | --- |
| 프론트 API 포트 정책 정리 | README는 8000, 프론트 dev는 8001을 바라봄 |
| 관리자 기능 분리/보호 | ingest 실행은 학생 화면에서 직접 노출되면 위험 |
| 데모용 guard 질문 숨김 | 실제 학생에게 개인정보 입력을 유도하는 것처럼 보일 수 있음 |
| 졸업센터 privacy QA | 성적증명서 처리 UI는 민감도 높음 |
| `.env` 기반 API base 전환 | 배포 환경마다 코드 수정 없이 연결 필요 |

### 15.2 P1: 사용성 개선

| 과제 | 기대 효과 |
| --- | --- |
| `App.jsx` flow hook 분리 | 유지보수성 향상 |
| 답변 섹션 카드화 | 긴 답변 가독성 개선 |
| 에러 상태 표준화 | 백엔드 미실행/네트워크 오류 UX 개선 |
| 로딩 단계 표시 | RAG 처리 대기 시간의 불안 감소 |
| 모달 focus/ESC 처리 | 접근성 개선 |
| 서류 초안 복사/다운로드 | 다음 행동 완결성 강화 |

### 15.3 P2: 확장 기능

| 과제 | 기대 효과 |
| --- | --- |
| 검색/출처 히스토리 | 학생이 이전 근거를 다시 찾기 쉬움 |
| 즐겨찾기 질문 | 반복 질문 접근성 개선 |
| 건물별 상세 페이지 | 캠퍼스 탐색형 정보구조 강화 |
| mock/demo mode | 발표와 QA 안정성 향상 |
| Playwright 기반 visual QA | 반응형 겹침/빈 화면 회귀 방지 |

---

## 16. QA 체크리스트

### 16.1 기본 실행

- [ ] `npm run dev` 후 `http://127.0.0.1:5173/` 접속 가능
- [ ] 백엔드 `8001` 실행 시 `/ask` 정상 연결
- [ ] 백엔드 미실행 시 친화적 오류 메시지 표시
- [ ] 빌드 후 FastAPI `/`에서 `frontend/dist/index.html` 서빙 확인

### 16.2 질문/답변

- [ ] 추천 질문 클릭 시 사용자 메시지와 에이전트 답변이 추가됨
- [ ] 직접 질문 입력 후 Enter로 제출 가능
- [ ] 로딩 중 중복 제출 방지
- [ ] `citations`가 대백과에 표시됨
- [ ] citation pill 클릭 시 해당 source card가 highlight됨
- [ ] `next_actions`가 있으면 서류함 액션으로 연결됨

### 16.3 개인정보

- [ ] `학번` 입력 시 프론트 경고 표시
- [ ] 주민번호 패턴 입력 시 프론트 경고 표시
- [ ] 휴대폰 번호 입력 시 프론트 경고 표시
- [ ] 서버 privacy blocked 응답 시 안전 메시지 표시
- [ ] action slot에 민감정보 입력 시 차단 처리
- [ ] 졸업센터 결과에 이름/학번/GPA/과목별 성적이 노출되지 않음

### 16.4 서류함

- [ ] action start 후 missing slot 필드가 렌더링됨
- [ ] 필수 slot 누락 시 인라인 에러 표시
- [ ] 완료 시 document와 checklist가 대화 기록에 추가됨
- [ ] 관련 퀘스트가 completed로 변경됨
- [ ] 모바일 폭에서 입력/미리보기 탭 전환이 정상 동작함

### 16.5 퀘스트/상태 저장

- [ ] 건물 선택 시 active building과 추천 질문이 변경됨
- [ ] trigger message 질문으로 퀘스트 완료 가능
- [ ] action 완료로 퀘스트 완료 가능
- [ ] XP 증가와 level up modal 동작
- [ ] 새로고침 후 `studentContext`, level, XP, quests 유지

### 16.6 졸업센터

- [ ] 모달 진입 시 `/graduation/status` 호출
- [ ] PDF 미선택 상태에서 파싱 버튼 disabled
- [ ] 이미지 기반 PDF는 Vision OCR 동의 필요 상태 표시
- [ ] transcript parsed 후 audit 탭으로 이동
- [ ] transcript 없을 때 분석 버튼 disabled
- [ ] 분석 결과 TXT 다운로드 가능

### 16.7 반응형

- [ ] 1440px 데스크톱에서 지도, HUD, 말풍선 겹침 없음
- [ ] 1024px 이하에서 서류함 탭 구조 정상
- [ ] 768px 모바일에서 좌우 메뉴와 말풍선 겹침 없음
- [ ] 520px 이하에서 HUD 텍스트가 화면을 밀지 않음
- [ ] 긴 한국어 텍스트가 버튼/카드 밖으로 넘치지 않음

---

## 17. 릴리즈 판단 기준

### 17.1 데모 릴리즈 가능 조건

- 주요 질문 5개가 `/ask`에서 정상 응답
- 출처 패널이 비어 있지 않음
- 공결 신청서 action flow가 완료됨
- 개인정보 차단 시나리오가 정상 동작
- 졸업센터 status가 ready이거나 준비 필요 메시지가 명확히 표시됨
- 데스크톱 해상도에서 UI 겹침이 없음

### 17.2 학생 대상 베타 조건

- 관리자 기능이 학생 화면에서 분리됨
- 데모용 guard 질문이 숨겨짐
- API base가 환경변수 기반으로 정리됨
- 백엔드 오류 메시지가 친화적으로 표준화됨
- 주요 모달의 키보드 접근성이 보강됨
- 졸업센터 민감정보 QA가 통과됨

### 17.3 운영 배포 조건

- 관리자 API 인증 적용
- CORS 운영 도메인 제한
- 수집/ingest 실행 권한 제한
- 개인정보/성적증명서 처리 고지 확정
- API/화면 회귀 테스트 자동화
- 공식 근거 최신성 정책 문서화

---

## 18. 부록: 현재 파일 기준 매핑

| 파일 | 기획상 영역 |
| --- | --- |
| `frontend/src/App.jsx` | 전체 화면 조립, 상태 관리, API 호출, 모달 전환 |
| `frontend/src/components/CampusMap.jsx` | 메타버스 캠퍼스 지도 |
| `frontend/src/components/RPGMessageConsole.jsx` | 상세 대화 기록 |
| `frontend/src/components/QuestBoard.jsx` | 퀘스트 보드와 NPC 안내 |
| `frontend/src/components/ActionForm.jsx` | 서류함/문서 초안 |
| `frontend/src/components/SourcePanel.jsx` | 대백과/출처 |
| `frontend/src/components/ProcessingStatusPanel.jsx` | 처리 상태 |
| `frontend/src/components/ToolLogPanel.jsx` | Tool Calling 로그 |
| `frontend/src/components/AdminDashboard.jsx` | 관리자 대시보드 |
| `frontend/src/components/GraduationCenter.jsx` | 졸업센터 |
| `frontend/src/styles.css` | 전체 화면, 모달, 반응형, 문서 미리보기 스타일 |
| `frontend/vite.config.js` | Vite 개발 서버 설정 |

---

## 19. 결론

현재 프론트엔드는 기능 데모 수준을 넘어, 국민대 캠퍼스 생활을 주제별로 탐색하고 실제 행정 행동으로 이어주는 제품 방향을 이미 갖고 있습니다. 다음 단계의 핵심은 기능 추가보다 다음 세 가지입니다.

1. 학생용 화면과 운영자용 기능을 명확히 분리합니다.
2. 긴 답변과 복잡한 상태를 더 읽기 쉬운 카드/단계형 UI로 정리합니다.
3. 개인정보 보호와 공식 근거 확인이라는 서비스의 신뢰 요소를 화면 전반에서 일관되게 유지합니다.

이 기준을 지키면 현재 메타버스 캠퍼스 UI는 단순한 장식이 아니라, 학생이 학사 행정 문제를 장소와 행동 중심으로 이해하게 만드는 핵심 경험으로 작동할 수 있습니다.
