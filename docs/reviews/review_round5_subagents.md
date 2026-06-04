# 적대리뷰 라운드5(최종) 종합 (18, raw 92, HIGH 7, REG 6)

## [HIGH] [REG] 위험등급 D '졸업불가 가능성'이 feasible=True·초과학기 없는 로드맵과 동시 표시 (gap>15/area_gap>15 절대 트리거가 수용량·feasibility 무시)
- file: graduation_center/v2/risk.py:32-34, 50-52, 99-101
- 문제: 재현 확정(/tmp/happy2.py): 미래모빌리티 2023, 잔여 2학기, 계절 허용, total_gap=47, 영역갭 전부 0. run_planner는 status='generated', feasible=True, overflow=None로 2개 정규학기에 전 요건을 배치한 완성 계획을 산출하는데 compute_risk는 grade='D'(label '졸업불가 가능성', score 52)를 반환한다. 원인: line 32 gap>15→D, line 50 max_area_gap>15→D 가 잔여학기 수용량(line 63-71에서 이미 계산)·roadmap_feasible과 무관하게 절대 학점차만으로 D를 강제한다. roadmap_feasible 인자는 받지만 line 99에서 is False일 때만 C로 가산할 뿐 True가 D를 완화하지 못한다. 잔여 2~3학기 학생은 남은 학점이 거의 항상 15 초과라 사실상 항상 'feasible 로드맵 + D 졸업불가' 조합이 난다. 라운드4 fix#3은 capacity 트리거(line 72)만 정합화했고 이 절대 트리거 2개는 그대로 남아 같은 모순을 다른 경로로 재유입한다. report_markdown 헤더 '종합 판정: D 졸업불가 가능성' 바로 아래 '## 추천 로드맵'에 완결 계획이 나란히 출력된다.
- 수정: 절대 임계 D 트리거를 수용량/feasibility로 게이트한다: roadmap_feasible is True(또는 gap<=capacity)이면 gap>15·max_area_gap>15의 최악 등급을 C로 클램프하고, D='졸업불가 가능성'은 capacity 초과(line 72)·GPA 미달(line 92)·roadmap blocked 등 '실제 졸업 불가' 신호에만 부여. 최소한 함수 말미에서 grade=='D' and roadmap_feasible is True and not(gpa fail or capacity trigger)이면 grade를 'C'로 강등.

## [HIGH] [REG] 2023학번 캡스톤 Ⅰ/Ⅱ가 카탈로그·alias 부재로 항상 '미이수 필수지정'으로 표시 — 실제 이수자도 거짓 미충족
- file: data/graduation/v2/required_names_by_year.json (mirae_mobility 2023 + aliases) / graduation_center/v2/audit_v2.py:329-338
- 문제: 재현 확정(/tmp/happy.py): 카탈로그의 실제 캡스톤 '다학제간캡스톤디자인'(0693316)·'다학제간캡스톤디자인+'(7159803) 두 과목을 모두 이수시켜도 missing_required_names에 '다학제간캡스톤디자인Ⅰ','다학제간캡스톤디자인Ⅱ'가 남는다. 2023 required_names는 Ⅰ(norm '...1')·Ⅱ('...2')를 요구하나 카탈로그엔 접미사 없는 캡스톤만 있고(둘 다 norm '다학제간캡스톤디자인', text_norm.py가 '+'를 제거해 by_norm 키 충돌) aliases에 캡스톤 동치가 없다(라운드4 의도적 미추가). _taken()이 둘 다 False → (1) risk가 '필수지정 2과목 미이수' severity 18로 강등, (2) 플래너가 이미 이수한 캡스톤을 로드맵에 재계획, (3) 보고서 '미이수 필수지정'에 거짓 2건. happy-path 채점 학번/학과에서 충족 경로 자체가 없다.
- 수정: 데모 transcript 명칭을 먼저 확정한 뒤, required_names_by_year.json aliases.mirae_mobility에 '다학제간캡스톤디자인Ⅰ'↔'다학제간캡스톤디자인', '다학제간캡스톤디자인Ⅱ'↔'다학제간캡스톤디자인+'를 명시 매핑(둘 다 들어야 둘 다 해소되므로 거짓충족 안 남), 또는 2023 요람 필수명을 카탈로그 실재 과목명으로 정정. 더불어 text_norm의 '+' 제거로 두 캡스톤 by_norm 키가 충돌하므로(catalog.py:88-93) 코드매칭 우선 처리도 필요. 코드만으로는 해결 불가 — 데이터·요람 정합 필요.

