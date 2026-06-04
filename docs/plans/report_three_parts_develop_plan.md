# 작업계획: 보고서 3파트(총평·로드맵·해설) develop — rev.2 (D-3)

> rev.1 검증 라운드1(codex MUST 5 + 적대 HIGH 5·MED 5·LOW 2) 전건 반영.
> 핵심 정정: ① KPI 정직화 — 미확인률 목표 "한 자릿수" 폐기(실측 반증: MR 제거 후 14.2%,
> 잔여는 융합 기인) ② §C markdown 변경은 화면 효과 0(프론트는 JSON 직렌더) → 최후순위
> ③ 결정론 해설 섹션은 run_explain 밖에서 합성 + deterministic 플래그 신설.
> 원칙 불변: 판정·배치 로직 불가침, 표시·선정·프롬프트 레이어만.

## A. 해설 — 필수과목 결정론 분리 (효과 최대 · 정직한 기대치)

1. `select_explain_items`: `missing_required` 제거 — 슬롯은 융합>영역>핵심교양 재배분.
   **정직 명시**: S4는 항목 3→2개로 축소(재배분 후보 없음), S2의 미확인 2줄은 융합 기인이라
   이 조치로 안 줄어듦(적대 6).
2. **결정론 섹션 합성은 `pipeline.run_audit`에서**(run_explain 밖 — 적대 4·codex 4):
   run_explain 반환 후 `explanations` 앞에 prepend. **trace·캐시·ungrounded 집계는 LLM
   섹션만 대상**(run_explain 내부 무변경 — 5개 return 분기·캐시-라이브 모순 회피).
3. 모델: `ExplainSection.deterministic: bool = False` 추가(codex 5 — "신규 필드 없이"는
   프론트 렌더상 불가로 판명). lines는 grounded=True·source_ids=["G1"].
   프론트: deterministic이면 파란 Y 배지 대신 **"결정론" 칩** + G1 배지 스타일 분기.
4. 기대 효과(실측 기반 정직): 미확인률 **23.7% → 약 14%**(전체 미확인의 61%인 MR 줄 제거).
   "필수과목 항목 자체의 미확인율 41%"와 분모 구분 표기(적대 2). 잔여 14%는 융합 해설
   기인 — D-3 범위 밖(발표 Q&A: "정책 해설의 인용 일관성은 알려진 한계, 필수는 결정론 분리로 해결").
5. **데모 장면 충돌 해소(적대 6·7)**: demo_script S3 비트의 "validator가 미확인 잡는 장면"
   주재료가 MR 미확인 3줄이었음 → 멘트를 "필수과목은 결정론 확정(결정론 칩) + 정책 해설의
   미확인 줄은 융합·영역에서 표시"로 교체. current_state §7 인용률은 워밍업 후 재측정 갱신
   (현 수치 이미 stale — S2 5/7·S3 7/11·S4 5/7).
6. 기존 `test_select_items_priority_and_cap`(items[0]==missing_required 고정) 기대값 갱신(codex 5).

## B. 총평 — 권고 변별 + 효과 컬럼 + 라벨 (백엔드 결정론 산출)

7. `_summary_prompt`: "채택 시나리오 중 리스크·졸업시점 **개선**이 있으면 recommendation·
   headline에 방향 반영, 개선 없고 로드맵 배치 가능이면 '유지 권장'" +
   **`SUMMARY_SCHEMA_VERSION = 5`**(현행 4 — codex 1). 권고는 여전히 enum 3종 —
   "포기 권장" 같은 단정 칩은 만들지 않음(판정 금지 경계, 교수 렌즈 — 방향은 headline 서사로만).
8. **효과 라벨은 백엔드 결정론 산출**(codex 2 — 프론트 추측 금지):
   `ScenarioOutcome.effect_label: str = ""` 추가 — build_diff 값으로 결정론 합성
   ("리스크 C→B 개선"/"예상 졸업 단축"/"초과학기 발생"/"변화 없음") +
   `effect_kind: Literal["improve","worsen","neutral"]`(행 시각 구분용).
   프론트 비교표: total_gap before=after면 "—", 효과 컬럼 표시, worsen 행 회색+⚠.
9. 시나리오 라벨: reason 한국어 칩은 **프론트 매핑 상수**로(계약 일원 — codex NICE),
   파라미터 나열은 보조 텍스트 강등.

## C. markdown 표면 — 최후순위 (적대 3: 화면 효과 0)

10. 프론트는 report_markdown을 읽지 않음(소비처 백엔드 1곳) — C는 export 정합용으로만:
    총평 섹션을 제목·종합판정 줄(L[0]·L[1]) **뒤, 영역별 현황 앞** 삽입(삽입점 명시) +
    로드맵 줄 satisfies/확인필요 병기. **시간 부족 시 통째 생략 가능**(발표 무영향).
    (프론트 로드맵 카드는 satisfies·assignment 칩이 이미 있음 — 화면은 기수정 상태.)

## D. 로드맵 화면

11. `term_risk` 배지: planner 결정론 산출이 high를 절대 안 냄(적대 9 — `>cap-3`만) →
    **`used >= cap`이면 "high" 임계 1줄 추가**(표시용 산출 — 배치 로직 불가침과 무관) +
    프론트 🟢저/🟡중/🔴고 배지. 데모 실측으로 high 등장 여부 확인(없으면 2단계로 표기).
12. blocked 미배치 그룹 칩: `RoadmapPlan.unplaced_by_area: dict[str, float] =
    Field(default_factory=dict)`(codex SHOULD) — **unplaced + unfillable의 area 합산**
    (적대 10 — unfillable 누락 방지), blocked_reason 문자열은 이 집계에서 **파생**(이중
    진실 금지). 프론트: "융합 ×6 · 전공 ×4" 요약 칩 + 접기 상세.

## E. 불가침

플래너 배치 알고리즘(균형 패스 보류)·audit·risk 수치·validator 완화·HyDE/검색 변경 금지.

## F. 테스트

explain 선정·결정론 섹션 합성(미이수 유/무) 2종 + 기존 선정 테스트 기대값 갱신 /
summary effect_label·kind 결정론 1종 + SCHEMA 5 키 변동 / planner unplaced_by_area
(unfillable 포함) 1종 / term_risk high 임계 1종 / 기존 117 회귀 + 빌드.

## G. 워밍업·검증

- **warm_whatif_cache.py에 해설 미확인률 집계 출력 추가**(적대 8 — 안 재면 검증 불가).
- 캐시 2종 삭제 → 1사이클(explain은 총평 run_audit에 동반 — 검증 라운드1에서 1사이클
  충분성 확인됨). 검수: 미확인률(기대 ~14%)·권고 다양성·내부 용어 0·effect_label 분포.
- 실행 라운드: 재기동 + 4명(등급·총점·미이수·겹침 불변, 해설·총평 텍스트 변동 허용) +
  whatif + 결정론 2회. 문서: current_state §7 재측정, demo_script S3 비트 교체(§A-5).

## H. 일정 (적대 12 재산정)

A 0.5일(분기 정합+플래그+프론트 칩) → B 0.3 → D 0.3 → C 0.1(여유 시) → 코드 검증
라운드(적대+교수) 0.3 → 워밍업·문서·실행 라운드 0.3. **총 ~1.7일** — D-3 내 가능하나
C 생략·검증 압축이 버퍼. 워밍업 실패(환각 재발) 대비 재실행 1회 버퍼 포함.
