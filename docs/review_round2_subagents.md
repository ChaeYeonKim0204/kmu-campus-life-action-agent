# 적대리뷰 라운드2 종합 (서브에이전트 18, raw 97, 확정 34, HIGH 10, regression 11)

## [HIGH] [REGRESSION] [로드맵 #1] feasible=True가 total_gap(일반선택/총학점 부족)을 무시 — 로드맵이 거짓 '충족'으로 졸업 가능 단정 (데모 top-1 모순)
- file: graduation_center/v2/planner.py:586-589, 626-629
- 문제: 병합: 동일 결함을 지목한 5개 리뷰(빈 selected 분기 / selected非빈 분기 모두). build_unified_candidates는 전공·필수·융합·기초/핵심/자유교양만 후보로 만들고 일반선택·총학점 충당 후보는 절대 생성하지 않는다(HARD_AREAS에서 일반선택 제외). 따라서 모든 영역 floor를 채웠지만 총학점이 졸업최저보다 모자란 학생은 (a) selected=[]면 586-589가 feasible=True·'졸업요건을 모두 충족했습니다'를 반환, (b) selected가 전공 등만 있고 전부 배치되면 626-629가 feasible=True·overflow=None을 반환한다. 두 경로 모두 project_overflow가 total_gap을 옳게 계산해놨어도 버린다. 동시에 risk.py는 total_gap으로 B~D를 매기고 헤더 StatBox는 116/136을 보여줘 한 화면에 '로드맵 ✅충족 + 리스크 D'가 공존. 프론트(GraduationV2.jsx:641-644)는 feasible===true & terms 0 → 초록 카드, '남은 요건' 칩(660)은 terms.length>0일 때만 떠서 일반선택 결손이 리포트 어디에도 안 보인다. ai_bigdata 기본 데모에서 바로 재현.
- 수정: feasible/overflow 판정을 '후보 배치 성공'이 아니라 졸업요건 전체(total_gap 및 area_gaps 잔여)에 근거하도록 변경. unplaced가 비어도 audit.total_gap>0이면 feasible=True로 마감하지 말고 project_overflow 결과를 plan.overflow/blocked_reason에 보존. 'feasible면 overflow=None'은 total_gap<=0이고 모든 area_gap이 닫혔을 때만. 또는 build_unified_candidates에 _slot_chunks('일반선택', total_gap-배치된자유슬롯, '일반선택') 슬롯을 추가해 risk/roadmap이 같은 결손을 보게 함.

## [HIGH] [REGRESSION] [로드맵 #2] 미이수 필수 학점이 카탈로그 무시·3.0 고정 → 전공 갭 과소계산 + 로드맵 학점 위조 (ai_bigdata 기본 학과)
- file: graduation_center/v2/planner.py:418-428, 448-450 (_required_meta:380-395)
- 문제: 병합: 6개 리뷰. required_names_by_year.json에는 mirae_mobility만 있고 ai_bigdata(프론트 기본 program_id, GraduationV2.jsx:211)는 없어 _required_meta('ai_bigdata',2025)={} 반환(검증). 모든 미이수 필수가 credits 기본 3.0으로 채워진다. 실제 ai_bigdata 필수 10과목 합은 26학점(검증: S-TEAM Class 1.0·사제동행세미나 1.0 포함)인데 코드는 30(3*10)으로 가정. ① req_major_credits=30 → major_gap_eff = major_gap-30 으로 전공 후보를 실제보다 4학점 적게 뽑아 로드맵이 전공 4학점 덜 배치, ② 후보 credits=3.0이라 로드맵 화면이 'S-TEAM Class 3학점' 등으로 잘못 표시·term_credits 부풀림, ③ offered_terms 누락으로 1학기 전용 과목이 2학기 배치 가능. _required_meta는 2025처럼 by_year 항목이 문자열(dict 아님)인 연도도 빈 dict 반환(391-394)이라 2025학번 mirae 데모로 전환해도 동일 발현.
- 수정: build_unified_candidates에서 _required_meta가 비거나 이름 미존재면 이미 로드한 cat(load_catalog)의 by_norm/by_code로 미이수 필수 이름을 정규화 매칭해 실제 credits·offered_terms를 채우고(confidence='catalog_verified', manual=False), 없을 때만 3.0/['1','2'] 폴백. major_gap 차감도 실제 학점 기준. (rmeta 있는 mirae 2023은 영향 없음.)

## [HIGH] [REGRESSION] [로드맵 #3] 선수과목 위상정렬이 name-only(필수지정·융합) 후보에서 무력화 — 선수와 종속과목 같은 학기 배치 (mirae_mobility 재현)
- file: graduation_center/v2/planner.py:418-428, 500-538
- 문제: 병합: 선수 위상정렬 결함 2건. plan_greedy의 선수 보류·배치추적은 전부 course_id[:5] prefix에 의존한다(sel_pref line 515, placed_at line 536, pres line 513). 그러나 '필수지정 미이수' 분기(421-427)는 course_id·prerequisites를 절대 부여하지 않아 미이수 필수는 모두 course_id 없는 name-only 후보가 된다. 그 결과 (1)sel_pref에 안 들어가 종속과목 defer 조건이 False, (2)placed_at에 안 기록돼 min_idx=0 → 선수가 필수지정이면 위상정렬이 완전 우회된다. mirae_mobility 공학수학Ⅰ(선수 공학기초수학, 둘 다 is_required)·ai_bigdata 수리통계↔경영통계 동일 구조. run_planner 검증(604-611)은 over_credit_cap·unplaced만 보고 선수순서를 재검증하지 않아 잘못된 계획이 feasible=True·vrep.ok=True로 통과한다. #2의 카탈로그 보강(course_id 부여)으로 대부분 해소되지만, 보강 후에도 안전망 필요.
- 수정: #2 수정으로 미이수 필수에 course_id·prerequisites를 부여한 뒤, run_planner 결정론 검증(604-611)에 선수순서 재검증(배치된 각 과목 prereq prefix가 completed이거나 더 이른 term index에 placed_at)을 추가. name-only 잔여 케이스용으로 normalize_name 보조키 매칭을 병행해 위반 시 ValidationError(prereq_unmet)로 ok=False 처리.

