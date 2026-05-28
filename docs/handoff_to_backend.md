# 백엔드 팀 인계 메모 — `agent_product_planning.md` 잔여 운영형 항목

> 작성: 김채연 (모델 담당), 2026-05-28
> 대상: 백엔드 담당자
> 발표: 2026-06-09 (12일 남음)

## 0. 한 줄 요약

모델 팀이 `agent_product_planning.md` 기준으로 **모델 영역 내 운영형 강화는 거의 완료**했어요 (Phase 5 + Codex follow-up + answer_validator 패턴 통일까지). 다만 명세상 운영형으로 끌어올리려면 **백엔드 영역 작업이 8개 정도 남았어요.** 발표 전 처리 추천 2개·발표 후로 미뤄도 무방 6개로 정리했습니다.

---

## 1. 모델 팀과 백엔드 팀 경계

```text
┌─────────────────────── 모델 팀이 담당한 영역 ───────────────────────┐
│ llm_client.py            ← GPT 보조 3노드 (expand/rerank/polish)    │
│ graduation_center/*      ← 졸업센터 RAG·분석·sanitize               │
│ tools/graduation.py      ← 졸업 진단 (P4 예외)                      │
│ tools/course_planner.py  ← 수강계획 (P4 예외)                       │
│ tools/document_drafter   ← graduation_audit 부분만 (P4 예외 2줄)    │
│ agent/answer_validator   ← 졸업센터와 패턴 통일 (b 예외)           │
│ tests/test_*             ← 회귀 134 + 8 live PASS                   │
│ pytest.ini / conftest    ← live_llm mark + 격리                     │
│ scripts/build_graduation_index.py ← NFC/NFD 안전화                  │
│ docs/demo_queries.md / llm_cost_budget.md / work_log_*.md            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────── 백엔드 팀이 손대야 할 영역 ────────────────────┐
│ agent/classifier.py     ← top_issues / 복합 의도                    │
│ agent/planner.py        ← action allowlist · 우선순위               │
│ agent/answer_builder.py ← live_check 본문 반영 · provenance       │
│ agent/guard.py          ← (현재 OK, 손댈 필요 없을 수도)            │
│ tools/checklist.py      ← provenance 구조                           │
│ tools/contact_router.py ← provenance 구조                           │
│ tools/deadline.py       ← 상대 날짜·공휴일 처리                     │
│ tools/document_drafter  ← 슬롯 schema 일괄 정리 (graduation 외)     │
│ app.py                  ← /ask·/actions early return 공통 필드     │
│                         ← /health.agent_metrics aggregate          │
└─────────────────────────────────────────────────────────────────────┘
```

> **모델 팀이 백엔드 영역에 예외로 손댄 곳은 단 3건** (`tools/document_drafter.py` 2줄, `agent/answer_validator.py` 패턴 dict 5줄, P4·b로 분리 commit). 모두 commit message에 사유 명시.

---

## 2. 인계 항목 8개

각 항목마다: 명세 출처 / 현재 상태 / 필요 작업 / 손댈 파일 / 추정 시간 / 모델 팀 코드와 인터페이스.

### 🟥 발표 전 처리 추천 (2개)

#### **A1. `/ask`·`/actions/continue` early return 공통 필드 일관화** (§16)

**명세 (agent_product_planning.md §16.1, README §10.4):**
응답에 항상 다음 필드가 있어야 함:
`answer / issue_type / classification / tool_logs / sources / citations / next_actions / safety_flags / answer_validation / output_privacy / llm / live_check`

**현재 상태:**
- 정상 응답: 위 필드 다 채워짐 ✓
- **early return (privacy 차단 / no-source 차단)**: 일부 필드 누락
  - `app.py:ask` 의 privacy_blocked 분기 (line ~237): `classification`, `answer_validation`, `output_privacy` 없음
  - no-source 분기 (line ~298): 비슷한 누락
- `/actions/continue` 도 비슷 (sources/citations/tool_logs가 completed 응답에만 있음)

**필요 작업:**
- privacy/no-source early return에 공통 필드를 기본값(빈 dict/list/None)으로라도 채우기
- 프론트(특히 "연구소 패널의 ProcessingStatusPanel")가 항상 같은 shape을 받아 안정적으로 표시

**손댈 파일:**
- `app.py` 의 `ask()` (line 231-357) 와 `action_continue()` (line 366-410)
- early return 4~5군데에 공통 필드 default 값 spread