## [HIGH] 로드맵이 다학제간캡스톤디자인Ⅱ를 Ⅰ보다 이른 학기에 배치 (선후 순서 역전, 화면 노출)
- file: graduation_center/v2/planner.py:559-604 (plan_greedy) / data/graduation/v2/required_names_by_year.json (mirae 2023 캡스톤Ⅰ terms=['1'], Ⅱ terms=['2'])
- 문제: 재현 확정(/tmp/happy2.py, feasible 로드맵): 캡스톤Ⅱ가 2026-2에, 캡스톤Ⅰ이 2027-1에 배치돼 Ⅱ가 Ⅰ보다 한 해 먼저 잡힌다. 원인: _required_meta가 Ⅰ→terms=['1'], Ⅱ→terms=['2']를 주고(코드 미매칭이라 prerequisites=[]), plan_greedy는 선수 엣지가 없으면 개설학기·우선순위·학점순만 보고 가장 이른 가용 학기에 배치한다. 잔여 학기 순서가 2026-S→2026-2(유일 2학기)→2026-W→2027-1(유일 1학기)이라 개설학기 제약만으로 Ⅱ가 먼저 들어간다. 결정론이라 매번 동일. 채점 라이브에서 즉시 보이는 시퀀스 모순.
- 수정: Ⅰ/Ⅱ·번호형 시퀀스 필수에 선후 제약 부여: required_names_by_year.json 캡스톤Ⅱ에 prereq로 Ⅰ을 넣고 build_unified_candidates가 prerequisites로 전달하거나, plan_greedy에 동일 베이스명+로마숫자/번호 오름차순 min_idx 제약(타이브레이크)을 추가. 캡스톤 alias 정정(위 항목)과 함께 처리.

## [HIGH] 핵심교양 영역 총량 충족(✅)인데 5개 세부영역 전부 0/N '부족' 표시 + 로드맵에 17학점 phantom 계획 (기초교양 fix5 가드가 핵심교양에 미적용)
- file: graduation_center/v2/audit_v2.py:305-321 / planner.py:510-513 / risk.py:77-80
- 문제: 재현 확정(/tmp/probe.py): 핵심교양 18학점을 들었으나 과목명이 gen_ed name_norm_to_area(50개)에 없어 core_area=None(verification.py:100) → core_area_earned 비어 있음. 결과 핵심교양 area_gap은 18/17 gap=0(✅)인데 core_area_gaps는 인문Ⅰ 0/3·인문Ⅱ 0/3·소통 0/5·글로벌 0/3·창의 0/3 전부 부족. build_unified_candidates(line 510-513)는 core_area_gaps를 무조건 슬롯으로 계획해 PLANNED 핵심교양 17학점을 phantom으로 추가(검증: 17). 기초교양은 fix5(line 501 basic_gap>0 가드)로 막았는데 핵심교양엔 같은 게이트가 없다. risk.py:77도 core_missing으로 강등. 프론트(GraduationV2.jsx:599-619)는 area 게이지 ✅와 세부영역 부족 카드를 동시 렌더 → 같은 화면 직접 모순 + phantom 학점이 총배치를 부풀려 거짓 blocked/초과학기 유발.
- 수정: 기초교양 fix5와 동일 게이트를 핵심교양에 적용: 핵심교양 area_gap.gap<=0이면 core_area_gaps를 phantom 슬롯으로 계획하지 말고(planner.py:510에 가드), audit/markdown/프론트에서 세부영역을 'attribution 미확정(과목명 미매핑) — 영역 학점은 충족'으로 다운그레이드하며, risk.py:77의 core_missing 강등도 총량 충족 시 제외/약화. 또는 계획 핵심교양 학점을 max(0, core_total_required - earned['핵심교양'])로 캡.

## [HIGH] [REG] 요람상 '과목 필수'인 기초교양 미이수가 영역 총량 충족 시 모든 판정에서 누락 → 거짓 졸업가능 (planner/risk/markdown 미반영, 프론트만 ⬜)
- file: graduation_center/v2/planner.py:499-508 / risk.py (gen_basic 미반영) / pipeline.py:_markdown (gen_basic 미출력)
- 문제: 라운드4 fix#5(basic_gap>0일 때만 계획)는 phantom 12학점은 막지만 반대 구멍을 만든다. 학생이 다른 기초교양으로 area_min(8)을 채우면 basic_gap=0이 되어 (a) planner가 미이수 필수 기초교양(예 글로벌영어)을 계획 안 함, (b) risk가 gen_basic 미이수를 어떤 RiskReason에도 반영 안 함(missing_required_names에도 안 들어감), (c) _markdown이 언급 안 함. 그러나 프론트 GraduationV2.jsx:621-631 '기초교양 필수 과목' 패널은 글로벌영어를 ⬜로 표시 → 화면에 '미이수 필수 ⬜'와 'A 안전·졸업가능' 초록 판정이 공존. 도메인상 영역 총량 충족이 지정과목 이수를 면제하지 않으므로 거짓 충족이다.
- 수정: gen_basic 미이수를 1급 부족 신호로 승격: ①risk에 missing_gen_basic 트리거 추가(미이수 시 최소 B), ②build_unified_candidates에서 missing_basic을 basic_gap과 무관하게 '미이수 필수 기초교양' name_only 후보로 selected에 추가, ③_markdown에 '미이수 기초교양 필수' 섹션. (단 _gen_basic_view substring 거짓매칭부터 고쳐야 — 아래 항목.)

