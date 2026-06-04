# docs/ 인덱스

> 발표 전 볼 것: **[graduation_center_current_state.md](./graduation_center_current_state.md)** (구현 현황 허브) → **[demo_script_2026-06-09.md](./demo_script_2026-06-09.md)** (발표 동선·Fallback·Q&A).
> 분류 원칙: 최상위 = 현행, `plans/` = 작업계획·검증 대장, `reviews/` = 검증 캠페인 원기록, `legacy/`·`archive/` = 옛 구조 보존.

## 현행 (최상위)

| 문서 | 한 줄 |
|---|---|
| [graduation_center_current_state.md](./graduation_center_current_state.md) | **팀 공유 허브** — 무엇이 완성됐고 어떻게 동작하나(워크플로우·데모 자산·품질·한계) |
| [demo_script_2026-06-09.md](./demo_script_2026-06-09.md) | 발표 비트·타임라인·Fallback·예상 Q&A·기여 매핑 |
| [graduation_center_direction.md](./graduation_center_direction.md) | 졸업센터 기획(방향) |
| [graduation_center_direction_vs_built.md](./graduation_center_direction_vs_built.md) | 기획 대비 실제 구현 차이·사유 |
| [second_topic_workflow_candidates.md](./second_topic_workflow_candidates.md) | 두 번째 주제 후보 3종 비교(CLAUDE.md 참조) |

## plans/ — 작업계획 + 발견 처리 대장 (검증 추적용)

| 문서 | 한 줄 |
|---|---|
| [whatif_consult_agent_plan.md](./plans/whatif_consult_agent_plan.md) | 졸업 시나리오 상담 Agent — 설계 + 검증 7라운드 발견 대장(§7) |
| [cleanup_unused_plan.md](./plans/cleanup_unused_plan.md) | 미사용 코드 unused/ 보관 계획(1차 시도 사고 분석 포함) |
| [trust_isugubun_plan.md](./plans/trust_isugubun_plan.md) | 이수구분 신뢰 전환 계획(코드표 매핑·융합 이중인정 가드) |
| [docs_reorg_plan.md](./plans/docs_reorg_plan.md) | 본 문서 구조 정리 계획 |

## reviews/ — 검증 캠페인 원기록 (품질 증빙·개인 기여 보고서 소스)

- `review_round2~5_{subagents,codex_batch}.md` — 적대 리뷰·수렴 루프 라운드별 발견(HIGH/MED, file:line, 재현)
- `review_codex_adversarial.md` / `review_subagents_adversarial.md` — 초기 적대 캠페인 원기록(대용량 덤프 포함)
- `codex_llm_placement.md` / `codex_scenario_design.md` — codex 설계 자문 기록

## legacy/ — 옛 캠퍼스라이프 `/ask` 시대 (코드 unused/ 보관과 짝, 참조용)

- `agent/backend/frontend/service_product_planning.md`, `current_service_plan.md` — 옛 파이프라인 기획 4+1종 (v1 졸업센터 8-task 스펙은 `agent_product_planning.md` §15가 여전히 출처 — `graduation_center/service.py` 주석이 참조)
- `handoff_to_backend.md`, `next_agent_handoff.md` — 옛 구조 인계 메모(시효 만료)
- `demo_queries.md` — /ask 시연 질의 풀(티어1 소멸)
- `work_log_2026-05-28.md` — 시점 작업 보고(기록)
- `llm_cost_budget.md` — 2026-05-28 실측 비용 — /ask 기준이지만 **gpt-5-mini 단가표는 참조 가치**(최신 단가 재확인 요)
- `graduation_center_spec_en.md` — 초기 영문 구현 스펙(LLM 로드맵 플래너 전제 — 현행과 다름, 폐기)
- `kmu_agent_project_proposal.md` — 초기 제안서(발표 "문제 정의" 비트의 역사적 원천)

## archive/ — 초기 기획 아카이브 (보존 전용)

`KMU_신규구축/재설계_기획문서.md`, `FE_Mock_데이터_기획문서.md`, `KMU_FE_Prototype.html`, `README_before_agent_planning.md`
