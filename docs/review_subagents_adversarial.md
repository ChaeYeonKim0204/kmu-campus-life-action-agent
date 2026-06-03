# 서브에이전트 적대적 리뷰 종합 (8명, raw 54, 확정 41)

## [HIGH] [로드맵 핵심] plan_greedy가 선수과목(prerequisites)을 전혀 검사하지 않아 의존 과목이 선수보다 먼저/같은 학기에 배치됨 — 데모 깨짐
- file: graduation_center/v2/planner.py:486-525 (plan_greedy), build_unified_candidates:435-436, run_planner:556-562
- 문제: 런타임 결정론 경로(run_planner→plan_greedy)가 추천 학기별 로드맵의 본체다. plan_greedy는 후보를 (priority, -credits)로만 정렬해 '맞는 첫 학기'에 채우고(488-505행) it.get('prerequisites')를 한 번도 보지 않는다. 전공 pool(435-436행)에는 prerequisites가 실려 오는데도 무시된다. 선수 검증이 있는 validate_roadmap(334-337행 prereq_unmet)은 LLM 경로(plan_roadmap) 전용으로 결정론 경로에서 호출되지 않는 사실상 죽은 코드다. 또 plan_greedy는 completed 집합(이미 이수한 선수)도 전달받지 못한다. 결과: 선수과목이 있는 과목이 선수보다 이른/같은 학기에 떨어진 '수강 불가능한 로드맵'을 feasible=True로 제시한다. 카탈로그에 실제 선수관계 존재(예 catalog_ai_bigdata.json: 경영데이터분석←인공지능수학 등). _SYS 프롬프트('선수과목 순서를 지켜라')와 정면 배치되고, 메인 기능 신뢰가 깨진다.
- 수정: plan_greedy에 completed 집합(verified.confirmed_courses의 course_id)을 전달하고, 배치 시 모든 prerequisites가 completed이거나 '엄격히 더 이른' term bucket에 이미 배치됐을 때만 같은/이후 학기에 배치하도록 위상 제약 추가(prior_planned 누적 유지). 배치 후 prior-term 위반 재검사 → 위반 시 재배치/unplaced. 융합·필수·교양 후보 dict에도 prerequisites를 일관되게 실어 보낼 것.

## [HIGH] [로드맵 핵심] 교양 부족분을 단일 N학점 슬롯으로 만들어 학기 분할 불가 → 잔여학기 충분해도 거짓 '실현불가(blocked)', overflow와 모순
- file: graduation_center/v2/planner.py:447-462 (슬롯 생성), 504 (원자 배치), 566-575 (blocked), 63-96 (project_overflow)
- 문제: 기초/핵심/자유교양 부족은 credits=부족학점 전체인 pool 항목 1개로 만들어진다(449,455,461행). plan_greedy는 항목을 원자적으로 배치(504행 used[lab]+credits<=cap)하므로 9·15학점짜리 단일 슬롯을 여러 학기로 쪼갤 수 없다. 전공이 학기를 거의 채운 뒤 큰 교양 슬롯이 남으면 어느 한 학기에 통째로 못 들어가 unplaced→feasible=False·blocked로 처리된다(566-575행). 반면 project_overflow(72-82행)는 학점을 분할 가능한 capacity로 보고 '잔여학기로 충분(return None)'이라 판단하므로, 같은 학생에 'overflow 없음 + 로드맵 blocked'라는 모순 화면이 데모에 그대로 뜬다.
- 수정: 교양/슬롯 부족분을 학기당 상한(또는 3학점) 단위로 잘게 쪼갠 여러 슬롯 항목으로 생성하거나, plan_greedy가 generic_slot 항목을 학기별 잔여 capacity만큼 부분 배치(분할)하게 처리. 분할 후 합이 need가 되도록.

## [HIGH] [로드맵 핵심] 초과학기(overflow) capacity가 계절학기를 무시 → 로드맵은 계절학기로 다 배치(feasible)인데 동시에 '초과학기 필요' 카드 출력
- file: graduation_center/v2/planner.py:76-96 (project_overflow) vs _ordered_terms:375-376, plan_greedy:497-505, pipeline.py:128-134, frontend GraduationV2.jsx:687
- 문제: project_overflow의 capacity = remaining*cap + bonus 로 계절학기(SEASONAL_TERM_CAP=6) 수용량을 전혀 더하지 않는다(76-81행). 반면 _ordered_terms는 seasonal_semester_allowed면 계절학기를 6학점 cap으로 실제 추가하고(375-376행) plan_greedy가 거기에 채운다. 프론트 기본값 seasonal_semester_allowed=true(GraduationV2.jsx:211)라 사실상 모든 사용자에서, greedy는 unplaced=[] (feasible=True, 완성 로드맵)인데 project_overflow는 '초과학기 N학기 필요' 카드를 띄운다. 같은 입력에 두 결정론 모듈 용량 모델이 불일치.
- 수정: overflow를 plan_greedy 실제 미배치(unplaced) 결과에서 파생시켜 단일 용량 모델로 통일(로드맵이 feasible이면 overflow=None 강제). 그게 어려우면 project_overflow에 계절학기 수용량을 risk.py/_ordered_terms와 동일 공식으로 반영. (project_overflow·risk·_ordered_terms 공용 term_capacity 헬퍼로 추출 권장.)

## [HIGH] [로드맵 핵심] 초과학기 shortfall이 연계·융합전공(다전공36/부전공18) 부족을 누락 → '초과학기 불필요'인데 로드맵은 융합후보를 못 배치해 blocked
- file: graduation_center/v2/planner.py:72-73 (shortfall), build_unified_candidates:418-431
- 문제: shortfall=max(total_gap, sum(area_gaps where gap>0))인데 area_gaps는 HARD_AREAS(전공/기초/핵심/자유)만 담고(audit_v2.py:22,250) convergence_checks(융합 36·연계 18)는 별도 리스트라 합산되지 않는다. 그런데 build_unified_candidates는 융합 부족분을 priority2 후보로 실제 플래닝한다(418-431행). 따라서 융합 36학점이 통째로 미이수여도 project_overflow는 그 36을 빼먹고 '잔여학기로 충분'이라 None 반환할 수 있는 반면, plan_greedy는 그 융합 후보들을 배치하려다 unplaced→feasible=False·blocked로 만든다. risk.py(78-86)는 융합 갭을 등급에 반영하므로 'risk 위험 + overflow 불필요 + 로드맵 blocked' 3중 모순.
- 수정: shortfall에 convergence 순증 부족분을 더한다: conv_short = sum(max(cc['gap'],0)). 단 제1전공 갭과 중복인정 가능분(double_recognizable) 겹침은 이중계상되므로 융합전용 순증분만 더하거나 overlap/cap 정보를 활용. 최소한 융합 갭이 있으면 overflow를 None으로 조기반환하지 않게 가드.

