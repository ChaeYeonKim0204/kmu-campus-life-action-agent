# 폴더 구조 안내

비전공자가 이 프로젝트를 파악할 때 쓰는 지도. 각 폴더가 *조립 라인의 한 공정*이라고 보면 된다.

## 전체 구조 한눈에

```
kmu-campus-life-action-agent/
├── app.py                ← 🚪 입구. 모든 요청이 여기로 들어옴
├── llm_client.py         ← 🪑 비어있는 LLM 자리
├── requirements.txt      ← 파이썬에 뭐 깔아야 하는지 적힌 쇼핑리스트
│
├── crawler/              ← 1️⃣ 학교 사이트에서 글 긁어오는 부서
├── ingestion/            ← 2️⃣ 긁어온 글을 잘게 자르는 부서
├── data/                 ← 3️⃣ 자른 글이 쌓이는 창고
├── retriever/            ← 4️⃣ 창고에서 질문에 맞는 조각 꺼내오는 부서
├── agent/                ← 5️⃣ 두뇌 (분류, 가드, 답변 조립)
├── tools/                ← 6️⃣ 두뇌가 쓰는 도구함
│
├── frontend/             ← 사용자가 보는 채팅 화면
├── tests/                ← 위 부서들이 잘 작동하는지 점검표
├── test/                 ← Streamlit 기반 졸업 도우미 프로토타입
│
└── *.md                  ← 문서들 (README, 계획, 진행상황, CLAUDE.md)
```

## 답변이 만들어지는 길

사용자가 채팅창에 질문을 넣으면 다음 순서로 처리된다.

```
질문
 → app.py (입구)
 → agent/guard.py        (개인정보 차단)
 → agent/classifier.py   (질문 유형 분류)
 → retriever/...         (창고에서 관련 조각 찾기)
 → agent/planner.py      (다음 행동 추천 결정)
 → agent/answer_builder.py (답 조립)
 → 응답
```

---

## 1️⃣ `crawler/` — 학교 사이트 다녀오는 수집원

각 파일이 사이트 하나씩 담당.

| 파일 | 담당 |
|---|---|
| `base.py` | 공통 규칙. 학교 서버 안 괴롭히도록 8~18초 쉬어가며 긁어옴. 재시도, 오류 처리. |
| `kmu_rule.py` | 규정관리시스템 (1순위 신뢰도) |
| `kmu_academic_guide.py` | 학사안내 (휴학·출석 등 절차) |
| `kmu_student_support.py` | 학생지원/증명서 |
| `kmu_schedule.py` | 학사일정 |
| `kmu_notice.py` | 공지사항 |
| `kmu_cradle.py` | 요람/교육과정 |
| `kmu_org.py` | 대학조직 (문의처) |
| `swell_public.py` | SWELL 공개 게시판 |

## 2️⃣ `ingestion/` — 긁어온 글 자르고 정리

| 파일 | 담당 |
|---|---|
| `parser.py` | HTML 같은 거에서 본문만 추출 |
| `file_extractors.py` | PDF/DOCX/HWP 파일 처리 |
| `chunker.py` | 긴 글을 검색하기 좋은 조각(chunk)으로 자름 |
| `pipeline.py` | 위 셋을 순서대로 돌리는 컨트롤러. `/ingest/run` 부르면 얘가 일함 |

## 3️⃣ `data/` — 창고

| 경로 | 역할 |
|---|---|
| `raw/` | 사이트에서 막 긁어온 원본 |
| `processed/chunks.jsonl` | **진실의 원천**. 46개 조각이 한 줄씩. |
| `vector/chroma/` | 의미 검색용 인덱스 (위 chunk를 숫자 벡터로 바꿔놓은 것) |
| `state/crawler_state.json` | "이 URL은 언제 마지막으로 받아왔다"는 기록 |
| `actions/` | 신청서 양식 스키마 |

## 4️⃣ `retriever/` — 창고지기

| 파일 | 담당 |
|---|---|
| `keyword_retriever.py` | 단어 매칭 검색 (튼튼함) |
| `vector_retriever.py` | 의미 매칭 검색 (Chroma 사용) |
| `hybrid_retriever.py` | **둘을 합쳐서 점수 매겨 top-N 꺼냄**. `app.py`가 이놈을 호출. |

