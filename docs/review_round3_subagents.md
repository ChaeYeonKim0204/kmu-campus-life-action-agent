# 적대리뷰 라운드3 종합 (서브에이전트 18, raw 111, HIGH 12, REG 12)

## [HIGH] [REG] [로드맵·HIGH·데모파괴·회귀] 일반선택 need가 필수지정·연계융합 학점을 차감하지 않아 총학점 이중계상 → 멀쩡한 학생이 초과학기/blocked로 거짓 표시
- file: graduation_center/v2/planner.py:510-514
- 문제: general_need = max(0, total_gap - area_floor_gap)인데 area_floor_gap은 HARD_AREAS의 floor 갭만 합산한다. 그러나 build_unified_candidates는 (1) 미이수 '필수지정'(전공영역이 이미 충족이면 area_floor_gap에 안 잡힘)과 (2) 연계융합 부족 need(area_gaps에 전혀 없음)도 후보로 추가하고, 이 학점들도 졸업 총학점에 산입된다. general_need가 이를 빼지 않으므로 같은 total_gap을 일반선택 슬롯과 필수/융합 후보가 '이중'으로 메운다. 결과 selected 합이 부풀고 plan_greedy의 unplaced가 부풀려져 _overflow_from_credits가 거짓 초과학기/blocked를 낸다. 라이브 데모에서 졸업요건을 사실상 충족한 학생이 '초과학기 필요/실현불가'로 표시될 수 있다. (18인 리뷰 중 단독 식별, 코드로 확인.)
- 수정: general_need를 area_floor_gap뿐 아니라 reqs에 이미 들어간 '총학점 산입' 후보 학점(필수지정 학점 + 각 convergence need 중 총학점 산입분)까지 차감해 산출하라. 가장 견고한 방법: 모든 reqs(필수·융합·교양)를 먼저 구성해 그 selected/credits 합을 구한 뒤 general_need = max(0, total_gap - 그 합). 연계전공처럼 총학점 미산입 케이스는 차감 대상에서 제외.

## [HIGH] [REG] [연계융합·HIGH·데모파괴·회귀] 프론트 그룹최저(groupsOk)가 백엔드 기본배정 group_checks에 고정 — 3-way 재배정에 반응 안 해 fits가 자기모순(거짓 충족/거짓 미충족)
- file: frontend/src/components/GraduationV2.jsx:106-107,112,141-142
- 문제: 라운드2 fix#6이 fits에 그룹최저를 넣었으나 미완성이다. fits의 primaryCr·fusionCr·dupCr(101-103)은 사용자 sel(3-way)에 reactive하게 재계산되지만 groupsOk(106)·shortGroups(112)·경고문(142)은 백엔드가 '기본 배정' 시점에 1회 산출한 정적 cc.group_checks를 그대로 읽는다(코드 확인). 사용자가 겹침과목을 fusion→primary로 옮기면 그 그룹 융합 산입이 per_group_min 아래로 떨어질 수 있는데 groupsOk는 갱신되지 않아, fits가 ✅'그룹별 최저 포함 충족'을 거짓 유지하거나 반대로 충족인데 경고를 유지한다. fits 세 조건 중 둘은 live·하나는 static이라 셀렉터를 만지는 순간 화면 수치가 모순. (리뷰 18인 중 ~13건이 이 한 결함을 중복 보고 — 단일 결함으로 병합.)
- 수정: sel 기준으로 그룹별 earned를 클라이언트에서 재계산하라. overlap_courses에 group이 이미 실려 있으므로(audit_v2.py:209-211), 융합전용(taken && !overlap) 과목의 group별 합 + sel[i]∈{dup,fusion}인 overlap 과목의 group별 합을 더해 per_group_min과 비교한 groupsOkLive를 만들고 fits·경고·shortGroups·suggest를 그 값으로 구동(fusionCr와 동일한 sel 의존성). 백엔드 group_checks는 기본값 표시용으로만.

## [HIGH] [REG] [연계융합·HIGH·데모파괴·회귀] 그룹최저를 '배정된 융합 학점(fusion_courses)'으로 산출 → 그룹 과목 전부 이수해도 phantom 그룹부족(중복인정 한도와 커버리지 혼동)
- file: graduation_center/v2/audit_v2.py:237-244
- 문제: 라운드2 fix#1이 group_checks를 fusion_courses(비겹침+dup+fusion배정)만으로 재산출하게 바꿨으나, 그룹 최저는 '그 그룹 과목을 얼마나 이수했나(커버리지)'이지 '그 학점을 어느 전공에 인정시켰나'가 아니다. 코드 확인: group_earned(238-242)는 fusion_courses만 누적한다. 제1전공과 코드가 겹치는 그룹(예: A그룹이 제1전공 학과 과목)에서, 배정기가 겹침 과목을 제1전공 필요분으로 밀어내면 fusion_courses의 A그룹 학점이 dup 한도만 남아, 학생이 A그룹 전 과목을 raw로 이수했어도 group_checks가 gap>0의 phantom 부족을 낸다. risk.py:78-86이 이 group_short로 등급을 B/C로 강등. 제77조 중복인정 한도(인정 측면)와 그룹 최저(이수 커버리지 측면)를 혼동한 회귀이며 위 프론트 결함의 백엔드 뿌리다.
- 수정: group_checks(그룹 최저 충족)는 designated(이수한 융합과목 전체) 기준 커버리지로 산출하고, 학점 중복인정 한도(cap)·전공 배정은 총 36/18 충족 산식에만 적용하라. Σgroup==fusion_eff 불변식을 그룹 최저 판정 분모로 쓰지 말 것(그건 총량 표시용). 백엔드를 designated 커버리지로 고치면 위 프론트 항목도 같은 기준으로 통일된다.