## [HIGH] [로드맵 핵심] 현재학기 미입력 시 '학기 배치 불가'가 초록 ✅ 성공 박스로 잘못 렌더 — happy-path 데모에서 졸업 부족 학생이 '충족'으로 보임
- file: frontend/src/components/GraduationV2.jsx:631-635 (백엔드 planner.py:548-554)
- 문제: current_term이 비면 run_planner는 status='generated', feasible=None, terms=[], why_this_plan='현재 학기 미입력 — 학기 배치 생략. 추가 이수 권장: [긴 과목 목록]'을 반환한다(548-554행). 프론트는 status==='generated' && terms.length===0 조건만 보고 무조건 초록 배경+✅ 박스로 why_this_plan을 출력한다(631-635행). 결과: 졸업요건이 한참 부족한데 current_term만 안 넣은 학생에게 미이수 목록이 '졸업 충족'처럼 초록 성공으로 표시된다. feasible===null(미상)과 진짜 충족(terms=[] + gap없음 + feasible===true, planner.py:542)이 프론트에서 구분되지 않는 게 근본 원인.
- 수정: 프론트에서 feasible===null인 경우를 별도 분기로 빼 중립/경고 색으로 '현재 학기를 입력하면 학기 배치를 제공합니다'를 안내하고, 진짜 충족(terms===[] && feasible===true && 모든 gap<=0)일 때만 초록 ✅ 박스를 렌더. 백엔드 feasible 값을 분기 조건에 추가.

## [HIGH] [로드맵 핵심] 연계융합 그룹별 최저(per_group_min) 미충족이 로드맵·'남은 요건'·'충족' 판정에서 누락 — risk는 빨강인데 융합블록/로드맵은 충족
- file: graduation_center/v2/planner.py:419-420 + frontend GraduationV2.jsx:105,109,642
- 문제: 다전공은 총36 외에 그룹별 최저(다전공 12)가 hard 제약이다. 학생이 총 36을 채워도 한 그룹이 미달이면 risk.py:78-86은 group_short로 융합 위험을 강등한다. 그러나 (1) build_unified_candidates는 cc.gap(총합)>0일 때만 융합 후보를 추가하고 need=cc['gap']이라(419-431행) 총합은 채웠지만 그룹 부족인 케이스에 후보를 0개 배치, (2) 프론트 '남은 요건' 요약도 cc.gap>0만 검사(GraduationV2.jsx:642)해 그룹 부족 미표시, (3) ConvergenceBlock fits는 fusionCr>=cc.required만 보고 group_checks 무시(105행), suggest의 fusionGap도 total 기반(109행)이라 '✅ 둘 다 충족' 초록 메시지를 띄운다. risk 빨강 vs 융합블록/로드맵/요약 충족의 정면 모순.
- 수정: 유효 부족 = max(cc.gap, Σ그룹 gap)으로 통일. planner 조건을 'cc.gap>0 or any group gap>0'로 바꾸고 need를 그룹 quota까지 채우게 그룹 단위로 후보 선택(아래 medium '총 gap만 채움'과 함께). 프론트 fits/suggest/'남은 요건'도 group_checks.gap>0을 반영(fits = ... && group_checks.every(g=>g.gap<=0)).

## [HIGH] [로드맵 핵심] run_planner의 검증(ValidationReport)이 학점상한만 보고 미배치·선수·미개설·중복·갭미충족을 무시 → 워크플로우 그래프에 거짓 '통과' 점등
- file: graduation_center/v2/planner.py:556-576 (run_planner), pipeline.py:72-77 (검증/repair 노드)
- 문제: run_planner의 report는 over_credit_cap만으로 errors를 채운다(557-561행). plan_greedy가 후보를 다 못 넣어 unplaced가 생기면 plan.feasible=False·blocked_reason은 설정되지만 report.ok는 여전히 True다(unplaced를 errors에 안 넣음). validate_roadmap(266-353행, 선수·not_offered·중복·gap_not_closed·required_not_planned 검사)은 결정론 경로에서 호출되지 않는 죽은 코드다. pipeline.py:72-77 '검증/repair' 노드는 vrep.ok로 branch_taken을 정하므로 실현 불가 로드맵인데도 검증 노드가 '통과'로 점등된다 — 교수가 채점하는 Dify식 노드 그래프에 '로드맵 blocked인데 검증은 통과'라는 거짓 통과가 표시된다.
- 수정: run_planner에서 unplaced 발생 시 ValidationError(code='unplaced'/'gap_not_closed')를 report.errors에 추가해 report.ok=False로 만들고, placed 결과에 대해 validate_roadmap 수준 재검증(필수 포함·영역 갭·선수·개설학기) 실행. pipeline의 검증 노드 branch_taken을 plan.feasible/blocked와 일관되게 표시.

## [HIGH] [로드맵 핵심] 워크플로우 trace가 실제 실행과 불일치 — 결정론 경로인데 '로드맵 플래닝'을 kind=llm로, repair/blocked 분기를 거짓 방출(rubric trace 정확성 위반)
- file: graduation_center/v2/pipeline.py:59,69,72-77
- 문제: run_planner는 결정론 greedy 플래너로 LLM·repair를 호출하지 않는다(planner.py:533 주석 'LLM 배치 미사용'; repair_attempted 항상 False). 그런데 node_trace는 '로드맵 플래닝' 노드를 kind='llm'으로(pipeline.py:69), '검증/repair' validator 노드를 방출한다. plan.status는 'generated'/'not_generated'만 set되고 'blocked'는 코드에서 set되지 않아(planner.py는 status는 generated 유지·feasible=False만), pipeline.py:59,75의 'blocked' 분기와 'repair 후 통과' 분기는 도달 불가 죽은 라벨이다. 교수가 그래프를 눈으로 검수하는 채점 포인트에서 LLM/repair 노드가 점등되지만 실제로는 아무것도 안 도는 '거짓 노드'로 신뢰를 깬다.
- 수정: 기본 결정론 경로 trace를 실제 실행에 맞춰라: 플래닝 노드 kind를 'tool'/'branch'로, 노드명을 '결정론 로드맵 배치'로. repair/LLM·blocked 분기는 실제 plan_roadmap+validate_roadmap을 쓰는 경로에서만 방출. 도달 불가 분기 라벨 제거. (status='blocked'를 실제로 set하려면 위 검증 finding과 함께 unplaced 시 status='blocked' 통일.)

