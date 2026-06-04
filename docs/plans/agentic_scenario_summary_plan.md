# 작업계획: 에이전트 총평 — 능동 시나리오 탐색 (bounded ReAct, 단일 턴) — rev.3

> 배경: 3자 자문 만장일치(옵션1 수동 총평 = "나레이터" → LLM에게 "이 학생의 갈림길" 판단·도구
> 선택 결정권 부여). 교수 피드백 "ReAct를 풀어야 함" 정면 대응.
> rev.2 = 라운드1(codex MUST 4 + 적대 HIGH 4·MED 4·LOW 2) 반영 — 독립 게이트 `run_summary`.
> **rev.3 = 라운드3 반영**: 적대 "HIGH 없음 — 수렴"(MEDIUM 3 반영) + **교수 페르소나 "조건부
> 불합격" 처방**(탐색 과정 가시화·delta 값 선택권·다양성 검수·충족 학생 분기 폐기) — 가드가
> LLM의 결정권을 죽이지 않도록(검증 패널 렌즈 균형, 사용자 지적).

## 0. 한 줄 정의 (불변)

보고서 생성 시 LLM이 결정론 facts를 보고 **what-if 후보 ≤5개를 스스로 제안·선정**(Thought —
reason과 delta 파라미터 값까지) → pre 필터 통과분 **결정론 재실행 ≤4회**(Action: 기존
`apply_delta→run_audit→build_diff`) → diff 관찰·post 판정(Observation, 탈락도 사유와 함께
화면 기록) → **채택 ≤3 비교 조언 총평**(Answer, 문장별 fact id·validator·캐시). LLM은 값을
만들지 않는다 — "무엇을 알아볼지"만 고른다. 단일 턴·캐시 고정·validator 통과분만.

## 1. 게이트 — **독립 플래그 `run_summary: bool = False`** [라운드1 H1+H2+codex SHOULD]