## 5️⃣ `agent/` — 두뇌

| 파일 | 담당 |
|---|---|
| `guard.py` | 🛡️ 학번/주민번호/PW 같은 거 들어오면 차단 |
| `classifier.py` | 🏷️ 질문 유형 분류 (attendance / leave_return / certificate ...) |
| `planner.py` | 📋 이 질문에는 다음 행동으로 뭘 추천할지 결정 |
| `citation.py` | 📚 chunk마다 `[S1]`, `[S2]` 번호 붙이기 |
| `answer_builder.py` | 🧱 **답을 조립하는 곳. LLM이 빠진 자리에서 템플릿으로 글 쓰는 그 파일.** |
| `action_state.py` | 신청서 작성 폼의 단계별 상태 관리 |

## 6️⃣ `tools/` — 두뇌가 쓰는 도구

| 파일 | 담당 |
|---|---|
| `checklist.py` | 해야 할 일 체크리스트 생성 |
| `contact_router.py` | 어디로 문의해야 할지 추천 |
| `deadline.py` | 날짜·기한 계산기 ("5월 15일 결석이면 언제까지 신청?") |
| `graduation.py` | 졸업요건 간이 진단 |
| `course_planner.py` | 수강계획 추천 |
| `document_drafter.py` | 출석인정신청서 초안 같은 문서 작성 |

## 7️⃣ `test/` — 졸업 도우미 실험실

메인 FastAPI/React 서비스와 별도로 실행되는 Streamlit 프로토타입. 성적증명서와 2025 국민대학교 요람을 이용해 졸업/진로 관련 기능을 실험한다.

| 파일/경로 | 담당 |
|---|---|
| `0_extract_structured_data.py` | 요람 별표5/별표6에서 학과별 졸업요건, 공학인증 요건, 이수구분 코드 JSON 추출 |
| `1_build_index.py` | 2025 국민대학교 요람 PDF를 chunk로 나누고 ChromaDB에 인덱싱 |
| `2_agents.py` | 졸업 진단, 대체 이수, 마이크로디그리, 졸업 후 체크리스트, 직무 역량 번역 로직 |
| `3_app.py` | Streamlit UI 진입점 |
| `graduation_requirements.json` | 학과별 졸업 최저이수학점 구조화 데이터 |
| `engineering_cert_requirements.json` | 공학인증 심화프로그램 학점 구조화 데이터 |
| `department_search_index.json` | 학과명 검색 인덱스 |
| `chroma_db/` | 요람 RAG 검색용 ChromaDB |

주의: 이 폴더는 성적증명서 기반 프로토타입이라 메인 서비스의 “성적표 원본/개인 성적 미수집” 정책과 다르다. 메인 서비스에 붙일 때는 비식별 학점 요약 입력 방식으로 조정해야 한다.

---

## 🚪 `app.py` — 모든 게 만나는 입구

웹 서버(FastAPI). 사용자가 보내는 5가지 요청을 받음.

| 엔드포인트 | 하는 일 |
|---|---|
| `POST /ask` | 질문 받음 → 가드 → 분류 → 검색 → 답변 조립 → 응답 |
| `POST /actions/start` | 신청서 작성 시작 (어떤 빈칸 채워야 하는지 알려줌) |
| `POST /actions/continue` | 채워진 빈칸 받아서 문서 초안 생성 |
| `POST /ingest/run` | 수집부터 인덱싱까지 전체 파이프라인 실행 |
| `GET /health`, `/sources` | 상태 확인용 |

---

## 🪑 `llm_client.py` — 비어있는 LLM 자리

지금은 일부러 빈 문자열만 돌려준다 (`return ""`). 답변은 `agent/answer_builder.py`가 템플릿 + 검색된 chunk로 조립한다. 환각 0%, 데모 안정성, citation 정확도가 목적.

진짜 LLM(Claude API, Ollama, OpenAI 등)을 이 자리에 끼우는 게 다음 단계.

## 실행 흐름 요약

1. 터미널 1: 백엔드
   ```bash
   conda activate kmu-campus-life
   uvicorn app:app --reload
   ```
2. 터미널 2: 프론트엔드
   ```bash
   cd frontend && npm run dev
   ```
3. 브라우저: `http://127.0.0.1:5173`