## [HIGH] [REG] unfillable 요건의 shortfall이 일반선택(general_need)에서 차감되지 않아 같은 부족분을 이중 계획
- file: graduation_center/v2/planner.py:548-549
- 문제: 코드 확인: general_need = round(max(0.0, audit.total_gap - sel_cr), 1) 가 selected에 실제 들어간 sel_cr만 차감하고 unfillable(후보 풀 고갈로 못 채운) 요건의 shortfall은 차감하지 않는다(소스에 shortfall 차감 없음 확인). unfillable 요건의 학점도 결국 total_gap을 메우는 학점이므로, 그만큼 일반선택을 또 계획하면 같은 부족분을 두 번 메우는 계획이 된다(예: total_gap=12, 융합 unfillable 6 → 일반선택 6이 아니라 12 슬롯 + blocked 사유로 융합 -6 별도 보고 = 사실상 18학점치). 라운드4 fix#7이 overflow 이중계상은 제거했으나 general_need 산식은 그대로다.
- 수정: general_need = max(0.0, round(audit.total_gap - sel_cr - sum(uf['shortfall'] for uf in unfillable), 1))로 unfillable shortfall도 차감.

## [HIGH] 전공 영역 '62/62 ✅'와 '미이수 필수지정 N과목 + 로드맵 전공학점 추가'가 한 화면에 동시 표시 — 채점자에 모순으로 보임
- file: graduation_center/v2/pipeline.py:96-98 (영역별 현황) + 114-115 (미이수 필수지정)
- 문제: 재현 확정(/tmp/happy2.py): 전공 62/62 gap 0(✅)인데 동시에 missing_required_names=['다학제간캡스톤디자인Ⅰ','Ⅱ']가 떠 미이수 필수지정 섹션에 표시되고 로드맵에 두 과목이 배치된다. 영역 학점 최저를 융합 중복인정 겹침 등으로 채웠기 때문에 도메인상 '영역학점 충족 ≠ 필수과목 이수'로 정당하나, _markdown이 ✅와 '필수 N과목 미이수'를 화해 문구 없이 병치해 채점자가 즉시 모순으로 본다. (캡스톤 false-missing 항목이 해소되면 magnitude는 줄지만 '✅ + 필수 미이수' 클래스 모순은 일반적으로 남는다.)
- 수정: _markdown에서 g.area=='전공' and audit.missing_required_names가 있으면 ✅를 '⚠️ 학점충족·필수 N과목 미이수'로 치환하거나, 영역 줄에 미이수 필수 건수를 묶어 조건부 라벨로 렌더.

## [MEDIUM] blocked 로드맵에서 blocked_reason·relaxation_hint·overflow note가 프론트에서 최대 3회 중복 표시
- file: frontend/src/components/GraduationV2.jsx:655, 707-710, 718-734
- 문제: 코드 확인: status==='blocked'이면 feasible===false도 항상 참이라 line 655(빨강 'blocked_reason · relaxation_hint')와 line 707-710(주황 박스 'blocked_reason · relaxation_hint')이 같은 문자열을 두 번 렌더한다. 게다가 planner.py:729에서 hint = ov.note(overflow note)이므로 overflow 카드(line 733)까지 합쳐 동일 문장이 세 번 노출된다. happy-path(잔여 2~3학기)는 거리가 멀어 실제 blocked가 자주 떠 채점 화면에서 그대로 보인다.
- 수정: blocked 분기를 한 곳으로 통합: line 655 제거하거나 line 707-710을 status!=='blocked'일 때만 렌더하도록 배타 조건화하고, relaxation_hint가 overflow.note와 같으면 overflow 카드에서만 표시. blocked_reason 1회·초과학기 상세 1회로 한정.