- `pipeline.run_audit(payload, client=None, *, skip_explain=False, run_summary=False)`.
- **`run_summary=True` 허용 경로는 정확히 2곳**: ① 라우트 `/graduation/v2/audit`
  (`app.py`에서 `run_audit(payload, run_summary=True)` 명시) ② **워밍업 스크립트의 opt-in 호출**
  (캐시 적재용 — 라운드2 충돌 해소). 그 외(기존 테스트의
  `run_audit(payload)` 직접 호출·whatif 상담·총평 내부 시뮬레이션은 기본 False → **기존 경로
  완전 무영향**(skip_explain 피기백이었으면 키 보유 개발자의 평범한 pytest가 실LLM 2콜 — 적대 H1).
- 재귀 차단: 시뮬레이션은 `run_audit(skip_explain=True)`(run_summary 기본 False) — 구조적으로 불가.
- **conftest autouse 격리 확장**: `_isolate_explain`에 `report_summary._get_client→None`·
  `report_summary.CACHE_PATH→tmp` 추가(테스트 라이브 LLM 원천 차단) — 구현 1단계로 선행.

## 2. 노드 4개 (BASE_NODES '해설 검증'과 '리포트' 사이 — 배열 위치 그대로 삽입)

```
갈림길 선정 🤖LLM   : facts → {candidates:[{delta, reason_code, rationale}]≤5} + pre 필터  ← Thought
갈림길 시뮬레이션 tool: before 1회 + pre 통과 후보 after ≤4회 재실행 → diff·post 판정·탈락 기록 ← Action+Observation
총평 생성 🤖LLM     : 비교표(구조화 필드만)+facts → {headline, lines[…fact_ids], recommendation}
총평 검증 validator : fact_ids 해소·수치 대조·판정 모순 금지 → 위반 줄 폐기
```

- 노드명은 BASE·CONSULT와 **어휘까지 분리**(상담 '시나리오 비교/졸업사정 재실행'과 혼동 금지 —
  적대 M3). disjoint 단언 테스트 추가. **생략·실패 시에도 4노드 skip placeholder trace 항상
  방출**(리포트 push 순서 안정·그래프 고립 방지 — codex SHOULD).
- 그래프-카드 모순 방지: trace는 점등되는데 카드가 없으면 모순(적대 M4) →
  **`summary_fallback: str | null`** 필드로 사유 안내("LLM 미설정"/"갈림길 없음 — 요건 충족" 등),
  프론트는 explain_fallback과 동일 패턴의 작은 안내 박스.

## 3. 백엔드 — `graduation_center/v2/report_summary.py` (신규)

### 3.1 import 구조 [codex MUST: 순환 차단]
- `report_summary`는 `whatif`(apply_delta·build_diff·delta schema)를 top-level import.
- **`pipeline.run_audit`는 함수 주입**: `run_report_summary(..., run_audit_fn)` — pipeline이
  run_audit 내부에서 lazy import + 자기 함수를 인자로 전달. (pipeline→report_summary→whatif→
  pipeline 순환을 함수 주입으로 절단.)
- `whatif._schema`에서 **`whatif_delta_schema(add_ids, drop_ids)` 헬퍼 분리**(codex MUST) —
  what-if 전체 schema와 시나리오 선정 schema가 공유.

### 3.2 facts (LLM 입력·캐시 키 원천)
- `_build_facts(...)` → `F1..` id. **canonical dump**: id 정렬·float `round(,1)`·
  `json.dumps(sort_keys=True, separators=(",",":"), allow_nan=False)` (codex SHOULD).
- 본 보고서 객체의 markdown·trace·explanations·agent_summary **미포함**(자기참조 오염 — 적대 H3).

### 3.3 갈림길 선정 (LLM ①) — rev.3: 탐색 과정 가시화 (교수 R3 처방)
- strict schema: **candidates ≤5**(채택 상한 3과 분리 — Thought의 폭이 보이게) of
  `{delta: whatif_delta_schema(...), reason_code: enum[graduate_faster, overflow_relief,
  conv_tradeoff, load_adjust, timeline_extend], rationale ≤80}`.
  **reason_code·rationale는 delta 밖**(build_diff에 delta만 전달 — 적대 H3).
- **delta 파라미터 값 선택권 명시**(교수 처방②): 프롬프트에 "같은 reason이라도 값(계절 3 vs 6학점·
  잔여 +1 vs +2·상한 15 vs 18)을 학생 상태에 맞게 골라라" — rationale에 값 선택 이유 포함.
- delta는 `WhatIfDelta.model_validate` 강제(범위 밖 → 해당 후보 reject).
- **탈락을 지우지 않고 기록**(교수 처방① — "필터가 답을 정해놓고 LLM이 받아 적는" 인상 차단):
  응답에 `candidates_review: [{label, reason_code, verdict: accepted|rejected, rejected_by:
  pre_mismatch|invalid_delta|no_op|post_no_change|null}]` → 카드 토글에 "검토 후 제외" 목록 표시,
  trace branch_taken = "후보 N → 채택 k·제외 m". **후보 공간→LLM 선택→필터 검증 과정이 화면에 남는다.**
- 비용 가드: pre 통과 후보 중 **시뮬레이션 ≤4회**, 최종 채택 ≤3.
- **결정론 관련성 필터 — reason_code 5종 전부 pre/post 조건 표준화**(라운드2 MUST):

  | reason_code | pre(현재 상태) | post(diff 결과) — 미충족 시 drop |
  |---|---|---|
  | `overflow_relief` | overflow 존재 | overflow 해소 or 졸업시점 단축 |
  | `conv_tradeoff` | 융합 선언 + 융합 갭>0 or 겹침>캡 | 융합/전공 갭·리스크 변화 |
  | `graduate_faster` | 미충족(총·영역 갭>0) | 졸업시점 단축 or feasible 전환 |
  | `load_adjust` | delta가 학점상한·계절·3.75 중 하나 | feasible·리스크 변화(— "배치 학기 수"는 WhatIfDiff에 없는 필드라 제외, 적대 R3) |
  | `timeline_extend` | delta가 휴학>0 or 잔여+N | 졸업시점 지연 표시 or blocked/overflow 완화 |

  **노드 귀속(적대 R3)**: pre 판정 = 선정 노드(시뮬 전), post 판정 = 시뮬 노드(diff 산출 후) —
  2단 실행, post는 WhatIfDiff 실재 필드만 사용. pre 위반·invalid_delta·no-op·post 위반 →
  **rejected 기록**(소거 아님 — candidates_review). reason_code별 accept/reject 테스트 각 1쌍.