## [HIGH] [데이터 모순] 연계융합 earned/gap이 중복인정 한도(cap)를 무시하고 겹침학점을 전공·융합 양쪽에 전액 이중계상 — 백엔드 '충족' vs 프론트 StatBox '부족'이 한 화면에 동시 표출
- file: graduation_center/v2/audit_v2.py:152-155,168-169 + verification.py:98 + pipeline.py:98-100 + frontend GraduationV2.jsx:102-103,572
- 문제: _convergence_checks의 designated는 융합 카탈로그 prefix 과목 전부, earned=sum(designated)(154행), gap=max(0,req-earned)(155행)를 cap 무관 산출한다. 동시에 그 overlap(168행) 과목은 verification에서 area='전공'으로 earned_by_area['전공']에 전액 들어가(verification.py:98) area_gaps['전공']·프론트 메인 전공 게이지(GraduationV2.jsx:572)에도 계상된다. 즉 학사규정 제77조 한도(다전공12/부전공6) 초과 겹침분이 제1전공·융합 양쪽에 동시 전액. 실측: overlap 36·cap 12면 백엔드 전공 earned=36·융합 earned=36/36 둘 다 '충족'으로 뜨지만 실제론 24는 한쪽에만 인정돼 한 요건은 미충족이어야 함. 프론트 ConvergenceBlock의 fusionCr=fusion_base+(dup+fusion선택)(103행)은 cap을 지켜 계산하므로, 같은 카드 안에서 백엔드 '충족' vs StatBox '부족'이 동시 표출돼 시연 중 교수가 바로 본다. risk.py:80 eff_gap, pipeline.py:99 markdown, planner build_unified_candidates(419행)도 모두 이 과대평가 gap을 신뢰. 코드 상단 TODO(107-113)가 미구현을 인정.
- 수정: 백엔드 earned/gap을 cap-aware로 통일: recognized = fusion_base + min(overlap_cr, cap)을 source of truth로 삼아 gap 계산(docstring 121-122행은 이미 이 산식을 적었으나 154행 미반영). risk/markdown/roadmap이 쓰는 cc['gap']은 '겹침을 제1전공에 우선 배정'한 보수 가정으로 잡아 대시보드와 일치. 또는 프론트 fits 산식을 백엔드 single source로 삼아 양쪽이 동일 산식을 쓰게 함.

## [HIGH] [데이터 모순] 3-way 배정이 프론트 state만 바꾸고 risk·roadmap·markdown은 기본가정(중복인정 전액)으로 동결 — 사용자 선택이 진단에 반영 안 됨
- file: frontend/src/components/GraduationV2.jsx:97-105 + risk.py:78-86 + pipeline.py:98-99 + GraduationV2.jsx:642
- 문제: ConvergenceBlock의 sel(3-way 선택)은 컴포넌트 로컬 state일 뿐 백엔드로 재전송·재사정되지 않는다(97-105행 로컬 계산). 반면 종합 리스크(risk.py:78-86은 cc.gap·group_checks), 로드맵 '남은 요건'(GraduationV2.jsx:642 cc.gap), report_markdown(pipeline.py:98-99 cc['earned']/cc['gap'])은 전부 백엔드 '기본=중복인정 전액' 고정값을 쓴다. 사용자가 겹침을 제1전공으로 돌려 융합이 부족해져도 히어로 등급·로드맵·다운로드 리포트는 안 바뀌어, StatBox '12학점 부족'인데 등급 'A 안전'/로드맵 '충족' 모순.
- 수정: 3-way 배정 확정값을 context에 담아 /audit를 재호출('재사정' 버튼)하거나, 최소한 risk·roadmap·markdown이 프론트 배정 반영 fusionCr/primaryCr와 동일 산식을 쓰도록 단일화. 결정론·일관성 루브릭상 배정 변경 시 백엔드 재계산 트리거 권장.

## [HIGH] [데이터 정합] 학번 요람 매칭이 두 경로에서 불일치 — 필수과목은 근사연도(2023), 영역최저학점은 정확연도(2025폴백)만 → 혼종 진단
- file: graduation_center/v2/catalog.py:102-112 (_requirements_by_year) + audit_v2.py:32-47 (_required_names_for_year) + audit_v2.py:282-283
- 문제: 같은 학번에 두 경로가 다른 요람을 적용한다. catalog._requirements_by_year는 '정확 연도만' 매칭(by_year.get(str(year)), 110-111행)이라 2024학번처럼 데이터 없는 연도는 None→graduation_requirements.json(=2025 기준 기초7) 폴백. 반대로 audit._required_names_for_year는 '입학연도 이하 가장 가까운 요람'(42-44행)→2024학번은 2023요람 필수명 적용. 결과: '필수과목은 2023요람·영역최저는 2025요람' 혼종. 게다가 compute_audit(282-283행)이 profile.applied_yoram을 '2023 요람 (학번 2024 기준)'으로 덮어쓰므로, 화면 라벨은 2023이라 주장하면서 영역최저는 2025값을 쓰는 모순까지 발생.
- 수정: 두 경로 연도선택을 단일 헬퍼(program_id,year)→applied_year로 통일. 정책을 '입학연도 이하 가장 가까운 보유 요람'으로 정하고 _requirements_by_year도 nearest-≤ 로직을 쓰게 함. applied_yoram 라벨·catalog·area_min·필수명이 전부 같은 연도를 가리키게 강제. (아래 '학번 미상 fallback 엇갈림' medium과 동일 리팩터로 함께 해결.)

## [HIGH] [데이터 정합] 핵심교양 총요건이 audit(영역최저합 17)와 graduation_requirements.json(15/소계24)에서 영구 불일치 — 동일출처 원칙 위반, 영역 선택제 검증 필요
- file: graduation_center/v2/audit_v2.py:244-262 + data/graduation/graduation_requirements.json(미래모빌리티.교양)
- 문제: audit_v2.py:247 core_total_required = sum(overrides.get(a,core_min) for a in gen_areas) = 소통5+나머지4×3 = 17을 핵심교양 총요건으로 삼고 5개 영역 각각 최저를 gap으로 잡는다(258-262행, '모든 5개 영역 필수' 의미). 그러나 graduation_requirements.json은 핵심교양=15·소계24(확인됨)로 총 15만 요구. 둘 중 하나가 틀렸다: 15가 맞으면 전영역 강제(17)는 거짓 미충족 경보, 17이 맞으면 데이터가 stale(소계도 26이어야). v1 compute_structured_check 등 다른 소비자가 15를 읽으면 같은 학생에 다른 졸업판정. KMU 핵심교양이 실제로 5영역 전부 이수를 요구하는지(보통 일부 선택제) 요람 원문 검증 없이 코드가 '전영역 필수'를 단정.
- 수정: 요람 원문으로 '5개 영역 전부 최저이수 필수' 여부 확인. 사실이면 graduation_requirements.json 핵심교양=17·소계=26으로 갱신하고 영역최저 override(소통5)도 같은 파일에 명시해 v1/v2 동일 값 사용. 영역 선택제면 audit_v2.py:247 '전영역 합산'을 실제 영역요건으로 교체. 어느 쪽이든 단일 출처화.

