# KMU Campus Life Action Agent 진행상황

작성일: 2026-05-12

## 현재 구현 상태

기존 seed JSONL 기반 MVP에서 다음 구조까지 확장했다.

- 국민대학교 공식자료 crawler 구현
- 공식자료 수집/파싱/청킹 pipeline 구현
- `data/processed/chunks.jsonl` source of truth 저장
- Chroma Vector DB 인덱싱 구현
- Chroma + JSONL keyword hybrid 검색 구현
- Chroma 장애 시 keyword fallback 유지
- 출처 기반 deterministic 답변 builder 유지
- action flow 확장
- Vite React 프론트엔드와 관리자 패널 구현
- conda 가상환경 `kmu-campus-life` 생성 및 Python 의존성 설치

## 실제 크롤링 결과

학교 서버 보호 정책을 적용한 뒤 실제 공식 URL 수집을 실행했다.

```text
documents_seen: 11
network_success: 11
fallback_used: 0
network_failed: 0
failed_urls: []
chunks_written: 46
vector_available: True
vector_indexed: 46
```

chunk 단위 확인 결과:

```text
chunks 46
network 37
fallback 0
statuses ['success']
```

`network_success`는 원문 문서 단위이고, `network`는 chunk 단위 집계다.

## 학교 서버 보호 정책

학교 서버가 bot 요청에 민감할 수 있어 crawler를 보수적으로 구성했다.

- 도메인별 요청 간격: 8-18초 랜덤 지연
- 첫 요청 전 지연: 1.5-4초 랜덤 지연
- crawler별 기본 최대 요청 수: 3페이지
- `/ingest/run` 동시 실행 방지 lock
- `/ingest/run` 기본 5분 cooldown
- `ETag` / `Last-Modified` 조건부 요청 지원
- 실패/빈 응답 시 fallback 사용 여부를 숨기지 않고 기록

`/ingest/run` 응답과 `crawler_state.json`에는 다음 필드가 남는다.

- `network_success`
- `fallback_used`
- `network_failed`
- `failed_urls`

## Action Flow 확장

기존 출석인정 action 외에 다음 action을 추가했다.

- `draft_attendance_recognition_form`
- `draft_leave_checklist`
- `draft_return_checklist`
- `course_registration_checklist`
- `certificate_issue_guide`
- `graduation_audit`
- `recommend_course_plan`
- `draft_contact_message`

모든 action은 `/actions/start`에서 slot 질문을 반환하고, `/actions/continue`에서 개인정보 guard를 거친 뒤 문서/체크리스트를 생성한다.

## 프론트엔드 상태

기존 `frontend/index.html` 인라인 React 데모를 Vite 앱 구조로 전환했다.

- `frontend/src/App.jsx`
- `frontend/src/components/ChatPanel.jsx`
- `frontend/src/components/ActionForm.jsx`
- `frontend/src/components/SourcePanel.jsx`
- `frontend/src/components/ToolLogPanel.jsx`
- `frontend/src/components/AdminDashboard.jsx`
- `frontend/src/styles.css`

관리자 패널에서는 health 상태와 공식자료 수집/인덱싱 실행 결과를 확인할 수 있다.

현재 작업 환경에는 `node`/`npm`이 없어 프론트엔드 build는 검증하지 못했다.

## 실행 방법

Python 환경:

```bash
source /home/carol/exit/etc/profile.d/conda.sh
conda activate kmu-campus-life
```

백엔드:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 `http://127.0.0.1:5173`, API 서버는 `http://127.0.0.1:8000` 기준이다.

## 검증

conda 환경에서 테스트 통과:

```bash
/home/carol/exit/envs/kmu-campus-life/bin/python -m pytest
```

결과:

```text
18 passed
```

## 남은 주의사항

- 학교 서버 보호를 위해 `/ingest/run`을 반복 실행하지 않는다.
- 실제 수집이 실패하는 환경에서는 fallback이 사용될 수 있으므로 `network_success`, `fallback_used`, `failed_urls`를 반드시 확인한다.
- 공식 포털 로그인 이후 개인 화면, 에브리타임 등 비공식/비공개 서비스는 수집 대상이 아니다.
- 프론트엔드 build는 Node/npm 설치 환경에서 별도 검증이 필요하다.