- **충족 학생 결정론 분기 폐기**(rev.3 — 교수 R3 "LLM 호출 전 분기는 에이전트성 0"): 충족
  학생도 **항상 LLM 선정을 돌린다**. 채택 0(전부 post_no_change)이면 fallback이 아니라 **정상
  총평**: recommendation="유지 권장" + "N개 시나리오를 검토했지만 개선 없음 — 현 계획 유지가
  최적". 에이전트가 '바꿀 필요 없음'을 *검증해서* 말하는 장면 — 적대 M2의 "0개 골랐습니다"
  우려는 candidates_review 가시화로 해소(검토 내역이 화면에 있음). `summary_fallback`은
  LLM 미설정·validator 전량 폐기 시에만.

### 3.4 시뮬레이션 (결정론) [적대 H3 반영]
- **before = `run_audit_fn(payload, skip_explain=True)` 별도 1회 재계산** — 본 보고서 객체
  재사용 금지(agent_summary 포함·skip 비대칭). after = pre 통과 후보 ≤4회(§3.3과 통일 — R4).
  `_graduation_term` 동일 산식 전제 유지.
- 비용 명시(적대 H2·R4 통일): before 1 + after ≤4 = run_audit 최대 5회 = planner 최대 10회 —
  전부 결정론 수십 ms, 실측으로 검증 단계에서 확인.
- 비교표 = **diff의 구조화 필드만**(risk_before/after·total_gap·graduation_term·overflow —
  headline 텍스트 재사용 금지: 휴학 전제 문구 혼입 방지, 적대 L2) + `applied_changes`·
  `assumptions`·unsupported 사유를 `S*` fact로 포함(codex SHOULD).

### 3.5 총평 생성·검증 (LLM ② + validator)
- 출력 schema: `{headline≤80, lines≤5 of {text≤200, fact_ids≤4 enum[F*,S*]},
  recommendation: enum[유지 권장, 변경 검토, 학과 상담 권장]}`.
- validator(explain 확장): fact_ids 실재·수치(2자리+)∈참조 fact 수치 집합·등급/판정 모순 금지·
  학번 마스킹. 위반 줄 폐기, 전부 폐기 → `summary_fallback` + 섹션 생략.
- 캐시: 키 = `sha256(model + SCHEMA_VERSION + canonical facts)`, **검증 통과분만**, 실패 시
  evict+재시도 1회(whatif 패턴). **캐시 값 = 최종 총평 + 채택 시나리오 + `candidates_review`
  전체**(탈락 후보·사유 포함 — 데모에서 탐색 과정 표시까지 캐시 일관, R4). `summary_cache.json`
  — **절대경로 고정 + .gitignore**(codex NICE).
- 지연 정책 — **단일 상태표**(라운드2 MUST):

  | 상태 | 동작 |
  |---|---|
  | cache hit | 즉시 반환(0 LLM콜) |
  | cache miss + client 없음 | 즉시 fallback(섹션 생략 + summary_fallback="LLM 미설정") |
  | cache miss + client 있음 + run_summary=True | LLM 2콜 허용(선정+총평, 타임아웃 20s) → 검증 통과분 캐시 |
  | run_summary=False (그 외 전 경로) | 총평 로직 자체 미진입 |

### 3.6 응답·markdown
- `AuditPipelineResponse.agent_summary: AgentSummary | None = None` + `summary_fallback:
  str | None = None`(기본값 필수 — 기존 직접 생성 테스트 보호, codex SHOULD).
- `WhatIfResponse.after.agent_summary == None` 단언(상담 경로 미실행 증명).
- markdown "## 에이전트 총평"은 `_markdown` 본문이 아니라 **run_summary=True일 때만 별도
  append**(시뮬 경로 markdown 오염 방지 — 적대 L1).

## 4. 프론트