## [HIGH] [REG] [연계융합·HIGH·데모파괴] 히어로 총학점(raw)과 전공 게이지(major_effective, 융합배정 차감)가 한 화면에서 모순 + 설명 부재
- file: graduation_center/v2/audit_v2.py:282,297; frontend/src/components/GraduationV2.jsx:553,585
- 문제: 전공 게이지 earned는 major_effective = earned['전공'] − to_fusion_total로 차감되는데(코드 확인: 282,297), 히어로(553)와 markdown(pipeline.py:94)은 raw total_earned를 그대로 표시한다. 다전공+융합배정 학생은 영역 게이지 합이 히어로 총학점보다 to_fusion_total만큼 작아지고, 그 차액이 어디 갔는지 화면 어디에도 주석이 없다. Gauge에 sub 프롭이 있으나 area_gaps 렌더(585)에서 전달하지 않는다. 채점 라이브 데모에서 '숫자가 안 맞는다'로 직격당하는 지점.
- 수정: 전공 게이지에 차감 근거를 노출('전공 인정 98 = 이수 125 − 융합 배정 27'), 또는 히어로 옆에 '※ 전공 일부 학점은 융합전공으로 배정 표시'. audit에 to_fusion_total을 노출해 프론트가 한 줄로 설명하게 한다. raw total_earned 자체는 졸업 총학점 기준으로 옳으므로 표시 방식만 정합화.

## [HIGH] [REG] [연계융합·HIGH·데모파괴·회귀] 융합 기본배정이 제1전공을 과도 우선해 '융합 N학점 부족·추가 이수 필요'를 거짓 표시(재배정만으로 충족 가능)
- file: graduation_center/v2/audit_v2.py:215-244
- 문제: 겹침 flex 배정이 p_need 충족(primary)을 최우선으로 하므로(코드 확인: 222-228), 제1전공 요건이 큰 학생은 한도초과 겹침이 전부 primary로 가고 융합엔 dup만 남아 fusion_eff·gap이 부족으로 나온다. 실제로는 3-way로 겹침을 primary→fusion 재배정만 하면 충족 가능(추가 이수 불필요)한데, 화면은 '추가 이수 필요'(GraduationV2.jsx:143)와 risk 강등을 그대로 노출한다. group_checks·gap·risk가 이 편향된 기본배정에서 산출돼 일관되게 틀린다(위 group_checks 항목과 동근).
- 수정: 기본배정을 '제1전공·융합 요건과 그룹최저를 동시에 만족시키는 실현가능 배정'으로(겹침 flex를 융합 요건/그룹최저 충족까지 먼저 fusion에 할당 후 잔여를 primary). 또는 gap/안내를 '재배정 가능 풀 포함 최선 배정' 기준으로 산출하고 '재배정만으로 충족 가능' 플래그를 별도 표기.

## [HIGH] [HIGH·데모파괴] 교과목코드 5자리 절단 충돌로 미이수 필수가 거짓 충족 (S-TEAM Class 0365007 ↔ 사제동행세미나 0365008, 기본 데모 학과 ai_bigdata)
- file: graduation_center/v2/audit_v2.py:329-330; graduation_center/v2/planner.py:432,486
- 문제: ai_bigdata는 required_names_by_year에 없어 코드-prefix 폴백을 탄다(확인: by_year 키 ['mirae_mobility']만). 폴백은 confirmed_prefixes={c.course_id[:5]}, missing_ids=[cid for cid in required if cid[:5] not in confirmed_prefixes]로 5자리만 비교한다. 카탈로그에 prefix 03650을 공유하는 두 필수가 실재한다(코드 실행 확인: 0365007 S-TEAM Class·0365008 사제동행세미나, 둘 다 is_required). 학생이 0365007만 이수하면 03650이 confirmed에 들어가 0365008이 missing에서 빠져 졸업불가 필수가 '충족'으로 오판된다. 프론트 기본 program_id가 ai_bigdata(GraduationV2.jsx:215)라 데모 기본값에서 발생. build_unified_candidates의 confirmed_pref(432,486)도 동일 [:5]라 미이수여도 후보 누락.
- 수정: 코드-prefix 폴백을 7자리 전체 비교로: confirmed_full={c.course_id}; missing_ids=[cid for cid in required if cid not in confirmed_full]. 코드 변형 흡수가 필요하면 prefix가 아니라 카탈로그 by_code 정규화 매핑을 쓰되 같은 prefix의 별 과목(07/08)은 반드시 구분. confirmed_pref도 7자리 또는 이름+코드로 교정.