**추정:** 1.5h (변경 + 회귀)

**모델 팀 코드와 인터페이스:**
- 모델 팀 P7 `tests/test_demo_scenarios.py` 가 이미 공통 contract 검증함 (`answer_validation.ok / output_privacy.ok / citations / tool_logs`). early return 공통화 후 회귀 시험에 privacy/no-source 케이스 추가하면 contract 통과 검증 자동.

---

#### **A2. live_check 결과를 답변 본문 [주의] 섹션에 반영** (§14·§18)

**명세 (agent_product_planning.md §14.3·§18.5):**
- live_check 시도 시 결과를 답변에 짧게 안내해야
- 네트워크 실패 시 "최신 확인 실패 — 저장 근거 사용" 같은 메시지
- 성공·실패·fallback 사용 3가지 상태를 사용자에게 노출

**현재 상태:**
- `app.py` 가 `live_check_result` dict 를 응답 metadata 로만 제공 (`data.live_check`)
- 답변 본문 `[주의]` 섹션엔 안 들어감
- 모델 팀 P6 polish 프롬프트에 "[주의] 톤 유지" 1줄만 추가 (LLM이 함부로 손대지 말라는 가드만)

**필요 작업:**
- `agent/answer_builder.py:build_final_answer` 에 `live_check_result` 인자 추가 (현재 시그니처: `query, issue_type, chunks, next_actions, student_context`)
- `[주의]` 섹션 조립 시 live_check.attempted=True 이면 상태 메시지 1줄 append
- 매핑 예:
  - `network_success > 0` → "최신 공식 자료 확인 완료 (관련 페이지 N건)"
  - `network_failed > 0 and network_success == 0` → "최신 확인 실패 — 저장된 근거로 답변 (공식 페이지를 한 번 더 확인해 주세요)"
  - `cooldown_remaining > 0` → "최근 확인됨 — N초 후 재확인 가능"

**손댈 파일:**
- `agent/answer_builder.py` (인자 추가 + 본문 조립)
- `app.py:ask()` (line 314): `build_final_answer(...)` 호출에 `live_check_result` 전달

**추정:** 1.5h

**모델 팀 코드와 인터페이스:**
- 모델 팀 P6 polish 프롬프트가 이미 "라이브 확인 결과의 의미·정확도는 변경하지 마라"고 지시하므로, 본문에 들어간 live 안내를 polish 가 깨뜨리지 않음.
- 모델 팀 회귀에 `tests/test_app_live_check.py` 가 있음 — 본문 반영 회귀 추가 시 활용 가능.

---

### 🟨 발표 후로 미뤄도 무방 (6개)

#### **B1. 복합 의도 분류 / `top_issues`** (§6.4)

**명세:** 한 질문에 여러 issue_type 후보를 score 함께 반환 (예: "복학생인데 등록금 고지서 안 떠요" → returning + registration_tuition).

**현재:** 단일 `issue_type` 만 반환. confidence는 score 기반.

**작업:**
- `agent/classifier.py:classify_issue` 가 `top_issues: list[{issue_type, score, confidence}]` 도 반환 (최대 3)
- `app.py` `/ask` 응답 `classification` 필드에 `top_issues` 추가
- 단 retrieval / answer / action 은 이번 범위에선 여전히 primary 만 사용 (추가 시 큰 작업)

**손댈 파일:** `agent/classifier.py`, `app.py:ask()`

**추정:** 2h (additive 형식, 호환 안전)

---

#### **B2. citation provenance 단위 엄격 검증** (§8.4)

**명세:** "절차·서류·기한·제출처·신청경로" 각각에 citation 필수 / 학생 팁·일반 안전 안내·default contact 는 citation 면제.

**현재:** `agent/answer_validator.validate_answer_contract` 는 marker 해소만 검사. 어느 라인이 procedural 인지·citation 필수인지는 모름.

**작업 (option):**
- `tools/checklist.py` / `tools/contact_router.py` 의 반환 구조를 `{text, source_chunk_id, provenance}` 로 변경 — provenance 종류: `official_chunk` / `default_policy` / `student_tip` / `generic_safety`
- `agent/answer_builder.py` 가 official_chunk 항목에 marker 자동 부착
- `agent/answer_validator` 가 official_chunk 라벨인데 marker 없으면 flag

**손댈 파일:** `tools/checklist.py`, `tools/contact_router.py`, `agent/answer_builder.py`, `agent/answer_validator.py`