## [MEDIUM] 연계융합 헤드라인 earned(fusion_effective)와 group_checks earned(designated 커버리지)가 다른 분모라 '부족'인데 그룹은 ✅ 산술 모순
- file: graduation_center/v2/audit_v2.py:240-251, 267 / pipeline.py:101-107
- 문제: convergence_checks의 헤드라인 earned/gap은 fusion_effective(중복인정 한도·배정 반영 후)이고 group_checks.earned는 designated(이수한 융합 지정과목) 전체 커버리지로, 두 분모가 의도적으로 다르다(라운드3 결정). _markdown(line 103-107)이 둘을 같은 카드의 부모/자식으로 출력해 'X융합전공 N/36 ⚠️'(캡 반영) 아래 'A그룹 M/12 ✅'(비캡)가 나오고 자식 합이 부모보다 클 수 있다(예 그룹 36/12 vs 헤드라인 27). 라벨 없이 병치돼 '부분>전체' 모순으로 읽힌다. (해피패스 단일 융합·총gap>0이라 즉발은 제한적이나 다전공/겹침 케이스에서 노출.)
- 수정: 표시 정합: group_checks.earned를 융합 산입(fusion_courses) 기준으로 별도 표기하거나, cc['designated_total']을 함께 렌더해 '이수 커버리지(중복인정 전) vs 융합산입(한도 반영)'을 명시 라벨링. 최소 '27/36(중복인정 한도 반영)' + '그룹 커버리지(한도 전): A21·B15' 식.

## [MEDIUM] [REG] 현재학기가 계절학기(S/W)일 때 risk 수용량이 planner보다 계절 6학점 과대 — planner blocked인데 risk가 D 강등 안 하는 반대방향 모순 가능
- file: graduation_center/v2/risk.py:66-71 vs graduation_center/v2/planner.py:357-377
- 문제: 재현 확정(/tmp/seasonal.py): current_term='2026-S', remaining=2 → planner _ordered_terms=[['2026-2',19],['2026-W',6],['2027-1',19]] plan_cap=44, 그러나 risk.py는 무조건 remaining*19 + remaining*SEASONAL(6)=50을 더해 risk_cap=50(MISMATCH, +6). 정규-start(2026-1)에서는 둘 다 50으로 일치. 계절-start면 risk가 수용량을 6 과대평가해 capacity 트리거(line 72)를 회피 → planner는 계절 슬롯 1개 부족으로 unplaced→blocked인데 risk capacity D는 누락되는 반대방향 모순. current_term은 프론트 자유입력이라 'S' 입력 시 재현.
- 수정: risk 수용량을 planner와 동일 출처로 산출: _ordered_terms(context, term_cap)를 호출해 sum(cap)을 capacity로 쓰거나, 계절 학기수를 _ordered_terms와 동일 규칙(현재가 계절이면 remaining-1)으로 계산. 두 모듈이 같은 학기-생성 헬퍼를 공유하도록 리팩터하는 것이 영구 정합.

## [MEDIUM] [REG] 워크플로우 trace 분기 라벨이 blocked 종류와 무관하게 항상 '실현불가(초과학기 필요)'·'미배치 → 초과학기'로 하드코딩 — 후보고갈/영역미해소와 모순
- file: graduation_center/v2/pipeline.py:61-62, 81
- 문제: 코드 확인: line 61-62 plan_branch는 plan.status=='blocked'이면 무조건 '실현불가(초과학기 필요)'. 그러나 blocked는 (a)no_candidates(overflow 미설정), (b)unfillable/gap_not_closed만(이때 unplaced=0이라 overflow=None) 경로에서도 발생해 overflow 카드가 없는데 trace 노드는 '초과학기 필요'로 점등된다. 마찬가지로 line 81 로드맵 검증 분기는 vrep.ok가 아니면 무조건 '미배치 → 초과학기'인데 vrep.errors엔 pool_exhausted·gap_not_closed도 있어 리포트 본문('초과학기로 해결 불가')과 그래프가 충돌한다. 워크플로우 그래프 시각화가 채점 포인트라 trace-리포트 불일치가 그대로 보인다.
- 수정: plan_branch를 plan.overflow 유무로 분기(있으면 '초과학기 필요', 없으면 blocked_reason 종류에 따라 '후보 없음(학과 확인)'/'영역 미해소'). line 81도 vrep.errors의 code 집합을 보고 unplaced/over_credit_cap→'미배치→초과학기', pool_exhausted→'후보 고갈', gap_not_closed→'영역 미해소'로 라벨링.

## [MEDIUM] _gen_basic_view substring 매칭으로 미이수 기초교양 필수가 거짓 '이수'로 판정될 수 있음
- file: graduation_center/v2/audit_v2.py:93
- 문제: 재현 확정(/tmp/probe2.py): taken = any(key in t for t in taken_norm) 부분일치라, 필수 '글쓰기'에 대해 학생이 '과학글쓰기'를 들으면 normalize('글쓰기') in normalize('과학글쓰기')=True → 글쓰기 taken=True(거짓). 반대로 'College English' 등은 명칭이 달라 ⬜로 남는다. 화면 ✅/⬜ 칩 자체가 틀려 채점자가 보는 상태 신뢰를 깬다. 위 'gen_basic 1급 승격' 항목과 결합 시 거짓 이수/거짓 미이수 양방향 오류.
- 수정: 정확일치(key==t) 우선 + 화이트리스트 접미사(startswith)로 좁히거나 aliases로 명시 동치만 허용. 최소한 startswith로 바꿔 임의 위치 부분일치 제거.

