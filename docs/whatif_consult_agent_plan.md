# 작업계획: 졸업 시나리오 상담 Agent (What-if) — rev.4

> 상태: 검증 루프 라운드3 완료 — 서브에이전트 "HIGH 없음" 판정 + codex 미세 MUST 2건(add_convergence 빈 후보 schema 타입 / KIND.branch)·서브 MEDIUM 1건(localStorage trace) 반영. **계획 수렴 — 구현 착수.**
> 작성: 2026-06-04 (발표 D-5) · 담당: 모델 파트

## 0. 한 줄 정의

졸업사정 보고서를 받은 학생이 자연어 후속 질문("다음 학기 휴학하면?", "부전공 빼면?")을 하면, **LLM이 질문을 안전한 시뮬레이션 파라미터로 변환**(매개변수 추출기)하고 **기존 결정론 파이프라인(`run_audit`)을 그 조건으로 재실행**, before/after 차이와 다음 행동을 카드로 제시. 예제06(매개변수 추출기→IF/ELSE→도구→집계)과 동형의 Tool Calling 패턴. LLM은 판정하지 않는다.

**비범위:** ReAct(B안)·멀티턴 없음. 기존 파이프라인 변경은 `run_audit` keyword-only `skip_explain` 1건. **3-way 배정(sel) 서버 반영은 범위 밖**(기존 갭) — UI 캐비엣 + 데모에서 sel 편집 회피.

## 1. 워크플로우 노드

```
질문 입력
→ ① 매개변수 추출기 (LLM 1회: category+delta+interpretable; trace는 질문 분류/매개변수 추출 2논리노드)
→ ② 조건 가드 (IF/ELSE·validator)
     ├─ 지원 범위 밖 → [안내 종료] (side 분기, reason을 branch pill에)
     └─ OK → ③ 졸업사정 재실행 (Tool: run_audit ×2 — 그래프에는 단일 압축 노드)
              → ④ 시나리오 비교 (Tool, 결정론 diff) → ⑤ 다음 행동 제안 (Tool, 룰 테이블)
```

- **[R1] `after.node_trace`는 그래프에 절대 합성하지 않는다**(byNode last-wins 덮어쓰기 → 본 보고서 노드가 what-if 값으로 표시되는 데모 차단급 모순). 재실행은 `node="졸업사정 재실행"` 단일 이벤트. **[R2] `after` 객체 안의 node_trace는 API 응답에 남지만 프론트가 그래프에 흘리지 않는 것이 계약** — §5.1에 명시, §6-7 테스트로 고정.

## 2. 스키마 (`models_v2.py` +~80줄)

Pydantic 모델은 rev.2와 동일(`WhatIfCategory`, `ConvChange`, `WhatIfDelta(calendar_delay_terms ge=0 le=4 / remaining_semesters_change ±4 / seasonal_semester_allowed / max_credits_per_term gt=0 le=24 / prev_term_gpa_ge_375 / add_convergence / drop_convergence)`, `WhatIfDiff(+already_met_after, convergence_changes)`, `WhatIfResponse`).

**[R1·R2] LLM용 strict json_schema는 수동 작성** (explain.py `_schema` 패턴):

- 모든 필드 `required` + Optional은 `{"type": ["integer","null"]}` union, 전 객체 `additionalProperties:false`.
- **빈 enum 절대 생성 금지** (OpenAI strict는 빈 enum invalid — R2 codex MUST):
  - `drop_convergence`: 후보(ctx에 선언된 융합 id) 있으면 `items:{"type":"string","enum":[...]}`, **없으면 `{"type":"array","maxItems":0,"items":{"type":"string"}}`** (enum 자체 미생성).
  - `add_convergence`: 후보(= programs.json 비-primary 중 ctx에 없고 **카탈로그 load 가능한** 것 — R2 M3) 있으면 `items` = ConvChange 객체 schema(`program_id` enum + `track` enum, 둘 다 required). **[R3] 후보 없으면 `{"type":"array","maxItems":0,"items":{<ConvChange 객체 shape, enum 없음>}}`** — items를 string으로 복사하면 안 됨(Pydantic `list[ConvChange]`와 타입 불일치). 빈 배열 `[]`은 `list[ConvChange]` 검증을 통과하므로 null 강제 불필요(null이면 오히려 Pydantic 깨짐).
- `track`: enum ["다전공","부전공"] required (default는 schema에 없음 — LLM이 명시, 프롬프트 규칙 "언급 없으면 다전공").

