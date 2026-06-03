# 적대리뷰 라운드4 종합 (18, raw 116, HIGH 10, REG 18)

## [HIGH] [REG] [데모 high·로드맵/리포트] 전역 seen 디둡이 융합 전용 후보를 전공 부족 quota에 거짓 가산 → 전공 갭이 거짓 충족
- file: graduation_center/v2/planner.py:534-538
- 문제: build_unified_candidates의 selected 구성 루프에서 seen 집합이 모든 요건(필수→융합(priority2)→전공부족(priority3)→교양)에 걸쳐 전역이다. 융합 풀에서 먼저 선택된 미이수 과목명이 전공 부족 풀에서 다시 나오면 line 535-536이 재선택 없이 acc += it['credits']로 학점만 전공 quota에 가산한다. 실데이터로 mirae_mobility 제1전공 카탈로그와 mobility_data_convergence 카탈로그가 정규화 이름 13건을 공유함을 확인(Python프로그래밍·자료구조및알고리즘·기초선형대수·모빌리티실험및실습 등). 한 과목이 전공 floor와 융합 floor(36)를 동시 완납하는 셈이라 제77조 중복인정 한도(다전공 12)를 우회한다. run_planner의 결정론 검증(675-684)에는 영역 커버리지 체크가 없어(gap_not_closed는 미사용 validate_roadmap에만 존재) 전공 후보 0개여도 status='generated'·feasible=True로 통과한다. 학생은 '졸업 가능'으로 안내받지만 전공이 실제로 비어 불가. 동일 결함이 별도 finding(요건 간 전역 seen 디둡)과 중복.
- 수정: key in seen 경로의 acc 가산을 제거(원래 동작 복원: skip → 풀 고갈 시 unfillable로 정직 기록). per-area seen으로 바꿔 교차영역 동일 과목은 한쪽에만 산입. 더불어 run_planner 종료 전 selected/placed를 requirement_area별 집계해 audit.area_gaps와 대조하는 gap_not_closed 체크를 결정론 경로에 이식.

## [HIGH] [REG] [데모 high·로드맵] 전공 필수지정 학점이 전공 갭에서 이중 차감되어 전공 선택과목 과소 계획
- file: graduation_center/v2/planner.py:484-496,530-540
- 문제: 전공 부족 풀 need를 major_gap_eff = major_gap - req_major_credits로 한 번 줄인다(488). 그런데 그 풀(491-495)은 미이수 카탈로그 전공과목 전체를 담아 미이수 '필수지정' 과목도 untaken이라 confirmed에서 빠지지 않고 풀에 들어간다. 그 과목명이 seen에 있어 재선택은 안 되지만 536줄 acc += it['credits']로 전공 quota에 다시 더해진다. 결과적으로 신규 전공 선택 = major_gap - 2*req_major_credits가 되어 필수지정 학점만큼 전공이 한 번 더 빠진다. 부족분은 545줄 general_need가 일반선택으로 흡수해 총학점은 맞으나 '전공' 영역으로는 안 채워진다. 위 seen 디둡 결함과 같은 코드 경로의 다른 발현이며 함께 수정해야 함.
- 수정: 536줄 seen-skip된 필수지정 과목을 acc에 더하지 않는다(필수는 이미 items로 별도 계획됨). major_gap_eff에서 한 번만 차감하고 풀의 acc 가산은 '실제 신규 선택분'만 세도록 한다.

## [HIGH] [REG] [데모 high·헤드라인] risk 잔여학기 수용량이 계절학기를 1회(+6)만 더해 결정론 플래너와 모순 (거짓 D 등급)
- file: graduation_center/v2/risk.py:60-73
- 문제: compute_risk의 capacity = remaining*term_cap + (3.75보너스) + SEASONAL_TERM_CAP로, 계절학기를 잔여 정규학기 수와 무관하게 단 1회(+6)만 더한다. 그러나 planner._ordered_terms(planner.py:366-377)는 정규학기마다 계절학기 1개씩 끼워(잔여 4학기면 계절 4개=+24) 배치 용량이 훨씬 크다. 같은 입력에서 risk는 capacity 부족으로 grade D(졸업불가 가능성)를 헤드라인에 띄우는데 run_planner는 feasible=True·overflow=None인 로드맵을 본문에 보여줘 정면 모순. roadmap_feasible=True를 넘겨도 _worse가 D를 유지해 강등이 상쇄 안 됨. 채점 데모에서 바로 드러나는 모순.
- 수정: risk capacity를 플래너와 동일 용량 모델로 통일. 가장 정합적인 방법은 _ordered_terms의 cap 합을 capacity로 쓰는 것(보너스·계절 끼움을 한 출처에서 산출). 최소 수정: 계절 항을 remaining_semesters * SEASONAL_TERM_CAP로, 보너스도 첫 정규학기 1회만.

## [HIGH] [REG] [데모 top-1·헤드라인 모순] 2023 mirae 필수 4과목 alias 누락 — 전공 84/62 충족인데 '미이수 필수지정'으로 오판
- file: data/graduation/v2/required_names_by_year.json (aliases.mirae_mobility) ↔ graduation_center/v2/audit_v2.py:325-330
- 문제: 데이터로 확인: required_names_by_year.json mirae 2023 필수에 '미래모빌리티기초','미래모빌리티AD','다학제간캡스톤디자인Ⅰ','다학제간캡스톤디자인Ⅱ'가 있는데 2025 개편명(자동차모빌리티기초·자동차모빌리티 Adventure Design·다학제간캡스톤디자인)과의 alias가 없다(현 alias는 미래모빌리티실험→모빌리티실험및실습 1건뿐). _taken()은 정규화이름·alias로만 대조하므로(audit_v2.py:325-330) 2025명/드리프트명으로 기록된 수강내역이면 4과목이 false 미이수로 잡힌다. 데모 보고서에서 '전공 84/62 ✅(초과)'와 '미이수 필수지정 4과목'이 동시에 떠 채점자가 가장 먼저 지적할 모순. missing_required는 risk(전공필수 severity)·planner(phantom 추가)·초과학기로 전파된다.
- 수정: aliases.mirae_mobility에 미래모빌리티기초↔자동차모빌리티기초, 미래모빌리티AD↔자동차모빌리티 Adventure Design, 다학제간캡스톤디자인Ⅰ/Ⅱ↔다학제간캡스톤디자인(또는 Ⅰ/Ⅱ 분리 카탈로그 항목 추가)을 보강. _required_aliases가 양방향 그룹을 만드므로 한 방향만 적으면 됨. 데모 전 2023 요람 20개 필수명 전부 회귀 검증.