**추정:** 4~6h (반환 구조 변경이라 호출처 다 손봐야)

---

#### **B3. action grounding 차단 정책** (§11.4, §12.4)

**명세:** action 종류별 grounding policy:
- 출석인정·휴학·복학·수강·증명서·학생증·장학·포털·학사일정·생활지원·학적부·보험·병무 → 공식 chunk 없으면 `status: blocked`
- draft_contact_message → 공식 chunk 없어도 허용 (contact_only)
- graduation/course_plan → 구조화 요약 허용 (structured_summary_allowed)

**현재:** action 호출 시 chunk 검색은 하지만 "공식 chunk 없으면 차단" 정책은 없음. 빈 chunks 로도 draft 시도.

**작업:**
- `tools/document_drafter.py:draft_action_document` 가 action 시작 시 grounding policy 확인
- 모델 팀 P4 가 이미 `_graduation_audit` 만 chunks 받도록 함 — 패턴 확장
- ACTION_SCHEMAS 에 `grounding: "official_chunk_required" | "contact_only" | "structured_summary_allowed"` 필드 추가

**손댈 파일:** `tools/document_drafter.py`, 호출처에 chunk 전달 보강

**추정:** 3h

---

#### **B4. 다른 action 슬롯 schema required/optional 분리** (§12.3)

**명세:** required_slots / optional_slots 분리. optional 미입력 시 "미입력: 담당 부서 확인 필요"로 처리.

**현재:** ACTION_SCHEMAS 전반에서 `_optional` 이름인데 required_slots 안에 들어있음 (예: `evidence_document_type_optional`, `instructor_name_optional`, `target_semester` 등). 사용자가 "없음" / "모름" 등을 명시적으로 채워야 함.

**모델 팀 P4가 이미 처리한 곳:** `graduation_audit` 만 — `target_total_credits_optional`, `target_major_credits_optional` 제거.

**작업:** 다른 action 들도 동일 패턴 정리. ACTION_SCHEMAS 에 `optional_slots: [...]` 키 추가하고 `start_action` 응답에도 `optional_questions` 포함.

**손댈 파일:** `tools/document_drafter.py`, `agent/action_state.py`

**추정:** 2~3h (action 약 14개 × 슬롯 정리)

---

#### **B5. `tools/deadline.py` 상대 날짜·공휴일 처리** (§9.5)

**명세:** "다음 주 월요일" / "이번 주 금요일" 같은 상대 날짜 파싱, 마감일이 공휴일·주말이면 다음 영업일로.

**현재:** `YYYY-MM-DD`, `2026년 5월 15일`, `5월 15일`(기본 연도 2026 고정). 상대 표현 / 공휴일 처리 없음.

**작업:**
- 기본 연도 고정 → `date.today().year`
- 상대 표현 파싱 (`dateparser` 라이브러리 활용 가능)
- 공휴일 처리: `holidays` 라이브러리 (한국 공휴일)

**손댈 파일:** `tools/deadline.py`, `requirements.txt` (의존성 1~2개 추가)

**추정:** 2~3h

---

#### **B6. `/health.agent_metrics` aggregate endpoint** (§20)

**명세:** 최근 N건 운영 지표 aggregate (privacy_block_rate, no_source_rate, citation_validation_fail_rate, output_privacy_fail_rate, live_check_success_rate, llm_fallback_rate).

**현재:** 모델 팀 P1 이 `data/state/llm_usage.jsonl` 에 LLM 호출 메트릭만 기록 (raw 미저장 + 파일 쓰기 silent fallback). 전체 `/ask` 단위 로그 + aggregate endpoint 는 없음.

**작업:**
- `/ask` 응답 직전에 별도 헬퍼로 `data/state/agent_usage.jsonl` 1줄 기록 (모델 팀 logger 패턴 재사용 가능 — `llm_client._record_usage` 참고)
- 기록 필드 예: `ts, route, issue_type, status, safety_flags, chunk_count, citation_count, privacy_blocked, no_source, output_privacy_ok, citation_validation_ok, live_check_attempted, llm_query_expansion_used, llm_rerank_used, llm_polish_used, llm_fallback, latency_ms`
- raw question/slots/answer 절대 저장 금지
- `/health.agent_metrics` 는 파일 tail 1000줄 정도 읽고 카운트·비율 aggregate

**손댈 파일:** `app.py` (logger 호출 + `/health` 응답에 `agent_metrics` 키 추가)