**질문→delta few-shot (rev.2와 동일):** 휴학→`calendar_delay_terms` / "한 학기 더·줄이면"→`remaining_semesters_change` / 계절→`seasonal_semester_allowed` / "15학점씩"→`max_credits_per_term` / "부전공 빼면"→`drop_convergence` / "3.75 넘기면"→`prev_term_gpa_ge_375` / 조기졸업·전과·절대시점("이번 학기 안에")→`interpretable=false`.

## 3. 백엔드 — `graduation_center/v2/whatif.py` (신규 ~320줄)

### 3.1 ① 매개변수 추출기 (LLM)
`interpret_question(question, ctx, programs, client)` — `explain._call_llm` 형태(responses API, strict, temp 0.1 폴백, reasoning minimal). 입력: 질문 + 컨텍스트 요약(학번·과목 비포함). **[R2] 프롬프트 규칙 추가: "현재 값과 동일한 변경(예: 이미 계절 허용인데 '계절 들으면')은 delta를 채우되, no-op 판정은 시스템이 한다"** — LLM이 컨텍스트 따라 출력을 바꾸지 않게 해 캐시 일관성 유지.

### 3.2 ② 조건 가드 (validator, 결정론)

`apply_delta(ctx, delta, profile) -> (new_ctx | None, applied_changes, reason | None)`:

1. `interpretable=false`/`delta.is_empty()` → unsupported.
2. **휴학(delay≥1):** `current_term` None → unsupported. `delay=0` no-op(`_nth_regular_term(n=0)=None` 회피).
   **[R2-H1 구현 방식 명확화]:** 헬퍼를 직접 호출하지 않는다 — `ret = _nth_regular_term(ctx.current_term, delay+1)`(복학 정규학기)을 구한 뒤, **`new_ctx.current_term`을 ret 직전 계절 슬롯**(`ret="Y-1"`→`"(Y-1)-W"`, `ret="Y-2"`→`"Y-S"`)으로 set한 **StudentContext 전체를 `run_audit`에 흘린다**. `_ordered_terms`/플래너/overflow는 모두 ctx에서 current_term을 읽으므로 일관 적용(R2 양 리뷰어 수치 검증: 2026-1·2026-2·2026-S·2026-W × delay 1~3 전부 ret부터 정확 생성, 휴학 중 계절학기 미포함, projected 동일 기준). `ret=None`(비정상 current) → unsupported.
   **전제 고정:** `_valid_term` 정규식이 `S/W` 라벨을 통과시킴(models_v2.py:43) — §6 테스트로 단언.
   `prev_term_gpa_ge_375=False` 리셋 + assumption "복학 첫 학기 신청학점 보너스 미적용 가정".
3. `remaining_semesters_change` → `max(0, ...)`.
4. `max_credits_per_term` > `regular_term_cap(profile.total_credits_min)` → **unsupported("학사규정 제32조 상한 {legal}학점 초과 설정 불가")** (규정 인용 가드).
5. `add_convergence`(존재·비-primary·비중복·카탈로그 load 가능) / `drop_convergence`(ctx 실재 id만, **tracks 동반 제거**). 위반 → unsupported.
6. **재검증: `StudentContext.model_validate({**ctx.model_dump(), **updates})`** (`model_copy`는 validator 미실행 — R1 실측).
7. `applied_changes` 사람용 문자열 반환.

### 3.3 ③ 졸업사정 재실행 (tool)

- `run_audit(payload, skip_explain=True)` ×2 (before 원본 / after 변경 ctx).
- **`pipeline.run_audit(payload, client=None, *, skip_explain=False)`** — keyword-only. **[R2-H2 범위 정정]:** "변경 1건"이 아니라 ① 시그니처 + ② pipeline.py:75 `run_explain` 호출을 skip 분기로 감싸기 + ③ **explain.py에 module-level `skip_explain_trace()` 헬퍼 추출**(현 `_skip_trace`는 run_explain 내부 클로저라 재사용 불가 — R2 codex) + ④ 기존 테스트 회귀 확인. skip 시에도 placeholder 2노드는 `after.node_trace` 안에 방출(단독 렌더 시 그래프 고립 방지) — 단 §1 계약대로 프론트는 이를 그래프에 안 흘림.
- **[R2-M3] `run_audit(after)`의 ValueError/KeyError도 잡아 unsupported로 degrade**("해당 변경은 시뮬레이션 불가") — 데모 중 500 화면 금지.

### 3.4 ④ 시나리오 비교 (tool, 결정론)