## [MEDIUM] 기초교양 영역 ✅인데 '기초교양 필수 과목' 칩이 미이수(⬜)로 동시 표시 — 표시 레이어 모순
- file: frontend/src/components/GraduationV2.jsx:621-631 / graduation_center/v2/audit_v2.py:83-95
- 문제: 재현 확정(/tmp/probe2.py): 기초교양 area_gap=0(✅)인데 gen_basic_courses의 College English·글로벌영어·English Conversation taken=False → 프론트가 주황 ⬜ 칩으로 렌더. 영역 게이지 ✅와 화해 문구 없이 병치돼 모순으로 읽힌다. 실제 증명서에서 명칭 드리프트가 흔해 happy-path에서 거의 확실히 재현.
- 수정: 기초교양 area_gap<=0이면 칩 옆에 '영역 학점은 충족 — 명칭 확인용(택1/대체 가능)' 화해 문구를 넣거나 ⬜를 회색 '확인 필요' 톤으로 낮춰 '미이수'로 단정하지 않게 한다.

## [MEDIUM] quota 선택 루프가 acc>=need를 가산 후 검사해 need를 초과 선택(over-select) — 권장 로드맵 학점이 부풀고 blocked 시 숫자 비정합
- file: graduation_center/v2/planner.py:533-542
- 문제: 코드 확인: pool 루프가 'if acc >= r["need"]: break'를 루프 진입부에서 검사하므로 마지막 추가 과목이 need를 넘긴다(예: need=30인데 2학점 과목이 마지막에 들어가 32 선택). blocked 시 화면에 (a)영역현황 부족, (b)gap_not_closed의 placed, (c)초과학기 미배치 학점이 서로 다른 분모로 떠 산술이 안 맞을 수 있다.
- 수정: 마지막 과목이 need를 넘기면 제외하거나(acc + it.credits <= need + tolerance일 때만 추가), blocked_reason의 placed와 overflow의 unplaced가 같은 selected 분모를 쓰도록 통일.

## [LOW] 프론트 '학사규정 제32조 17/18/19 자동' 안내가 동작 안 함 — programs.json에 max_credits_per_term 없어 항상 기본 18
- file: frontend/src/components/GraduationV2.jsx:243,270,452 / data/graduation/v2/programs.json
- 문제: 확인: programs.json 모든 프로그램에 max_credits_per_term 필드 없음(전부 undefined). 프론트 line 243·270의 progs[id]?.max_credits_per_term가 항상 falsy → ctx.max_credits_per_term 기본 18 고정. line 452 hint는 '제32조: 졸업학점 따라 17/18/19 자동'이라 안내. 졸업 136인 미래모빌리티는 제32조상 19여야 하나 18로 전송(보수적). 백엔드 regular_term_cap이 클램프만 하므로 결과가 틀리진 않으나 UI 주장과 동작 불일치.
- 수정: programs.json에 학과별 max_credits_per_term을 채우거나 프론트가 status.total_credits_min으로 17/18/19 계산해 기본값 세팅. 최소한 hint 문구를 실제 동작(기본 18, 수동)에 맞게 수정.

## [LOW] 사용자가 낮춘 학기당 학점 상한이 첫 정규학기 직전3.75 보너스(+3)로 초과됨
- file: graduation_center/v2/planner.py:373 (_ordered_terms) / risk.py:66-67
- 문제: 재현 확정(/tmp/bonus.py): max_credits_per_term=12, prev_term_gpa_ge_375=True → _ordered_terms 첫 정규학기 cap=15(12+PREV_GPA_BONUS 3)로 사용자 명시 12를 초과. 보너스는 '법정 허용'이지 의무가 아닌데 무조건 가산된다. risk.py:66-67 capacity도 동일 정책. 사용자가 상한을 낮춰 입력하면 첫 학기만 더 채운 로드맵이 나와 입력과 모순.
- 수정: 보너스를 사용자 override가 없을 때(법정 cap 사용 시)만 더하거나, 첫 학기 cap = min(reg_cap+bonus, user_override 있으면 그 값). planner와 risk 양쪽 정책 일치.