## [HIGH] [데이터 정합] 2023 by-year에 핵심교양 키 없어 profile.area_min[핵심교양]=15(2025값) 폴백 — by-year 영역합(119)+15≠졸업합계 136
- file: data/graduation/v2/requirements_by_year.json:5-12 + graduation_center/v2/catalog.py:126
- 문제: requirements_by_year.json mirae_mobility/2023은 전공62·기초8·자유2·일반47·졸업합계136만 있고 핵심교양 키가 없다(확인됨). catalog.py:126 (yr or {}).get('핵심교양', gyo.get('핵심교양',0))가 없는 키를 기본값 15로 폴백한다. 그러나 by-year 영역합 62+8+2+47=119이고 136-119=17이 implied 핵심교양 — 데이터상 17이어야 하는데 profile.area_min['핵심교양']=15가 박힌다. audit area_gaps는 core override합(17)을 쓰지만, profile.area_min['핵심교양']=15는 risk.py/planner 등 다른 소비자에 잘못 노출되고 영역합 invariant(119+15=134≠136)가 깨진다.
- 수정: requirements_by_year.json mirae_mobility/2023에 "핵심교양": 17 추가(영역합=졸업합계 136 일치). catalog.py에서 by-year 존재 시 핵심교양도 by-year에서 필수로 읽도록(누락 시 build-time 검증 실패) 변경. 영역최저합==졸업최저합계 invariant 단위테스트 추가.

## [HIGH] [데이터 정합] 본인 전공선택 과목이 카탈로그 미매칭 시 무음으로 일반선택 강등 — 2023학번 vs 2025카탈로그 mismatch에서 전공 학점 과소집계
- file: graduation_center/v2/verification.py:54-58
- 문제: build_verification_table는 코드/이름 매칭 실패 시 status=aggregate_only로 두고, area_raw가 '전공선택/전공필수'면 area='전공'이 된 뒤 57행에서 무조건 '일반선택'으로 재분류한다. 의도는 '타과·다전공 전공과목은 일반선택'이지만, 카탈로그가 2025 요람으로만 빌드돼(MEMORY: applied-yoram-by-admission-year) 2023학번 학생의 본인 학과 전공과목이 명칭/코드 개편으로 코드·이름 둘 다 매칭 실패하면 본인 전공 학점이 조용히 일반선택으로 빠져 전공 earned 과소집계. 화면/리포트에 강등 사유 표시가 없어 학생이 알 수 없고 HITL로도 복구 어렵다.
- 수정: aggregate_only && area=='전공' 라인은 무조건 강등하지 말고 (a) exclude_reason/note에 '전공 추정이나 카탈로그 미매칭 — 본인전공 여부 확인 필요'를 달아 HITL에서 되돌릴 수 있게 하거나, (b) name 부분일치/alias로 본인 카탈로그 재시도 후 실패한 것만 강등. 최소한 강등 과목 수/학점을 audit에 노출. 데모는 매칭 가능한 더미로 한정.

## [HIGH] [데이터 정합] risk.py 잔여학기 capacity가 project_overflow와 학기상한·계절학기 처리 불일치 — risk는 D 안 띄우는데 overflow는 '초과학기 필요'(또는 반대)
- file: graduation_center/v2/risk.py:62-71 vs planner.py:76-81
- 문제: risk.compute_risk은 term_cap = context.max_credits_per_term or 18(하드코딩 18 폴백) + 계절 6 1회 + 보너스로 capacity 계산(62-67행). 반면 project_overflow는 cap = override or regular_term_cap(profile.total_credits_min)(120/130/136→17/18/19)에 계절학기 +0(76-81행). 즉 override 비면 risk=18 vs overflow=17/19로 상한 불일치, 계절학기 risk +6 vs overflow +0. 프론트 기본 seasonal_semester_allowed=true(GraduationV2.jsx:211)라 사실상 모든 사용자에서 갈린다. 결과: risk 'D 졸업불가' 미표시인데 초과학기 시나리오는 '못 채움'(또는 반대) 자기모순이 데모에 노출. risk.py는 profile 인자도 안 받아 요람별 상한을 모름.
- 수정: capacity 계산을 공용 헬퍼 term_capacity(context, profile)로 단일화. risk.compute_risk에 profile을 넘겨 regular_term_cap(profile.total_credits_min) 공통 사용(하드코딩 18 제거), 계절학기 가산 정책을 risk·project_overflow가 동일 적용.

## [MEDIUM] [데이터 정합] 융합 group_earned도 cap 미적용 — 그룹별 최저 충족을 과대평가
- file: graduation_center/v2/audit_v2.py:160-166
- 문제: group_checks의 group_earned는 designated 과목을 그룹별 합산하는데(154행 earned와 동일 풀) 겹침 과목이 cap 없이 전부 포함된다. 따라서 제1전공과 겹치는 과목이 한도를 넘어도 그룹별 최저(다전공12/부전공6)를 충족한 것처럼 표시될 수 있다. 그룹 최저는 한쪽에만 산입되는 겹침분으로는 실제 충족 안 될 수 있는데 headline gap=0으로 떨어진다.
- 수정: group_checks도 배정(primary/fusion/dup) 결과를 반영한 net 학점으로 계산하거나, 프론트처럼 shortGroups를 배정 후 재평가하도록 백엔드에서 cap-aware group earned를 별도 필드로 제공.

## [MEDIUM] [로드맵] 연계융합 후보 선택이 총 gap만큼만 채워 그룹별 최저(다전공12/부전공6)를 보장 못함
- file: graduation_center/v2/planner.py:419-431,474-482
- 문제: 융합 부족 need=cc['gap'](총 부족)으로 잡고 build_unified_candidates 선택 루프는 acc>=need까지만 후보를 담는다(476-482행). 정렬이 부족그룹 우선(short)이라 부분 완화는 되지만 총 gap 충족 시점에서 멈추므로 per_group_min 미달 그룹이 남아도 추가 후보를 안 뽑는다. 그룹별 최저가 졸업요건 hard 제약인데 로드맵이 미충족인 채 '완료'처럼 배치. (위 high '그룹최저 누락'의 백엔드 후보생성 측면.)
- 수정: 융합 후보 선택을 그룹별 잔여 최저(group_checks gap)를 각각 충족하도록 분할 quota로 뽑은 뒤 총 need까지 보충. 검증 단계에서 그룹별 최저 미충족을 에러로 surfacing.

