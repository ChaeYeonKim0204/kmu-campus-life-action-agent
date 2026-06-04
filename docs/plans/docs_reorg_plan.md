# 작업계획: docs/ 정리 — 현행/계획/검증기록/레거시 4분류

> 원칙(코드 정리와 동일): 삭제 금지 — git mv 분류 보관. 발표 D-5: 발표자·팀원이 봐야 할 현행 문서가
> 첫 화면에 5~6개만 보이게. 32개 문서 ≈ 1.7만 줄 전수 분류(아래 표). codex 검증 후 실행.

## 목표 구조

```
docs/
  README.md                            ← 새로 작성: 인덱스(무엇을 어디서·시효 표시)
  graduation_center_current_state.md   ← 현행 5종 (top-level 유지)
  demo_script_2026-06-09.md
  graduation_center_direction.md
  graduation_center_direction_vs_built.md
  second_topic_workflow_candidates.md
  plans/        ← 작업계획+검증 대장 3종 (whatif_consult_agent / cleanup_unused / trust_isugubun / docs_reorg)
  reviews/      ← 검증 캠페인 원기록 11종 (review_* 9 + codex_llm_placement + codex_scenario_design)
  legacy/       ← 옛 /ask 시대·완료된 일회성 11종
```

## 분류표 (32개 전수)

| 문서 | 분류 | 근거 |
|---|---|---|
| graduation_center_current_state / demo_script / direction / direction_vs_built / second_topic | **현행(유지)** | 팀·발표가 직접 보는 5종 — current_state가 나머지를 링크하는 허브 |
| kmu_agent_project_proposal | **현행(유지)** | 초기 제안서 — 발표 "문제 정의" 비트의 원천, 시효 무관 |
| whatif_consult_agent_plan / cleanup_unused_plan / trust_isugubun_plan / docs_reorg_plan(본 문서) | **plans/** | 작업계획+발견 대장 — 검증 추적용, 일상 참조 아님 |
| review_round2~5_{subagents,codex_batch} (8) / review_codex_adversarial(5394줄) / review_subagents_adversarial | **reviews/** | 검증 캠페인 원기록(루브릭 "품질" 증빙) — 개인 기여 보고서 소스 |
| codex_llm_placement / codex_scenario_design | **reviews/** | codex 자문 원기록 |
| agent/backend/frontend/service_product_planning (4, 4200줄) | **legacy/** | 옛 /ask 파이프라인 기획 — 코드가 unused/로 간 것과 짝 |
| current_service_plan | **legacy/** | 5-22 작성 /ask 서비스 기획(중복: service_product_planning과 동일 계열) |
| handoff_to_backend / next_agent_handoff | **legacy/** | 옛 구조 인계 메모(다른 머신 경로 언급 — 시효 만료) |
| demo_queries | **legacy/** | /ask 시연 질의 풀(chunks.jsonl·issue_type 기준 — 티어1 소멸) |
| work_log_2026-05-28 | **legacy/** | 시점 작업 보고(기록 가치만) |
| llm_cost_budget | **legacy/** | 5-28 측정 — /ask 시대 비용. 단 gpt-5-mini 단가표는 유효하므로 README 인덱스에 "단가표 참조용" 표기 |
| graduation_center_spec_en | **legacy/** | 코딩 에이전트용 영문 스펙 — v2 구현 완료로 역할 종료(direction의 영문판) |

## 링크 보수 (이동 시 깨지는 참조 — 조사 완료)

- **CLAUDE.md**: `docs/second_topic_workflow_candidates.md`(유지 — 무변), 기타 docs 참조 grep 후 경로 갱신.
- **current_state.md 헤더 링크**: direction·direction_vs_built·demo_script(동일 폴더 유지 — 무변), `whatif_consult_agent_plan.md` → `plans/` 경로 갱신. §6 "상세 대장" 참조도.
- **demo_script**: 기여 매핑 표의 `docs/review_round*.md` → `reviews/` 갱신.
- **reviews/ 내부 상호 참조**: 같은 폴더로 함께 이동하므로 상대 링크 자동 보존(검증: 이동 후 grep).
- **메모리/계획 문서 안 참조**: plans/ 내부 문서끼리는 함께 이동. unused/README는 docs 참조 없음(확인).
- 이동 후 검증: `grep -rn "docs/[a-z_]*\.md" CLAUDE.md README.md docs/ --include="*.md"`로 끊긴 경로 0 확인 + docs/README.md 인덱스의 모든 링크 실존 확인 스크립트 1회.

## docs/README.md 인덱스 (신규)

각 분류별 1줄 설명 + 시효 표시(현행/기록/레거시) + "발표 전 볼 것: current_state → demo_script" 안내.

## 실행·검증·커밋

git mv(이력 보존) → 링크 보수 → 링크 무결성 grep → 단일 커밋 → push.
risk: 코드가 docs 경로를 읽는 곳 없음(grep 확인 예정 — CLAUDE.md는 문서라 빌드 무관).