`build_diff(before, after) -> WhatIfDiff`. 졸업 예상 학기 단일 헬퍼 `_graduation_term(resp)`:
- feasible+terms: **terms 중 정규학기(`-1`/`-2`)만 추려 마지막 라벨**. **[R2 codex SHOULD] 정규학기가 0개(전부 계절)면 `(None, False)` + 표시 "계절학기 수강만 산출 — 졸업 사정 시점 학과 확인"** (IndexError 방지).
- feasible+terms 빈 → `(None, already_met=True)`.
- blocked+overflow → `projected_graduation_term`. 그 외 None("산출 불가").

`convergence_changes`: convergence_checks before/after 짝지어 추가/제거/gap 변화 + `to_fusion_total` 영향 한 줄.

headline 우선순위: **[R2-L1] 휴학(delay≥1)은 already_met이어도 "졸업요건 충족 유지 — 휴학으로 졸업 시점 N학기 지연" 우선** > 졸업시점 변화 > already_met > 리스크 등급 > 융합 변화 > 갭 변화 > "유의미한 변화 없음".

### 3.5 ⑤ 다음 행동 제안 — rev.2와 동일(룰 8종+already_met, 최대 3개).

### 3.6 trace 조립 — rev.2와 동일(질문 분류/매개변수 추출/조건 가드/[안내 종료]/졸업사정 재실행/시나리오 비교/다음 행동 제안 — audit 노드명 미사용). **[R3] kind는 기존 4종(tool/llm/hitl/validator)만 사용 — `"branch"` 금지**(프론트 `KIND` 맵에 branch 키가 없어 `KIND[n.kind].color` 런타임 에러). 방어로 프론트 `KIND`에 branch 폴백 1줄 추가.

### 3.7 캐시·폴백 — `data/graduation/v2/whatif_cache.json`

- **[R2-M1 선행 작업] `.gitignore`에 `data/graduation/v2/whatif_cache.json` 추가**(현재 explain_cache.json만 등록 — 워밍업이 더러운 diff 생성). `.tmp`는 `os.replace`로 즉시 소멸하나 `data/graduation/v2/*.tmp`도 함께 등록.
- 키: `sha256(model + normalize(question) + program_id + admission_year + sorted(convergence_ids) + sorted(tracks) + sorted(비-primary 모집단 id) + seasonal + remaining + max_credits)[:24]` — **[R2-M4] add enum 모집단 변화·[R2 NICE] 컨텍스트 요약 입력값 변화에 의한 schema-캐시 드리프트 차단.**
- 값: LLM raw 출력만. LLM 미설정+미스 → unsupported("예시 질문 버튼 이용"). 워밍업: 데모 학생 4명 × 칩 3개.

## 4. API — `app.py` (+~40줄)

`POST /graduation/v2/whatif` = /audit payload + `question`(1~200자). LLM 예외 **및 after 재실행 예외** → 500 아닌 unsupported. question 누락/초과 → 400.

## 5. 프론트

### 5.1 `GraduationV2.jsx` (+~170줄)

- **payload 동결:** audit 성공 시점 payload를 `auditPayload`로 저장, whatif 요청·**칩 조건 계산 모두 `auditPayload.context` 기준**(live ctx 금지 — R2 codex: 칩 라벨과 실제 payload 불일치 방지).
- **[R2-M5] dirty 가드:** audit 후 검증 테이블이 편집되면(JSON 비교) whatif 입력 비활성 + "편집 내용 미반영 — 졸업사정을 다시 실행하세요" 배지.
- 컨텍스트 인지형 칩(동결 ctx 기준): 휴학(현재학기 있을 때) / 계절(이미 true면 "계절학기 못 듣게 되면?") / 융합 빼면(선언 학생만) / "15학점씩만 들으면?".
- 결과 카드: unsupported(회색 reason) / ok(리스크 배지 전환, 졸업학기 before→after·already_met 문구, 갭 변화, changed_areas·convergence_changes 칩, headline, 다음 행동, 접기식 after 로드맵 — **[R2-L2] 캡션 "휴학 N학기 반영, 복학 후 {첫 학기}부터 배치" + 학기 라벨 S/W 표기 변환("2027-S"→"2027 하계")**).
- 캐비엣: "시뮬레이션은 서버 기본 겹침 배정 기준".
- **그래프 합성 계약: `[...verify, ...audit, ...whatif.node_trace]` — `whatif.after.node_trace`는 절대 미포함**(§1). **[R3] 이 합성은 인라인 그래프(line 782)와 `v2_workflow_trace` localStorage write(line 338, `#workflow` 전용 페이지 WorkflowPage의 데이터 출처) 양쪽에 적용** — 한쪽만 갱신하면 전용 페이지에서 상담 노드가 안 보이는 모순(R3 서브 MEDIUM).