## [LOW] _overflow_from_credits가 계절학기 가용량을 무시하고 정규 cap만으로 초과학기 수 산정 — risk 수용량 모델과 비대칭
- file: graduation_center/v2/planner.py:398-413, 720
- 문제: 코드 확인: extra=ceil(unplaced/reg_cap)로 정규학기만 가정. seasonal_semester_allowed=True여도 초과 구간에 계절(6학점)을 못 쓰는 전제라, 같은 화면의 risk 수용량(계절 포함, remaining*6 가산)과 분모가 다르다. plan_greedy가 이미 계절을 써 unplaced는 '계절까지 쓰고 남은 분'이라 보수적 과대추정 방향(거짓 충족 아님). note에 '개설학기 제약…' 꼬리말은 붙으나 계절 미반영 명시는 없다.
- 수정: 초과 구간에도 _ordered_terms식 정규+계절 용량을 적용해 extra 산출하거나 note에 '계절학기 미반영(보수적 추정)' 명시. 두 곳을 공통 capacity 헬퍼로 단일화 권장.

## [LOW] 미사용 project_overflow 데드코드가 활성 _overflow_from_credits와 다른 용량모델(계절 미가산) 보유 — 향후 재사용 시 회귀 위험
- file: graduation_center/v2/planner.py:63-96
- 문제: 확인: grep 결과 project_overflow 호출처 NONE(데드코드), 활성 경로는 _overflow_from_credits만. project_overflow는 capacity=remaining*cap+bonus로 계절을 전혀 더하지 않아 라운드4에서 정합화한 risk/planner 용량 모델과 불일치. 현재 데모 무영향이나 누군가 다시 연결하면 초과학기 숫자가 두 모델 사이에서 달라지는 모순 재발.
- 수정: project_overflow를 삭제하거나, 보존 시 docstring에 'DEPRECATED — 활성 경로는 _overflow_from_credits' 명시 + 단일 용량 모델 강제(테스트로 호출처 단일성 보장).

## [LOW] gap_not_closed 억제가 unfillable 라벨 문자열 매칭에 의존 — '필수지정 미이수' area=전공이 'startswith 전공'에 안 걸려 취약(현재 무해)
- file: graduation_center/v2/planner.py:705-706
- 문제: 확인: 억제는 `g.area in u['label'] or u['label'].startswith(g.area)`로 unfillable 라벨과 매칭. '필수지정 미이수'(area=전공)는 '전공' 문자열을 포함하지 않아 매칭 실패하나, 이 라벨은 items 경로(line 525-530)를 타 unfillable 엔트리를 만들지 않으므로 현재는 무해. 그러나 향후 필수지정을 pool 기반으로 바꾸면 거짓 충족/메시지 충돌 가능. 라벨 텍스트 의존 설계가 취약.
- 수정: unfillable append(line 544)에 r['area']를 함께 기록하고 line 706을 any(u.get('area')==g.area for u in unfillable)로 비교 — 텍스트 매칭 제거.

## [LOW] 교차요건 seen-dedup가 융합 quota 미가산으로 거짓 unfillable(pool_exhausted) → 거짓 blocked 유발 가능
- file: graduation_center/v2/planner.py:533-544
- 문제: 확인: 라운드4 fix#1로 seen에 든 과목은 후속 요건 acc에 가산 안 하고 continue(이중계상 방지엔 맞음). 부작용: 융합 pool 과목이 앞선 '필수지정 미이수'·'전공 부족'에 이미 seen이면 융합 acc에 안 잡혀, 그 과목 하나로 양쪽 충족 가능해도 acc<need → unfillable→pool_exhausted→blocked('초과학기로 해결 불가, 학과확인')라는 강한 거짓 메시지. 해피패스는 융합 gap<=0이라 step2를 건너뛰어 미발현(unfillable=[] 검증)이나 겹침 많은 다전공 조합에서 발화 가능.
- 수정: 요건 간 과목 공유를 quota 회계에서 분리 — need 충족 판정은 audit의 영역/그룹 coverage 기준으로, selected는 학기배치용 합집합으로만. 또는 seen skip 시 그 과목이 현재 요건 영역도 충족하면 acc에 가산(배치 중복만 막고 충족 회계는 공유 허용).

## [LOW] match_course 이름매칭(step2)이 이수구분(area_raw)을 무시 → 교양 이수 과목이 전공으로 오분류돼 영역 학점 왜곡
- file: graduation_center/v2/catalog.py:166-170
- 문제: 확인: match_course는 코드 미스 시 이름 정규화 유니크 매칭(step2)을 이수구분보다 우선해 requirement_area=cc.requirement_area(전공)로 확정하고 area_raw 원문을 버린다. transcript 이수구분이 '기초교양'이라도 과목명이 전공 카탈로그와 유니크 이름일치하면 전공으로 잡혀 교양 영역은 학점이 빠지고(거짓 부족) 전공은 부풀려진다(거짓 충족). 임의 transcript에서 영역 게이지가 직관과 어긋날 수 있다(해피패스 데모는 잘 안 나옴).
- 수정: step2 이름매칭 시 raw.area_raw가 명시적 교양(기초/핵심/자유)이면 카탈로그 전공 매칭을 적용하지 말고 area_from_isugubun 우선(aggregate_only). 즉 이름매칭 덮어쓰기는 area_raw가 비었거나 전공류일 때만.