## [HIGH] [데모 high·로드맵] 기초교양 영역 충족(gap 0)인데 이름 미매칭만으로 필수 12학점 phantom 추가
- file: graduation_center/v2/planner.py:498-503
- 문제: build_unified_candidates step4의 missing_basic 분기가 'if missing_basic:'로만 들어가 basic_gap(영역 학점 부족)을 전혀 참조하지 않는다(line 500). 기초교양 영역이 9/8(gap 0)이어도 이름 미매칭 필수명이 있으면 College English/글로벌영어 등을 일률 credits=3.0으로 selected에 넣어 sel_credits를 부풀리고 일반선택 잔여를 줄이며 거짓 초과학기를 유발한다. 전공 필수와 달리 교양은 영역 총량으로도 충족 가능한데 이름 미매칭만으로 의무 취급. 이름 드리프트(top-1)와 결합되면 '충족인데 더 들으라'는 데모 모순. 또한 gen_basic 미이수 학점을 3.0 하드코딩해 실제 1~2학점 영어 과목과도 불일치.
- 수정: step4에서 basic_gap<=0이면 missing_basic을 '권장(확인)'으로만 표기하고 selected/need에서 제외, 또는 추가 학점을 max(0, basic_gap)로 클램프. gen_basic에도 credits 메타를 부여하거나 missing_basic 학점 합을 basic_gap으로 클램프. 핵심교양 step5도 영역총량 충족 시 per-area 슬롯 추가 제한 검토.

## [HIGH] [REG] [데모 high·선수위반] plan_greedy가 미선택·미이수 선수과목을 침묵 통과 + 선수/배치를 5자리 절단 비교
- file: graduation_center/v2/planner.py:567-593
- 문제: 두 결함이 같은 함수에 공존. (1) _try_place의 선수 검사(line 571)는 '선수가 selected 풀(sel_pref)에 있는데 미배치'일 때만 defer한다. 선수가 이수도 안 했고 후보 풀에도 없으면(진짜 미충족) 제약 없이 배치된다. min_idx도 placed_at에 있는 선수만 본다. 필수지정 미이수 과목도 fix#6로 prereqs를 부여받아 이 경로로 선수 위반 계획이 나간다. (2) placed_at·completed·sel_pref·선수 비교가 모두 course_id[:5]로 절단(568,570,591)돼, audit_v2가 7자리로 막은 충돌(0365007 S-TEAM↔0365008 사제동행, ai_bigdata 03650 prefix 실재)을 plan_greedy만 재유입한다. 같은 5자리 prefix 별개 과목이 서로의 선수·배치 추적을 오염시켜 거짓 선수 충족. run_planner 검증은 선수를 재검증하지 않고 prereq_unmet은 죽은 validate_roadmap 전용이라 호출되지 않는다. 별도 finding(데모 top-2 캡스톤Ⅰ/Ⅱ 순서 역전)도 이 선수 부재의 발현.
- 수정: 선수 prefix가 completed에도 placed_at에도 없으면(sel_pref 여부와 무관하게) 해당 과목을 unplaced로 보내거나 prereq_unmet을 errors로 수집해 run_planner 검증에 반영. placed_at·completed·sel_pref·선수 키를 7자리 전체 course_id로 통일. 캡스톤·…Ⅰ/Ⅱ 동일 어간은 낮은 번호를 선수로 주입.

## [HIGH] [REG] [데모 high·전공게이지] 다중 연계·융합전공 선언 시 겹침과목 to_fusion 이중 차감으로 major_effective 붕괴
- file: graduation_center/v2/audit_v2.py:288-289
- 문제: compute_audit가 to_fusion_total = Σ(각 cc.to_fusion_credits)를 전공 earned에서 차감해 major_effective를 만든다. _convergence_checks는 각 융합 프로그램마다 '다른 모든 선택 프로그램'을 other_prefixes로 보고 같은 과목을 독립 배정하므로, 두 융합전공(dsci_convergence + mobility_data_convergence)에 공통 + 제1전공과도 겹치는 과목을 다전공 둘로 선언하면 동일 과목 학점이 양쪽 cc에서 to_fusion으로 잡혀 전공에서 두 번 차감된다(공유 겹침 24학점 → SUM 24 → major_effective 0). 프론트(GraduationV2.jsx:592 tf reduce)도 같은 이중합을 표시. 단일 융합 데모 happy-path는 _convergence_checks가 한 번만 돌아 무영향. 라운드3가 HIGH 회귀로 명시했으나 미반영. 동일 결함이 medium/low로도 중복 신고됨.
- 수정: to_fusion 차감을 과목(course_id) 단위 distinct 집계로 변경: 전체 선택 융합 프로그램에 걸친 전역 1회 배정 패스를 두고 같은 물리 과목의 전공 차감은 최대 1회만. compute_audit는 전역 배정 결과의 과목집합 학점만 차감(중복 합산 금지). 데모가 단일 융합만 다루면 다중 시 경고 가드로도 충분.

## [HIGH] [REG] [데모 high·로드맵 모순] pool_exhausted(후보 고갈) shortfall을 초과학기 학점으로 합산 — '시간 부족'과 '과목 없음' 혼동 + 일반선택과 이중계상
- file: graduation_center/v2/planner.py:539-552,692-696
- 문제: 두 연결된 결함. (1) line 692 unplaced_cr = Σunplaced + Σunfillable.shortfall로 합산해 _overflow_from_credits로 초과학기를 산출한다. unfillable(pool_exhausted)은 채울 후보가 카탈로그에 없다는 뜻이라 학기를 늘려도 해결되지 않는데 overflow note는 '초과학기 약 N학기 추가 필요(예상 졸업 …)'로 표시해 원인을 가린다(재현: 융합 need9·untaken6 → blocked '후보 부족' + overflow '+1학기'). (2) unfillable.shortfall만큼 sel_cr이 낮아져 545줄 general_need = total_gap - sel_cr이 커지고 일반선택 슬롯이 그 부족분을 배치하는데, 692줄에서 같은 shortfall이 overflow에 또 더해져 이중계상. 라운드3 ④의 'unfillable→초과학기 합산' 설계 자체가 회귀.
- 수정: _overflow_from_credits 입력에서 unfillable shortfall을 빼고 '용량/개설/선수로 잔여 학기에 못 넣은' unplaced 학점만 학기로 환산. unfillable은 별도 메시지('해당 요건 수강 후보 없음 — 학과/교육과정 확인, 초과학기로 해결 불가')로 분리. unfillable만 있고 unplaced 없으면 overflow=None. general_need 산식도 sel_cr이 아닌 '커버된 요건 학점' 기준으로 바꿔 이중 흡수 차단. 692줄 + sum(u['shortfall']) 제거.