## [MEDIUM] [데이터 정합] 이름기준 필수 충족 판정이 area-agnostic — 일반선택으로 강등된 과목이 전공필수 충족하면서 전공 학점엔 미반영(모순 진단)
- file: graduation_center/v2/audit_v2.py:271-279
- 문제: missing_required 판정 confirmed_norm은 모든 confirmed_courses의 normalize_name으로 area 무관 매칭이다. 위 verification 강등으로 본인 전공필수가 일반선택으로 빠져도 _taken()이 True가 돼 '미이수 필수'에선 빠진다. 그러나 그 학점은 earned_by_area['일반선택']로 가서 전공 area_gap엔 반영 안 됨. 결과: '필수는 다 들었다'면서 동시에 '전공 학점 부족'이 뜨는 모순 진단, 학생은 어느 쪽을 믿어야 할지 모름.
- 수정: 필수 충족 판정에 area 정합 조건 추가(전공 필수는 requirement_area=='전공'인 confirmed만 인정)하거나, verification 강등을 바로잡아 두 판정이 같은 분류를 보게 함. 최소한 '필수 충족이나 학점이 일반선택으로 집계됨 — 이수구분정정 필요' 경고를 묶어 표시.

## [MEDIUM] [데이터 정합] _required_meta와 _required_names_for_year의 요람연도/입학연도 폴백 규칙이 갈려 미이수 필수의 학점·개설학기가 다른 연도에서 옴
- file: graduation_center/v2/planner.py:380-395 (_required_meta) vs audit_v2.py:32-47,98-104,268-269
- 문제: (1) year가 모든 보유 연도보다 작을 때 audit은 avail[0](가장 이른 요람, 44행), planner는 avail[-1](가장 최신, 388-389행)을 고른다. (2) build_unified_candidates는 _required_meta에 profile.admission_year를 넘기나(408행), audit은 _admission_year(transcript 추정 폴백, 268행)를 쓴다. admission_year가 None이면 audit는 추정연도 요람 필수명을, planner는 year None→avail[-1](최신) 메타를 읽어, 미이수 필수의 credits·offered_terms가 audit이 '누락'으로 본 요람과 다른 연도에서 와 학점합·개설학기 hard-check 신뢰도 훼손.
- 수정: 요람 선택을 단일 함수(_pick_yoram_year(program_id,year))로 통합해 audit·planner·_required_meta가 모두 호출. fallback 정책(이른 vs 최신)을 한 곳에서 결정. 연도 인자도 양쪽 _admission_year(profile, verified) 동일 소스 사용. (위 high '필수=근사·영역최저=정확' 리팩터와 함께.)

## [MEDIUM] [데이터] 2025요람 required_names가 문자열 리스트뿐 — _required_meta가 학점 3.0·개설학기 미정으로 디폴트(실제 1~2학점 과목 과대계상)
- file: graduation_center/v2/planner.py:380-395 + data/graduation/v2/required_names_by_year.json(mirae_mobility/2025)
- 문제: required_names_by_year.json의 2023은 {name,credits,terms} 객체지만 2025는 19개 문자열 리스트뿐(확인됨). _required_meta는 isinstance(it,dict)일 때만 meta를 채우므로(392행) 2025요람 적용 학생은 모든 필수 meta가 비어 build_unified_candidates에서 credits=3.0·offered_terms=['1','2']로 디폴트(413-414행). 일반물리실험Ⅰ(1)·S-TEAM Class(1) 등 1학점 과목이 3학점으로 과대계상돼 로드맵 학점합·학기배치(제32조 상한)가 틀어지고 개설학기 제약이 사라져 잘못된 학기에 배치될 수 있다.
- 수정: required_names_by_year.json 2025 리스트도 {name,credits,terms} 객체로 채운다(2025요람 p772-773 기준). meta 부재 시 디폴트 3.0 대신 confidence='name_only'로 표시하고 학점 합산에서 제외하거나 확인 플래그를 띄우게 변경.

## [MEDIUM] [데이터] 기초교양 필수 판정의 부분일치(substring)가 거짓양성 — 한 과목이 두 요건을 동시 충족
- file: graduation_center/v2/audit_v2.py:83-95 (line 93)
- 문제: _gen_basic_view의 taken = any(key in t for t in taken_norm)는 정규화 이름 부분일치다. 'collegeenglish'와 'englishconversation'은 'collegeenglishconversation'의 부분문자열이므로 단일 'College English Conversation' 한 과목으로 두 요건이 모두 taken 표시될 수 있다. '글쓰기'(짧은 키)도 '과학글쓰기'·'글쓰기와토론'에 흡수돼 거짓충족. '택1·ABEEK접미사 흡수' 의도는 이해되나 짧은 키에서 과매칭.
- 수정: 부분일치를 한정: (a) startswith로 좁히거나 (b) 매칭된 taken 과목을 소비(1:1 그리디 배정)해 동일 과목이 복수 요건 동시 충족 못하게, (c) 짧은 키는 정확일치만 허용하고 알려진 접미사(ABEEK)만 정규식으로 흡수.

## [MEDIUM] [데이터] 기본 학과 ai_bigdata에 연도별 요람 데이터 없어 학번 무관 항상 '2025 요람'·130학점 — 'KMU는 학번 요람을 본다' 차별점이 데모 학과에서 무력화
- file: graduation_center/v2/catalog.py:133 + frontend GraduationV2.jsx:208
- 문제: requirements_by_year.json·required_names_by_year.json은 mirae_mobility만 보유. 기본 program_id는 ai_bigdata(GraduationV2.jsx:208)인데 연도 데이터가 없어 _requirements_by_year가 None 반환(catalog.py:111), area_min/total은 graduation_requirements.json(2025) 폴백, applied_yoram도 yr None이라 무조건 '2025 요람' 고정(catalog.py:133). 2020·2022학번이 ai_bigdata로 시연하면 학번을 넣어도 2025 요람이 적용돼 핵심 차별점이 무력화. UI 힌트 '→ 2022 요람 적용'과 리포트 '적용 요람 2025'가 불일치.
- 수정: 데모 기본 학과를 연도 데이터가 있는 mirae_mobility로 바꾸거나 ai_bigdata 연도별 요람 데이터를 채운다. 연도 데이터 없을 때 applied_yoram을 '2025 요람(학번별 데이터 미보유 — 최신 요람 적용)'처럼 정직하게 표기.