## [LOW] term_risk가 정상 부하 학기에도 거의 항상 'medium' — cap 의존 임계로 의미 희석(현재 미노출)
- file: graduation_center/v2/planner.py:632
- 문제: 확인: term_risk='medium' if used > cap-3 else 'low'. 계절학기는 cap=6이라 4학점↑이면 무조건 medium, 정규는 16↑이면 medium. 6학점 꽉 찬 정상 계절과 19학점 과부하 정규가 같은 medium으로 묶여 의미가 희석. 현재 프론트가 term_risk를 렌더하지 않아 화면 영향 없으나 데이터 계약 비일관.
- 수정: 절대 학점(>=18 high, >=15 medium) 또는 used/cap 비율(>=0.95 high, >=0.8 medium)로 바꿔 계절/정규를 동일 척도로 평가. 미사용이면 노출 계획에 맞춰 정리.

## [LOW] 다중 융합 선언 시 전공 게이지 to_fusion footnote가 dedup 안 해 백엔드 실제 차감과 어긋남
- file: frontend/src/components/GraduationV2.jsx:592 vs graduation_center/v2/audit_v2.py:292-297
- 문제: 확인: 백엔드는 to_fusion을 과목 앞5자리 단위 dedup(to_fusion_by_course)해 전공에서 한 번만 차감하나, 프론트 footnote는 convergence_checks.reduce((s,c)=>s+(c.to_fusion_credits||0),0)로 프로그램별 단순 합산(dedup 없음). 두 융합이 같은 과목을 fusion 배정하면 footnote 값이 실제 차감/게이지와 어긋난다. 단일 융합(해피패스)은 무영향, 다전공 검색 UI가 2개 이상 융합을 허용하므로 데모 중 발생 가능.
- 수정: 백엔드가 dedup된 to_fusion 총합을 audit 응답 최상위 필드로 노출하고 프론트가 그 값을 쓰게 하거나, 프론트 reduce를 to_fusion_course_credits를 prefix 키로 합쳐 dedup.

## [LOW] plan_greedy front-load 그리디가 선수체인 위상을 무시해 실현가능 계획을 거짓 blocked로 만들 수 있음
- file: graduation_center/v2/planner.py:565, 606-619
- 문제: 확인: items가 (priority, -credits)로만 정렬되고 _try_place는 첫 적합 학기에 그리디 배치 — 선수체인 깊이/임계경로를 고려하지 않는다. 독립 고우선 채움과목이 이른 학기 용량을 선점하면 prereq 체인 말단이 학기를 잃어 status=blocked·거짓 '초과학기 필요'가 날 수 있다(while 루프의 defer는 순서만 늦출 뿐 이른 학기 용량을 예약 못함). 미래모빌리티 카탈로그는 선수쌍이 적어 데모 즉발 가능성은 낮으나 선수가 늘거나 1학기-only 개설이 섞이면 트리거.
- 수정: 정렬 키에 선수체인 깊이/후행 의존 수를 추가하거나 prereq 있는 과목 우선 배치 후 독립 채움과목으로 빈 용량을 메우는 2-pass. 최소 unplaced 발생 시 독립 채움과목을 뒤 학기로 재배치하는 백트랙 1회 추가.

## [LOW] 선수 미배치/배치실패 과목에도 manual·prereq_warn이 남아 계획에 없는 과목 주의문구가 출력됨
- file: graduation_center/v2/planner.py:581-583, 633-637
- 문제: 확인: _try_place가 선수 미충족 후보에 it['manual']=True·prereq_warn 추가를 배치 성공 여부와 무관하게 수행. 이후 그 과목이 용량/개설로 unplaced여도 assumptions(any manual)·prereq_warn에 이름이 남아 '선수과목 이수 여부 확인 필요'가 로드맵에 없는 과목에 대해 출력된다. 사소한 비정합.
- 수정: manual·prereq_warn 기록을 배치 성공(return True 직전)으로 미루거나, assumptions/prereq_warn 집계 시 unplaced 과목 제외.

## [LOW] 핵심교양 총요건 산식이 영역최저 합을 우선해 요람 핵심교양 총학점이 더 큰 학과에서 과소계상
- file: graduation_center/v2/audit_v2.py:305
- 문제: 확인: core_total_required = sum(overrides.get(a,core_min) for a in gen_areas) or profile.area_min['핵심교양']. 미래모빌리티는 5+3+3+3+3=17이 요람 17과 일치해 무증상. 그러나 영역최저 합(예 15)이 truthy면 or 뒤(요람 핵심교양, 예 18)로 폴백하지 않아 요람 총학점 > 영역최저 합인 학과에서 과소계상(거짓 충족) + 별도 데이터 드리프트 시 경고 없음.
- 수정: core_total_required = max(영역최저 합, profile.area_min['핵심교양'])로 바꿔 둘 중 큰 값을 요건으로. 빌드 시 두 값 일치 assert 권장.