## [HIGH] 활성 결정론 플래너에 영역(이수구분) 커버리지 검증 부재 — 영역 미달이 feasible로 통과
- file: graduation_center/v2/planner.py:675-684
- 문제: run_planner의 결정론 검증은 over_credit_cap·unplaced·pool_exhausted만 본다. selected/placed가 audit.area_gaps(특히 전공 floor)를 실제 닫는지는 검사하지 않는다. 동등 검사 gap_not_closed/planned_by_area는 LLM 전용 validate_roadmap(340-352)에만 있고 활성 경로(run_audit→run_planner→plan_greedy)에서 호출되지 않는다. 따라서 전공 갭이 일반선택/교양 슬롯으로 총량만 메워지거나 seen 디둡(위)으로 전공 후보가 누락돼도 status='generated'·feasible=True. 위 seen·필수 이중차감 결함의 안전망이 없어 함께 묶어 수정 권장.
- 수정: run_planner 종료 전 selected/placed를 requirement_area별 집계해 audit.area_gaps의 각 gap(전공 등 MAJOR_AREAS)과 대조하고, 미충당 영역이 있으면 ValidationError(code='gap_not_closed')와 함께 blocked(또는 overflow 산입)로 강등. validate_roadmap의 영역 검사 로직을 결정론 경로에 이식.

## [HIGH] [REG] [데모 high·suggest 모순] 프론트 융합 '졸업 가능 시나리오'가 그룹별 최저를 보장하지 않아 충족 불가 추천을 표시
- file: frontend/src/components/GraduationV2.jsx:114-121
- 문제: 백엔드 build_unified_candidates(planner.py:469-475)는 부족 그룹 quota를 먼저 채운 뒤 총 need를 채우지만, 프론트 suggest 로직(line 117-121)은 총 fusionGap 학점만 채우면 break한다. 정렬은 shortGroups 우선이나 '학점 총량'만 누적할 뿐 그룹 quota 충족을 보장하지 않는다. B그룹 untaken이 그룹 gap보다 적으면 suggest가 A그룹으로 총량을 채워 '추가 이수하면 충족'이라 표시하는데 fits(line 110, groupsOk 포함)는 false라 같은 카드 안에서 '충족 시나리오' 문구와 빨간 경고가 모순. (단 line 144-146에 !groupsOk 경고 분기는 존재.)
- 수정: suggest를 백엔드 build_unified_candidates와 동일 알고리즘으로: 먼저 각 shortGroup에 그 그룹 untaken으로 gap만큼 채우고(그룹 quota 보장) 그 다음 남은 fusionGap을 채운다. 또는 suggest 후 가정 coverage를 재계산해 groupsOk=false면 '충족' 문구를 '추가 필요'로 바꾼다. 백엔드 conv 풀 선택 결과를 응답에 실어 프론트가 재사용하는 것이 가장 안전.

## [MEDIUM] [REG] 필수과목 연도선택 정책이 audit·planner·catalog 세 함수에서 불일치 (입학연도 < 최초 요람일 때 다른 요람 적용)
- file: graduation_center/v2/planner.py:387-389
- 문제: 요람 연도 선택 폴백이 세 곳에서 다르다. (1) audit_v2._required_names_for_year(42-44)·_gen_basic_names(76-80): le 비면 avail[0](가장 이른). (2) planner._required_meta(388-389): [...][-1:] or [avail[-1]] → avail[-1](최신). (3) catalog._requirements_by_year(113-114): None. mirae avail=[2023,2025], 입학연도<2023이면 audit는 2023 요람 필수명으로 미이수 판정하는데 _required_meta는 2025를 픽(2025 필수항목은 bare 문자열이라 meta_count=0 → credits 3.0·terms['1','2'] 기본값으로 강등). 같은 학생에 두 노드가 다른 요람을 적용해 미이수 필수의 학점·개설학기 메타가 어긋나 로드맵 학점합·학기배치 오염. 4건의 중복 finding을 병합.
- 수정: 연도 선택을 단일 헬퍼(예: catalog.pick_yoram_year)로 통합하고 audit/planner/catalog가 모두 호출. 폴백 정책 합의(권장: 정확연도 → 입학연도 이하 가장 가까운 → 없으면 avail[0]). _required_meta line 388 폴백을 avail[-1]→avail[0]로 맞춤. 부수로 2025 mirae 필수항목을 2023처럼 {name,credits,terms} dict로 통일하거나 _required_meta가 문자열도 catalog로 보강.

## [MEDIUM] [REG] malformed current_term이 미입력과 구분되지 않아 잘못된 분기(feasible=None로 로드맵·초과학기 무음 손실)
- file: graduation_center/v2/planner.py:656-669, models_v2.py:21
- 문제: StudentContext.current_term에 형식 검증이 없어 '26-1','2026-13','2026/1','garbage' 모두 통과한다. _ordered_terms는 파싱 실패 시 []를 반환(357,363)하고, run_planner는 line 658이 'current_term and remaining<=0'만 blocked로 처리해 그 외(말포맷 + remaining>0)는 665-669 '현재 학기 미입력 — 학기 배치 생략'(feasible=None) 경로로 떨어진다. 잔여 2학기·136학점 부족 학생이라도 current_term만 말포맷이면 terms=[]·overflow=None으로 로드맵·초과학기가 통째로 사라지고 '현재 학기를 입력하면…'(실제 입력함)이라는 잘못된 안내가 나간다.
- 수정: StudentContext에 current_term validator 추가(예: ^20\d{2}-(1|2|S|W)$, None 허용). 형식 위반은 422 또는 명시적 입력오류로 처리하고, _ordered_terms 빈 결과를 '미입력(None)'과 '형식오류'로 분리해 분기.