## [MEDIUM] [로드맵 #4] plan_greedy가 후보풀에도 이수목록에도 없는 미충족 선수를 무시하고 배치 (silent prereq violation)
- file: graduation_center/v2/planner.py:512-538
- 문제: 병합: 동일 결함 2건. _try_place의 defer 조건은 선수 p가 sel_pref(선택후보)에 있을 때만 보류한다(516). 선수가 (1)미이수·(2)후보풀에도 없으면 조건 False → defer 안 됨, placed_at에도 없어 min_idx=0 → 선수 미충족 상태로 배치된다. build_unified_candidates 전공풀이 quota(acc>=need, 489-496)로 조기 종료돼 선수가 selected에서 누락되거나 선수가 다른 영역이면 발생. 검증: plan_greedy([{prerequisites:['Q'],...}], completed=set())가 Q 미충족인데 unplaced=[]로 feasible 보고. infeasible 로드맵을 feasible로 표시.
- 수정: _try_place에서 선수 p가 completed에도 sel_pref에도 없으면(충족 불가) 배치하지 말고 unplaced 처리 또는 manual_check 경고. 또는 build_unified_candidates에서 선택된 후보의 미충족 선수를 quota 무관하게 후보풀에 강제 포함해 선수 체인이 끊기지 않게.

## [HIGH] [연계융합 #1] 다중 연계융합 동시선택 시 공유 겹침과목의 to_fusion이 전공에서 이중차감 — major_effective 과소(0/음수)
- file: graduation_center/v2/audit_v2.py:235-269
- 문제: 병합: 9개 리뷰가 지목한 동일 결함. _convergence_checks는 프로그램별 독립으로 to_fusion_credits를 계산하고, compute_audit(268-269)이 to_fusion_total=Σ(전 프로그램 to_fusion), major_effective=earned[전공]-to_fusion_total로 한 번에 차감한다. dsci·mobility 두 다전공이 prefix 9개 공유(검증: dsci&mob 9개), triple-shared 1개. 같은 물리 과목이 양쪽 designated/overlap에 들어가 각 프로그램에서 따로 to_fusion 배정 → 동일 학점 이중차감. 재현: 공유 전공 24학점 학생이 두 융합 선언 시 to_fusion_total=12+12=24 → major_effective=0(전공 24 들었는데 0 집계). 269에 max(0,...) 클램프 없어 음수도 가능 → area_gap=required-음수로 과대, project_overflow·risk까지 전파. 단일 융합(데모 happy-path)은 정상이라 회귀 미검출이나 프론트는 convergence_program_ids 다중선택 허용.
- 수정: 겹침 배정을 프로그램별 독립이 아닌 학생 과목 단위 전역 1패스로: 각 course_id를 제1전공/정확히 한 융합/중복인정 중 하나로만 배정. 또는 to_fusion 차감 시 course_id 합집합 기준(중복 dedup) 합산. 추가로 269에 major_effective=max(0.0, round(...)) 클램프. 데모가 단일 융합만 시연하면 convergence_program_ids 길이>=2일 때 명시적 미지원/경고도 임시 방어책.

## [HIGH] [REGRESSION] [연계융합 #2] group_checks.earned가 배정/중복인정 한도 무시(designated 원시합) → 그룹최저 false-pass·총량과 다른 분모 (그룹 다 충족인데 총량 부족 모순)
- file: graduation_center/v2/audit_v2.py:160-166
- 문제: 병합: 4개 리뷰. group_earned는 designated(중복인정·배정 전 전체)로 합산하나 cc['earned']=fusion_effective(=fusion_base+dup_cr+to_fusion, 한도초과 겹침을 제1전공으로 돌린 배정값)다. 두 모집단이 달라 Σgroup_earned=designated_total != fusion_effective. 재현(미래모빌리티+모빌리티데이터 2023): 겹침 13과목 전부 A그룹·전공필수와 겹쳐 한도초과 27학점이 전부 제1전공 배정(to_fusion=0) → 화면 'A그룹 39/12 ✅, B그룹 12/12 ✅'인데 융합 총계 '24/36 ⚠️12 부족'. 채점자가 즉시 지적할 모순. 파급: pipeline.py:105-107 마크다운 자기모순, risk.py:79-86 eff_gap의 그룹 gap이 0으로 깔려 과소평가, planner build_unified_candidates:430-445 short=set(group_gaps) 비어 부족그룹 정렬 무력, GraduationV2.jsx:110 shortGroups도 동일.
- 수정: group_earned/group_checks를 배정(dup_ids·to_primary/to_fusion) 산출 이후로 옮겨 재산출: 융합 산입 집합 = (non-overlap designated) ∪ (dup 양쪽인정 overlap) ∪ (to_fusion 배정 overlap)을 그룹별 합산. to_primary로 빠진 overlap은 그룹 earned에서 제외 → Σgroup_earned==fusion_effective 보장. risk/markdown/planner/프론트가 같은 배정 위에서 일관.

