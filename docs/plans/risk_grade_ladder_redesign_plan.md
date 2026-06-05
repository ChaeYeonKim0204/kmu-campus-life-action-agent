# 작업계획: 등급 사다리 재설계 — S/A+/A/B/C/D (사용자 설계) — rev.3 (R2 잔여 MUST 3 반영 — go)

> rev.1 검증: codex가 "D-2 no-go" 판정했으나 **마감 전제 오류(실제 D-4 — 발표 6/9, 오늘 6/5)**.
> MUST 5건은 전부 설계로 폐쇄 가능 — rev.2에 전건 반영. 작업 ~1.5일 + 검증 0.5일 + 리허설 여유.
> 신규(사용자 지시): **S 등급 학생에게 조기졸업 요건을 학사규정 RAG로 LLM이 안내**.

## 등급 사다리 (의미 고정 — codex MUST 3 반영)

등급은 **"현재 제약 기준"이 아니라 보편적 졸업 여유도**: 판정 시나리오는 사용자 ctx와
독립적으로 고정한다(성적우수 보너스·계절 허용은 시나리오별 명시 — 사용자 입력은 실제
로드맵 표시에만 반영).

| 등급 | 정의 | 판정(결정론 — 위에서 첫 충족) |
|---|---|---|
| **S** | **학점·요람 요건** 전부 충족(잔여 ≥0) — 라벨 하향(R2: 논문·인증제 등 hard-verify 불가 항목 caveat) | `_already_met(audit)` 헬퍼: total_gap·전 area_gaps·전 core_area_gaps·missing_required·전 conv gap·전 group gap == 0 ∧ gen_basic 전부 taken ∧ required_check_available ∧ **ctx.gpa_min_met == "yes"**(R2 잔여 — unknown이면 S 금지, A+로) |
| **A+** | 계절 없이 학기당 **15학점 이하**로 졸업 가능 | 시나리오 런: ctx{seasonal=False, max_credits=15, **prev_gpa=False**(MUST 2 — 보너스 차단)} → feasible |
| **A** | 계절 없이 법정 상한으로 졸업 가능 | 시나리오 런: ctx{seasonal=False, cap=법정, prev_gpa=False} → feasible |
| **B** | 초과학기 없이 가능하나 **계절학기 필요** | 시나리오 런: ctx{seasonal=**True**(사용자 설정 무관 — 의미 고정), cap=법정, **prev_gpa=False**(R2 잔여 — A와 동일 기준)} → feasible |
| **C** | 초과학기 1학기(**경로 검증됨**) | 위 전부 실패 ∧ overflow.extra==1 ∧ **overflow_verified is True**(MUST 3 — 미검증 추산은 C 금지) |
| **D** | 초과 2학기↑·검증 안 된 초과·후보 고갈·평점 미달 | 나머지 전부. gpa_min_met=="no"는 무조건 D |

- 라벨(한글 우선 — codex SHOULD·게임등급 반박 방어): S=요건 충족 / A+=여유 / A=가능 /
  B=계절 필요 / C=초과 1학기 / D=초과 다수·불가. 배지 명칭 "리스크"→**"졸업 여유도"**.
- 기존 트리거(갭·필수·영역·인증제 등)는 reasons로 전부 유지(정보 무손실), score도 유지.
- fe05a88의 B 클램프는 본 사다리로 대체(흡수).

## 시나리오 런 비용 (codex MUST 1 — 정직 명세)

- 등급 시나리오 런 ≤3회(A+/A/B — S·C·D는 기존 산출로 판정)는 **run_audit 1회당** 추가.
  what-if(before/after 2회)·총평(before 1 + after ≤4회)이 run_audit를 재호출하므로 **최악
  /audit(run_summary=True) 1요청 = planner 총 ~24런**. planner 1런은 결정론 수 ms —
  S1 실측 audit 0.01s에 이미 2런 포함. **구현 직후 최악 경로 wall-clock 실측을 게이트로**
  (50ms 초과 시 등급 런 결과를 run_audit 인자로 전파해 재계산 생략하는 최적화 — 설계 예비).
- 단조 가지치기: A+ feasible이면 A·B 런 생략(최선 1런), S면 0런.

## 조기졸업 RAG (사용자 지시 — S 등급 연계)

- S 판정 학생: `select_explain_items`는 부족 기반이라 S면 items=[] — **별도 `early_graduation` 항목을 S일 때 삽입**(R2). 쿼리 "조기졸업 신청 요건 평점 학기" — Chroma에 조기졸업 8건·제95조 chunk 실재(codex 확인).
- **Chroma/키 실패 fallback(R2 MUST)**: `data/graduation/policies.json`의 조기졸업 curated 소스를 **결정론 섹션**으로 부착(필수 분리와 동일 패턴 — deterministic=True·G 근거).
- 판정은 안 함(평점 데이터 없음) — LLM은 요건 **안내**만(기존 해설 패턴: 인용·validator·캐시).
- S 배지 옆 라벨: "조기졸업 요건은 아래 규정 안내 참고 — 평점 등은 본인 확인".
- 데모 4명에 S 없음 → 데모 캐시 무영향. S 시연용 합성 학생 1명(요건 전부 충족) 추가 검토(여유 시).

## 등급 문자열 연쇄 전수 (codex MUST 4 — 전부 이번 범위)

- `risk.py` GRADE_RANK·LABELS / `models_v2.RiskAssessment.grade` Literal 확장
- `report_summary._GRADE_ORDER`(S=0,A+=1,...)·`_GRADE_RE`(`S|A\+|A|B|C|D` — 한글 인접 규칙
  유지, 'A+'의 '+' 이스케이프)·facts 등급 텍스트·validator 등급 모순
- `whatif.py:385` 문자 비교(`risk_after > risk_before` — 'A+'에서 깨짐) → **공용
  `grade_rank()` 헬퍼**로 교체(risk.py에 두고 import)
- 프론트 GRADE_COLOR(S·A+ 추가)·what-if diff 색·총평 effect(_effect도 _GRADE_ORDER 사용 ✓)
- 테스트 `{"B","C","D"}` 단언 갱신·demo/current_state 문서·SUMMARY_SCHEMA_VERSION +1
- grep 전수: `grade`·`risk_before`·`GRADE` 사용처 체크리스트를 구현 시 작성

## 영향·검증

- 데모 예상(실측 확정): S4→A+(15캡 2학기 배치 가능 시; 안 되면 A), S1·S2→C(verified 확인),
  S3→D. demo_script·current_state 수치 갱신, summary 캐시 전체 재워밍업(facts 등급),
  whatif 캐시 유효(delta 저장).
- 테스트: 사다리 6 + 경계(보너스 차단·계절 의미 고정·미검증 overflow→D·S 헬퍼 부분 미상 금지·
  A+ 가지치기) + 기존 갱신. 코드 검증 라운드(적대+교수) + 실행 라운드 수렴.

## 일정 (D-4)

1일차(6/5~6): 백엔드(사다리·시나리오 런·연쇄 교체)+테스트 → 2일차(6/6~7): 프론트·조기졸업
RAG·재워밍업·검증 라운드·실행 라운드·문서 → 6/8: 리허설 여유 확보.