## [MEDIUM] [REG] 마크다운 컨설팅 리포트의 연계융합 표시가 산술 모순 (그룹 합·designated_total ≠ 헤드라인 earned, 설명 없음)
- file: graduation_center/v2/pipeline.py:99-111
- 문제: 라운드3 fix#1로 group_checks.earned는 designated(이수 커버리지) 기준이 됐는데 헤드라인 cc['earned']는 중복인정 한도 적용 fusion_effective다. _markdown(line 103-107)은 둘을 같은 블록에 나란히 출력하면서 차이를 설명하지 않는다. 데모 보고서: '모빌리티데이터분석융합전공 27/36 ⚠️ 9 부족 · A그룹 15/12 ✅ · B그룹 15/12 ✅ · designated_total 30'처럼 (a) 두 그룹 모두 충족인데 총 9 부족, (b) designated 30 vs earned 27 차이가 설명 없이 노출돼 모순으로 읽힌다. note에 한도초과 안내는 있으나 27·30·gap 9의 인과가 보고서에서 연결되지 않음. '결과 정형성·품질' 루브릭 직격. 프론트 ConvergenceBlock은 designated_total 별도줄·각주로 설명하나 결정론 마크다운에는 없음.
- 수정: _markdown 연계융합 줄에 designated_total과 중복인정 한도 차감을 한 줄로 명시('이수 30학점 중 중복인정 한도(12) 초과 3학점은 제1전공 고정 → 융합 인정 27/36'). 그룹 행 헤더에 '(이수 커버리지 기준)' 라벨. 동일 분모 혼용 finding 다수와 병합.

## [MEDIUM] [REG] 로드맵 '남은 요건' 칩·마크다운이 연계융합 그룹별 최저 미충족을 누락 (배치된 과목과 요약 불일치)
- file: frontend/src/components/GraduationV2.jsx:673, graduation_center/v2/pipeline.py:114-118
- 문제: plan_greedy는 융합 need=max(cc.gap, Σgroup_gaps)로 그룹 부족분까지 배치한다(planner.py:462-464). 그러나 프론트 '남은 요건' 칩(line 673)은 cc.gap>0만 검사하고 _markdown도 cc['gap']만 본다(미이수 필수지정/핵심교양 부족은 별도 처리). fix#1로 그룹 최저는 designated 기준이라 cc.gap(effective)=0이어도 특정 그룹 gap>0가 가능해, 로드맵에는 융합 과목이 배치되는데 요약·리포트에는 한 줄도 안 떠 어긋난다.
- 수정: 칩 생성과 _markdown 연계융합 요약을 risk.py:80-88처럼 cc.gap뿐 아니라 cc.group_checks의 gap>0도 합산: const gNeed = Math.max(cc.gap, Σ max(0,g.gap)); if (gNeed>0) rem.push. 마크다운도 동일.

## [MEDIUM] [REG] blocked 로드맵에서 차단 사유가 화면에 두 번 렌더됨
- file: frontend/src/components/GraduationV2.jsx:655,707-711
- 문제: 655줄은 status==='blocked'일 때 {blocked_reason} · {relaxation_hint}를 출력하고, 707줄은 feasible===false && blocked_reason일 때 같은 내용을 다시 출력한다. blocked 플랜은 항상 feasible=False이고 blocked_reason이 채워지므로(planner.py:646·661·701) 모든 차단 분기에서 동일 문구가 중복 표시된다.
- 수정: 707줄 조건을 audit.roadmap.feasible===false && audit.roadmap.status!=='blocked' && blocked_reason으로 좁히거나, 655줄을 terms가 없을 때만 렌더(status==='blocked' && !terms.length)하도록 분리해 한 곳에서만 표시.

## [MEDIUM] [REG] 융합전공 그룹최저(designated)와 총량 gap(fusion_effective)이 다른 분모라 '커버리지 충족인데 N학점 부족' 거짓 신규수강 권고
- file: graduation_center/v2/audit_v2.py:240-251, graduation_center/v2/planner.py:462-464
- 문제: fix#1로 group_checks는 designated 커버리지 기준, 총량 cc['gap']/earned는 dup-cap 반영 fusion_effective 기준으로 분리됐다. 제1전공이 겹침학점을 필요로 하는 학생은 designated 42(≥36)·그룹 모두 충족이면서 cap(12) 때문에 fusion_eff=27→gap=9가 된다. planner는 need=max(cc.gap=9, Σgroup_gap)=9를 받아 '융합 9학점 부족'을 로드맵 신규 수강 요건으로 넣는다(실제론 이수구분정정/중복인정 신청만 필요, 추가 수강 불요). 그룹은 '충족'인데 총량은 '부족'으로 표시되는 내부 모순 + 거짓 추가수강. need가 두 분모를 max로 혼용하는 것도 같은 뿌리. 다수 중복 finding 병합.
- 수정: 총량 gap에 '재배정으로 해소 가능한 부족(dup-cap artifact)'과 '신규수강으로만 메울 진성 부족(designated<36 또는 그룹 커버리지 부족)'을 구분. 후자만 로드맵 신규 수강 요건으로 plan, 전자는 '이수구분정정/중복인정 신청' 안내로 분기. 표시는 그룹 패널 '이수 커버리지 기준', 총량 '제77조 중복인정 한도 적용' 라벨 병기.

## [MEDIUM] 핵심교양 area-총량(earned 전체)과 per-area 합(미매핑 미산입)의 분모 불일치로 '영역 충족인데 per-area 부족' 모순
- file: graduation_center/v2/audit_v2.py:300-313, verification.py:100-101
- 문제: area_gaps의 핵심교양 earned는 confirmed의 모든 핵심교양 학점이지만, core_area_gaps의 earned는 core_area가 매핑된 학점만(gen_ed name_norm_to_area 한정). 매핑 없는 핵심교양 과목은 area-총량엔 들어가 '핵심교양 17/17 ✅'가 되면서 per-area는 0으로 남아 planner가 핵심교양 슬롯을 추가 요구할 수 있다(미매핑 과목 1건만 있어도 area 충족·per-area 부족 동시 노출). 실데이터 매핑률 의존이지만 구조적 모순.
- 수정: 핵심교양 area earned를 sum(core_area_earned)+미매핑분으로 일관시키거나, area 충족 시 per-area 부족 합이 area 잔여(required-earned)를 넘지 못하도록 클램프. 또는 미매핑 핵심교양 과목을 '영역 미상 — 확인 필요'로 표기.