**추정:** 3h

**모델 팀 코드와 인터페이스:**
- `llm_client._record_usage` 가 raw 미저장 + 파일 쓰기 silent fallback 패턴의 reference implementation. 같은 패턴으로 agent_usage 로거 작성하면 안전.

---

## 3. 우선순위 추천

| 우선순위 | 항목 | 발표 효과 | 시간 |
|:---:|---|---|---:|
| 🔴 1 | **A1. early return 공통 필드** | 프론트 안정성 ↑·`agent_product_planning.md` §16 명세 충족 | 1.5h |
| 🔴 2 | **A2. live_check 본문 [주의] 반영** | 시연에서 "최신 확인" 토글 켰을 때 실제 답변에 효과 보임 | 1.5h |
| 🟡 3 | B6. agent_metrics endpoint | 운영 어필 (관찰 가능성) | 3h |
| 🟡 4 | B3. action grounding 차단 정책 | 안전성 ↑·근거 없는 초안 방지 | 3h |
| 🟢 5 | B4. 다른 action 슬롯 분리 | UX 부드러움 | 2~3h |
| 🟢 6 | B2. citation provenance | 진짜 운영형 보호 | 4~6h |
| 🟢 7 | B1. 복합 의도 top_issues | 다중 의도 대응 | 2h |
| 🟢 8 | B5. deadline 상대 날짜 | 사용성 마이너 개선 | 2~3h |

→ **A1·A2 (총 3h)** 만 발표 전 추가 처리하면 사용자 평가표의 🟡 항목 중 §14·§16 두 줄이 ✅로 올라감. **모델 팀과 백엔드 팀 합쳐 발표 모델 어필 한 단계 더 강화 가능.**

→ 나머지 B1~B6 (총 16~20h) 는 발표 후 로드맵으로 미뤄도 발표 평가엔 큰 영향 없음.

---

## 4. 모델 팀 작업과 합쳐 보는 전체 그림

```text
agent_product_planning.md 명세 충족도 (사용자 평가 416fe44 기준 + 백엔드 A1·A2 후 추정)

✅ 거의 완료:
  - 핵심 RAG / Privacy guard (input) / Source guard / 답변 섹션
  - 학생 playbook · 학생식 표현 / Student context guidance
  - LLM 보조 3노드 + metadata + reasoning effort
  - 졸업센터 §15.4 5섹션 + sanitize 8 패턴 + 8 task 회귀
  - 데모 5 시나리오 자동 회귀 + live_llm mark
  - LLM usage log (raw 미저장)
  - /ask answer_validator GPA·성적·이메일 검증 (졸업센터와 통일)

🟡 모델 팀이 한 작업 위에 백엔드 작업 더해지면 ✅:
  - live_check 본문 반영 (A2)
  - early return 공통 필드 (A1)

🟡 백엔드 단독 작업 필요 (발표 후):
  - 복합 의도 top_issues
  - citation provenance 단위 엄격 검증
  - action grounding 차단 정책
  - 다른 action 슬롯 정리
  - deadline 상대 날짜·공휴일
  - agent_metrics aggregate endpoint
```

---

## 5. 모델 팀이 만든 인프라 (백엔드 작업 시 재사용 권장)

| 인프라 | 위치 | 백엔드가 활용할 만한 점 |
|---|---|---|
| `live_llm` mark 자동 skip 훅 | `tests/conftest.py` | 신규 회귀가 실제 OpenAI 호출하면 마크만 붙이면 됨 |
| usage log 헬퍼 패턴 | `llm_client.py:_record_usage` | B6 agent_metrics 로거 작성 시 raw 미저장 + silent fallback 패턴 참고 |
| Sanitize 패턴 dict | `graduation_center/service.py:SENSITIVE_PATTERNS` | A1·B2 작업에서 동일 패턴 dict 재사용 가능 (이미 `answer_validator`엔 통일됨) |
| `pytest.ini` marker 등록 | `pytest.ini` | 새 마크 추가 시 같이 등록 |
| Demo 시나리오 회귀 | `tests/test_demo_scenarios.py` | A1 early return contract 회귀를 같은 파일에 추가하면 자연스러움 |

---

## 6. 질문 있으시면

작업 중 의존성·인터페이스 의문 있으시면 알려주세요. 모델 팀이 한 작업의 디테일은 `docs/work_log_2026-05-28.md` 참고.