## [HIGH] [REG] [로드맵·HIGH·회귀] 초과학기 추정이 개설학기·선수 병목을 무시 — _overflow_from_credits가 미배치를 학점/cap으로만 환산해 과소추정
- file: graduation_center/v2/planner.py:398-413
- 문제: _overflow_from_credits는 extra=ceil(unplaced_credits/reg_cap)로만 초과학기를 낸다(코드 확인). 그러나 plan_greedy가 과목을 unplaced로 남기는 원인은 용량뿐 아니라 개설학기 제약(특정 학기에만 개설)·선수 위상 교착이다. 개설학기 병목이면 학점/cap 환산이 실제 필요 학기를 크게 과소평가한다(예: 가을학기에만 개설되는 5과목이면 학점상 1~3학기로 나와도 실제는 가을 4번 필요). 단일 용량 모델이 bottleneck을 구조적으로 과소추정. blocked일 때 사용자에게 낙관적 학기수를 제시.
- 수정: 초과학기는 동일 plan_greedy 배치기를 잔여학기 뒤에 가상 정규/계절학기를 점증 추가하며 모든 selected가 배치될 때까지 돌려 그 길이로 산출(개설학기·선수·cap 동시 준수). 최소한 unplaced 사유가 용량 아님(개설/선수)이면 note에 '개설학기 제약으로 추가 학기 수가 더 늘 수 있음' 명시.

## [HIGH] [HIGH·데모파괴] max_credits_per_term 상한 미적용 — 사용자가 99 입력 시 한 학기 98학점 로드맵이 'feasible'로 산출(제32조 무력화)
- file: graduation_center/v2/planner.py:622; graduation_center/v2/models_v2.py:25
- 문제: StudentContext.max_credits_per_term은 bound가 없고(확인: float|None, Field 제약 없음), 프론트는 Number()로만 받아 큰 값을 그대로 전송(GraduationV2.jsx:257). run_planner의 reg_cap = context.max_credits_per_term or regular_term_cap(...)은 0만 falsy 처리하고 99는 그대로 쓴다. 실행 확인: cap=99로 _ordered_terms가 99학점 학기를 만들고 plan_greedy가 98학점을 한 학기에 채운 뒤 status=generated·feasible로 반환. over_credit_cap 검증기(653)도 같은 99 cap을 써 위반을 못 잡는다. 데모에서 비현실적 보고서가 정상 판정으로 나온다.
- 수정: 사용자 override를 제32조 상한으로 클램프: reg_cap = min(user_override, regular_term_cap(total)+PREV_GPA_BONUS) 같은 하드 상한. 또는 models_v2.py에서 max_credits_per_term에 le=22 Field 제약. 최소한 프론트 input에 max 속성+클램프.

## [HIGH] [REG] [HIGH] 핵심교양 요건이 영역floor 합(17)으로 산출돼 공식 요람치(15)와 충돌 — 한 화면에 두 권위 숫자
- file: graduation_center/v2/audit_v2.py:289-290
- 문제: core_total_required = sum(overrides.get(a, core_min) for a in gen_areas) or area_min['핵심교양']. gen_areas 5개라 합이 항상 truthy → or 폴백 미발동. 실행 확인(mirae 2023): area_min['핵심교양']=15.0인데 core_total_required=17.0(소통 override 5 + 3×4)이 산출돼 area_gaps 핵심교양 required=17로 표시, json/요람 15와 충돌. override 없는 ai_bigdata는 5×3=15로 우연히 일치해 버그가 가려진다. (total 136과 17이 정합이라 17이 도메인상 옳을 수 있으나, 두 출처가 동시에 권위 있는 숫자로 노출되는 게 결함.)
- 수정: 총량 요건과 하위영역 floor를 분리. 핵심교양 required는 단일 source of truth(area_min 또는 max(json, Σfloor) 정책 확정)를 쓰고 하위영역 최저는 core_area_gaps에서만 검사. 화면에 15와 17이 동시에 안 나오게 통일.

