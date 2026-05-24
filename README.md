# KMU Campus Life Action Agent

국민대학교 공식 자료를 근거로 학교생활 전반의 질문에 답하고, 필요한 다음 행동까지 도와주는 Agent MVP입니다.

## 주요 기능

- 공식자료 자동 수집: 규정, 학사안내, 학생지원, 학사일정, 공지, 요람, 대학조직, 공개 SWELL 수집
- Chroma Vector DB + JSONL keyword hybrid 검색
- 문장별 출처 표시: 답변에 `[S1]`, `[S2]` citation 부착
- Tool Calling 로그: 분류, 검색, guard, checklist, 문의처 추천 과정을 화면에 표시
- 개인정보 guard: 학번, 성적, 주민번호, 연락처, 포털 ID/PW 요청 차단
- Action flow: 출석인정신청서, 휴학/복학 체크리스트, 수강신청 확인, 증명서 발급, 졸업요건 간이 진단, 수강계획 추천, 문의문 초안
- 문의처 라우팅: 이슈별 담당 부서/교강사/종합서비스센터 추천
- `test/` 졸업 도우미 프로토타입: 성적증명서 기반 졸업 진단, 대체 이수 과목 탐색, 마이크로디그리 발굴, 졸업 전후 체크리스트, 직무 역량 번역
- 요람 특화 인덱싱: 로컬에 준비한 2025 국민대학교 요람 PDF에서 졸업요건 구조화 JSON을 추출하고 ChromaDB RAG 인덱스를 구축하는 실험 기능

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

API 서버는 `http://127.0.0.1:8000`에서 실행됩니다.

OpenAI API 보조 기능은 기본적으로 꺼져 있습니다. 검색어 확장과 검색 결과 재정렬에만 사용되며, 최종 답변은 계속 공식 근거 chunk와 citation 기반으로 조립됩니다.

```bash
export OPENAI_API_KEY="..."
export OPENAI_ENABLED=true
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_GRADUATION_MODEL=gpt-4o
# 선택: deterministic 답변을 citation 보존 검증 후 문장만 다듬기
export OPENAI_POLISH_ENABLED=true
uvicorn app:app --reload
```

로컬 실행 시 루트 `.env`와 `test/.env`도 자동으로 읽습니다. 이미 쉘에 설정된 환경변수는 덮어쓰지 않습니다.