## [MEDIUM] [데이터] 학기당 상한 17/18/19 자동 미작동 — programs.json에 max_credits_per_term 없어 항상 18 전송, 136학점 학과는 실제 cap 19를 못 받음
- file: frontend/src/components/GraduationV2.jsx:210-211,232-234,245
- 문제: ctx 기본 max_credits_per_term=18(211행). 자동채움(232-234행)은 programs[id].max_credits_per_term에 의존하나 programs.json의 모든 학과가 None이라 no-op. 프론트는 항상 Number(18)을 보내(245행) 백엔드 regular_term_cap을 override. 미래모빌리티는 졸업136→제32조 상한 19인데 18로 계산돼 학기당 1학점 과소평가→경계 케이스에서 로드맵이 불필요하게 '초과학기/배치 실패'로 뒤집힐 수 있다. 힌트 '졸업학점 따라 17/18/19 자동'(435행)도 허위.
- 수정: programs.json에 학과별 max_credits_per_term을 채우거나, 사용자가 손대지 않으면 프론트가 max_credits_per_term을 null로 보내 백엔드 regular_term_cap이 졸업학점 기준 산출하게 위임. 힌트 문구를 실제 동작과 일치.

## [MEDIUM] [데이터] 학번 마스킹이 프론트에서만 수행되고 서버측 강제 없음 — raw student_id가 백엔드로 전송됨
- file: frontend/src/components/GraduationV2.jsx:242-249 + graduation_center/v2/models_v2.py(StudentContext)
- 문제: contextPayload()는 masked_student_id를 클라이언트에서 만들면서(247행) 동시에 ...ctx spread로 raw student_id 전체를 요청 본문에 함께 보낸다(243행). StudentContext에 student_id 필드가 없어 Pydantic이 떨어뜨리지만, 평문 학번이 네트워크/서버 로그로 흘러갈 수 있고, /audit를 직접 호출하면 masked_student_id에 평문을 넣어도 백엔드가 재마스킹 안 함. CLAUDE.md 가드레일은 '출력 학번 마스킹'을 백엔드 책임으로 둠.
- 수정: payload에서 raw student_id 제거(masked만 전송)하고, 백엔드 StudentContext에 validator를 추가해 masked_student_id를 ^\\d{4}X{4}$ 형태로 강제·정규화(평문 입력 시 서버에서 슬라이스).

## [MEDIUM] [데이터] max_credits_per_term override가 0/빈값일 때 risk(18)와 overflow(요람별 17/19) 폴백 갈림
- file: graduation_center/v2/risk.py:62 + planner.py:76 + frontend GraduationV2.jsx:245
- 문제: 프론트는 Number(ctx.max_credits_per_term)를 항상 보내 사용자가 비우면 0 전송. risk.py:62 0 or 18→18, planner.py:76 0 or regular_term_cap→요람별 17/19로 서로 다른 상한. risk의 하드코딩 18은 졸업120(상한17)·136(상한19)에서 틀린 capacity를 만들어 D 트리거 오작동.
- 수정: 0/None을 모두 regular_term_cap로 폴백하도록 risk·planner 동일 헬퍼 사용, 또는 프론트가 빈값을 안 보내고 서버 모델에서 0→None 정규화. (위 risk/overflow capacity 단일화 finding과 함께.)

## [MEDIUM] [데이터 정합] graduation_requirements.json 핵심교양 15/소계24가 audit 산출(17)과 영구 불일치 — 결정론 출처 충돌
- file: data/graduation/graduation_requirements.json(자동차융합대학_미래모빌리티학과.교양)
- 문제: 교양={기초7,핵심15,자유2,소계24}(확인됨)인데 audit은 핵심교양을 17로 계산(소통5 override 포함). 같은 시스템에서 핵심교양 요건이 데이터(15)와 진단(17)으로 갈리고 소계도 17이면 26이어야. v1 compute_structured_check가 직접 읽으면 15를 써서 같은 학생에 다른 졸업판정 가능. (위 high '핵심교양 영역선택제'와 동일 근원 — 데이터 측면.)
- 수정: 핵심교양 single source of truth 결정. 영역최저합 방식이면 graduation_requirements.json 핵심교양=17·소계=26 갱신하고 영역최저 override(소통5)도 같은 파일에 명시해 v1/v2가 동일 값을 읽게 함.

## [MEDIUM] [데이터] 백엔드 recommend_double_count와 프론트 defaultSel(3-way 기본배정)이 독립 계산 — 권장 칩과 실제 토글 불일치, rec cap 누적 버그
- file: graduation_center/v2/audit_v2.py:195-203 + frontend GraduationV2.jsx:85-96
- 문제: 백엔드 rec(197-203행)는 '(not primary_required,-credits) 정렬, cap까지'로 권장 목록 생성. 프론트 defaultSel(85-96행)은 '(primary_required desc, credits desc) 정렬 후 cap까지 dup → 제1전공 부족분 → 나머지 fusion'으로 독립 계산. 정렬·cap 채우기가 미묘하게 달라 권장 칩 집합 ≠ 실제 dup 토글. 또 rec 누적(200-203행)은 acc>=cap 체크를 더하기 '전'에 해 마지막 과목이 cap 초과해도 포함될 수 있다(cap6, 4+4→둘 다 권장 합8).
- 수정: 권장 목록과 기본 배정을 백엔드 한 곳에서 결정해 동일 집합 사용. 프론트 defaultSel을 recommend_double_count(또는 배정 객체)로 시드. rec 누적을 acc+credits<=cap으로 바꿔 cap 초과 과목 배제.

## [MEDIUM] [데이터] primary_base = primary_major_earned - overlap_cr 가정 위험 — overlap이 전부 제1전공 '전공' 영역에 있다는 보장 없어 음수/과소 가능
- file: graduation_center/v2/audit_v2.py:213,168 + verification.py:54-58
- 문제: primary_base(213행)는 primary_major_earned에서 overlap_cr 전액을 뺀 '제1전공 non-overlap' 추정. 그러나 overlap(168행)은 '융합 카탈로그 + other_prefixes(제1전공+다른 다전공 합집합, 138-139행) 겹침' 과목이라 다전공 2개 이상이면 제1전공 전공영역에 없는 과목이 섞일 수 있고, verification에서 타과/다전공 전공과목은 일반선택 재분류(57-58행)돼 primary_major_earned에 없을 수도 있다. 이 경우 primary_base가 실제보다 작거나 음수가 돼 프론트 primaryCr·fits 판정 왜곡.
- 수정: primary_base를 뺄셈 추정 대신 제1전공 전공영역에 실제 산입된 overlap 과목만 골라 그 합을 빼라. 다전공 다수 시 프로그램별 base 분리 계산하고 max(0, ...) 가드로 음수 방지.