## [HIGH] [REGRESSION] [연계융합 #3] 프론트 ConvergenceBlock fits가 그룹최저(per_group_min) 무시 + 상단 전공게이지·리스크와 미연동 → 한 화면 모순 수치
- file: frontend/src/components/GraduationV2.jsx:105, 127-140, 581, 652-666
- 문제: 병합: fits 그룹최저 누락 + 3-way 재배정 미연동 2건. (1) fits=!overCap && primaryCr>=primary_required && fusionCr>=cc.required(105)는 융합 '총' 학점만 보고 그룹별 최저(다전공12/부전공6)를 검사하지 않아, 총학점은 넘지만 특정 그룹 미달인데 '✅ 둘 다 충족'(초록) 표기. 백엔드 risk.py:78-86은 group_short를 등급에 반영해 B/C로 강등 → 카드(초록)와 등급(위험) 모순. (2) ConvergenceBlock은 sel을 로컬 state로 관리하며 primaryCr/fusionCr를 자체 재계산하나, 상단 전공 게이지(581, major_effective)·종합 리스크·'남은 요건'(657)은 백엔드 기본배정에 고정돼 사용자가 겹침을 옮겨도 갱신 안 됨. StatBox '제1전공 부족'인데 위 게이지 '충족' 동시 표시.
- 수정: fits에 (cc.group_checks||[]).every(g=>g.gap<=0) AND 조건 추가(단 #연계융합 #2 수정으로 group_checks가 배정 반영값이어야 함). 재배정은 sel 변경 시 onChange로 (program_id별 to_fusion/effective)를 부모로 끌어올려 전공 게이지 earned=raw-Σto_fusion, 융합·남은요건·리스크를 그 값으로 파생; 또는 재배정 시 백엔드 audit 재호출. 최소한 sel≠기본일 때 '재배정 반영: 졸업사정 다시 실행' 안내로 모순 노출 차단.

## [MEDIUM] [연계융합 #4] major_effective에 음수 가드 없음
- file: graduation_center/v2/audit_v2.py:269
- 문제: 병합: 다수 리뷰. major_effective = round(earned['전공'] - to_fusion_total, 1)에 max(0.0,...) 가드가 없다. 연계융합 #1 이중차감과 결합 시 to_fusion_total>earned[전공]이면 전공 이수학점이 음수로 집계돼 area_gap(required-음수)을 부풀리고 전공부족·초과학기·리스크를 과대평가. 단일 융합이라도 배정 로직 변경 시 안전망 부재.
- 수정: major_effective = max(0.0, round(...)) 하한 0으로 막고, 근본적으로는 연계융합 #1의 전역 배정으로 to_fusion_total이 전공 이수학점을 넘지 않게 보장.

## [MEDIUM] [REGRESSION] [연계융합 #5] overlap/primary_base가 designated 전체(일반선택 재분류 포함)를 전공으로 가정 → primary_base 음수/이중차감
- file: graduation_center/v2/audit_v2.py:153, 168-169, 213
- 문제: 병합: 5개 리뷰. designated/overlap 판정은 requirement_area를 보지 않고 course_id[:5]만 본다(교양 GYO만 제외, 일반선택 포함). verification.py:57-58은 선택전공 카탈로그 미매칭 전공선택을 '일반선택'으로 재분류한다. 즉 prefix는 제1전공과 겹치지만 일반선택으로 재분류된 과목이 overlap에 잡혀, primary_base=primary_major_earned(=earned['전공'])-overlap_cr에서 전공 earned에 없는 학점이 차감돼 primary_base가 부당히 깎이거나 음수(재현 -11~-12). 이후 dup_cr·to_primary로 자기보정되기도 하나 cap을 채워 flex가 줄면 p_need/to_fusion이 어긋난다. 결정론 회계 전제(overlap=전공 이수 겹침)가 데이터로 깨짐.
- 수정: designated/overlap을 requirement_area=='전공'으로 인정된 겹침으로 한정하거나, primary_base 차감에서 overlap 중 전공 earned에 실제 포함된 학점만 빼고 primary_base=max(0,...)로 클램프. 일반선택 재분류 과목을 융합 designated로 인정할지 정책을 명시적으로 결정해 일관 적용.

## [MEDIUM] [REGRESSION] [연계융합 #6] to_primary/to_fusion·planner 융합후보 선택이 그룹최저를 보장하지 않아 그룹 부족을 인위적으로 유발/미겨냥
- file: graduation_center/v2/audit_v2.py:228-238; graduation_center/v2/planner.py:430-496
- 문제: 병합: 2건. (1) flex를 제1전공 필요분까지 무조건 to_primary로 먼저 돌려(228-235) 특정 그룹 기여가 사라져 그룹최저를 깨는데 반대 배정을 탐색하지 않음. (2) build_unified_candidates는 융합 부족을 need=max(cc.gap,Σgroup_gaps)로 잡지만 selection 루프(489-496)는 acc(총학점)만 보고 그룹별 quota를 추적하지 않아 '총 need는 채웠지만 부족 그룹은 미충족'인 후보집합이 나올 수 있다. 연계융합 #2로 group_gaps가 0으로 깔리는 현 상태에선 short도 비어 정렬조차 무력 → 로드맵을 다 따라도 그룹최저 미충족으로 졸업불가가 남는데 feasible=True. audit_v2.py:107-113 TODO가 이미 한계 인지.
- 수정: 선택 루프에서 그룹별 잔여 quota를 추적해 부족 그룹 과목을 우선 소진 후 총 need 보충. 선행으로 연계융합 #2를 고쳐 group_gaps가 배정 반영값이 되게. flex를 to_primary로 돌릴 때 그룹최저를 가급적 보존하도록 순서 조정하거나 위반 시 note/risk 명시.

## [MEDIUM] [연계융합 #7] dedup(seen)이 융합 필요과목을 필수지정 이름충돌로 누락 → 융합 그룹요건 미반영
- file: graduation_center/v2/planner.py:478-496
- 문제: 단일 전역 dedup seen(normalize_name)이 우선순위 순(필수지정1→융합2→전공3)으로 채워져, 미이수 필수지정과 동명인 미이수 융합과목이 있으면 융합 pool에서 skip된다. mirae_mobility 2025 필수명과 mobility_data_convergence가 5개 충돌(Python프로그래밍·자동차모빌리티기초·기초선형대수·자료구조및알고리즘·모빌리티실험및실습). X를 한 번 들으면 양쪽 동시충족인데, 로드맵은 '전공/필수지정'으로만 표기해 융합 그룹 충족으로 연결 못 하고 대체후보도 제안 못 함. 융합 acc가 그 과목 분만큼 다른 과목으로 메워져 pool 부족 시 그룹최저 미충족 잔존.
- 수정: 융합 필요과목이 필수지정과 이름충돌 시 단일 전역 dedup으로 떨구지 말고 (a)satisfies/assignment를 '필수지정+융합 A그룹' 다중 귀속으로 표기하거나 (b)dedup을 요건(req)별 scope로 분리해 융합 그룹 카운트를 별도 유지. 최소한 skip될 때 그 항목의 그룹 충당분을 fusion need에서 차감하거나 '이 과목이 융합 A그룹도 충족' 가정을 assumptions에 추가.

## [HIGH] [REGRESSION] [초과학기 #1] project_overflow가 연계융합·핵심교양 영역별 부족을 shortfall에 미반영 → blocked인데 overflow=None (초과학기 카드 사라짐)
- file: graduation_center/v2/planner.py:63-96, 616-625
- 문제: 병합: 5개 리뷰(검토차원 #12). project_overflow의 shortfall=max(total_gap, Σarea_gaps.gap)인데 area_gaps는 전공·기초/핵심교양 총계·자유교양만 본다. (1)핵심교양 영역별 부족(core_area_gaps)과 (2)연계·융합전공 부족(convergence_checks gap·group_checks)은 area_gaps에도 total_gap에도 없다(융합전공은 졸업최저 130에 미포함 오버레이). 따라서 총학점·영역은 채웠지만 융합/핵심세부영역만 부족해 졸업이 막힌 학생은 build_unified_candidates가 후보를 selected에 넣고 plan_greedy가 잔여학기에 못 넣어 status='blocked'·feasible=False가 되는데, ov=overflow or project_overflow(...)가 둘 다 None → blocked인데 초과학기 카드 미표시(GraduationV2.jsx:702). pipeline 트레이스는 '실현불가(초과학기 필요)'·'미배치→초과학기'로 점등되지만 정량 시나리오(부족학점·필요학기·예상졸업)는 사라짐 — feature fd483e0의 핵심 회귀.
- 수정: project_overflow shortfall에 핵심 영역별 부족 합과 연계융합 부족(conv_short=Σ max(cc.gap, Σgroup부족))을 포함. 더 견고하게는 run_planner가 plan_greedy의 unplaced 학점 합을 shortfall 하한으로 넘겨 project_overflow가 그 값으로 산출 → area_gaps 누락원과 무관하게 미배치 총량과 정합.

## [HIGH] [REGRESSION] [초과학기 #2] capacity 모델 3중 불일치 — project_overflow·risk·_ordered_terms의 계절학기 가산·학기상한 폴백이 제각각
- file: graduation_center/v2/planner.py:76-95; graduation_center/v2/risk.py:62-67
- 문제: 병합: 검토차원 #11·#12 다수. 같은 '학기 수용량'을 세 곳이 다르게 계산한다. (1)risk.py:62-67은 capacity=remaining*term_cap+PREV_GPA_BONUS+SEASONAL_TERM_CAP(계절 1회만), term_cap 폴백 18 하드코딩. (2)project_overflow(76-81)는 remaining*cap+bonus만, 계절 미가산, cap 폴백=regular_term_cap(17/18/19). (3)_ordered_terms(357-377)는 정규학기 사이마다 계절학기(6학점)를 넣어 remaining=2면 계절 2개(12학점) 배치 가능. 미래모빌리티(136학점) 정규상한 19인데 risk는 18로 과소→경계에서 risk D-강등인데 plan_greedy는 19/계절로 feasible=True 모순. risk는 사용자 max_credits_per_term을 상한 없이 신뢰해(GraduationV2.jsx:445 무제한 number) 사용자가 30 넣으면 졸업불가를 안전으로 오판. 프론트가 항상 18을 보내 데모선 가려지나 API 직접호출·도메인규칙(제32조)과 어긋남.
- 수정: 수용량을 단일 헬퍼 term_capacity(context, profile)로 추출해 risk·project_overflow·_ordered_terms가 동일 규칙(계절 가산 정책 일치 + term_cap=min(사용자값, regular_term_cap(total_credits_min)) 클램프, 폴백도 regular_term_cap) 공유. risk가 profile을 받도록 시그니처 확장. roadmap_feasible가 risk에 이미 전달되므로 capacity-기반 D-강등은 feasible 결과에 양보하는 것도 방법.

## [HIGH] [로드맵 #5] remaining_semesters=0과 current_term 미입력을 _ordered_terms가 구분 못 해 잘못된 안내·feasible=null (졸업직전 학생 재현)
- file: graduation_center/v2/planner.py:357-377, 592-599
- 문제: 병합: 2건. _ordered_terms는 current_term이 없으면 []를 반환하는데, current_term='2026-1'이라도 remaining_semesters=0이면 while reg<0이 안 돌아 []를 반환한다. run_planner의 if not terms 분기(593-599)는 무조건 '현재 학기 미입력 — 학기 배치 생략'·feasible=None을 준다. 졸업 직전(마지막 학기, 잔여 0) 학생에 갭이 있으면 사실과 다른 '미입력' 메시지·feasible=None(프론트 GraduationV2.jsx:646 주황 보류)로 졸업불가를 보류로 오인. pipeline:54 feasible None→None이라 risk의 로드맵 D-트리거(risk.py:94)도 안 걸림. 프론트 '남은 학기'를 비우면 Number('')=0으로 쉽게 발생.
- 수정: 두 조건 분리: current_term is None → '현재 학기 미입력' 분기(feasible=None); current_term은 있고 selected 남았는데 terms 빈(remaining 0) → status='blocked', feasible=False, blocked_reason='잔여 정규학기가 없습니다' + overflow 설정해 risk 강등.

## [HIGH] [REGRESSION] [학번요람 #1] 연도해석 3경로 불일치: 영역최저는 정확매칭(미보유→2025 기본값), 필수명·라벨은 le-fallback → 한 학생에 두 요람 혼합
- file: graduation_center/v2/catalog.py:102-133; graduation_center/v2/audit_v2.py:300-314, 32-44; graduation_center/v2/planner.py:386-395
- 문제: 병합: 검토차원 #9 다수. 연도해석 경로가 3개·폴백 규칙이 다르다. (1)_required_names_for_year(audit_v2:42-44)·_required_meta(planner:388) — '입학연도 이하 가장 가까운 요람' le-fallback. 단 이 둘조차 범위밖(year<최저요람)에선 audit는 avail[0], planner는 avail[-1]로 서로 다른 요람 픽(불일치 → 미이수 필수가 credits 3.0·terms 기본값으로 degrade). (2)_requirements_by_year(catalog:110-111) — 정확매칭만, 미보유면 None→graduation_requirements.json(2025). requirements_by_year.json엔 mirae 2023만. 실측: admission_year=2024 → 라벨 '2023 요람'(compute_audit:314 덮어씀)인데 기초교양 최저 7·일반선택 50(2025 기본값), 2023이면 별표5 기초교양 8·일반선택 47이어야 함. 필수명·gen_basic은 2023, 영역최저는 2025 — 졸업사정 핵심 수치와 표기 근거가 어긋남.
- 수정: 연도해석을 단일 헬퍼로 통일: _requirements_by_year도 le-fallback 사용, 실제 적용연도(pick)를 한 곳에서 산출해 area_min·required_names·gen_basic·meta·applied_yoram 라벨 모두 그 pick으로. _required_meta의 범위밖 픽도 audit과 동일하게(le[-1] if le else avail[0]). 라벨은 assemble에서 한 번만, compute_audit 덮어쓰기 제거. 데이터 미보유 연도 폴백 시 '(요람 미보유→근사)' 확신도 표기.

## [MEDIUM] [핵심교양 #1] 핵심교양 총요건을 영역최저 합으로 산출(17) — 공식 총요건 15·area_min·structured_check와 모순, 동일 결손 이중경고
- file: graduation_center/v2/audit_v2.py:277, 282-287
- 문제: 병합: 5개 리뷰. core_total_required=sum(overrides.get(a,core_min) for a in gen_areas)면 미래모빌리티(소통 override 5+나머지4×3=17). 그러나 gen_ed_catalog total_min_credits=15, graduation_requirements 핵심교양=15, profile.area_min['핵심교양']=15. 소통 override는 core_area_gaps에서 이미 반영되는데 총요건에도 더해 이중 적용. 재현: 핵심교양 정확히 15(소통5+나머지10) 학생이 area_gaps required=17·gap=2 유령부족, core_area_gaps에서도 같은 결손 경고 → 동일 2학점 이중경고. risk.py max_area_gap에 2가 섞여 등급 강등. audit_v2 docstring(4-5)의 'structured_check와 동일 산식' 계약 위반. 277의 `or float(profile.area_min...)` 폴백은 gen_areas 비지 않는 한 도달 불가.
- 수정: 핵심교양 area_gap의 required는 공식 총최저(profile.area_min['핵심교양']=15 또는 by-year)를 쓰고, 소통5 등 영역별 최저는 core_area_gaps에서만 hard-constraint로 강제. 총량 게이지와 영역 게이지가 같은 결손을 중복카운트하지 않게 분리.

## [MEDIUM] [로드맵 #6] plan_greedy가 max_courses_per_term을 enforce 안 함 — 한 학기 8과목 등 비현실적 배치
- file: graduation_center/v2/planner.py:533
- 문제: _try_place는 학점상한(used+credits<=cap)만 검사하고 과목 수 상한을 보지 않는다. StudentContext.max_courses_per_term(기본 6, models_v2.py:24)이 정의돼 있으나 결정론 플래너·validate_roadmap 어디에서도 enforce되지 않는다. 2학점 8과목=16학점이 19 cap 아래라 한 학기 8과목 배치(실측). _slot_chunks(3학점 분할) 교양 슬롯까지 더해지면 한 학기 과목수가 비현실적으로 커져 데모 로드맵 품질을 떨어뜨림.
- 수정: _try_place 배치조건에 len(bucket[lab]) < context.max_courses_per_term 추가(context를 plan_greedy 인자로 전달), 검증기에도 term별 과목수 상한 체크 추가.

## [MEDIUM] [로드맵 #7] major_effective(to_fusion 차감)가 total_gap엔 미반영 — area_shortfall이 total_gap보다 커져 초과학기가 '이미 이수한 학점 재배정'을 추가이수로 이중 요구
- file: graduation_center/v2/audit_v2.py:268-287, 328; graduation_center/v2/planner.py:72-73
- 문제: compute_audit은 to_fusion만큼 전공 area_gap을 부풀리지만 total_earned/total_gap은 원본 그대로(이게 맞음 — 학점은 사라지지 않음). 그러나 project_overflow는 area_shortfall=Σ(area gap)을 쓰고 이 전공 gap에는 to_fusion으로 부풀린 분이 포함된다. 이미 이수한 겹침을 융합으로 돌리면 전공 gap이 커져 area_shortfall>total_gap → 초과학기가 '새 전공과목을 더 들어라'로 산출되나 실제로는 재배정일 뿐. risk.py:29 max_area_gap도 부풀린 전공 gap을 보고 과대 강등.
- 수정: to_fusion은 이미 이수한 겹침의 배정 이동이므로 overflow/risk의 '추가 이수 필요 학점'에 그대로 합산하지 말 것. (a)전공 gap을 '추가 신규이수'와 '재배정 명목 gap'으로 분리하거나 (b)overflow는 total_gap 기준만 쓰고 area gap은 영역요건 표시에만 사용하도록 일원화.

## [MEDIUM] [5자리 prefix #1] course_id[:5] 절단으로 서로 다른 과목을 동일/이수로 오판 (교내·교차 프로그램 충돌)
- file: graduation_center/v2/audit_v2.py:132,149,152-153,168,181,316-317; graduation_center/v2/planner.py:414,505,513,515,536
- 문제: 병합: 3건(low/high 혼재 → 데이터로 충돌 확인되어 medium 상향). audit convergence designated/overlap·required 매칭·planner confirmed-dedup·placed_at·선수 모두 course_id[:5]로 식별하는데 충돌이 실재. 검증: prefix 01568이 mirae=0156810 C프로그래밍, dsci=0156812 객체지향프로그래밍(서로 다른 과목). mirae 학생이 C프로그래밍 이수+dsci 다전공 선언 시 designated 판정 `c.course_id[:5] in conv_prefixes`가 01568을 dsci에 매칭해 C프로그래밍을 dsci 융합과목으로 오산입 → 융합 earned 과대·gap 과소. 교내 충돌도 ai_bigdata 03650={S-TEAM Class, 사제동행세미나}(검증), mirae 16216 동일 — 선수/dedup에서 한쪽 이수가 다른 쪽을 '이수'로 오판해 전공후보 풀에서 제외 가능. 데모 happy-path도 학번/전공 조합에 따라 조용히 틀어짐.
- 수정: 과목 식별을 7자리 full course_id로 전환(권장). prefix 매칭이 불가피하면 (prefix, 정규화이름) 쌍으로 비교하거나 충돌 시 7자리 fallback. designated/overlap/confirmed-dedup·plan_greedy 선수·placed_at을 full course_id 집합으로 비교하고, prefix는 같은 카탈로그 내 명칭드리프트 보정용으로만 제한.

## [LOW] [로드맵 #8] plan_greedy quota pool 중복이름 skip 시 충당학점을 acc에 미가산해 전공 과배치
- file: graduation_center/v2/planner.py:488-496
- 문제: pool 요건 충당 루프에서 seen에 있는 이름은 continue로 건너뛰며 그 과목 credits를 acc에 더하지 않는다. 필수지정으로 이미 selected된 과목이 전공-부족 pool에도 등장하면 그 학점이 need 충당에 기여 못 해 추가 과목을 더 끌어온다(전공 과배치). feasible은 안 깨나 불필요한 과목이 들어가 정형성/품질 저하.
- 수정: continue 전에 '이미 selected된 동일 과목이 이 요건 영역을 충당하면' acc에 가산하거나, 요건별 need에서 선행 selected 학점을 미리 차감한 잔여 need로 pool을 채울 것.

## [LOW] [로드맵 #9] 미이수 필수지정 학점을 무조건 '전공' gap에서 차감 — 비전공 필수 학과에서 과소/과대 차감(현 시드는 안전)
- file: graduation_center/v2/planner.py:428, 446-450
- 문제: 병합: 4건. build_unified_candidates는 모든 missing_required_names를 area='전공'으로 생성(428)하고 req_major_credits를 전공 major_gap에서 차감(중복선택 방지). 그러나 missing_required_names는 학번 요람 필수명(코드무관)에서 와 이론상 기초교양 등 비전공 과목 포함 가능(예: 일반물리/공학기초수학류, 또는 카탈로그 미존재 '미래모빌리티기초'). 현 시드(mirae/ai)는 필수가 카탈로그상 전부 requirement_area='전공'이라 안전(검증). 비전공 필수가 들어오면 전공 gap 과소차감 + area 귀속 오류.
- 수정: missing_required 항목에 실제 requirement_area(카탈로그/요람 메타)를 부여하고, major_gap 차감은 area=='전공'인 필수에만 적용. 비전공 필수는 해당 영역 갭에서 처리.

## [LOW] [로드맵 #10] plan_greedy가 first-fit-decreasing으로 앞 학기에 학점 front-load + term_risk high 미산출
- file: graduation_center/v2/planner.py:524-538, 565-566
- 문제: 병합: 2건. _try_place가 항상 가장 이른 적합 학기에 배치해 30학점/2학기가 18/12로 쏠림(15/15 아님). 순수 FFD라 드물게 실제로 적합한 학점multiset을 false-blocked 처리도 가능(3학점·18cap 현실에선 희박). 또 term_risk='medium' if used>cap-3 else 'low'로 high를 절대 산출 안 해 19/19 학기도 high 미표기 — 모델은 high 허용·프론트도 대비. '빡센 학기' 경고가 약함.
- 수정: 배치를 best-fit/round-robin으로 균형화하거나 2차 패스로 term_credits를 레벨링(offered_terms·선수 순서 존중). term_risk를 used>=cap-0.01→'high', cap-3 이내→'medium', 그 외 'low' 3단계로.

## [MEDIUM] [리스크 #1] 졸업평점 미달(gpa_min_met='no')이 C로만 강등 — 확정적 졸업불가인데 16학점 부족(D)보다 약하게 평가
- file: graduation_center/v2/risk.py:88-90
- 문제: 학점·필수·영역 모두 충족해도 졸업평점(2.0) 미달이면 졸업 원천 불가인데 risk는 grade를 C(severity 20)로만 올린다. 재현: total_gap=0·전 영역 충족·gpa_min_met='no' → grade C, score 80. 총학점 16부족만으로도 D. 확정적 하드 블로커가 '학점 부족'보다 가볍게 표시돼 프론트 히어로가 낙관적으로 보임.
- 수정: gpa_min_met=='no'는 _worse(grade,'D')로 강등(또는 최소 다른 D 트리거와 동급)하고 detail에 '평점 미달 시 학점 충족과 무관하게 졸업 불가' 명시.

## [LOW] [리스크 #2] 미이수필수(severity 18/10)와 전공 영역갭(8~20)이 동일 부족분을 score에서 이중 감점
- file: graduation_center/v2/risk.py:42-58
- 문제: 미이수 필수지정 학점은 전공 영역갭에도 포함되므로 '전공필수' reason과 '영역' reason이 같은 부족분을 두 번 깎는다. 재현: '필수 9과목 미이수'(sev18)+'전공 24부족'(sev20) 동시발화 → score 과도하게 낮음. grade는 worst-trigger라 동일(D)이라 영향 적어 low이나 연속지표(score) 왜곡.
- 수정: 동일 부족분 이중계상 방지: 미이수 필수 severity를 전공 영역갭과 상호배타로(둘 중 큰 것만) 적용하거나, 미이수 필수는 등급 트리거로만 쓰고 score 가중은 영역 갭에 일임.

## [LOW] [기초교양 #1] _gen_basic_view 부분일치(substring)로 무관 과목이 필수 충족 처리 / 한 과목이 복수 필수 충족
- file: graduation_center/v2/audit_v2.py:91-94
- 문제: 병합: 2건. taken = any(key in t for t in taken_norm)로 필수명을 학생 과목명의 부분문자열로 매칭(택1·ABEEK 흡수 의도). 부작용: '글쓰기' key가 '과학과글쓰기'·'기술글쓰기'에 포함돼 false-positive 충족(실측 '글쓰기' in normalize('과학과글쓰기')=True), 한 과목이 여러 필수를 동시 taken 처리 가능(1:1 소비 미강제). 데모 데이터는 즉시 충돌 없으나 데이터 추가 시 구조적 오탐.
- 수정: 매칭에 소비된 학생 과목을 set으로 제거해 1:1 소비 강제하거나, 부분일치 대신 정규화 완전일치+명시적 alias/접미사 화이트리스트(택1 그룹·로마숫자·ABEEK)에만 substring 적용.

## [LOW] [연계융합 #8] 융합전공+제1전공 동시부족 시 공유 미이수 과목 중복인정 여지 무시하고 과다 계획(over-plan)
- file: graduation_center/v2/planner.py:430-456, 478-497
- 문제: build_unified_candidates는 융합 gap(pri2)·전공 gap(pri3)을 별도 quota로 뽑고 normalize_name dedup으로 상호 배제. 그러나 앞으로 들을 공유과목(양쪽 카탈로그)은 잔여 중복인정 한도(cap-double_used)에서 동시 인정 가능. 현재는 한쪽에만 배정+다른 쪽 또 다른 과목 계획 → 잔여 한도만큼 불필요하게 더 계획. 재현: 전공 gap 42+융합 gap 30이 별개 72학점으로 계획(공유 0). audit_v2:107 TODO가 의도된 한계로 명시. 프로토타입에서 '과목/학기 과다'로 품질 저하.
- 수정: 잔여 중복인정 한도 범위에서 공유 미이수 과목을 양쪽 gap에 동시 산입하도록 후보선택 보정. 최소한 selected 단계에서 공유과목 우선선택해 두 quota를 같은 과목으로 동시 차감. 데모 우선순위는 낮음.

## [LOW] [연계융합 #9] group_checks가 designated 원시합이라 to_primary로 빠진 겹침을 그룹충족에 중복계상
- file: graduation_center/v2/audit_v2.py:160-166, 235-238
- 문제: group_earned는 designated 전체를 합산하나 한도초과 겹침 일부는 to_primary로 제1전공에 빠져 융합엔 미산입. 어떤 그룹의 group_earned가 to_primary 분을 포함해 per_group_min을 통과한 듯 보이는데 fusion_eff엔 안 들어감 — 그룹최저 판정과 총 융합인정학점이 다른 산식(원시 vs 배정). 연계융합 #2와 같은 뿌리. 데모 happy-path(겹침 적음)는 거의 미발현.
- 수정: 연계융합 #2와 함께 해결: group_earned를 배정 반영값(중복인정+to_fusion만 그룹에 산입)으로 재산출하거나, group_checks가 '원시 designated 기준'임을 필드명/note에 명시해 fusion_eff와 다른 기준임을 분명히.

## [LOW] [연계융합 #10] verification 재수강 '최신 이수만 포함'이 성적/이수여부와 무관해 직전 미이수 학기를 최신으로 채택 가능
- file: graduation_center/v2/verification.py:64-69
- 문제: 동일 코드 여러 학기 시 _term_order로 가장 늦은 학기 1건만 포함. 수강내역에 성적 컬럼이 없어 F·미이수 후 재수강과 정상이수 후 성적향상 재수강을 구분 못 함. 최신 학기가 실제 미이수였고 직전이 이수면 잘못된 학기 포함. HITL로 조정 가능하나 기본이 항상 '최신'이라 오해 소지. 설계상 의도된 단순화라 low.
- 수정: 기본 포함을 '최신' 대신 사용자 확인 필요로 두거나, possible_retakes에 어느 학기를 기본 포함했는지 명시해 HITL에서 즉시 보이게.

## [LOW] [정리 #1] audit_v2 note의 죽은 코드 'len(flex)*3 if False else ...' + 미사용 rec_keys
- file: graduation_center/v2/audit_v2.py:199-203, 240
- 문제: 병합: 8개 리뷰가 같은 줄 지목. 240 note f-string에 `{len(flex)*3 if False else round(sum(c.credits for c in flex),0):.0f}` — 항상 else만 평가되는 죽은 삼항. 추가로 199-203의 rec_keys.add(id(c))는 이후 전혀 미사용(죽은 코드). 동작엔 영향 없으나 결정론 보고서 생성 코드의 가독성·신뢰성·리뷰비용 저해.
- 수정: note를 `round(sum(c.credits for c in flex),0):.0f`로 단순화하고 미사용 rec_keys 누적 제거.

## [LOW] [REGRESSION] [프론트 #1] WorkflowGraph 범례가 점등되지 않는 'LLM 판단' kind를 광고
- file: frontend/src/components/WorkflowGraph.jsx:8, 86-88
- 문제: 병합: 5개 리뷰. 거짓 llm/repair 노드 제거 후 pipeline의 node_trace는 tool/hitl/validator만 방출(NODES에 llm kind 없음). 그러나 KIND.llm이 남아 있고 범례 필터가 '분기'만 제외해 화면에 '✦ LLM 판단(파랑)'이 항상 노출. 실제 파란 노드가 없어 채점자에게 'LLM 노드가 있다/빠졌다'는 오해 — 루브릭의 ReAct/결정론 시각요소와 직결.
- 수정: 범례를 trace에 실제 등장하는 kind만 렌더하도록 필터하거나, 결정론 통합 플래너 현 설계에 맞춰 KIND.llm 항목 삭제. (LLM 플래너 재가동 계획이면 해당 노드를 NODES/trace에 실제 추가.)

## [LOW] [프론트 #2] blocked 로드맵에서 blocked_reason·relaxation_hint가 화면에 2번 렌더링
- file: frontend/src/components/GraduationV2.jsx:639, 691-694
- 문제: 병합: 2건. run_planner은 status='blocked'면 항상 feasible=False(planner.py:623). 프론트는 639(status==='blocked')와 691(feasible===false && blocked_reason)에서 같은 blocked_reason+relaxation_hint를 빨강/주황으로 중복 출력. blocked는 두 조건 동시 충족이라 중복 노출(데모 어색).
- 수정: 691 가드를 status!=='blocked'로 좁히거나, 639 블록을 status==='blocked' && terms.length===0(부분배치 없을 때)으로 제한해 정확히 한 번만 표시.

## [LOW] [프론트 #3] ConvergenceBlock defaultSel epsilon·의존성 — 백엔드와 부동소수 경계 불일치 + 사용자 선택 리셋
- file: frontend/src/components/GraduationV2.jsx:85-98
- 문제: 병합: 2건. (1)defaultSel(89) `dup+ov[i].credits <= cap`에 epsilon 없음(백엔드 audit_v2:226은 <= cap+0.01) → 1·2학점 누적 경계에서 한 과목을 dup에서 제외해 백엔드 earned와 StatBox 표시 어긋남. (2)defaultSel은 useMemo([cc])라 cc 새 객체마다 useEffect(98)가 setSel로 사용자 3-way 선택을 초기값으로 되돌림 — 부모 리렌더 시 조정이 소리없이 리셋. 데모 happy-path 영향은 작으나 입력 데이터흐름 추적성 약점.
- 수정: epsilon을 `<= cap + 0.01`로 맞추거나 프론트 재계산을 없애고 백엔드 배정값(double_used/to_fusion)을 초기 상태로 사용. 수동 조정 플래그로 조정 후 defaultSel 덮어쓰기 방지(또는 배정 상태를 부모로 끌어올림).

## [LOW] [로드맵 #11] current_term 형식 검증 부재 — '26-1' 같은 2자리 연도가 비정상 학기 라벨 생성
- file: graduation_center/v2/planner.py:357-377
- 문제: _ordered_terms/_allowed_terms/_nth_regular_term이 current_term을 'y-s'로 split. '2026'(대시 없음)은 split 실패→[]→feasible=None(허용 가능). 그러나 '26-1'은 예외 없이 year=26으로 통과해 '26-2','27-1' 등 무의미한 학기 라벨 생성(크래시 없지만 무의미 출력). 입력 검증 부재.
- 수정: current_term을 정규식 r'^20\d{2}-[12SW]$'로 검증해 미충족 시 feasible=None 안내 분기로 보내거나 프론트 입력단에서 형식 강제.

## [LOW] [데드코드 #1] validate_roadmap(LLM 경로) 선수검사 키가 plan_greedy와 불일치 — 현재 프로덕션 데드코드, 재활성화 시 오작동
- file: graduation_center/v2/planner.py:266-353
- 문제: validate_roadmap은 prereq를 7자리 그대로 비교(334-337)하나 라이브 경로 plan_greedy는 5자리 prefix로 비교. run_audit은 plan_roadmap/validate_roadmap/build_planning_context를 호출하지 않아(grep 확인) 이 LLM 경로 검증기는 프로덕션 데드코드. 추후 ReAct/LLM 배치 경로를 되살리면 두 경로의 선수 동일성 규칙(5 vs 7자리)·name-only 추적 부재가 어긋나 서로 다른 합/불합 판정. 당장 라이브 회귀 아님.
- 수정: LLM 경로를 보존만 한다면 deprecated 주석/가드를 달고, 되살릴 때 plan_greedy와 동일 동일성 규칙(7자리 통일 권장)·name-only 보조키 매칭을 공유 헬퍼로 추출해 한 곳에서 관리.