## [HIGH] [HIGH] 핵심교양 earned 산식 불일치 — 미매핑 핵심교양 학점이 총량엔 들어가고 영역엔 안 들어가 게이지/하위카드가 모순 진단
- file: graduation_center/v2/audit_v2.py:297,305
- 문제: area_gaps 핵심교양 earned = earned['핵심교양'](모든 핵심교양 과목 합)인데, core_area_gaps earned = core_area_earned(core_area 매핑이 있는 과목만). 학생이 gen_ed 카탈로그 미등록(name_norm_to_area 없음) 핵심교양 과목을 들으면 match_course가 core_area=None을 줘(catalog 경로), 그 학점이 총량엔 반영되나 어느 하위영역에도 안 들어간다. 결과: 영역 게이지는 '거의 충족'인데 하위영역 카드는 소통/글로벌/창의 부족으로 정면 충돌. 두 뷰가 다른 결론을 보여 컨설팅 신뢰도 훼손.
- 수정: 두 뷰의 earned 기준을 정합. 핵심교양 총량 earned도 영역에 매핑된 학점만 카운트(미매핑은 '영역 미상 N학점 — 확인 필요'로 분리)하거나, 미매핑분을 결정론 규칙으로 영역 귀속. 최소한 미매핑 핵심교양 존재 시 그 사실을 명시.

## [HIGH] [HIGH] 기초교양 필수 substring 매칭 오탐 — '글쓰기'가 '과학기술글쓰기' 등에 부분일치해 무관 과목을 필수 이수로 거짓 표시
- file: graduation_center/v2/audit_v2.py:93
- 문제: _gen_basic_view에서 taken = any(key in t for t in taken_norm)로 필수명을 부분일치 판정. 실행 확인: normalize('글쓰기') in normalize('과학기술글쓰기')=True, '영어글쓰기실습'=True, '글로벌영어' in '글로벌영어회화'=True. 임의 포함 과목을 충족으로 오판해 실제 미이수 기초교양 필수를 ✅이수로 거짓 표시. (단 taken_norm이 requirement_area=='기초교양' 과목으로 한정되므로 블래스트 반경은 좁고 mirae 전용 데이터.)
- 수정: 정확일치 우선(nn(rn) in confirmed_norm)으로, 접미사 흡수가 필요하면 t==key or t.startswith(key)로 제한하거나 _required_aliases 동치그룹 사용. 임의 substring(key in t)은 제거.

## [HIGH] [REG] [HIGH·회귀] 학번요람 연도 선택 정책이 3개 함수에서 불일치 — below-range 학번에서 필수명·메타·영역최저가 서로 다른 요람을 참조
- file: graduation_center/v2/planner.py:388; graduation_center/v2/audit_v2.py:43-44; graduation_center/v2/catalog.py:113-114
- 문제: 입학연도가 가용 최소요람(예 2023)보다 이른 경우 fallback이 제각각이다(코드 확인): _required_names_for_year(audit 43-44)는 le 비면 avail[0](가장 이른), _required_meta(planner 388)는 [...y<=year][-1:] or [avail[-1]]로 avail[-1](가장 늦은!), _requirements_by_year(catalog 113-114)는 le 비면 None(기본 json). 따라서 매우 오래된/미상 학번은 필수 과목명은 이른 요람에서, 그 과목의 credits·terms 메타는 늦은 요람에서 와 normalize 매칭이 어긋나 메타가 비고 기본값(3.0학점, ['1','2'])으로 떨어진다 → 로드맵 학점/개설학기 왜곡·초과학기 오트리거. applied_yoram 라벨과도 모순. 프론트는 학번 미입력 시 admission_year=null 전송(GraduationV2.jsx:247)이라 도달 가능.
- 수정: 세 함수가 단일 헬퍼 resolve_yoram_year(program_id, year)를 공유하도록 통일(정확연도 → 입학연도 이하 가장 가까운 → 없으면 avail[0]). _required_meta의 `or [avail[-1]]`를 `or [avail[0]]`로, _requirements_by_year도 le 비면 avail[0]로.

## [MEDIUM] [MEDIUM·회귀] risk 잔여학기 수용량이 학기상한 18 하드코딩 — planner의 regular_term_cap(136학점→19)과 불일치해 feasible 로드맵에 D 부여 가능
- file: graduation_center/v2/risk.py:62; graduation_center/v2/pipeline.py:55
- 문제: compute_risk는 term_cap = float(context.max_credits_per_term or 18)로 18 고정(profile 미전달). planner/overflow는 regular_term_cap(total_credits_min)으로 136→19/130→18/120→17(실행 확인: mirae 136 → 19). max_credits_per_term이 None일 때 136학과는 risk가 18로 수용량을 과소평가해 planner는 전부 배치(feasible)인데 risk는 '수용량 초과 D'를 띄울 수 있다. 또 비교 기준이 total_gap뿐이라 '총학점 충분·영역 floor 큰' 학생에서 planner=blocked인데 risk capacity 미발동 불일치. (프론트는 항상 cap을 전송하므로 happy-path 영향은 제한적 — 그래서 high가 아닌 medium.)
- 수정: compute_risk에 profile(또는 total_credits_min)을 전달하고 term_cap fallback을 regular_term_cap(profile.total_credits_min)로 통일. 더 견고하게는 risk가 자체 capacity를 재계산하지 말고 plan.overflow.extra_semesters>0를 D 트리거로 사용해 planner와 단일 출처화.