### 5.2 `WorkflowGraph.jsx` — **[R2-H3 규모 정정: 레이아웃 동적화 리팩터 ~120줄, 별도 커밋]**

- 정적 `NODES` 전역 상수를 **컴포넌트 내부 `visibleNodes = useMemo(() => BASE.concat(hasConsult ? CONSULT : []), [trace])`** 로 전환. `KNOWN/idxOf/nodeY/mains/height/W`를 전부 visibleNodes 기준 재계산(현재 전역·정적이라 단순 필터 불가 — R2 양 리뷰어 합치).
- 사이드 노드 탐색(97행 `NODES.find`)을 **branchFrom 키별 매핑**으로 일반화(기존 "초과학기 시나리오" + 신규 "안내 종료" 2개 공존).
- `리포트` push(40-44행): audit trace 마지막 직후 삽입, 상담 keys는 그 뒤에 연결.
- 상담 클러스터 표시 조건 = **trace에 상담 이벤트 존재 여부만**(compact 여부 무관 — R2-M2: compact에서 숨기면 "상담 워크플로우 보여달라" 장면에서 안 보이는 모순). audit-only 화면은 기존 12노드 그대로(회귀 스냅샷 확인).

### 6. 테스트 — `tests/test_v2_whatif.py` (~250줄)

rev.2의 9종 + R2 추가:
10. `_valid_term`이 `"2026-W"/"2027-S"`를 통과(전제 고정).
11. all-seasonal feasible terms → `_graduation_term` IndexError 없이 안내 문구.
12. `run_audit(after)` 내부 KeyError(깨진 program_id 주입) → unsupported, 500 없음.
13. 휴학+already_met → headline에 "지연" 포함(L1).
14. WorkflowGraph: audit-only trace 렌더 시 상담 노드 미표시 + whatif trace 포함 시 표시(프론트는 수동 확인 + 가능하면 trace 합성 유틸 단위 테스트).

## 7. 발견 처리 대장

**라운드1 (18건):** rev.2에 전건 반영 — 그래프 덮어쓰기 / model_copy 무검증 / 휴학+계절 / delay=0 / 절대시점 매핑 삭제 / 상한 초과 unsupported / strict 수동 schema / 리포트 push / convergence diff / 칩-기본값 / 캐시 키 융합 포함 / sel 캐비엣 / 졸업학기 헬퍼 / tracks 제거 / payload 동결 / 3.75 리셋 / 조건부 렌더 / 성적우수 칩 제외.

**라운드2 (codex MUST 1·SHOULD 4·NICE 1 + 서브 HIGH 3·MED 5·LOW 2):**

| # | 발견 | 처리 |
|---|---|---|
| H1 | 휴학 서술이 헬퍼 직접 호출로 오독 가능(시그니처 불일치) | §3.2-2 — ctx 전체 주입으로 명시 + 정규식 전제 테스트 |
| H2 | skip_explain "변경 1건" 과소평가 | §3.3 — 4단계 범위 + module-level 헬퍼 추출 |
| H3 | WorkflowGraph 정적 NODES 리팩터 규모 | §5.2 — 동적화 ~120줄·별도 커밋·회귀 확인 |
| MUST | 빈 enum strict invalid (add 쪽 포함) | §2 — maxItems:0 형태 명문화 |
| M1 | whatif_cache .gitignore 누락 | §3.7 선행 작업 |
| M2 | compact 숨김 시 상담 안 보이는 모순 | §5.2 — 표시 조건을 trace 존재로만 |
| M3 | run_audit(after) 예외 미degrade | §3.3·§4 |
| M4 | add enum 모집단 캐시 드리프트 | §3.7 키 확장 |
| M5 | 편집 후 질문 직관 위반 | §5.1 dirty 가드 |
| L1 | 휴학+already_met headline 소실 | §3.4 우선순위 |
| L2 | 로드맵 라벨 점프·S/W 미변환 | §5.1 캡션+라벨 변환 |
| S1 | all-seasonal 졸업학기 IndexError | §3.4 |
| S2 | 칩을 live ctx로 계산 | §5.1 동결 기준 |
| S3 | visibleNodes 재계산 범위 | §5.2 |
| S4 | _skip_trace 재사용 불가 | §3.3 헬퍼 추출 |
| N1 | 캐시 키 입력값 확장 | §3.7 |

**라운드3 (서브 HIGH 0 + codex MUST 2 + 서브 MED 1):** add_convergence 빈 후보 = ConvChange shape·enum 없음·maxItems:0(§2) / trace kind에 branch 금지 + 프론트 KIND 폴백(§3.6) / localStorage 합성 양쪽 갱신(§5.1) — 전건 반영, 직접 코드 대조로 검증 완료.