## [MEDIUM] normalize_name이 영문 끝 I/II/III를 무조건 숫자 치환 — 'AI'→'a1','API'→'ap1','Wiki'→'wik1'
- file: graduation_center/v2/text_norm.py:20-24,38-40
- 문제: _TRAILING_ROMAN이 단어 끝 영문 I/II/III를 IGNORECASE·lower 전에 숫자로 치환한다. 표준 정규화로 재현 확인: normalize_name('AI')→'a1','경영API'→'경영ap1','Wiki'→'wik1'. 카탈로그 빌드·런타임이 같은 함수라 v2 코드↔이름 매칭은 대칭이지만, (1) required_names_by_year·gen_ed name_norm_to_area 등 외부 생성 키와 조인할 때 한쪽만 안 거치면 어긋남, (2) 한 프로그램이 AI빅데이터라 'AI' 토큰 과목 충돌 위험. 현 seed 과목엔 끝 토큰이 없어 잠재. 이름 매칭은 7자리 코드 폴백이라 blast radius 제한.
- 수정: 후행 로마 치환을 '직전 문자가 한글/숫자이거나 로마 맥락일 때만' 가드: (?<=[가-힣0-9])(III|II|I)$, 또는 2글자 이하 전체 영문 토큰(AI/UI/API)은 치환 금지. 화이트리스트로 실제 차수 과목만 처리.

## [MEDIUM] _gen_basic_view 기초교양 필수 substring 매칭이 거짓 충족 ('글쓰기' ⊂ '글쓰기특강')
- file: graduation_center/v2/audit_v2.py:93
- 문제: _gen_basic_view가 taken = any(key in t for t in taken_norm)로 '요람 필수명이 학생 과목명의 부분문자열인가'를 본다. 방향이 위험해 짧은 필수명이 무관한 긴 과목명에 들어가면 거짓 충족. mirae 2023 기초교양 필수 '글쓰기'가 '글쓰기특강'만 들은 학생에게 taken=True로 표시될 수 있다. ABEEK 접미사 흡수 의도는 정확/접미사 매칭으로 충분. 화면 기초교양 배지(GraduationV2.jsx:621)와 planner step4 미이수 필수 후보(planner.py:498)가 이 값을 신뢰해 거짓 충족 시 필수 누락을 통째로 놓친다.
- 수정: 부분일치를 좁힌다: key == t 또는 t.startswith(key) and 남은 부분이 괄호·ABEEK·로마숫자 접미사일 때만. 또는 _required_aliases식 명시 동치 그룹. 짧은 필수명에는 정확매칭만.

## [MEDIUM] [REG] _convergence_checks가 5자리 prefix로 designated/overlap/required/group 판정 — 미이수 필수는 7자리로 강화됐는데 비대칭
- file: graduation_center/v2/audit_v2.py:132,149,153,162,166-175,238,247
- 문제: fix#6는 동일 충돌 근거(0365007 S-TEAM↔0365008 사제동행)로 미이수 필수·전공풀 제외를 7자리+이름으로 강화했으나, _convergence_checks 전반은 여전히 course_id[:5]로 prog_prefixes·other_prefixes·required_prefixes·overlap·prefix_to_group·alloc_by_pfx를 구성한다. ai_bigdata 필수에 03650 prefix가 S-TEAM/사제동행 2과목(req 한쪽만 True)으로 실재. 현 융합 카탈로그엔 충돌 prefix가 없어 잠재이나, 학생 수강내역의 임의 과목이 융합 prefix와 5자리만 겹치면 무관 과목이 융합 designated/중복인정으로 잘못 산입돼 fusion_effective·major_effective 차감이 틀어진다. 필수 경로와 견고성 비대칭. 다수 중복 finding 병합.
- 수정: _convergence_checks의 prefix 매칭을 전부 7자리 course_id 전체 비교로 통일(conv_prefixes/other_prefixes/required_prefixes/taken_prefixes/alloc_by_pfx). prefix 매칭이 설계 의도면 최소한 미이수필수와 동일한 7자리+이름 폴백으로 동치성 보장.

## [MEDIUM] 엑셀 파서가 한 파일=한 학기로 가정 — 통합/헤더없는 파일 업로드 시 동일 term_label로 재수강 최신판정 무력화
- file: graduation_center/v2/excel_parser.py:64-72,95,118
- 문제: _header_term은 헤더 위 6행 내 '수강학기' 셀 하나만 읽어 파일 전체에 동일 term_label을 부여한다. 학기별 파일 업로드 happy-path는 OK지만, '수강학기' 셀이 없으면 filename 폴백, filename에 연도가 없으면 _term_order=(0,0)으로 모든 행이 동순위가 돼 verification의 재수강 '최신 이수만 포함'(verification.py:42-44,66)이 임의(첫 항목)로 결정돼 오래된 이수가 included될 수 있다.
- 수정: term_label을 헤더 셀 외에 파일명/시트명 정규식으로 보강 추출, 실패 시 사용자 학기 입력 요구 또는 재수강 판정을 '확인 필요'로 강등. 가능하면 행 단위 학기 컬럼도 읽어 한 파일 내 다학기 지원.

## [MEDIUM] 전공/융합 게이지·to_fusion 안내가 서버 기본배정 고정값 — 프론트 3-way 재배정에 반응하지 않음
- file: frontend/src/components/GraduationV2.jsx:589-598
- 문제: 상단 '영역별 이수 현황' 전공 Gauge는 서버가 1회 계산한 audit.audit.area_gaps(major_effective)를 고정 표시하고, line 592의 tf 안내도 c.to_fusion_credits(서버 기본배정) 합산만 쓴다. ConvergenceBlock의 sel(3-way)은 로컬 state라 토글 시 카드 내 primaryCr/fusionCr만 갱신되고 상단 게이지·tf 주석은 기본배정에 머물러 두 화면이 모순된 전공학점을 보인다. 사용자가 겹침을 융합→제1전공으로 옮겨 전공 충족을 만들어도 메인 게이지는 부족으로 보임. 라운드3 설계상 'what-if는 카드 한정' 의도지만 데모 중 3-way를 만지면 드러남.
- 수정: 게이지/tf 안내를 sel 기반으로 클라이언트 파생 계산(전공 earned = major_base + dup + to_primary)하거나, 3-way 변경 시 재감사 호출로 동기화. 최소한 '기본 배정 기준' 문구를 달아 게이지가 사용자 변경을 반영하지 않음을 명시.