## [MEDIUM] [trace/데이터] run_planner의 requirements_summary가 응답에 미노출 — 프론트가 갭 집계를 독자 재구현해 이중계상 위험
- file: graduation_center/v2/pipeline.py:53,56,82-85 + planner.py:536-539 + frontend GraduationV2.jsx:637-651
- 문제: run_planner는 requirements_summary(label/area/need)를 pctx에 담지만(planner.py:536-539) run_audit은 sources만 꺼내고 summary는 버린다(pipeline.py:56,82-85). AuditPipelineResponse에도 필드 없음. 프론트 '남은 요건' 칩(637-651)은 백엔드 산식과 별개로 area_gaps/missing_required_names/convergence를 다시 합산하는데, build_unified_candidates는 normalize_name로 중복제거(464-482행)하지만 프론트는 '필수지정 N과목'+'전공 X학점'을 단순 합산해 같은 과목을 이중계상할 수 있다.
- 수정: requirements_summary를 AuditPipelineResponse(또는 roadmap)에 노출하고 프론트가 그 값을 그대로 렌더해 단일 출처화. 최소한 프론트 합산을 백엔드 build_unified_candidates의 중복제거·우선순위와 일치.

## [LOW] [데이터] 미이수 필수 카운트 폴백 경로의 prefix 매칭이 카운트 왜곡 가능
- file: graduation_center/v2/risk.py:28 + audit_v2.py:285-286
- 문제: risk는 missing = len(audit.missing_required_names)로 카운트하며 일반 경로는 정확하다. 다만 코드 폴백 경로(req_names 없음)는 required_course_ids를 코드 앞5자리 prefix로 매칭(audit_v2.py:285-286)하므로 동일 prefix 다른 과목을 들으면 '이수'로 보거나 복수코드 시 중복 카운트돼 등급 트리거(missing>=2→C)가 과/소 산정될 여지.
- 수정: 폴백 경로에서 prefix 매칭 대신 정확 course_id 매칭 우선, prefix는 명시적 alias 테이블 있을 때만. 카운트를 set으로 중복제거.

## [LOW] [로드맵] plan_greedy가 학기 균형 없이 front-load — 첫 학기 과적·뒷 학기 공백(컨설팅 품질 저하)
- file: graduation_center/v2/planner.py:497-505,521
- 문제: 배치가 '맞는 첫 학기' first-fit이라 부담을 이른 학기에 몰아넣는다. 첫 정규학기는 3.75 보너스로 cap이 더 커(예 19+3=22) 더 적재되고 term_risk는 used>cap-3일 때 medium(521행)이라 첫 학기 과적·고위험, 마지막 학기 공백의 비현실적 로드맵. 루브릭3(결과 품질)상 학기 분산이 자연스러워야 함.
- 수정: 학기별 목표 학점을 균등 분배(잔여 총학점/잔여학기로 학기당 목표)하거나 최소적재 학기 우선으로 채우는 방식으로 변경.

## [LOW] [데이터] 별칭(alias)이 필수 판정에만 적용되고 _required_meta(학점/학기 조회)엔 미적용 — 드리프트 과목 메타 누락
- file: graduation_center/v2/audit_v2.py:50-63,274-279 vs planner.py:391-394
- 문제: audit의 _taken은 양방향 alias를 적용해 미이수 판정 드리프트를 흡수하나, planner._required_meta는 by_year 이름을 normalize_name 그대로 키로 쓰고 alias를 안 본다. 현재 데이터(미래모빌리티실험이 2023에 정상 존재)에선 무해하나, 미이수로 남아 후보가 되는 과목명이 alias로만 일치하면 메타 조회가 빗나가 디폴트 3.0/['1','2']로 떨어진다.
- 수정: _required_meta도 _required_aliases를 적용해 alias 동치집합으로 메타를 찾게 통일하거나, alias 정규화를 카탈로그 빌드 단계에서 canonical name으로 흡수.

## [LOW] [로드맵] 필수지정(priority1) 이름기준 항목이 동일 전공과목의 카탈로그 개설학기를 가려 hard 개설학기 체크가 사라짐
- file: graduation_center/v2/planner.py:407-417,464-482,500
- 문제: missing_required_names는 _required_meta로 terms를 채우되 요람 메타에 terms 없으면 offered_terms=['1','2']·confidence='name_only'로 만든다(413-416행). 선택 dedup의 seen은 normalize_name 기준이고 reqs는 priority순(필수지정1<전공부족3)이라, 같은 과목이 전공 카탈로그 pool(catalog_verified, 실제 offered_terms 보유)에 있어도 이미 seen에 들어가 추가 안 됨. 결과: 카탈로그가 아는 개설학기가 name_only로 강등돼 plan_greedy의 hard 개설학기 체크(known and off, 500행)를 우회 → 1학기만 개설 필수과목이 2학기에 배치 가능.
- 수정: 필수지정 항목 생성 시 program 카탈로그에서 동일 정규화이름 매칭으로 course_id·offered_terms·prerequisites를 끌어와 confidence='catalog_verified'로 승격(요람 메타에 terms 없을 때 카탈로그 fallback).

## [LOW] [로드맵] overflow 잔여학기 0인데 직전3.75 보너스(+3)가 capacity에 더해짐
- file: graduation_center/v2/planner.py:79-81
- 문제: project_overflow capacity = remaining*cap + bonus. remaining=0·prev_term_gpa_ge_375=True면 capacity=0*cap+3=3이 돼 들을 학기가 없는데 3학점 여유처럼 계산. 제32조 보너스는 첫 정규학기에 붙는 것이라 정규학기 0이면 대상 없음. 영향은 경계값 한정이나 학점 계산이 미세하게 틀림.
- 수정: 보너스를 remaining>0일 때만, 실제 첫 정규학기에 1회로 제한. capacity 식을 _ordered_terms처럼 첫 정규학기에만 보너스 더하는 방식으로 통일하거나 remaining==0이면 bonus=0.