## [MEDIUM] [REG] [로드맵·MEDIUM·회귀] markdown 로드맵이 blocked 시 부분배치 학기를 통째 누락 + satisfies/assignment 미출력 → JSON/프론트와 발산
- file: graduation_center/v2/pipeline.py:122-131
- 문제: _markdown은 status=='blocked' 분기에서 blocked_reason만 출력하고 plan.terms를 순회하지 않는다(코드 확인). 그러나 run_planner의 unplaced 경로(planner.py:667)는 status='blocked'이면서 terms=placed(부분배치)를 함께 반환해, 마크다운에는 실제 배치 학기/과목이 사라지고 JSX(terms 무조건 렌더)와 발산한다. 또 generated 분기에서도 과목을 'name(credits)'로만 찍고 satisfies/assignment(JSX는 칩으로 표시)를 누락. 검토차원 #12 요구('배정값·미배치·초과학기 반영')를 마크다운이 미충족.
- 수정: blocked여도 plan.terms가 있으면 학기 스케줄을 먼저 렌더하고 그 아래 blocked_reason/미배치/초과학기를 덧붙이도록 분기 통합. 학기 루프에서 satisfies/assignment도 출력(f"{name}({cr}) [{satisfies} · {assignment}]").

## [MEDIUM] [REG] [로드맵·MEDIUM·회귀] blocked 플랜에서 blocked_reason·relaxation_hint이 카드 상·하단 두 번 렌더
- file: frontend/src/components/GraduationV2.jsx:643,695-699
- 문제: 643은 status==='blocked'일 때, 695-699는 feasible===false && blocked_reason일 때 동일한 '{blocked_reason} · {relaxation_hint}'를 출력한다(코드 확인). blocked 플랜은 항상 feasible===false이므로 같은 문장이 두 번 표시된다.
- 수정: 643은 terms 비었을 때(완전 blocked)만, 695는 terms 있을 때(부분배치 blocked)만 렌더하도록 조건을 status==='blocked' && terms.length===0 / feasible===false && blocked_reason && terms.length>0로 좁혀 한 번만 나오게.

## [MEDIUM] [REG] [로드맵·MEDIUM·회귀] 연계융합 인라인 suggest가 그룹 전용 미충족에 발화 안 함 — 백엔드 후보 로직과 불일치
- file: frontend/src/components/GraduationV2.jsx:111-118
- 문제: suggest는 fusionGap = max(0, cc.required - fusionCr)가 0이면 빈다(114 guard). 그러나 총 융합학점은 채웠어도 특정 그룹 최저가 미달이면 fusionGap=0·fits=false라 '추가 이수 필요'만 뜨고 '무엇을 들어야 하는지'가 사라진다. 백엔드 build_unified_candidates(planner 461-476)는 need=max(gap, Σgroup_gaps)로 그룹부족까지 후보를 뽑으므로 로드맵은 옳게 추천 → 인라인 suggest만 누락해 둘이 어긋난다.
- 수정: 부족량을 max(fusionGap, Σ(group_checks gap>0))로 잡고, 추천 풀을 shortGroups 우선 정렬해 그룹별 부족이 메워질 때까지 누적(백엔드 need 산식과 동일). 위 그룹최저 항목 해결 후 동일 기준으로.

## [MEDIUM] [로드맵·MEDIUM] '남은 요건' 칩이 백엔드 요건요약과 불일치 — 전공 갭 이중계상·일반선택 누락
- file: frontend/src/components/GraduationV2.jsx:656-670
- 문제: 칩은 audit 원시 갭에서 프론트가 독립 재계산해 '필수지정 N과목'(659)과 '전공 {gap}학점'(660)을 따로 푸시한다. 그러나 백엔드 build_unified_candidates는 전공 갭에서 필수지정 학점을 빼고(major_gap_eff) 계획하므로 칩에 전공 부족이 이중으로 보인다. 또 백엔드가 실제 배치하는 '총학점(일반선택)' 슬롯은 칩에 전혀 없어 칩 합과 term 카드가 어긋난다.
- 수정: 칩을 원시 갭에서 재계산하지 말고 백엔드 requirements_summary(run_planner ctx['requirements_summary'])를 응답에 실어 그대로 렌더하거나, 전공 칩을 major_gap_eff(=전공gap−필수지정 학점)로 바꾸고 일반선택 general_need 칩을 추가.