## [MEDIUM] 초과학기 산정이 계절학기·직전3.75 보너스 용량을 무시(정규학기만) — risk 수용량과 모델 불일치 + 학기수 과소추정
- file: graduation_center/v2/planner.py:398-413,373
- 문제: _overflow_from_credits는 extra=ceil(unplaced/reg_cap)·total=remaining+extra·projected=_nth_regular_term으로 순수 정규학기만 센다. 그러나 plan_greedy의 _ordered_terms는 계절학기(2026-S 등)와 첫 정규학기 +3 보너스를 적극 사용한다(재현: 플래너는 2026-S·2026-2 두 학기 배치인데 overflow는 '총 3학기'). risk.capacity(seasonal+bonus)와도 상한이 달라 세 모델(배치/risk/overflow)이 어긋난다. 또 _ordered_terms line 373은 사용자가 낮춘 override 위에 보너스를 더해(클램프된 reg_cap에 +3) 의도 부하를 초과(15→18). 개설학기 병목 시에는 학기수가 과소추정될 수도 있어 방향이 양면. 다수 중복 finding 병합.
- 수정: overflow를 _ordered_terms와 동일 capacity 헬퍼로 통일(계절·보너스 한 출처). 보너스는 법정 상한 기준으로만 더하고 사용자 override가 더 낮으면 미적용. projected_graduation_term/note에 '정규학기 기준·계절 활용 시 단축 가능' 또는 개설학기 병목 시 하한 보정을 표기.

## [MEDIUM] [REG] 필수과목 이름→코드 폴백이 by_norm 다중 hit에서 hit[0]을 맹목 선택 + 빈 course_id를 catalog_verified로 오표기
- file: graduation_center/v2/planner.py:446-458
- 문제: build_unified_candidates 보강에서 hit = cat['by_norm'].get(...) 후 len(hit) 검사 없이 cc = cat['by_code'].get(hit[0])로 첫 코드를 쓴다. mirae '다학제간캡스톤디자인'이 0693316(필수)·7159803('…+',비필수)로 정규화 충돌(+ 제거)해 임의 0693316 선택 — 선수/개설/학점 오선택 위험. 또 line 455 known=bool(terms)라 캡스톤Ⅰ/Ⅱ처럼 terms 메타는 있으나 카탈로그 매칭 실패(로마 접미사 차이)면 cid=''인데 known=True→confidence='catalog_verified'+course_id='' 후보가 생성돼 선수/개설 추적이 깨지고 신뢰도 과장. audit_v2.py:342 미이수 필수 이름 폴백도 같은 by_norm 사용. 라운드3가 MEDIUM 회귀로 명시했으나 미반영.
- 수정: len(hit)==1일 때만 cid/credits/terms/prereqs를 카탈로그로 확정. 0/다중 hit은 confidence='name_only'·manual=True로 강등. known은 'cid를 카탈로그로 확정했는가' 기준(terms 존재만으로 catalog_verified 금지). 또는 is_required=True 코드 우선 선택, 또는 required_names에 course_id 명시.

## [MEDIUM] general_need 과차감 — unfillable/unplaced 시 일반선택 과소 산정(자기보정 가정 깨짐)
- file: graduation_center/v2/planner.py:544-552
- 문제: general_need = max(0, total_gap - sel_cr)는 '모든 후보가 이수돼 total_earned에 산입'을 가정한다. happy-path에선 자기보정되나, 융합 풀 unfillable이거나 후보가 unplaced가 되면 그 학점은 실제로 total_earned에 안 들어가는데 general_need는 이미 차감한 상태로 산정돼 일반선택이 과소 산정된다(그 차이는 위 unfillable 이중계상 결함과 연결). 위 pool_exhausted finding과 같은 산식 뿌리.
- 수정: general_need를 selected 학점이 아니라 '실제 배치(plan_greedy 이후 placed)+이수확정' 학점 기준으로 산정하거나, unfillable/unplaced 발생 시 shortfall을 다시 더해 보정. pool_exhausted 이중계상 수정과 함께 단일화.

## [MEDIUM] risk 잔여학기 수용량이 total_gap만 사용 — 영역 부족 미반영(planner와 불일치로 등급 과소평가)
- file: graduation_center/v2/risk.py:70
- 문제: 수용량 D 강등은 gap=audit.total_gap > capacity로만 판정한다. 총학점은 충족(total_gap=0)이나 hard 영역(전공)이 크게 부족해 잔여로 못 채우는 경우 발동하지 않는다. 같은 상황에서 planner는 selected/unplaced로 blocked+초과학기를 산출해, planner는 '초과학기 필요'인데 risk는 roadmap_feasible=False로 C까지만 강등돼 등급 과소평가. 폐기된 project_overflow의 max(total_gap, area_shortfall) 보정을 라이브 risk가 잃음.
- 수정: capacity 비교 대상을 max(audit.total_gap, Σ(area_gaps gap>0))로 바꾸거나 planner overflow.extra_semesters>0을 직접 D 트리거로 연동.

