# 프론트엔드 Mock 데이터 기획 문서

> **대상:** 프론트엔드 담당자 전용
> **목적:** 백엔드 완성 전 독립 개발을 위한 Mock 데이터 & 레이어 구성 가이드
> **작성일:** 2026-05-21
> **버전:** v1.0

---

## 목차

1. [Mock 개발 전략](#1-mock-개발-전략)
2. [Mock 레이어 설정](#2-mock-레이어-설정)
3. [TypeScript 타입 정의](#3-typescript-타입-정의)
4. [API별 Mock 데이터](#4-api별-mock-데이터)
   - 4-1. POST /ask — 성공 시나리오 5종
   - 4-2. POST /ask — 에러 시나리오 3종
   - 4-3. POST /actions/start
   - 4-4. POST /actions/continue
   - 4-5. GET /health
5. [컴포넌트별 개발 시나리오](#5-컴포넌트별-개발-시나리오)
6. [Mock → 실제 API 전환 체크리스트](#6-mock--실제-api-전환-체크리스트)

---

## 1. Mock 개발 전략

### 전제

- BE-004 (API 응답 스키마 확정)가 **1주차 수요일**에 완료됨
- 그 전까지 FE는 이 문서의 Mock 데이터로 모든 컴포넌트 개발을 진행
- Mock과 실제 API의 **응답 구조가 동일**하므로 전환 시 컴포넌트 코드 수정 없음

### Mock 전환 조건

```
VITE_USE_MOCK=true   → Mock 데이터 사용 (개발 초기)
VITE_USE_MOCK=false  → 실제 API 호출 (BE 완성 후)
```

환경변수 하나로 전환되도록 API 레이어를 구성한다. 컴포넌트는 `useAsk`, `useAction` 훅만 호출하고 내부가 Mock인지 실제인지 신경 쓰지 않는다.

---

## 2. Mock 레이어 설정

### 파일 구조

```
src/
├── api/
│   ├── client.ts          ← 실제 API 호출 함수
│   ├── mock/
│   │   ├── handlers.ts    ← Mock 응답 반환 함수
│   │   ├── scenarios.ts   ← 시나리오별 Mock 데이터 모음
│   │   └── index.ts       ← Mock 레이어 진입점
│   └── index.ts           ← 환경변수 분기 (Mock or Real)
└── hooks/
    ├── useAsk.ts
    └── useAction.ts
```

### src/api/index.ts — 환경변수 분기

```typescript
import * as real from './client'
import * as mock from './mock'

const isMock = import.meta.env.VITE_USE_MOCK === 'true'

export const askQuestion = isMock ? mock.askQuestion : real.askQuestion
export const startAction  = isMock ? mock.startAction  : real.startAction
export const continueAction = isMock ? mock.continueAction : real.continueAction
export const getHealth    = isMock ? mock.getHealth    : real.getHealth
```

### src/api/mock/handlers.ts — Mock 응답 함수

```typescript
import { AskResponse, ActionStartResponse, ActionContinueResponse, HealthResponse } from '../types'
import { scenarios } from './scenarios'

// 질문 키워드로 시나리오 자동 매핑
export async function askQuestion(question: string): Promise<AskResponse> {
  await delay(1800) // 실제 처리 시간 시뮬레이션

  if (question.includes('학번') || question.includes('성적') || question.includes('주민')) {
    return scenarios.ask.privacyBlocked
  }
  if (question.includes('수강') || question.includes('수변')) {
    return scenarios.ask.courseRegistration
  }
  if (question.includes('휴학') || question.includes('복학')) {
    return scenarios.ask.leaveReturn
  }
  if (question.includes('출석') || question.includes('결석') || question.includes('예비군')) {
    return scenarios.ask.attendance
  }
  if (question.includes('일정') || question.includes('언제') || question.includes('기간')) {
    return scenarios.ask.schedule
  }
  if (question.includes('장학') || question.includes('국장')) {
    return scenarios.ask.scholarship
  }

  return scenarios.ask.noSource // 기본 — 소스 없음 에러
}

export async function startAction(actionId: string): Promise<ActionStartResponse> {
  await delay(500)
  return scenarios.action.start[actionId] ?? scenarios.action.start.attendance_approval
}

export async function continueAction(
  actionId: string,
  slots: Record<string, string>
): Promise<ActionContinueResponse> {
  await delay(1200)
  const required = ['event_date', 'reason']
  const filled = required.every(key => slots[key])
  return filled ? scenarios.action.completed : scenarios.action.pending
}

export async function getHealth(): Promise<HealthResponse> {
  return scenarios.health
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
```

---

## 3. TypeScript 타입 정의

> `src/api/types.ts`에 저장. BE-004 스키마 확정 후 이 파일을 기준으로 검수.

```typescript
// ──────────────────────────────────────────────
// 공통
// ──────────────────────────────────────────────

export type ErrorCode =
  | 'privacy_blocked'
  | 'no_source'
  | 'server_error'
  | 'unauthorized'

export interface ApiError {
  error_code: ErrorCode
  message: string
  detail?: string
}

// ──────────────────────────────────────────────
// POST /ask
// ──────────────────────────────────────────────

export interface AskRequest {
  question: string
  student_context?: {
    status?: string
    term?: string
    concern?: string
  }
  llm_assist?: boolean
  live_check?: boolean
}

export interface Citation {
  id: string        // "S1", "S2", ...
  title: string
  url: string
  text: string      // 발췌문 (최대 140자)
}

export interface NextAction {
  action_id: string
  label: string
  description: string
}

export interface Checklist {
  tasks: string[]
  required_documents: string[]
  application_paths: string[]
}

export interface Contact {
  name: string
  label: string
  phone?: string
}

export interface Deadline {
  deadline: string       // "YYYY-MM-DD"
  description: string
}

export interface AskResponse {
  answer: string
  issue_type: string
  citations: Citation[]
  next_actions: NextAction[]
  checklist: Checklist
  contacts: Contact[]
  deadline: Deadline | null
  tool_logs: string[]
}

// ──────────────────────────────────────────────
// POST /actions/start
// ──────────────────────────────────────────────

export interface Slot {
  key: string
  question: string
  required: boolean
}

export interface ActionStartRequest {
  action_id: string
}

export interface ActionStartResponse {
  action_id: string
  title: string
  slots: Slot[]
}

// ──────────────────────────────────────────────
// POST /actions/continue
// ──────────────────────────────────────────────

export interface ActionContinueRequest {
  action_id: string
  slots: Record<string, string>
}

export type ActionContinueResponse =
  | { status: 'completed'; document: string; checklist: string[]; citations: Citation[] }
  | { status: 'pending';   next_slot: { key: string; question: string } }
  | { status: 'blocked';   error_code: ErrorCode; message: string }

// ──────────────────────────────────────────────
// GET /health
// ──────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded'
  keyword_chunks: number
  vector_available: boolean
  llm_status: 'connected' | 'no_key' | 'error'
  last_ingest: string | null
}
```

---

## 4. API별 Mock 데이터

> `src/api/mock/scenarios.ts`에 저장.

---

### 4-1. POST /ask — 성공 시나리오 5종

#### 시나리오 1: 수강신청 (`course_registration`)

> 트리거 키워드: "수강", "수변", "시간표", "수강신청"

```typescript
export const courseRegistration: AskResponse = {
  answer: `수강신청 관련 공식 공지를 확인했습니다.[S1] 수강신청 완료 여부는 수강신청시스템 '나의 시간표' 또는 ON국민 포털 '개인수업시간표 조회' 기준으로 확인합니다.[S2]`,
  issue_type: 'course_registration',
  citations: [
    {
      id: 'S1',
      title: '2026학년도 수강신청 안내',
      url: 'https://www.kookmin.ac.kr/notice/academic/2026-course-reg',
      text: '2026학년도 1학기 수강신청은 2월 17일(월)부터 21일(금)까지 진행됩니다. 수강신청시스템(sugang.kookmin.ac.kr)에서 신청 가능합니다.',
    },
    {
      id: 'S2',
      title: '수강신청 확인 방법 안내',
      url: 'https://www.kookmin.ac.kr/notice/academic/confirm',
      text: '수강신청 완료 여부는 ON국민 포털 로그인 후 [학사정보 > 개인수업시간표 조회] 메뉴에서 확인하세요.',
    },
  ],
  next_actions: [
    {
      action_id: 'course_plan',
      label: '수강계획 추천받기',
      description: '졸업요건 기반 수강 추천 목록을 확인합니다.',
    },
  ],
  checklist: {
    tasks: [
      'ON국민 포털에서 개인수업시간표 조회로 신청 완료 확인',
      '수강신청시스템에서 장바구니 → 신청으로 이동 여부 확인',
      '폐강 과목 수강정정 기간(2월 24일~28일) 확인',
    ],
    required_documents: [],
    application_paths: [
      'ON국민 포털 → 학사정보 → 개인수업시간표 조회',
      '수강신청시스템: sugang.kookmin.ac.kr',
    ],
  },
  contacts: [
    { name: '교학처 학사지원팀', label: '수강신청 문의', phone: '02-910-4131' },
  ],
  deadline: null,
  tool_logs: [
    'guard.inspect_privacy 호출됨',
    'classify_issue 호출됨 → course_registration',
    'search_official_sources 호출됨',
    'suggest_actions 호출됨',
    'build_final_answer 호출됨',
  ],
}
```

---

#### 시나리오 2: 출석 인정 (`attendance`)

> 트리거 키워드: "출석", "결석", "예비군", "공결"

```typescript
export const attendance: AskResponse = {
  answer: `출석인정 관련 공식 근거를 확인했습니다.[S1] 예비군 훈련은 출석인정 신청 가능 사유에 해당하며,[S2] 사유 발생 7일 이내 출석인정신청서와 증빙서류를 제출해야 합니다. 훈련 날짜가 2026-05-10이라면 제출 기한은 2026-05-17입니다.`,
  issue_type: 'attendance',
  citations: [
    {
      id: 'S1',
      title: '국민대학교 학사운영규정 — 출석인정',
      url: 'https://www.kookmin.ac.kr/rule/academic/attendance',
      text: '제29조(출석인정) 학생이 공적 사유로 결석한 경우 담당 교강사에게 출석인정 신청서를 제출하여 출석인정을 받을 수 있다.',
    },
    {
      id: 'S2',
      title: '예비군·민방위 출석인정 안내',
      url: 'https://www.kookmin.ac.kr/notice/military/2026',
      text: '예비군 및 민방위 훈련 참가 시 소집통지서 또는 훈련필증을 첨부하여 사유 발생 후 7일 이내 신청하세요.',
    },
  ],
  next_actions: [
    {
      action_id: 'attendance_approval',
      label: '출석인정신청서 작성하기',
      description: '신청서 초안을 자동으로 작성해드립니다.',
    },
  ],
  checklist: {
    tasks: [
      '예비군 훈련필증 또는 소집통지서 준비',
      '출석인정신청서 작성 (학과사무실 또는 ON국민 포털)',
      '사유 발생 후 7일 이내 담당 교강사에게 제출',
      '교강사 승인 후 처리 결과 ON국민 포털에서 확인',
    ],
    required_documents: ['예비군 훈련필증 또는 소집통지서', '출석인정신청서'],
    application_paths: [
      'ON국민 포털 → 학사정보 → 출석인정신청',
      '담당 교강사에게 직접 제출 가능',
    ],
  },
  contacts: [
    { name: '소속 학과사무실', label: '출석인정 서류 제출', phone: '' },
    { name: '교학처 학사지원팀', label: '출석인정 제도 문의', phone: '02-910-4131' },
  ],
  deadline: {
    deadline: '2026-05-17',
    description: '훈련일(2026-05-10)로부터 7일 이내 — 2026-05-17까지 제출',
  },
  tool_logs: [
    'guard.inspect_privacy 호출됨',
    'classify_issue 호출됨 → attendance',
    'search_official_sources 호출됨',
    'tools.deadline.calculate_deadline 호출됨',
    'suggest_actions 호출됨',
    'build_final_answer 호출됨',
  ],
}
```

---

#### 시나리오 3: 휴학·복학 (`leave_return`)

> 트리거 키워드: "휴학", "복학"

```typescript
export const leaveReturn: AskResponse = {
  answer: `휴학/복학 관련 공식 안내를 확인했습니다.[S1] 신청 경로와 필요서류는 휴학 유형(일반·질병·군)에 따라 달라지며, ON국민 포털의 휴학/복학 신청 메뉴를 우선 확인해야 합니다.`,
  issue_type: 'leave_return',
  citations: [
    {
      id: 'S1',
      title: '휴학·복학 신청 안내',
      url: 'https://www.kookmin.ac.kr/academic/guide/leave',
      text: '휴학은 일반휴학, 질병휴학, 군휴학으로 구분되며 각 유형별 제출서류와 신청 기간이 다릅니다. ON국민 포털에서 온라인 신청이 가능합니다.',
    },
  ],
  next_actions: [
    {
      action_id: 'leave_checklist',
      label: '휴학 체크리스트 받기',
      description: '유형별 필요 서류와 절차를 정리해드립니다.',
    },
  ],
  checklist: {
    tasks: [
      'ON국민 포털에서 휴학 신청 유형 선택',
      '유형별 필요서류 준비 (질병휴학: 진단서, 군휴학: 입영통지서 등)',
      '지도교수 또는 학과장 서명 필요 여부 확인',
      '등록금 환불 기준 확인 (휴학 시점에 따라 상이)',
    ],
    required_documents: [
      '휴학신청서 (ON국민 포털에서 출력)',
      '유형별 증빙서류',
    ],
    application_paths: [
      'ON국민 포털 → 학사정보 → 휴·복학신청',
    ],
  },
  contacts: [
    { name: '교학처 학사지원팀', label: '휴학·복학 신청 문의', phone: '02-910-4131' },
    { name: '소속 학과사무실', label: '지도교수 서명 안내', phone: '' },
  ],
  deadline: null,
  tool_logs: [
    'guard.inspect_privacy 호출됨',
    'classify_issue 호출됨 → leave_return',
    'search_official_sources 호출됨',
    'suggest_actions 호출됨',
    'build_final_answer 호출됨',
  ],
}
```

---

#### 시나리오 4: 장학금 (`scholarship`)

> 트리거 키워드: "장학", "국장", "근로장학"

```typescript
export const scholarship: AskResponse = {
  answer: `장학금 관련 공식 공지를 확인했습니다.[S1] 국가장학금(국장)은 한국장학재단 사이트에서 신청하며, 교내 장학금은 ON국민 포털에서 별도 신청합니다.[S2] 중복 지원 제한 규정이 있으므로 신청 전 확인이 필요합니다.`,
  issue_type: 'scholarship',
  citations: [
    {
      id: 'S1',
      title: '2026학년도 장학금 신청 공고',
      url: 'https://www.kookmin.ac.kr/notice/scholarship/2026',
      text: '2026학년도 1학기 교내 장학금 신청은 3월 10일부터 3월 21일까지입니다. ON국민 포털 → 장학 → 장학신청에서 신청하세요.',
    },
    {
      id: 'S2',
      title: '국가장학금 신청 안내',
      url: 'https://www.kstudy.com',
      text: '국가장학금은 한국장학재단(www.kstudy.com)에서 신청합니다. 1차 신청 기간을 놓친 경우 2차 신청 기간을 이용하세요.',
    },
  ],
  next_actions: [],
  checklist: {
    tasks: [
      '한국장학재단 사이트에서 국가장학금 신청 기간 확인',
      'ON국민 포털에서 교내 장학금 신청 기간 확인',
      '중복 수혜 제한 규정 확인 후 신청',
      '신청 완료 후 서류 제출 여부 확인',
    ],
    required_documents: ['가구원 소득 증빙서류 (국가장학금)', '재학증명서 (일부 장학금)'],
    application_paths: [
      '국가장학금: www.kstudy.com',
      '교내 장학금: ON국민 포털 → 장학 → 장학신청',
    ],
  },
  contacts: [
    { name: '학생처 장학팀', label: '교내 장학금 문의', phone: '02-910-4053' },
    { name: '한국장학재단 콜센터', label: '국가장학금 문의', phone: '1599-2000' },
  ],
  deadline: null,
  tool_logs: [
    'guard.inspect_privacy 호출됨',
    'classify_issue 호출됨 → scholarship',
    'search_official_sources 호출됨',
    'suggest_actions 호출됨',
    'build_final_answer 호출됨',
  ],
}
```

---

#### 시나리오 5: 학사일정 (`schedule`)

> 트리거 키워드: "일정", "기간", "언제", "이번 주"

```typescript
export const schedule: AskResponse = {
  answer: `학사일정 공식 근거를 확인했습니다.[S1] 아래 일정 상태는 오늘(2026-05-21) 기준 참고 정보이며, 신청·납부가 필요한 항목은 ON국민 포털에서 다시 확인해야 합니다.`,
  issue_type: 'schedule',
  citations: [
    {
      id: 'S1',
      title: '2026학년도 학사일정',
      url: 'https://www.kookmin.ac.kr/academic/schedule/2026',
      text: '2026학년도 학사일정은 학교 홈페이지 학사안내 > 학사일정에서 확인할 수 있습니다.',
    },
  ],
  next_actions: [],
  checklist: {
    tasks: [
      '수강신청 정정 기간(5/25~5/29) 내 변경 필요 시 신청',
      '중간고사 성적 입력 기간(6/1~6/7) 확인',
      '등록금 분납 2차(6/15) 기한 확인',
    ],
    required_documents: [],
    application_paths: ['ON국민 포털 → 학사정보 → 학사일정'],
  },
  contacts: [
    { name: '교학처 학사지원팀', label: '학사일정 문의', phone: '02-910-4131' },
  ],
  deadline: null,
  tool_logs: [
    'guard.inspect_privacy 호출됨',
    'classify_issue 호출됨 → schedule',
    'search_official_sources 호출됨',
    'build_final_answer 호출됨',
  ],
}
```

---

### 4-2. POST /ask — 에러 시나리오 3종

#### 에러 1: 개인정보 차단 (`privacy_blocked`)

> 트리거 키워드: "학번", "성적", "주민번호"

```typescript
export const privacyBlocked: ApiError = {
  error_code: 'privacy_blocked',
  message:
    '실제 학번, 성적, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력받지 않습니다. 가상 사례나 비식별 정보로만 안내할 수 있습니다.',
}
```

---

#### 에러 2: 공식 자료 없음 (`no_source`)

> 트리거: 키워드 없는 질문 또는 데이터 없는 이슈

```typescript
export const noSource: ApiError = {
  error_code: 'no_source',
  message:
    '공식 자료에서 관련 내용을 찾지 못했습니다. 담당 부서에 직접 문의하거나 학교 공식 포털을 이용해주세요.',
}
```

---

#### 에러 3: 서버 오류 (`server_error`)

> 트리거: 네트워크 오류, 백엔드 미실행

```typescript
export const serverError: ApiError = {
  error_code: 'server_error',
  message:
    '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
}
```

---

### 4-3. POST /actions/start

```typescript
// 출석인정신청서
export const attendanceApprovalStart: ActionStartResponse = {
  action_id: 'attendance_approval',
  title: '출석인정신청서 작성',
  slots: [
    { key: 'event_date',  question: '결석한 날짜는 언제인가요? (예: 2026-05-10)', required: true },
    { key: 'reason',      question: '사유를 선택해주세요. (예비군훈련 / 민방위훈련 / 공무 / 기타)', required: true },
    { key: 'course_name', question: '해당 수업 이름을 입력해주세요. (예: 운영체제론)', required: true },
    { key: 'professor',   question: '담당 교수님 성함을 입력해주세요.', required: true },
  ],
}

// 휴학 체크리스트
export const leaveChecklistStart: ActionStartResponse = {
  action_id: 'leave_checklist',
  title: '휴학 유형별 체크리스트',
  slots: [
    { key: 'leave_type', question: '휴학 유형을 선택해주세요. (일반 / 질병 / 군)', required: true },
    { key: 'semester',   question: '휴학 예정 학기를 입력해주세요. (예: 2026-2학기)', required: true },
  ],
}
```

---

### 4-4. POST /actions/continue

```typescript
// 완료 — 출석인정신청서 초안
export const attendanceCompleted: ActionContinueResponse = {
  status: 'completed',
  document: `
출석인정신청서

학  과: _______________
학  번: _______________
성  명: _______________

결석 날짜: 2026-05-10
결석 사유: 예비군 훈련
해당 수업: 운영체제론 (담당: _____ 교수)

위와 같이 결석하였기에 출석인정을 신청합니다.
첨부서류: 예비군 훈련필증

2026년  월  일
신청인: _______________  (서명)

⚠️ 이 초안은 참고용입니다. 제출 전 담당 교강사 및 학과사무실에 확인하세요.
  `.trim(),
  checklist: [
    '예비군 훈련필증 첨부 필수',
    '담당 교강사 제출 기한: 사유 발생 후 7일 이내 (2026-05-17까지)',
    'ON국민 포털에서 처리 결과 확인',
  ],
  citations: [
    {
      id: 'S1',
      title: '국민대학교 학사운영규정 — 출석인정',
      url: 'https://www.kookmin.ac.kr/rule/academic/attendance',
      text: '제29조 출석인정 신청은 사유 발생 후 7일 이내 제출해야 한다.',
    },
  ],
}

// 추가 슬롯 필요
export const actionPending: ActionContinueResponse = {
  status: 'pending',
  next_slot: {
    key: 'professor',
    question: '담당 교수님 성함을 입력해주세요.',
  },
}

// 개인정보 차단
export const actionBlocked: ActionContinueResponse = {
  status: 'blocked',
  error_code: 'privacy_blocked',
  message:
    '실제 학번이나 개인정보는 입력하지 않아도 됩니다. 초안에는 빈칸으로 처리됩니다.',
}
```

---

### 4-5. GET /health

```typescript
// 정상 상태
export const healthOk: HealthResponse = {
  status: 'ok',
  keyword_chunks: 103,
  vector_available: true,
  llm_status: 'connected',
  last_ingest: '2026-05-21T09:00:00',
}

// 저하 상태 (벡터 DB 없음, LLM key 없음)
export const healthDegraded: HealthResponse = {
  status: 'degraded',
  keyword_chunks: 103,
  vector_available: false,
  llm_status: 'no_key',
  last_ingest: '2026-05-20T14:30:00',
}
```

---

## 5. 컴포넌트별 개발 시나리오

각 컴포넌트를 개발할 때 아래 시나리오로 렌더링을 검증합니다.

### 질문 입력 컴포넌트 (`QuestionInput`)

| 시나리오 | 검증 항목 |
|---|---|
| 기본 상태 | 페이지 로드 시 자동 포커스 |
| 텍스트 입력 | 입력값 state 반영 |
| 전송 클릭 | `useAsk` 훅 호출, 버튼 비활성화 |
| 빈 입력 전송 | 전송 방지, 경고 없음 (버튼만 비활성) |
| Enter 키 | 전송 동작 |
| Shift+Enter | 줄바꿈 |

---

### 로딩 컴포넌트 (`LoadingSteps`)

| 시나리오 | 검증 항목 |
|---|---|
| 로딩 시작 | "이슈 분류 중..." 표시 |
| 1.5초 후 | "공식 자료 검색 중..." 전환 |
| 3초 후 | "답변 생성 중..." 전환 |
| 응답 수신 | 컴포넌트 unmount, 답변 카드 mount |

---

### 답변 카드 5종 (`AnswerCards`)

| 카드 | 시나리오 | 검증 항목 |
|---|---|---|
| 요약 카드 | `scenarios.ask.attendance` | `[S1]`, `[S2]` 마커 렌더링 |
| 체크리스트 카드 | `scenarios.ask.courseRegistration` | tasks 3개 목록 렌더링 |
| 기한 카드 | `scenarios.ask.attendance` | deadline 날짜 표시 |
| 기한 카드 | `scenarios.ask.scholarship` | deadline null → 카드 숨김 |
| 문의처 카드 | `scenarios.ask.attendance` | 부서명 + 전화번호 표시 |
| 근거 출처 카드 | 기본 상태 | 접힘 상태 |
| 근거 출처 카드 | 클릭 후 | 펼쳐져 citation 목록 노출 |
| 인용 마커 클릭 | `[S1]` 클릭 | 근거 출처 카드로 스크롤 |

---

### 에러 컴포넌트 (`ErrorMessage`)

| 시나리오 | 검증 항목 |
|---|---|
| `privacy_blocked` | 붉은 배경 인라인 경고 메시지 |
| `no_source` | 회색 안내 메시지 + 담당 부서 문의 안내 |
| `server_error` | 경고 메시지 + "학교 공식 포털" 링크 버튼 |

---

### 신청서 작성 플로우 (`ActionFlow`)

| 단계 | 시나리오 | 검증 항목 |
|---|---|---|
| 시작 | `attendanceApprovalStart` | 슬롯 4개 중 첫 번째 질문만 표시 |
| 입력 중 | `actionPending` | 다음 슬롯 질문으로 전환 |
| 개인정보 입력 | `actionBlocked` | 인라인 차단 메시지 |
| 완료 | `attendanceCompleted` | 초안 텍스트 + 체크리스트 + 복사 버튼 |
| 복사 버튼 클릭 | — | 클립보드 복사 + "복사됨" 피드백 |
| 면책 문구 | — | 항상 노출 확인 |

---

### 관리자 페이지 (`AdminPage`)

| 시나리오 | 검증 항목 |
|---|---|
| 토큰 미입력 | 기능 버튼 비활성화 |
| `healthOk` | 청크 수 103, Chroma ✅, LLM ✅ 표시 |
| `healthDegraded` | Chroma ❌, LLM ⚠️ (no_key) 표시 |
| 인제스트 버튼 클릭 | 로딩 → 성공 메시지 |

---

## 6. Mock → 실제 API 전환 체크리스트

> BE-005, BE-006 완성 후 아래 항목을 순서대로 확인합니다.

### 전환 방법

```bash
# .env.development
VITE_USE_MOCK=true    # 개발 중

# .env.production (또는 BE 완성 후)
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```

### 전환 후 검증 항목

- [ ] `POST /ask` — 수강신청 질문 → 실제 청크 기반 답변 반환 확인
- [ ] `POST /ask` — 개인정보 포함 질문 → `privacy_blocked` 에러 코드 반환 확인
- [ ] `POST /ask` — 백엔드 미실행 상태 → `server_error` UI 렌더링 확인
- [ ] `POST /actions/start` — `attendance_approval` → 슬롯 4개 반환 확인
- [ ] `POST /actions/continue` — 슬롯 완성 → `completed` 초안 반환 확인
- [ ] `GET /health` — 실제 청크 수 / LLM 상태 반영 확인
- [ ] TypeScript 타입 오류 없음 (BE 응답 구조와 `src/api/types.ts` 일치 확인)
- [ ] Mock 지연(`delay()`) 제거 또는 비활성화 확인

### 응답 구조 불일치 시

BE 응답에서 필드가 추가/변경된 경우:
1. `src/api/types.ts` 타입 먼저 수정
2. Mock 데이터(`scenarios.ts`) 동기화
3. 영향받는 컴포넌트 확인 후 수정
4. BE 담당자에게 변경 이력 공유 요청 (계약 변경 시 당일 공지 원칙)
