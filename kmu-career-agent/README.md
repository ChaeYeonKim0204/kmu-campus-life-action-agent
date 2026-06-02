# KMU Career Agent — Human-in-the-Loop 학업·커리어 매니지먼트 에이전트

국민대 AI빅데이터융합경영학과 학우 맞춤형 **행동형(action) 에이전트**. 학사 공지(비정형)와
학생 개인 데이터(정형: 졸업요건·프로젝트 이력·희망직무·캘린더)를 **다층 융합(Data Fusion)**해,
적합한 공모전/활동을 찾아 **소요시간을 개인 역량으로 보정**하고, **일정 타당성(30% 버퍼)**을
검증한 뒤, 사용자의 **명시적 승인(Human-in-the-Loop)** 하에 캘린더 가등록·서류 초안을 자율 실행한다.

> 메인 프로젝트(`graduation_center`, RAG 기반 졸업사정)와 **대비되는 워크플로우 archetype**
> (능동·행동형 + HITL)으로, "두 번째 주제" 자리에 해당. **현재 = 뼈대(scaffold)**.

## 상태: 뼈대 (walking skeleton)
파이프라인 흐름은 끝까지 동작하지만 핵심 로직은 placeholder/모의다. 각 모듈의
`# TODO(vibe-coding ...)` 와 스펙 프롬프트를 채우면 실동작으로 완성된다.

| 모듈 | 역할 | 채울 핵심 로직 |
|---|---|---|
| `modules/scraper.py` | 공지 수집 | requests+BeautifulSoup, UA 헤더, 1.5~3.0s 지연, 인메모리 파기 |
| `modules/document_ai.py` | PDF 평가기준 파싱 | io.BytesIO + pdfplumber 표 추출 |
| `modules/analyzer.py` | 맥락 분석 | OpenAI 구조화 출력(Pydantic) + 역량 가중치 0.7/1.5 |
| `modules/validator.py` | 일정 검증 | Google Calendar Free/Busy + 30% 버퍼 |
| `modules/executor.py` | HITL 액션 | Telegram 승인 → Calendar/Notion 액션 |
| `main.py` | 오케스트레이션 | 노드 순차 배선(완료) |

## 실행
```bash
cd kmu-career-agent
pip install -r requirements.txt        # (뼈대 실행만이면 requests/pydantic/python-dotenv 정도면 됨)
python main.py
```
API 키가 하나도 없어도 **끝까지 동작**한다(각 노드가 모의/콘솔로 폴백). 키는 `.env.example`을
`.env`로 복사해 채운다.

## 데모 스토리라인 (발표용)
- **안전한 자율성**: AI가 독단으로 일정을 망치지 않도록 — `validator.py`의 **30% 버퍼**와
  `executor.py`의 **텔레그램 승인(Human-in-the-Loop)** 으로 대응.
- **시각적 로그**: 실행 시 터미널에 노드별 단계가 점등된다 — "RAM에서 HTML 즉시 파기 완료",
  "개인 역량 가중치 0.7배 적용 완료", "30% 스케줄 안전 버퍼 계산 완료" 등.
- 실행 후 `trace.json`에 워크플로우 트레이스가 저장돼, (향후) 노드 그래프 시각화 프론트가 소비 가능.

## LLM 공급자 주의
스펙 헤더는 "Gemini 3.5 Flash"지만 구현 프롬프트(requirements·analyzer)는 OpenAI 기반이다.
팀 OpenAI 키를 쓰므로 **OpenAI로 구현**(`OPENAI_MODEL`로 모델 교체 가능). Gemini로 바꾸려면
`analyzer.py`의 LLM 호출부만 교체하면 된다.