## [MEDIUM] [MEDIUM] malformed current_term('2025-X' 등)이 '현재 학기 미입력' 분기로 오라우팅 — 잔여학기 있는 학생이 blocked/overflow 없이 거짓 무해 결과
- file: graduation_center/v2/planner.py:631-644
- 문제: _ordered_terms는 학기 토큰을 {1,S,2,W}로만 파싱하고 예외 시 []를 반환(실행 확인: '2025-X' → []). run_planner은 terms==[]일 때 line 633에서 'current_term and remaining_semesters<=0'을 검사하는데, current_term이 truthy이고 remaining>0이면 False → line 641 '현재 학기 미입력 — 학기 배치 생략'(feasible=None) 분기로 떨어진다. 실제로는 학기 입력했고 잔여학기도 있으나 거짓 무해 결과(blocked/overflow 미표시). 프론트 current_term이 free text라 도달 가능.
- 수정: terms==[] 분기에서 '현재 학기 미입력'은 current_term이 falsy일 때로 한정하고, current_term truthy && terms empty && remaining>0이면 'current_term 형식 오류' 경고로 분기(NodeTrace/응답 노출). 프론트도 ^\d{4}-(1|2|S|W)$ 검증 추가.

## [MEDIUM] [MEDIUM] area_from_isugubun 치환 순서로 '다전공/부전공/융합전공'이 모두 '전공'으로 매핑 — 다전공→일반선택 매핑이 dead code
- file: graduation_center/v2/catalog.py:22-34
- 문제: _ISU_TO_AREA를 substring(key in s)으로 순회하는데 '전공' 키가 '다전공'보다 먼저라 area_from_isugubun('다전공')='전공', '부전공'='전공', '융합전공'='전공'을 반환(실행 확인). 의도된 '다전공'→'일반선택' 매핑이 도달 불가. 현재는 verification.py:57의 'aggregate_only & area==전공 → 일반선택' 구제가 카탈로그 미매칭 타전공을 일반선택으로 되돌려 happy-path를 살리나, 코드/이름이 매칭되면 구제 전에 전공 처리되어 의도와 다를 수 있고 데이터 변경 시 조용히 오집계.
- 수정: 더 긴/특수 라벨('다전공/부전공/복수전공')을 '전공' substring 검사 전에 분기하거나 dict에서 앞에 둔다. 또는 정규식 경계로 정확/접두 매칭.

## [MEDIUM] [연계융합·MEDIUM] 다중 연계융합 동시선택 시 같은 겹침과목 학점이 제1전공에서 이중 차감(to_fusion_total 합산 결함)
- file: graduation_center/v2/audit_v2.py:281-282
- 문제: compute_audit는 to_fusion_total = Σ(cc.to_fusion_credits) 후 major_effective = earned['전공'] − to_fusion_total로 차감한다(코드 확인). _convergence_checks는 각 융합전공을 독립 호출하므로, 두 융합전공이 공유하는 겹침과목이 두 cc 모두 'fusion'으로 잡히면 동일 물리 과목 학점이 to_fusion_total에 두 번 더해져 전공에서 이중 차감 → 거짓 전공부족·risk 강등·overflow 연쇄. audit_v2.py:107-113이 동시배정 최적화를 '미구현'으로 명시. (단 프론트 happy-path는 단일 융합이라 회귀가 아니라 latent — 그래서 medium.)
- 수정: 겹침→융합 배정을 program별 독립이 아니라 전역 1패스로 풀어 각 겹침과목을 한 융합에만 fusion 산입. 최소 수정으로 to_fusion에 산입된 course_id를 전역 dedup해 major_effective 차감에 1회만 반영. 그 전까지 convergence_program_ids 길이>1이면 프론트 경고 배너/백엔드 note로 시범 범위 밖임을 명시.

## [MEDIUM] [REG] [로드맵·MEDIUM] 미이수 필수 prereq 우회 + area 하드코딩 — 캡스톤Ⅰ/Ⅱ 순서 미강제·비전공 필수가 전공갭에서 차감
- file: graduation_center/v2/planner.py:443-459,551-559
- 문제: (1) required_names의 '다학제간캡스톤디자인Ⅰ/Ⅱ'는 normalize로 '...1'/'...2'가 되어 by_norm('다학제간캡스톤디자인') 매칭 실패 → cid='', prereqs=[]가 되고 plan_greedy가 순서 제약 없이 배치(Ⅱ가 Ⅰ보다 앞 학기 가능). cid='' 과목은 placed_at에 등록 안 돼(573 가드) 다른 과목의 선수로도 작동 못함. (2) build_unified_candidates는 missing_required_names 전체를 area='전공'으로 박고(459) major_gap_eff에서 차감하므로, 요람 필수가 기초/핵심교양 성격이면 전공갭이 잘못 줄어 거짓 충족.
- 수정: by_norm 매칭을 접미사 무시 부분일치로 보강하거나 required_names 메타에 prereq·area 명시. cid 없어도 이름키 placed_at으로 Ⅰ→Ⅱ 순서 강제, 미해소 선수는 manual_check. area는 카탈로그 requirement_area에서 가져오고 major_gap_eff 차감은 실제 area=='전공'만.