## [LOW] [로드맵] build_unified_candidates 전역 seen 이름 dedup이 융합 필요 과목을 전공/필수와 이름충돌로 누락시켜 need 미충족 가능
- file: graduation_center/v2/planner.py:464-483
- 문제: selected를 정규화 이름 기준 전역 seen으로 중복제거(469-482행). 필수지정·전공부족 후보가 융합 pool과 같은 정규화 이름이면 먼저 처리된 요건이 이름을 선점해 뒤 요건 quota 후보가 건너뛰어진다(acc 미증가). 중복인정 맥락에서 같은 과목이 두 요건을 동시 메워야 하는데 한쪽 need가 과소충족돼 plan_greedy가 부족분을 못 채울 수 있다. 융합 과목명이 전공과 겹칠 여지(같은 학과코드)로 발생 가능.
- 수정: dedup 키를 (정규화이름, area) 또는 course_id 기준으로 좁혀 동일 과목이 서로 다른 요건 quota에 기여하게 하거나, 중복인정 대상은 double_recognizable 한도 내에서 의도적으로 양 요건에 산입.

## [LOW] [프론트] '→ {연도} 요람 적용' 힌트가 백엔드 실제 적용연도와 불일치 — 입력연도를 그대로 표시
- file: frontend/src/components/GraduationV2.jsx:238-241,364
- 문제: 입력 학번에서 추출한 연도(admissionYear())를 그대로 '→ 2024 요람 적용'처럼 표시(364행). 그러나 백엔드는 2024학번에 필수=2023요람·영역최저=2025기본을 적용하므로 '2024 요람'은 존재·적용되지 않는다. 데모에서 grounding 신뢰가 깨짐.
- 수정: /audit 응답의 profile.applied_yoram(백엔드 실제 선택연도)을 받아 표시하거나, 분석 전에는 '입학연도 기준 요람 적용(분석 후 확정)'처럼 중립 표기. 보유 요람({2023,2025})을 드러내 근사 적용을 숨기지 않음.

## [LOW] [프론트] 연계전공(cap=0)에 비활성 '중복인정' 3-way 버튼을 그대로 노출 + note 자기모순 '중복인정 최대 0까지'
- file: frontend/src/components/GraduationV2.jsx:77-79,172-188 + audit_v2.py:148,205-211,220-221
- 문제: 연계전공은 중복인정 불가(cap=0). 그럼에도 겹침 과목은 assignment='중복인정', selectable=True(audit_v2.py:210-211)로 설정되고 note는 '중복인정 최대 0까지'(220-221행) 자기모순. 프론트 SEL3는 항상 3버튼을 그려 cap=0이면 '중복인정' 버튼이 영구 비활성(177행), 사용자에게 누를 수 없는 옵션을 노출해 '연계는 중복인정 0' 규칙을 시각적으로 흐림.
- 수정: is_yeonge(cap==0)일 때 겹침 과목 selectable=False로 두고 SEL3에서 'dup' 옵션을 제거(제1전공/융합 2-way), note를 '연계전공은 중복인정 불가 — 겹침과목은 한쪽에만 산입'으로 분기.

## [LOW] [프론트] 히어로 진행바의 total_required 0 나눗셈 미가드 (NaN% 너비)
- file: frontend/src/components/GraduationV2.jsx:543
- 문제: width = Math.round(total_earned/total_required*100)인데 total_required=0이면 NaN→width:'NaN%'. Gauge(36행)는 required>0 가드가 있으나 히어로 바엔 없다. 연계·융합 단독(program_total_min None→0)이나 requirements_key 매칭 실패 시 진행바 깨짐.
- 수정: const pct = total_required>0 ? Math.min(100, Math.round(total_earned/total_required*100)) : 0; total_required 미상 시 '졸업 최저학점 미상' 안내.

## [LOW] [trace] roadmap status==='blocked' 프론트 분기는 dead code — 백엔드가 blocked를 보내지 않음
- file: frontend/src/components/GraduationV2.jsx:630 + planner.py:566-575 + pipeline.py:59,70-77
- 문제: 프론트는 roadmap.status==='blocked'일 때 빨강 메시지를 렌더(630행)하나, run_planner는 배치 실패에도 status='generated' 유지·feasible=False+blocked_reason만 set(566-575행). RoadmapPlan에 'blocked' 리터럴은 있으나 set되지 않아 630 분기·pipeline trace의 '실현불가(blocked)' 매핑이 발동 안 됨 → 워크플로우 그래프에 blocked 노드 점등 안 보임.
- 수정: 정직한 blocked를 쓰려면 run_planner가 unplaced 발생 시 status='blocked'를 set하도록 통일(위 검증/trace finding과 함께)하거나, 프론트 630 분기를 제거하고 feasible===false 경로로 일원화.

## [LOW] [데이터] missing_required_names(이름기준)가 validate_roadmap의 required_not_planned/gap 체크와 연결 안 됨 — code_ids만 검사
- file: graduation_center/v2/audit_v2.py:280 + planner.py:346,407
- 문제: 학번 요람 경로에서 missing_required_ids는 항상 [](audit_v2.py:280), 누락은 names에만 담긴다. build_unified_candidates(planner.py:407)는 names로 후보를 만들지만 course_id 없어 confidence=name_only이라, validate_roadmap의 required_not_planned(346행, course_id 기반)·gap_not_closed는 빈 리스트라 무검증. 기본 경로는 validate_roadmap을 호출조차 안 해 실질 피해는 작으나 결정론적 보장이 약하다.
- 수정: run_planner가 placed 결과에 대해 '필수지정 names가 모두 배치됐는지'를 이름 기준으로 검증하고 누락 시 blocked/feasible=False로 반영. 또는 missing required를 selected에 반드시 포함되게(현재 priority1·need=None의 quota 컷 누락 여지 점검).

## [LOW] [코드 위생] audit_v2 rec_keys 데드 코드, _ordered_terms/risk/overflow 보너스 의미 미세 불일치, 프론트 selByName 미사용
- file: graduation_center/v2/audit_v2.py:199,203 + planner.py:79,366-377 + risk.py:64-67 + frontend GraduationV2.jsx:120
- 문제: (1) audit_v2.py:203 rec_keys=set()에 id(c)를 add하지만 이후 읽히지 않는 데드코드(동시배정 최적화 TODO 잔재). (2) PREV_GPA_BONUS를 _ordered_terms는 첫 정규학기 1회(373행)로 정확히 부여하나 risk.py(64-65행)·project_overflow(79행)는 capacity에 위치 모델 없이 평탄하게 1회 더해 학기 수가 많을수록 보너스 의미가 미묘하게 다르고, 계절학기 가산도 risk는 1회·overflow는 0으로 모듈마다 어긋난다. (3) 프론트 GraduationV2.jsx:120 selByName을 채우지만 미참조(미완성 흔적).
- 수정: rec_keys·selByName 제거(또는 의도대로 배정 라벨 연동). 보너스/계절학기 가산을 _ordered_terms 합 기준 공용 헬퍼로 통일해 risk·overflow가 동일 산식 사용. (위 capacity 단일화 finding으로 흡수 가능.)