## [LOW] 다중 융합전공 동시 선언 시 동일 과목이 두 융합 총량(각 36)에 동시 산입 (TODO 미구현 영역)
- file: graduation_center/v2/audit_v2.py:107-113, 151-154, 238-240
- 문제: 확인: audit_v2.py:107-113 TODO가 명시한 미구현 영역. 두 융합전공을 동시 선언하면 같은 물리 과목이 각 프로그램 designated/fusion_courses에 모두 포함돼 두 융합 모두의 36학점 요건에 동시 카운트된다(전공 차감용 to_fusion_by_course는 dedup하나 '각 융합 총량 인정'은 dedup 안 함). 두 융합이 같은 과목들로 동시 '충족'으로 표시될 수 있어 채점 시 지적 가능. 신규 회귀는 아님.
- 수정: 프로토타입 범위상 데모 다전공은 단일 융합으로 고정(권장), 또는 note에 '두 융합 간 동일 과목 동시 인정은 학과 확인 필요' 명시. 정합 원하면 융합 간 공유 과목에도 중복인정 한도/배타 배정.

## [LOW] 전공-부족 후보 풀이 alias를 미적용 — 요람명/구명칭으로 기록된 이수완료 과목을 신규 추천
- file: graduation_center/v2/planner.py:490-495
- 문제: 확인: 미이수 필수 체크(_taken)는 이름+alias를 쓰나, 전공 부족 후보 풀의 이수 제외(line 495)는 confirmed_full(코드) 또는 confirmed_norm(이름)만 보고 alias를 적용하지 않는다. 학생이 요람명(예 '미래모빌리티AD')으로 이수했고 수강내역 코드가 없거나 다르면 카탈로그명(예 '자동차모빌리티 Adventure Design', alias 동치)이 전공 부족 후보로 떠 이미 이수한 과목을 재추천. ON국민 export가 정확 코드를 실으면 가려지나 구명칭 기록에선 노출.
- 수정: step3 전공 풀 제외 조건에 _required_aliases와 동일 alias 그룹 적용 — 카탈로그 과목 norm이 confirmed_norm에 있거나 alias 동치가 있으면 제외(이수완료 판정과 후보 제외를 같은 alias 규칙으로 일원화).

## [LOW] 이름기준 미이수 필수가 course_id 없음에도 catalog_verified·manual_check=False로 라벨링 — 신뢰도 표기 과장
- file: graduation_center/v2/planner.py:455-458
- 문제: 확인: confidence를 known=bool(terms)로 정해, 요람 연도메타에 terms만 있으면 코드 매칭(course_id='')이 없어도 catalog_verified·manual=False가 된다. 캡스톤Ⅰ/Ⅱ·미래모빌리티실험 등 카탈로그 코드 미매칭 과목이 로드맵에 '검증됨·확인불요'로 나와 사용자가 개설학기·코드 확인을 건너뛸 수 있다(데이터 무결성보다 표기 신뢰도 문제).
- 수정: course_id가 빈 값이면 terms가 연도메타에서 왔어도 confidence=name_only·manual=True로 두거나 '코드 확인 필요' 표시. 연도메타 terms는 개설학기 근거로 쓰되 코드 매칭 여부와 신뢰도 라벨을 분리.

## [LOW] 라운드4 fix #3(risk 계절 수용량 remaining×6) — 정규학기 시작에선 planner와 정합 확인(회귀 없음)
- file: graduation_center/v2/risk.py:66-71 / planner.py:357-377
- 문제: 검증 통과 기록: current_term이 정규학기(예 2026-1)일 때 risk capacity와 _ordered_terms cap 합이 모든 플래그 조합에서 일치(잔여 2학기, 계절 on, /tmp/seasonal.py: 둘 다 50). 이 경로의 '플래너 feasible인데 capacity 트리거로 D' 모순은 해소됨. project_overflow 데드, _overflow_from_credits 단일 활성도 확인. 단 (a)risk.py 절대 gap>15 트리거(별도 high 항목)와 (b)계절-start 불일치(별도 medium 항목)는 여전히 모순 유발 — 이 두 건만 고치면 라운드5 핵심 결함 해소.
- 수정: 수정 불필요(정합 확인). 단 capacity 트리거와 gap>15 트리거가 같은 D를 서로 다른 기준으로 발화하는 비일관을 위 high 항목과 함께 정리.