## [LOW] [로드맵·LOW] 결정론 검증이 외부 미충족 선수 위 배치를 누락 — 후보풀에 없는 선수는 검사 통과
- file: graduation_center/v2/planner.py:554,651-656
- 문제: _try_place의 deferral 조건이 `p not in completed and p not in placed_at and p in sel_pref`라, 선수가 후보풀(sel_pref)에도 없고 이수도 안 된 경우(외부/갭초과 선수) deferral 없이 그대로 배치한다. run_planner 결정론 검증(651-656)은 over_credit_cap·unplaced만 보고 선수를 재확인하지 않는다(prereq 검사는 미사용 validate_roadmap에만). 시드 데이터엔 미발현이나 학과 확대 시 잘못된 학기 배치 가능.
- 수정: _try_place에서 미충족 선수(p not in completed and p not in placed_at)를 sel_pref 여부와 무관하게 다루거나, run_planner 검증에 prereq_unmet 체크를 추가해 unplaced로 떨어뜨린다.

## [LOW] [연계융합·LOW] 중복인정(dup) 그리디가 cap을 최적 충전 못해 과소 인정 + 권장(rec)과 실제 배정(alloc)이 다른 산식이라 표시 불일치
- file: graduation_center/v2/audit_v2.py:193-197,218-220
- 문제: dup 배정은 ov_sorted fit-first 그리디라 cap=12·overlap=[9,6,6]이면 9만 잡고 6+6=12 최적을 놓쳐 과소 인정(코드 확인). 또 rec(191-197)은 courses_view에서 acc>=cap break, alloc(218-220)은 overlap에서 dup_cr+credits<=cap fill이라 모집단·종료조건이 달라 '중복인정 권장' 목록과 실제 배정 과목이 어긋날 수 있다. 현 시드는 전 과목 3학점·cap 6/12라 미발현(latent).
- 수정: dup 충전을 cap에 대한 subset-sum/배낭으로 최적화(또는 skip 후 작은 과목 second pass)하고 프론트 defaultSel도 동일 로직으로 동치 유지. rec를 별도 산출하지 말고 alloc 결과(dup 배정 과목)에서 파생해 단일 출처화.

## [LOW] [LOW] double_recognizable(min(overlap,cap)) 표시값이 과목단위 dup_used와 어긋날 수 있음
- file: graduation_center/v2/audit_v2.py:164,252,262; frontend/src/components/GraduationV2.jsx:133
- 문제: double_recognizable=round(min(overlap_cr,cap))은 연속값이고 실제 dup_cr(218-220)은 과목단위 패킹이라 cap을 정확히 못 채우면 더 작다. markdown(pipeline 104)·StatBox 헤더(133)는 double_recognizable을, 본문은 과목단위 effective를 써 한 화면에 6/6 인정인데 배정은 4만 반영되는 모순 가능. 현 3학점 시드에선 미표면(latent).
- 수정: 표시·근거에 double_used(dup_cr)를 쓰거나 double_recognizable을 '한도'로만 명시하고 '실제 인정'은 double_used로 분리. 비3학점 카탈로그 추가 시 즉시 드러나므로 배정 결과로 통일 권장.

## [LOW] [LOW] risk 융합 eff_gap(max group)과 planner need(sum group)가 달라 등급과 로드맵 부담이 다른 부족량을 전제
- file: graduation_center/v2/risk.py:80; graduation_center/v2/planner.py:463
- 문제: risk는 eff_gap = max(cc.gap, *group_short gaps)로 '최대 한 그룹'을, planner는 need = max(cc.gap, sum(group_gaps))로 '그룹 부족의 합'을 본다(코드 확인). 두 그룹이 각 6 부족이면 risk는 6(B), planner는 12를 로드맵에 배치 → 보고서 내 정합이 어긋난다.
- 수정: 두 곳을 동일 정의로 통일(그룹별 최저는 독립 제약이므로 sum이 실제 추가 이수량에 가까움 — risk도 max(cc.gap, sum(group_gaps))로).

## [LOW] [LOW] 연계융합 후보 선택이 그룹별 최저를 보장 못함(총 credit 기준 acc>=need 종료)
- file: graduation_center/v2/planner.py:460-476,526-534
- 문제: build_unified_candidates는 need=max(총gap, Σgroup_gap)로 잡고 untaken을 부족그룹 우선·-credits 정렬 후 acc>=need까지 누적 선택한다. 정렬로 부족그룹을 앞세우나 종료조건이 '총 학점'이라 한 그룹의 큰 과목으로 총량을 채우면 다른 부족그룹을 못 채운 채 멈출 수 있다(그룹별 quota 미추적) → 추천으로도 그룹최저 미충족 가능.
- 수정: 그룹별 잔여 quota를 dict로 추적해 각 부족 그룹의 gap을 개별 충족할 때까지 해당 그룹 과목을 우선 선택하도록 종료조건을 그룹별로 분리.