- 총평 카드: 판정 배지 아래, **기본 접힘 — headline + recommendation 칩만 노출**, 시나리오
  비교 미니표·문장(fact 배지)은 토글(적대 M1: 해설+총평+상담 3중 텍스트 과다 방지).
- 상담과의 중복 규칙(설계로 박음): 상담 질문의 delta가 총평 선정 시나리오와 동일하면 diff 카드
  상단에 "총평에서 다룬 갈림길입니다" 1줄 안내(프론트 비교 — delta JSON 동등성).
- WorkflowGraph: BASE_NODES '해설 검증'↔'리포트' 사이 4노드, **보고서+상담 동시 화면 렌더를
  검증 단계에서 실확인**(적대 M3).

## 5. 워밍업·데모 [적대 H4]

- `warm_whatif_cache.py` 확장: summary 워밍업 + 검수 출력 **"학생별 후보 조합·탈락 사유·
  recommendation 표 + 데모 4명 캐시 히트 여부"**. **다양성 지표**(교수 처방③): S1~S4의 채택
  reason_code 조합·추천이 전부 동일하면 경고("에이전트가 아니라 라우터") → 프롬프트 보강 후
  재워밍업. 충족 학생(S4류)은 "검토 후 유지 권장" 총평이 정상임을 확인.
- **demo_script 명문화**: 데이터(요건·카탈로그) 정정 시 `whatif_cache.json`+`summary_cache.json`
  **둘 다 삭제 후 재워밍업** — facts 해시 키는 audit 수치 변화에 전량 미스(의도된 민감성).
- 데모 동선: 총평 하이라이트는 **갈림길 명확한 S1**(conv_tradeoff)로, S4는 "충족 — 갈림길 없음"
  안내형이 정상임을 발표자가 인지.

## 6. 테스트 (`tests/test_v2_summary.py` + conftest 확장)

1. conftest 격리(LLM None·캐시 tmp) 선행 2. **run_summary 게이트: 기존 run_audit(payload)
   호출이 총평 미실행(LLM 0콜 — fake client 카운트)** 3. facts canonical 결정론
4. 선정 schema·delta 분리·관련성 필터(reason_code별 accept/reject 쌍 + rejected 기록 보존)
5. 충족 학생 → 채택 0 시 "검토 후 유지 권장" 정상 총평(fallback 아님)
6. before 별도 재계산(본 보고서 객체 비참조) 7. validator 3모드
   (위조 수치·없는 fact·판정 모순) + 전량 폐기 degrade 8. 캐시 결정론·미캐시 evict 재시도
9. 노드명 disjoint(BASE∪CONSULT) 10. WhatIfResponse.after.agent_summary None
11. 데모 4명 기존 수치 불변. (whatif 36종·기존 전체 회귀 포함 실행)

## 7. 문서 동기화 [codex NICE — "문서가 크게 말한다" 재발 방지]

- "LLM은 파란 노드 둘뿐" 멘트 전면 갱신(demo_script 아키텍처 비트·Q&A 2·current_state §2
  bullet·v2 status note): **"LLM 4노드 — 해설·추출기·갈림길 선정·총평, 전부 판정 금지"**.
- current_state §1 표에 총평 행, §2 mermaid에 4노드, demo_script에 총평 시연 비트(S1) 추가.
- CLAUDE.md ReAct 절: "1-step bounded" 서술을 "보고서 총평 = Thought→Action→Observation→Answer
  단일 턴 구현"으로 갱신 — 과장 금지 톤 유지.

## 8. 일정 (라운드1 지적 반영해 보정)

백엔드를 쪼갬(적대 R3 — 검증 착수를 당김): **1일차 핵심**(conftest·게이트·facts·선정+필터·시뮬·
candidates_review) → **0.5일** validator·캐시·fallback → 프론트 0.5일 → 워밍업·문서 0.5일 →
검증 1일(**적대 + 교수 페르소나 동라운드** + codex + 실행 라운드로만 수렴 선언, 06-06 착수 목표).
코드 검증 라운드에도 교수 렌즈 포함 — 가드 추가로 에이전트성이 다시 죽지 않는지 매 라운드 판정.