## [LOW] [데드코드 묶음] project_overflow·confirmed_pref·LLM 플래너 경로(plan_roadmap/build_planning_context/validate_roadmap)가 클램프 안 된 옛 모델로 잔존
- file: graduation_center/v2/planner.py:63-96,136,432,211-353
- 문제: 활성 경로는 결정론 run_planner + _overflow_from_credits뿐인데 다음이 미사용으로 남아 있다(grep로 호출처 없음 확인): (1) project_overflow(63-96) — line 76 cap이 사용자 override를 법정 상한으로 클램프하지 않아(fix#7 누락) max(total_gap,area_shortfall)·1회 보너스의 다른 산식. (2) build_planning_context(136) term_cap도 미클램프. (3) confirmed_pref(432) — fix#6가 confirmed_full 7자리로 교체하며 미사용 데드변수. (4) plan_roadmap/validate_roadmap/_allowed_terms/_SCHEMA/_SYS — tests/test_v2_pipeline.py만 의존. app.py docstring·status note('로드맵만 LLM 사용')도 LLM 미사용 현실과 불일치. 재배선 시 99 override·옛 용량모델·fix#7 위반 재유입 위험. 이 항목에만 동일 신고가 12건 중복.
- 수정: project_overflow·confirmed_pref 제거. LLM 함수 보존 시 '# LEGACY LLM PATH (not wired)' 가드 + 살릴 거면 build_planning_context/project_overflow에 min(override, legal) 클램프 통일. 관련 테스트를 결정론 경로로 교체하고 app.py/status 문구를 결정론 플래너로 갱신.

## [LOW] 핵심교양 총요건이 by-year 값(17)과 gen_ed override 합(17) 두 출처에서 독립 산출 — fix#8 '단일출처' 미달(우연 일치)
- file: graduation_center/v2/audit_v2.py:296-297
- 문제: core_total_required = Σ(overrides.get(a,core_min) for a in gen_areas) or area_min['핵심교양']. mirae는 소통5+3×4=17이 by-year 17과 우연히 일치하지만, gen_areas가 비지 않는 한 'or' 우변(by-year)은 절대 쓰이지 않고 좌변(override 합)이 진짜 출처다. requirements_by_year의 핵심교양을 17→15로 바꿔도 게이지는 17 유지(조용한 드리프트). 진짜 단일출처가 아님. 동일 finding 6건 병합.
- 수정: source of truth를 하나로 고정: by-year 값이 있으면 그것을 권위로 쓰고 override 합과 불일치 시 경고/assert, 또는 by-year 핵심교양 키를 제거하고 override 합을 유일 출처로 문서화.

## [LOW] 프론트 dup 한도 비교에 epsilon 누락 — 백엔드(+0.01)와 부동소수 경계 불일치 소지
- file: frontend/src/components/GraduationV2.jsx:89,187
- 문제: 백엔드 _convergence_checks(audit_v2.py:219)는 dup_cr + c.credits <= cap + 0.01, 프론트 defaultSel(89)·dup버튼 disable(187)은 <= cap로 epsilon 없음. 정수/0.5 학점에선 퍼징 불일치 0건이라 현재 데이터로는 무해하나, 비정수 누적 드리프트나 cap 경계에서 한 과목의 dup/primary 기본 배정이 백/프론트에서 갈릴 수 있다(3차 동치 깨짐).
- 수정: 프론트 두 비교에 동일 epsilon: dup + ov[i].credits <= cap + 0.01, dupCr + ov[ovIdx].credits > cap + 0.01.

## [LOW] max_courses_per_term 제약이 결정론 플래너에서 미적용 (입력 슬롯 미소비)
- file: graduation_center/v2/planner.py:567-593
- 문제: StudentContext.max_courses_per_term(기본 6)이 모델·입력에 있으나 plan_greedy의 _try_place는 학점상한만 검사하고 학기당 과목 수 상한은 검사하지 않는다(bucket 길이 미확인). 1~2학점 슬롯이 섞이면 한 학기 6과목 초과 배치 가능. 정의된 입력 제약이 데이터 흐름에서 소비되지 않아 '데이터 관리' 루브릭상 불완전(통상 17~19학점이면 happy-path는 대체로 무해).
- 수정: plan_greedy 배치 시 len(bucket[lab]) < context.max_courses_per_term 조건 추가, 또는 의도적 미사용이면 모델/입력에서 제거해 계약 일치.

## [LOW] 재수강 처리 docstring이 동작과 반대 ('첫 이수' vs 실제 최신 이수)
- file: graduation_center/v2/verification.py:3-5
- 문제: 모듈 docstring은 '동일 코드 여러 학기면 첫 이수만 기본 포함'이라 적었으나 build_verification_table은 latest(최신 학기)만 included=True로 두고 이전 이수를 '재수강(이전 이수)'로 제외한다(39-45,66). 프론트 안내·F후 재이수 시맨틱상 최신 유지가 옳으므로 버그는 동작이 아니라 stale docstring. 유지보수자 혼동.
- 수정: docstring을 '최신 이수만 기본 포함, 이전 이수는 제외(확인 필요)'로 정정.

## [LOW] [REG] 융합 group_checks 상단 주석이 라운드3 변경과 불일치 ('배정 확정 후' → 실제 designated 기준)
- file: graduation_center/v2/audit_v2.py:155-157
- 문제: fix#1로 group_earned는 designated 전체 커버리지 기준으로 산출(243-249, 올바름)되도록 바뀌었는데 상단 주석(155-157)은 여전히 "group_checks는 '배정 확정' 후 산출 — 융합에 실제 산입되는 과목만"이라 옛 동작을 기술한다. 코드는 맞으나 주석이 거짓이라 다음 수정자가 group을 fusion_effective 기준으로 되돌릴 회귀 위험.
- 수정: 155-157 주석을 'group 최저=designated(이수 커버리지) 기준, 중복인정 한도는 총량(fusion_effective)에만'으로 수정.

## [LOW] [REG] build_unified_candidates 반환 타입 주석·docstring이 2-튜플로 stale (실제 3-튜플)
- file: graduation_center/v2/planner.py:427-429
- 문제: fix#4에서 반환이 (selected, reqs, unfillable) 3-튜플로 바뀌었으나 시그니처 -> tuple[list[dict], list[dict]]와 docstring '반환 (선택후보, 요건요약)'은 미갱신(유일 호출처 run_planner는 3-튜플 언패킹). 런타임 무해하나 정적분석/후속 호출자 오해.
- 수정: 어노테이션을 tuple[list[dict], list[dict], list[dict]]로, docstring에 unfillable(후보 고갈 요건) 추가.

## [LOW] no_candidates blocked 분기가 total_gap>0이면 도달 불가 (general 슬롯이 항상 selected를 채움)
- file: graduation_center/v2/planner.py:545-552,643-648
- 문제: 643줄 'if reqs and not selected'는 후보 0일 때 blocked(no_candidates)를 내려는 분기다. 그러나 total_gap>0이면 545줄 general_need가 양수라 일반선택 슬롯이 selected에 추가돼 selected가 절대 비지 않는다. 따라서 no_candidates는 total_gap==0인 특수상황(총학점 충족·영역 갭만)에서만 도달해 사실상 죽은/오분류 분기.
- 수정: no_candidates 판정을 general 슬롯 추가 '이전'의 요건별 후보 유무로 하거나, '카탈로그 후보 필요한 요건(전공·필수)인데 후보 0'을 별도 플래그로 반환해 643줄이 그 플래그로 판정(일반선택 슬롯 존재가 가리지 않게).

## [LOW] 초과학기 개설학기 캐비엇이 unfillable 경로에서 안 붙음 (#pool_exhausted 수정과 함께 정리 필요)
- file: graduation_center/v2/planner.py:694-696
- 문제: '(개설학기 제약으로 실제 필요 학기는 더 늘 수 있음)' 캐비엇은 unplaced 중 catalog_verified & offered_terms != ['1','2']일 때만 붙는다. pool_exhausted(unfillable)만 발생하면 unplaced가 비어 캐비엇이 절대 안 붙는다. unfillable을 overflow에서 빼는 상위 수정 후 이 분기를 unplaced 전용으로 재정렬해야 함.
- 수정: unfillable을 overflow에서 분리하는 수정과 함께 캐비엇을 unplaced 전용으로 옮기고, unfillable 경로는 overflow 없이 '후보 부족' 안내만.

## [LOW] 선수과목 검사가 5자리 절단 — 동일 prefix 과목으로 거짓충족 가능(audit 7자리와 비일관)
- file: graduation_center/v2/planner.py:568,591,671
- 문제: plan_greedy의 prerequisites·completed·placed_at 비교가 모두 course_id[:5]다. 5자리만 같은 별개 과목이 선수로 거짓 충족될 수 있다. 현 prereq 데이터가 희소(mirae 1·ai_bigdata 3)해 발현 낮으나, audit이 0365007↔0365008 충돌을 7자리로 막은 것과 비일관. 위 plan_greedy high finding(5자리 절단)과 같은 뿌리이며 함께 7자리 통일로 해소.
- 수정: 선수/배치/이수 비교를 7자리 전체 course_id로 통일. 5자리 절단이 꼭 필요하면 충돌 검출 가드.

## [LOW] 다학제간캡스톤디자인 vs '…+' 정규화 충돌로 by_norm 다중 hit — 이름매칭 unresolved 강등/오탐
- file: graduation_center/v2/text_norm.py:43, graduation_center/v2/catalog.py:166-170
- 문제: normalize_name이 '+'를 제거해 catalog_mirae_mobility의 '다학제간캡스톤디자인'과 '다학제간캡스톤디자인+'가 동일 키로 충돌(by_norm 길이 2). match_course는 len(hits)==1일 때만 이름 매칭하므로 코드 미일치·이름만 있는 행은 매칭 실패→aggregate_only/unresolved로 떨어지고, 요람 필수명 이름체크(_taken)도 둘을 구분 못 해 오탐/누락 가능. 위 hit[0] 맹목선택 finding과 같은 데이터 원인.
- 수정: 정규화에서 의미 있는 접미사('+', P/F, 차수)를 보존하거나 by_norm 충돌 시 credits/group 보조키로 disambiguate. 최소한 충돌 키를 빌드 리포트 경고로 노출.

## [LOW] 엑셀 헤더 탐지·컬럼 매핑이 정확 문자열 일치라 헤더 변형에 비견고
- file: graduation_center/v2/excel_parser.py:16-20,57-61,92-93
- 문제: _find_header는 셀 == '교과목코드' 정확 일치만 헤더로 인정하고 컬럼 매핑도 label in _LABELS 정확 일치다. '교과목 코드'(내부 공백)·'학수번호'·'과목명'·'학점(이수)' 등 변형이 오면 헤더 미검출 또는 컬럼 누락(학점 0). _s는 앞뒤 공백만 strip. 프로토타입 happy-path는 준비된 양식이라 무해하나 견고성 미달.
- 수정: 헤더 매칭을 정규화(내부 공백 제거 + 동의어 사전: 교과목코드/학수번호, 교과목명/과목명, 이수구분/이수구분명)로 완화. fail_fast_columns가 누락을 422로 돌려주므로 동의어 추가만으로도 상승.

## [LOW] 융합 overlap 과목이 일반선택으로 재분류되면 primary_effective가 실제 전공학점과 불일치
- file: graduation_center/v2/audit_v2.py:151-153,206-241
- 문제: designated는 requirement_area가 GYO만 아니면 포함하므로 verification에서 '일반선택'으로 재분류된 타전공/미매칭 과목도 코드 prefix가 융합 카탈로그에 있으면 overlap/designated로 잡힌다. 그러나 primary_major_earned는 earned['전공']뿐이라 그 과목은 빠진다. primary_base=max(0, primary_earned-overlap_cr)는 0으로 클램프되지만 배정 로직은 dup/to_primary로 overlap 전체를 primary_effective에 산입해 StatBox '제1전공(배정 반영)'이 major 게이지와 어긋난다.
- 수정: overlap/designated 판정을 requirement_area=='전공' 과목으로 한정하거나, 재분류된 일반선택이 융합 코드에 매칭되면 verification에서 전공/융합 후보로 승격하는 일관 규칙. 최소한 to_primary 상한을 primary_base 클램프분으로 둬 실제 전공 이수 학점을 넘지 않게.

## [LOW] 전공·융합 gap이 동일 겹침 자유도에서 이중 감점 가능(risk severity 합산) — 디폴트 배정만 반영
- file: graduation_center/v2/risk.py:50-58,80-88
- 문제: 겹침학점 디폴트 배정에서 to_fusion>0이면 major_effective가 전공 area_gap을 만들고(audit 288-289), 동일 한도초과 겹침이 fusion gap도 만들 수 있다. risk는 max_area_gap(전공, severity≤20)과 융합전공(severity≤14)을 독립 합산해 같은 근본 부족을 이중 감점할 수 있고, 사용자가 3-way로 바꿀 수 있는 디폴트 한 가지만 반영(최선/최악 미고려).
- 수정: 겹침에서 비롯된 전공·융합 gap을 '재배정으로 동시 해소 가능분'과 '진성 신규수강분'으로 구분해 전자는 한쪽에서만(또는 severity 0) 감점, 또는 동일 자유도 두 factor의 합산 severity 상한.

## [LOW] [거짓양성] WorkflowGraph '리포트' 터미널 노드는 프론트가 합성 점등 — backend trace 불요
- file: frontend/src/components/WorkflowGraph.jsx:37
- 문제: 여러 findings가 '리포트 노드가 trace에 없어 영구 미점등'이라 지적하나 코드 확인 결과 거짓양성이다. WorkflowGraph는 execKeys = trace 노드들 + (있으면) '리포트'를 직접 push한다(line 37: if (ks.length) ks.push('리포트')). 따라서 backend NodeTraceEvent가 없어도 replay 시 마지막 '리포트' 터미널 노드가 점등된다. 데모 시각적 흠은 발생하지 않음.
- 수정: 수정 불필요. 굳이 backend에 리포트 노드를 명시하고 싶다면 run_audit 끝에 NodeTraceEvent(node='리포트', kind='tool', summary='컨설팅 리포트 조립')를 추가할 수 있으나 점등에는 영향 없음(이중 push 방지 확인).