## [LOW] [LOW] Σgroup_earned==fusion_eff 불변식이 group 없는 융합과목에 취약(현 데이터는 안전)
- file: graduation_center/v2/audit_v2.py:238-244
- 문제: group_earned는 fusion_courses 중 g truthy인 과목만 누적(241 if g:)하지만 fusion_eff(234)는 전 과목 합이라, group이 None/'' 인 융합과목이 있으면 Σgroup_earned < fusion_eff가 되어 라운드2가 주장한 불변식이 깨진다. 현 dsci/mobility 카탈로그는 전 과목 group 보유라 미발현(확인). risk.py group_short 강등도 영향.
- 수정: group 없는 과목을 '기타' 그룹으로 묶어 포함하거나, 빌드 시 모든 융합 카탈로그 과목에 group 필수 검증(assert)을 추가해 불변식을 명시 보장.

## [LOW] [LOW] 연계융합 required/double_cap이 group_rules·convergence_required를 무시하고 36/18·12/6 하드코딩 — per_group_min만 데이터주도라 출처 갈림
- file: graduation_center/v2/audit_v2.py:147-148
- 문제: req = 36 if 다전공 else 18, cap = 12/(연계0/6)로 하드코딩인데 per_group_min은 같은 함수에서 cat['group_rules'][track]['per_group_min']을 읽는다(158-159). 동일 요건의 total/cap은 상수·per_group_min만 데이터라 출처가 갈리고, 데이터값이 시드와 달라지면 total/cap만 안 따라가 group_min과 모순. programs.json의 convergence_required=36도 미사용.
- 수정: rules=(cat.get('group_rules') or {}).get(track,{})에서 req=rules.get('total', ...), cap=rules.get('double_cap', ...)로 일관 로드해 단일 출처화.

## [LOW] [LOW] applied_yoram 라벨이 해석된 요람연도가 아닌 입학연도를 표기 — nearest-prior 적용 시 라벨이 실제 출처와 어긋남
- file: graduation_center/v2/catalog.py:136
- 문제: applied = f'{admission_year} 요람 (학번 기준)' if (yr and admission_year)인데 yr은 nearest-prior 결과이고 라벨은 입학연도를 그대로 박는다. mirae year=2024는 2023데이터를 쓰는데 라벨은 '2024 요람'. compute_audit이 by-year 필수데이터 있는 학과에선 라벨을 '{applied_year} 요람 (학번 {year} 기준)'으로 덮어써 우연히 교정되나, 덮어쓰지 않는 경로에선 틀린 라벨 노출.
- 수정: 라벨을 _requirements_by_year가 실제 고른 연도로 구성하도록 헬퍼가 (data, picked_year)를 함께 반환하게 하고 단일 resolve_yoram_year로 라벨까지 산출.

## [LOW] [LOW] 미사용 죽은 코드 project_overflow 잔존 — 초과학기 단일모델(_overflow_from_credits)과 다른 용량식 공존
- file: graduation_center/v2/planner.py:63-96
- 문제: 라운드2 fix#4가 초과학기를 _overflow_from_credits(미배치 학점 기반) 단일모델로 통일했으나 구 모델 project_overflow(area_shortfall·total_gap, capacity=잔여×cap+보너스)가 호출처 없이 잔존(grep 확인: 호출 0). 두 산식이 공존해 누가 재호출하면 결과가 갈린다. (또 build_planning_context/plan_roadmap/validate_roadmap도 프로덕션 미사용 — validate_roadmap·build_planning_context는 테스트만. audit_v2.py:193 rec_keys도 add만 하고 read 없는 미사용 변수.) 18인 리뷰 중 ~12건이 project_overflow를 중복 보고 — 단일 항목으로 병합.
- 수정: project_overflow를 삭제하거나 docstring에 '미사용/_overflow_from_credits로 대체' 명시. rec_keys 미사용 변수 제거. 초과학기 단일 모델 유지.

## [LOW] [FALSE POSITIVE 의심·LOW] 초과학기 capacity가 직전3.75 보너스·계절학기를 무시 — risk 모델과 미세 비대칭
- file: graduation_center/v2/planner.py:398-413
- 문제: _overflow_from_credits는 extra=ceil(unplaced/reg_cap)로 보너스·계절을 제외한다. 그러나 unplaced는 plan_greedy가 _ordered_terms(첫 정규 +보너스, 계절 6)를 모두 써서 배치한 '뒤' 잔량이므로 입력 자체는 보너스/계절을 이미 반영한다. 초과 '학기' 환산만 reg_cap을 쓰므로 보수적(과대)일 뿐 거짓충족은 아니다 — 다수 리뷰어가 이를 '과소추정'과 '과대추정' 양쪽으로 엇갈리게 보고했는데, 정작 거짓충족 위험은 위 '개설학기 병목' 항목이 본질. 이 항목 단독은 화면 간 가정 표기 차이 수준의 경미한 정합 문제로, high로 본 일부 보고는 과대평가.
- 수정: 초과학기에도 동일 학기별 용량 가정(계절·첫학기 보너스)을 적용하거나, note에 '정규학기 상한 기준 추정(계절 활용 시 단축 가능)'을 명시해 화면 간 가정을 일치. 기능 결함은 아니므로 표기 보강으로 충분.