프론트엔드 개발 서버:

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`을 열면 데모 UI와 관리자 대시보드를 볼 수 있습니다.

## 졸업 도우미 프로토타입 (`test/`)

`test/` 폴더에는 메인 FastAPI/React 서비스와 별도로 실행되는 Streamlit 기반 **국민대학교 졸업 도우미** 프로토타입이 포함되어 있습니다.

주요 기능:

- 성적증명서 PDF 또는 수동 입력 기반 졸업 가능 여부 진단
- 요람 별표5/별표6 파싱을 통한 학과별 졸업요건 구조화
- 2025 국민대학교 요람 PDF ChromaDB 인덱싱
- 폐강/수강 실패 과목의 대체 이수 후보 탐색
- 이수 과목 기반 마이크로디그리/소학위 달성 가능성 분석
- 졸업 전후 행정 체크리스트 생성
- 이수 과목을 자기소개서용 직무 역량 키워드와 문장으로 변환
- 교학팀 확인 요청서 및 분석 결과 TXT 다운로드

실행 예시:

```bash
cd test
pip3 install -r requirements.txt
# 공식 요람 PDF를 test/2025국민대학교요람_20250910.pdf 경로에 직접 배치
python3 0_extract_structured_data.py
python3 1_build_index.py
streamlit run 3_app.py
```

주의: 이 프로토타입은 성적증명서와 개인 성적 정보를 직접 다루는 흐름을 포함합니다. 메인 서비스의 개인정보 guard 정책과 통합하려면 성적표 원본 업로드 대신 비식별 이수학점 요약 입력 방식으로 재설계해야 합니다.

## 테스트

```bash
pytest
```

실제 성적증명서 PDF를 사용하는 졸업센터 E2E는 민감정보와 OpenAI 비용 때문에 기본 테스트에서는 건너뜁니다. 로컬에서 명시적으로만 실행하세요.

```bash
RUN_REAL_TRANSCRIPT_E2E=1 REAL_TRANSCRIPT_PDF_PATH="./문대한_성적증명서.pdf" pytest tests/test_graduation_real_e2e.py -q
```

## 데모 질문

- `예비군 때문에 결석하는데 뭐 해야 해?`
- `5월 15일에 예비군 때문에 결석하는데 출석인정 언제까지 내야 해?`
- `질병휴학 하려면 뭐 필요해?`
- `수강신청 완료됐는지 어디서 확인해?`
- `졸업예정증명서 어디서 뽑아?`
- `내 학번이랑 성적으로 처리해줘.`

## API

- `POST /ask`: 질문 답변, 출처, Tool 로그, 다음 행동 반환
- `POST /actions/start`: action 시작
- `POST /actions/continue`: action slot 입력 후 초안 생성
- `POST /ingest/run`: 공식자료 수집, JSONL 저장, Chroma 인덱싱 실행
- `POST /ingest/live-refresh`: 특정 `issue_type`의 관련 공식 공개 소스만 즉시 재확인
- `GET /sources`: 공식 chunk 목록
- `GET /health`: 서버 상태
- `GET /graduation/status`: 졸업 센터 준비 상태와 개인정보 처리 정책 확인
- `POST /graduation/transcript/parse`: 성적증명서 PDF 임시 파싱, 텍스트 PDF 우선, 동의 시 Vision OCR
- `POST /graduation/audit`: 업로드한 성적증명서 요약 기반 졸업 진단
- `POST /graduation/early-graduation`: 조기졸업 가능 여부와 주의사항 확인
- `POST /graduation/customized-major`: Customized전공 인정 제도 및 필수과목 대체 가능성 확인
- `POST /graduation/credit-drop`: 학점 드랍에 해당하는 공식 성적포기 제도 확인
- `POST /graduation/substitute-courses`: 대체 이수 과목 탐색
- `POST /graduation/micro-degree`: 마이크로디그리/소학위 가능성 분석
- `POST /graduation/post-graduation-checklist`: 졸업 전후 체크리스트 생성
- `POST /graduation/career-translator`: 이수 과목 기반 직무 역량 번역

`POST /ask`는 선택적으로 `live_check: true`와 `llm_assist: false`를 받을 수 있습니다. `live_check`가 켜지면 개인정보 guard와 분류 이후, 관련 공식 공개 소스만 즉시 확인하고 네트워크 fetch가 성공한 문서만 로컬 근거 chunk에 반영합니다. 네트워크 실패나 차단으로 fallback이 사용된 문서는 기존 chunk를 덮어쓰지 않으며, 응답의 `live_check.network_success`, `fallback_used`, `network_failed`, `failed_urls`로 실제 확인 상태를 볼 수 있습니다. `llm_assist`는 OpenAI API 보조 기능을 질문 단위로 켜고 끄는 옵션이며, 서버에서 `OPENAI_ENABLED=false`이면 요청값과 관계없이 사용되지 않습니다.

`POST /actions/continue`도 선택적으로 `live_check: true`를 받을 수 있습니다. 이 경우 초안 생성 전에 action의 `issue_type`에 맞는 공식 공개 소스를 같은 방식으로 재확인합니다. 개인정보 guard가 slot 값을 차단한 경우에는 live check를 실행하지 않습니다.

졸업 센터는 성적증명서 PDF 업로드가 필수입니다. PDF 원본과 raw OCR text는 임시 처리 후 삭제하며, 응답과 다운로드 결과에는 이름/학번/GPA 숫자/과목별 성적을 포함하지 않습니다. 이미지 기반 PDF는 사용자가 Vision OCR 전송에 명시 동의한 경우에만 OpenAI Vision으로 처리합니다.

## 데이터와 근거

수집/청킹된 데이터는 `data/processed/chunks.jsonl`에 저장됩니다. 이 파일은 source of truth이며, Chroma가 사용 가능하면 같은 chunk가 `data/vector/chroma` collection에 인덱싱됩니다. Chroma가 사용 불가한 경우에도 JSONL keyword fallback으로 답변 API가 동작합니다.

Crawler는 학교 서버 보호를 위해 보수적으로 동작합니다.

- 도메인별 요청 간격을 사람 속도에 맞춰 랜덤 지연합니다.
- `/ingest/run`은 동시 실행을 막고, 기본 5분 cooldown을 둡니다.
- `ETag`와 `Last-Modified`가 내려오면 다음 수집 때 조건부 요청에 사용합니다.
- 네트워크 실패나 차단 시에는 같은 공식 URL에 연결된 curated fallback text를 사용합니다.
- `/ingest/run` 응답에는 `network_success`, `fallback_used`, `network_failed`, `failed_urls`가 포함되어 실제 크롤링 성공 여부를 숨기지 않습니다.

Source tier:

1. 규정관리시스템
2. 학사안내
3. 학생지원/대학생활 안내
4. 학사일정
5. 공지사항
6. 요람/규정집
7. 대학조직/문의처
8. SWELL 공개 게시판

## 한계와 주의사항

- 실제 행정 처리를 대신하지 않습니다.
- 공식 포털 로그인 이후 개인 화면에는 접근하지 않습니다.
- 실제 학번, 성적, 연락처, 포털 ID/PW는 입력하지 마세요.
- `test/` 졸업 도우미는 별도 프로토타입이며, 메인 서비스에 통합하기 전 개인정보/성적 데이터 처리 정책을 다시 설계해야 합니다.
- Chroma Vector DB는 구현되어 있으나, 설치/인덱스 장애가 있어도 JSONL 키워드 검색 fallback으로 데모가 동작합니다.
- 최종 처리는 국민대학교 공식 포털, 담당 부서, 학과사무실 또는 담당 교강사 확인이 필요합니다.