**코드 검증 라운드1 (적대 3 + codex · 발견 23 · 수정 17 · 거짓양성 2 기각):** 커밋 bffb211 — 휴학+blocked headline / 캐시 포이즈닝(검증 전 저장) / 한도 메시지 / localStorage stale closure(useEffect 일원화) / remaining 클램프 / seasonal after 기준 / 다음행동 상호배타 / 상한 0.5·:g 표기 / 휴학+3.75 가정 명시 / extra=forbid / 캐시 키 과민 / 칩 4개 / 예상졸업 숨김 / whatif 인라인 에러 / 버튼 전역 잠금. 기각: storage 이벤트(cross-tab엔 발화 — 사양 확인), 졸업학기 계절 라벨(수여 시점 기준 현행 정확 — 코드 주석화).

**코드 검증 라운드2 (적대 3 + codex · HIGH 3 전건 수정):**
- 캐시 evict+재해석 폴백(ValidationError 시 영구 고착 차단) + 캐시 키 schema 버전(v=2) + 오염 로컬 캐시 삭제.
- 휴학 headline 비대칭(gt_b만 존재) 분기 — "산출되지 않았습니다" 명시.
- **데모 통합(§신규)**: demo_script에 S4 상담 비트(0:45)·아키텍처 멘트 "LLM 파란 노드 둘(RAG 해설=근거 생성 / 추출기=Tool Calling)"·fallback 행·Q&A 2-1(왜 LLM 덜 썼나+HyDE 회피)·기여 매핑 추가. `scripts/warm_whatif_cache.py`(환각 검수 포함) 신설 — §3.7 워밍업 약속 이행.
- MEDIUM: LLM 환각 drop(e2e 실증) → 프롬프트 negative 규칙 + 워밍업 검수 / verify-only 리포트 거짓 점등 게이트 / category 결정론 재도출(분기 pill 정직성) / track 변경 메시지 분리.
- 수용한 한계(프로토타입): add 후보의 학과별 자격 필터 없음(요람 데이터 필요 — 다음행동 캐비엣으로 안내), 등록금·리스크 게이트는 라운드1 결정 유지, /health llm.enabled는 티어1 레거시(범위 밖).

**코드 검증 라운드3 (적대 3: 수정부작용·데모리허설e2e·fresh-eyes + codex):**
- [MUST·리허설 HIGH-1 실증] **환각 semantic guard** — 프롬프트 규칙만으로 부족(워밍업 16건 중 6건 환각 재발 실측). `_semantic_guard`: 질문에 전공·융합·연계 미언급 시 add/drop_convergence 결정론 제거 + assumptions 명시 + `CACHE_SCHEMA_VERSION=3`(구 오염 캐시 전체 미스). 리허설 에이전트가 재기동+재워밍업으로 **환각 0건(exit 0) 라이브 검증**.
- [MUST] 워밍업 스크립트 python 3.8 즉사 → 버전 가드 + kmu-agent 경로 명시(demo_script 동기화). [SHOULD] cwd 무관 CACHE_PATH 고정. 환각 의심 키 자동 evict.
- [R3-① MED] headline (None→산출) 역방향 분기 보강 — 4조합 전수 커버. [R3-③ MED] "변경 후에도"→"에는" 문구, `g` 섀도잉 제거.
- [리허설 HIGH-2] stale 서버(미재기동) 운영 함정 → demo_script fallback에 "수정 후 무조건 재기동" 행 추가. [MED-1] S1 멘트 수치 21/9 → 실측 27/15(융합 부족 9는 일치).
- 기각(거짓양성): 재수강 팝업 과목명(테이블 행에 표시됨 — possible_retakes payload는 화면 비노출 경로).
- 판정: 서브① "HIGH 없음·수렴", 서브③ "HIGH 없음", 리허설 HIGH 2건은 본 커밋(가드)+체크리스트로 해소 — **라운드4 확인 패스로 수렴 판정**.

## 8. 검증 프로토콜

- 계획: codex + 서브에이전트 교차, critical 0까지 (라운드1~3 완료, 수렴).
- 구현 후: **적대적 서브에이전트 3개 병렬/라운드** + codex 교차, `[HIGH]/[MEDIUM] + file:line + 재현`, HIGH 0까지.
- 커밋 분리: ① .gitignore+스키마+whatif.py ② skip_explain+라우트+테스트 ③ WorkflowGraph 동적화(단독) ④ GraduationV2 상담 UI ⑤ 캐시 워밍업+문서.
