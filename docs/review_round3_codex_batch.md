===== /tmp/codex_r3_0.txt =====
   566	                </div>
   567	              </div>
   568	            </div>
   569	
   570	            {/* 졸업 최소 평점 주의 (충족이 아닐 때) */}
   571	            {audit.context?.gpa_min_met !== "yes" && (
   572	              <div style={{ ...card, background: audit.context?.gpa_min_met === "no" ? "#fef2f2" : "#fff7ed",
   573	                border: `1px solid ${audit.context?.gpa_min_met === "no" ? "#fecaca" : "#fed7aa"}`,
   574	                color: audit.context?.gpa_min_met === "no" ? C.danger : "#b45309", fontSize: 13 }}>
   575	                ⚠️ {audit.context?.gpa_min_met === "no"
   576	                  ? "졸업 최소 평점(전학년 평점평균 2.0/4.5) 미달 — 졸업요건을 충족하지 못합니다. 평점 관리가 필요합니다."
   577	                  : "졸업 최소 평점(2.0/4.5) 충족 여부가 확인되지 않았습니다 — 성적표로 직접 확인하세요. (미달 시 졸업 불가)"}
   578	              </div>
   579	            )}
   580	
   581	            {/* 영역별 현황 */}
   582	            <div style={card}>
   583	              <div style={sectionTitle}>📊 영역별 이수 현황</div>
   584	              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
   585	                {audit.audit.area_gaps.map((g, i) => <Gauge key={i} label={g.area} earned={g.earned} required={g.required} gap={g.gap} />)}

**Findings**

1. HIGH [REGRESSION] Primary-required overlap can still be assigned `fusion`.
`_convergence_checks` states primary-required courses cannot move to fusion-only, but after duplicate cap fill, flex courses go to `primary` only while `acc_p < p_need`; otherwise they become `fusion`: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:107), [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215). Current data has required overlaps such as `경영통계` and `AI빅데이터프로그래밍Ⅰ`: [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:13), [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:85).
Fix: force any `primary_required` overlap not selected as `dup` to `primary`, never `fusion`; then recompute `fusion_courses`, group checks, and gaps.

2. HIGH [REGRESSION] Multi-convergence allocation double-counts and can double-subtract the same primary credits.
Each convergence check independently treats every other selected program as overlap: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:138). Then `compute_audit` blindly sums every `to_fusion_credits`: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281). AI Big Data overlaps both data-science convergence programs on many prefixes, so the same primary course can be consumed twice.
Fix: build one global per-course allocation across all selected convergence programs; each course gets one primary/fusion owner plus bounded duplicate recognition, and primary subtraction happens at most once per course.

3. HIGH [REGRESSION] `일반선택` residual overplans when required or convergence courses also fill total credits.
General need is `audit.total_gap - sum(area_gaps)` only: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:508). But convergence deficits and missing required items are selected earlier and also add real credits: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:461), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:436). Example: total gap 9 and convergence gap 6 produces convergence 6 plus general 9, overplanning by 6.
Fix: compute total residual after all non-general selected credits that count toward graduation total, or run an iterative simulated audit after candidate selection.

4. MEDIUM [REGRESSION] Frontend 3-way allocation does not recompute group checks after user changes.
`primaryCr` and `fusionCr` recompute from `sel`, but `groupsOk` and shortage text use static backend `cc.group_checks`: [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105). A user can move a B-group overlap into fusion and the UI still says group shortage, or move it out and the UI still says groups pass.
Fix: recompute group earned/gap in React from `cc.courses`, `overlap_courses`, and current `sel`; base suggestions on recomputed group gaps.

5. MEDIUM [REGRESSION] Required-course catalog fallback is unsafe and can silently lose course id/prereqs.
Fallback takes `hit[0]` even when normalized names are non-unique: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445). Current catalog has duplicate normalized `다학제간캡스톤디자인`: [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639), [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781). Worse, 2023 required names `다학제간캡스톤디자인Ⅰ/Ⅱ` have metadata but no catalog match, yet `known = bool(terms)` makes them `catalog_verified` with empty `course_id`: [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455).
Fix: only mark `catalog_verified` when a unique or explicitly preferred catalog course id is found; otherwise `manual=True`, `confidence=name_only`, and surface missing id/prereq uncertainty.

6. MEDIUM [REGRESSION] Overflow estimate is still credit-only and underestimates term count under offering/prereq constraints.
`_overflow_from_credits` uses `ceil(unplaced_credits / cap)` only: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:398). If remaining is 0 after `2026-1` and the unplaced course is only offered in 1학기, it can report one extra term projected `2026-2`, which is impossible.
Fix: extend `_ordered_terms` semester by semester and rerun `plan_greedy` until all unplaced courses fit, respecting offered terms, prerequisites, seasonal rules, and caps.

7. MEDIUM [REGRESSION] Malformed `current_term` is treated like missing current term.
`_ordered_terms` returns `[]` for parse errors: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:357). `run_planner` then falls into the “현재 학기 미입력” feasible-null path unless `remaining_semesters <= 0`: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631). Input `26-1` is not missing; it is invalid.
Fix: add a `StudentContext` validator for `^20\d{2}-(1|2|S|W)$`; invalid should be a 422 or explicit validation error, not a neutral roadmap deferral.

8. LOW Total credits vs effective major credits are internally logical but unexplained to users.
Major area uses `major_effective` after subtracting fusion allocation: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:282). Total still shows raw earned credits: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:334), [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:553). Demo viewers will see “총 144” but “전공 64” after subtraction and may read it as inconsistent.
Fix: add a short note near the area gauges: total is raw 취득학점, 전공 is 배정 반영 인정학점.

**Round-2 Status**

Risk `gpa_min_met='no' -> D` is correct: [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88). The other round-2 fixes are only partial: allocation, general residual, overflow, required fallback, and frontend group handling still have correctness holes above.

Also, I could not run live Python probes fully in this workspace: current `python` is 3.8.5 and imports fail on `str | None` annotations such as [models_v2.py](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:20). For the demo, either pin Python >=3.10 explicitly or remove PEP 604 syntax.
===== /tmp/codex_r3_1.txt =====
   705	
   706	              {audit.roadmap.overflow && (
   707	                <div style={{ marginTop: 12, padding: 14, borderRadius: 10, background: "#fff7ed", border: "1px solid #fed7aa" }}>
   708	                  <div style={{ fontWeight: 700, color: "#b45309", fontSize: 13.5, marginBottom: 8 }}>⏳ 초과학기 예상 시나리오</div>
   709	                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 8 }}>
   710	                    {[["부족 학점", `${audit.roadmap.overflow.shortfall_credits}학점`],
   711	                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
   712	                      ["필요 총학기", `${audit.roadmap.overflow.total_semesters_needed}학기`],
   713	                      ["초과학기", `${audit.roadmap.overflow.extra_semesters}학기`],
   714	                      ["예상 졸업", audit.roadmap.overflow.projected_graduation_term || "—"]].map(([k, v]) => (
   715	                      <div key={k}>
   716	                        <div style={{ fontSize: 11, color: C.muted }}>{k}</div>
   717	                        <div style={{ fontSize: 15, fontWeight: 700, color: "#b45309" }}>{v}</div>
   718	                      </div>
   719	                    ))}
   720	                  </div>
   721	                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{audit.roadmap.overflow.note}</div>
   722	                </div>
   723	              )}
   724	            </div>
   725	
   726	            {/* 워크플로우 그래프 — 별도 페이지로 분리 */}
   727	            <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
   728	              <div>
   729	                <div style={{ fontSize: 13.5, fontWeight: 700, color: C.navy }}>🔀 워크플로우 실행 그래프</div>
   730	                <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>

**Findings**

1. **HIGH [REGRESSION] 총학점 일반선택 슬롯이 융합 부족 학점을 이중계상합니다.**  
   [planner.py:461](/home/carol/kmu_genai/graduation_center/v2/planner.py:461)에서 융합 부족 과목을 후보로 추가한 뒤, [planner.py:510](/home/carol/kmu_genai/graduation_center/v2/planner.py:510)에서 `general_need = audit.total_gap - area_floor_gap`만 계산합니다. 융합 과목도 총학점에 물리적으로 더해지는데 residual에서 빠지지 않아, `total_gap=6`, `융합 gap=6`, 영역 gap=0이면 융합 6 + 일반선택 6을 계획합니다.  
   Fix: 일반선택 residual은 이미 계획될 물리 학점, 특히 융합/그룹 부족 후보 학점을 차감한 뒤 산출하세요. `selected` 후보를 만들기 전에 quota별 “총학점에 기여하는 planned_floor_credits”를 추적하거나, 일반선택을 마지막에 `audit.total_gap - non_general_selected_credits` 기준으로 재계산해야 합니다.

2. **HIGH 융합 그룹 부족 로드맵이 그룹별 최저를 보장하지 않습니다.**  
   [planner.py:462](/home/carol/kmu_genai/graduation_center/v2/planner.py:462)에서 그룹별 gap을 계산하지만, [planner.py:467](/home/carol/kmu_genai/graduation_center/v2/planner.py:467)의 pool은 “부족 그룹 우선” 정렬만 하고 [planner.py:527](/home/carol/kmu_genai/graduation_center/v2/planner.py:527)에서 총 `need`까지만 채웁니다. A/B가 각각 6 부족해도 카탈로그 순서상 한 그룹 과목만 먼저 12학점 뽑힐 수 있고, [planner.py:649](/home/carol/kmu_genai/graduation_center/v2/planner.py:649)의 검증은 미배치/상한만 봐서 그룹 미충족을 통과시킵니다.  
   Fix: 그룹 gap별로 별도 requirement를 만들고 `pool`을 해당 그룹으로 제한하세요. 계획 후에는 기존 이수 + 계획 과목으로 `group_checks`를 재계산해 검증해야 합니다.

3. **HIGH 다중 융합전공 동시 선택은 아직 전공 학점을 중복 차감/오배정합니다.**  
   [audit_v2.py:127](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:127)에서 선택된 모든 융합 프로그램 prefix를 서로의 `other_prefixes`에 넣고, [audit_v2.py:207](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:207)은 그 overlap 전체를 `primary_major_earned`에서 뺍니다. 이후 [audit_v2.py:281](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281)는 각 convergence check의 `to_fusion_credits`를 단순 합산해 전공에서 차감합니다. 같은 과목이 두 융합에 걸치면 “제1전공”이 아닌 다른 융합 overlap까지 제1전공처럼 처리되고, 같은 물리 과목이 여러 번 차감될 수 있습니다.  
   Fix: 전체 선택 프로그램을 한 번에 푸는 allocation pass를 두세요. 과목 prefix별로 primary/dup/fusion assignment를 전역 1회 결정하고, 프로그램별 cap/group은 그 전역 배정을 참조해야 합니다.

4. **MEDIUM [REGRESSION] 프론트 3-way 선택에서 그룹 충족 상태가 정적으로 고정됩니다.**  
   [GraduationV2.jsx:100](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100)는 사용자의 `sel` 변경으로 `primaryCr/fusionCr`를 다시 계산하지만, [GraduationV2.jsx:106](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:106)의 `groupsOk`와 [GraduationV2.jsx:142](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:142)의 부족 메시지는 백엔드 `cc.group_checks` 그대로입니다. 사용자가 overlap 과목을 융합으로 돌려 그룹을 채워도 계속 부족으로 보이거나, 반대로 그룹 과목을 제1전공으로 빼도 충족으로 보일 수 있습니다.  
   Fix: 현재 `sel` 기준으로 taken non-overlap + `dup/fusion` overlap의 group earned를 프론트에서도 재계산하세요.

5. **MEDIUM [REGRESSION] 필수과목 catalog fallback이 다중 hit/미존재 capstone을 안전하게 처리하지 않습니다.**  
   [planner.py:445](/home/carol/kmu_genai/graduation_center/v2/planner.py:445)는 `by_norm` hit가 여러 개여도 `hit[0]`을 택합니다. 실제로 미래모빌리티 카탈로그에는 `다학제간캡스톤디자인`과 `다학제간캡스톤디자인+`가 같은 정규화명입니다([catalog_mirae_mobility.json:639](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639), [catalog_mirae_mobility.json:781](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781)). 반대로 2023 요람의 `다학제간캡스톤디자인Ⅰ/Ⅱ`는 카탈로그에 없는데([required_names_by_year.json:133](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133)), terms만 있으면 [planner.py:455](/home/carol/kmu_genai/graduation_center/v2/planner.py:455)에서 `catalog_verified`처럼 취급됩니다.  
   Fix: `len(hit) == 1`일 때만 코드/선수/개설 정보를 확정하고, 0 또는 다중 hit는 `name_only`, `manual=True`로 낮추세요. 요람 필수 메타에 course_id/prereq를 명시하는 게 더 안전합니다.

6. **MEDIUM [REGRESSION] 초과학기 산정이 실제 미배치 사유를 다시 버립니다.**  
   `plan_greedy`는 개설학기/선수/용량 때문에 미배치를 만들지만([planner.py:560](/home/carol/kmu_genai/graduation_center/v2/planner.py:560)), `_overflow_from_credits`는 미배치 학점 ÷ 정규학기 cap만 봅니다([planner.py:398](/home/carol/kmu_genai/graduation_center/v2/planner.py:398)). 1학기 개설 과목이 남았는데 현재 다음 잔여학기가 2학기이면 “학점상 한 학기”가 아니라 다음 1학기까지 밀립니다.  
   Fix: overflow 산정도 `_ordered_terms`를 잔여 이후로 확장해서 같은 greedy 제약으로 몇 번째 정규학기까지 필요한지 시뮬레이션하세요.

7. **LOW [REGRESSION] malformed `current_term` + `remaining_semesters=0`이 잘못된 blocked로 분류됩니다.**  
   `_ordered_terms`는 파싱 실패 시 빈 리스트를 반환합니다([planner.py:361](/home/carol/kmu_genai/graduation_center/v2/planner.py:361)). 그런데 [planner.py:633](/home/carol/kmu_genai/graduation_center/v2/planner.py:633)는 `context.current_term`이 truthy이고 잔여 0이면 “잔여 학기 0” blocked로 처리합니다. `"26-1"` 같은 잘못된 값은 current_term missing/invalid와 구분되어야 합니다.  
   Fix: `_ordered_terms`가 `empty_reason`을 반환하게 하거나 current_term validator를 두고, invalid는 `feasible=None`/입력오류 안내로 분기하세요.

**Round-2 Pass Checks**

`gpa_min_met="no"`는 D로 강등됩니다([risk.py:88](/home/carol/kmu_genai/graduation_center/v2/risk.py:88)). Backend/frontend 기본 overlap ordering은 현재 코드상 동치입니다([audit_v2.py:215](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215), [GraduationV2.jsx:86](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:86)). 현재 융합 카탈로그가 전부 3학점이라 greedy cap fill은 현 데이터에서는 cap 6/12를 못 채우는 반례가 안 보이지만, 가변 학점이 들어오면 knapsack으로 바꿔야 합니다.
===== /tmp/codex_r3_2.txt =====
    80	        eff_gap = max(cc.get("gap", 0), *(gc["gap"] for gc in group_short)) if group_short else cc.get("gap", 0)
    81	        if eff_gap > 0:
    82	            grade = _worse(grade, "C" if eff_gap >= 9 else "B")
    83	            detail = f"{cc['name']} 총 {cc['gap']:.0f}학점 부족" if cc["gap"] > 0 else f"{cc['name']}"
    84	            if group_short:
    85	                detail += " · 그룹 부족: " + ", ".join(f"{gc['group']} {gc['gap']:.0f}" for gc in group_short)
    86	            reasons.append(RiskReason(factor="융합전공", detail=detail, severity=14 if eff_gap >= 9 else 8))
    87	
    88	    if context.gpa_min_met == "no":
    89	        # 졸업 평점(전학년 2.0) 미달은 확정적 졸업불가 → 최악 등급(D)
    90	        grade = _worse(grade, "D")
    91	        reasons.append(RiskReason(factor="평점", detail="졸업 평점 기준(2.0/4.5) 미달 — 졸업 불가", severity=30))
    92	    elif context.gpa_min_met == "unknown":
    93	        reasons.append(RiskReason(factor="평점", detail="평점 기준 충족 여부 확인 필요", severity=0))
    94	
    95	    if roadmap_feasible is False:
    96	        grade = _worse(grade, "C")
    97	        reasons.append(RiskReason(factor="로드맵", detail="잔여 학기 내 실현 가능한 계획 없음", severity=15))
    98	
    99	    if grade == "A" and not reasons:
   100	        reasons.append(RiskReason(factor="종합", detail="확인된 부족·위험 항목 없음", severity=0))

I have enough for the review now. The round-2 fixes are partly correct, but there are still accounting holes around planner feasibility and multi-convergence handling that can affect a live demo.
**Findings**

HIGH [REGRESSION] [graduation_center/v2/planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:510): 일반선택 residual still double-counts non-area obligations, especially 융합전공.
`build_unified_candidates()` adds 융합 부족 candidates at lines 461-476, then computes `general_need = total_gap - sum(area_gaps)` at lines 510-511. 융합 candidates also raise total earned credits, but they are not in `area_gaps`, so a case like `total_gap=10`, `융합 gap=6`, `area_gaps=[]` plans 6 융합 + 10 일반선택 = 16 credits. This is not false satisfaction, but it is a round-2 residual fix that is incomplete and can force fake 초과학기.
Fix: compute residual after de-duplicated selected obligations that count toward total credits, e.g. build required/floor candidates first, sum their actual selected credits, then `general_need = max(0, total_gap - selected_floor_credits)`. Include 융합, 필수, 전공, 교양 slots in that subtraction.

HIGH [graduation_center/v2/planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:624): unmet requirements with an empty candidate pool are reported as “졸업요건을 모두 충족했습니다.”
`reqs` can be non-empty while `selected` is empty: for example `전공 부족` with no untaken catalog pool at lines 482-487, or 융합 부족 with no remaining untaken courses at lines 461-476. `run_planner()` only checks `if not selected` and returns `feasible=True` at lines 624-627. That is a direct false-satisfaction path.
Fix: distinguish `not reqs` from `not selected`. If `reqs` is non-empty but no candidates can be selected, return `status="blocked"`, `feasible=False`, with a validation error like `no_candidate_for_unmet_requirement`.

HIGH [REGRESSION] [graduation_center/v2/audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281): multiple convergence programs can subtract the same credits from 제1전공 more than once.
Each convergence check treats every other selected program prefix as overlap at lines 136-139, then `compute_audit()` sums every check’s `to_fusion_credits` and subtracts it from raw 전공 at lines 281-282. With two 융합전공s sharing a course, the same course can affect both convergence checks, and a non-primary/shared convergence overlap can still contribute to the primary subtraction model.
Fix: perform allocation globally per course across primary + all convergence programs. Only subtract from 제1전공 when the course was actually counted in `earned_by_area["전공"]` and assigned away from primary. Track course identity/prefix allocations once, not per convergence check.

MEDIUM [REGRESSION] [graduation_center/v2/planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:398): overflow is still under-estimated when the blocker is offered-term or prerequisite topology, not raw capacity.
`_overflow_from_credits()` uses only `ceil(unplaced_credits / cap)` at lines 405-413. But `plan_greedy()` rejects courses by offered term and prereq order at lines 560-568. A 3-credit course offered only in 2학기 can require two extra regular terms if the next extra term is 1학기, but overflow reports one.
Fix: estimate overflow by extending future terms and rerunning the same placement constraints until unplaced is empty, then compute the number of extra regular terms actually needed.

MEDIUM [frontend/src/components/GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:106): frontend group status is stale after the user changes 3-way assignment.
`primaryCr` and `fusionCr` recompute from `sel`, but `groupsOk` and shortage text use backend `cc.group_checks` from the initial assignment only. After moving a course from 융합전공 to 제1전공, the UI can still say “그룹별 최저 포함 충족.”
Fix: recompute group earned/gaps in the component from `cc.fusion_base`, `ov`, `sel`, and each overlap course’s `group`, or call backend for recalculation.

MEDIUM [graduation_center/v2/risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62): risk capacity ignores 제32조 default cap when `max_credits_per_term` is omitted.
Planner uses `regular_term_cap(profile.total_credits_min)`, but risk hardcodes `18` at line 62. For 136-credit programs the default should be 19. API callers that omit `max_credits_per_term` can get an inflated 잔여학기 risk.
Fix: pass `profile` into `compute_risk()` or compute the cap from `audit.total_required` using the same `regular_term_cap()` helper.

LOW [graduation_center/v2/audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:217): duplicate-recognition cap fill is greedy, not optimal.
Current convergence catalogs are all 3-credit courses, so this does not fail the present data. But the algorithm takes ordered courses while `dup_cr + credits <= cap`; variable-credit future data can leave capacity unused where another subset fits better.
Fix: use bounded subset selection under cap, with required-course priority as a hard or weighted constraint, then 학점 내림차순 as tie-break.

LOW [graduation_center/v2/planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631): malformed `current_term` is treated like missing current term.
`_ordered_terms()` returns `[]` for malformed labels, and `run_planner()` falls through to “현재 학기 미입력” unless `remaining_semesters <= 0`. `26-1` should be rejected or labeled invalid, not missing.
Fix: add explicit current-term validation and return a validation error/assumption for invalid format.

**Verified Round-2 Items**

The GPA `no -> D` fix is correct in [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88). The frontend now includes group checks in `fits`, but the recomputation is stale after UI changes. The backend convergence totals do recompute from allocated `fusion_courses`, but multi-convergence and greedy cap issues remain. The planner no longer uses `project_overflow()` in `run_planner()`, but the new overflow model is still too coarse for offered-term blockers.
===== /tmp/codex_r3_3.txt =====
    32	    },
    33	    "required_marked": 19,
    34	    "unresolved_required": [],
    35	    "ambiguous_override": [],
    36	    "unresolved_prereq": [],
    37	    "group_unmatched": [],
    38	    "grouped": 0
    39	  },
    40	  "dsci_convergence": {
    41	    "course_count": 23,
    42	    "duplicate_codes": [],
    43	    "code_conflicts": [],
    44	    "ambiguous_name_norm": {},
    45	    "required_marked": 0,

**Findings**

1. **HIGH [REGRESSION] General-election residual double-counts convergence requirements**  
   [planner.py:460](/home/carol/kmu_genai/graduation_center/v2/planner.py:460), [planner.py:510](/home/carol/kmu_genai/graduation_center/v2/planner.py:510)  
   `general_need = total_gap - Σarea_gaps` ignores convergence shortages already selected in step 2. If the student is short 6 total credits and also short 6 융합 credits, the planner selects 6 융합 credits plus 6 일반선택 credits, even though the 융합 courses also raise total credits.  
   **Fix:** compute residual after all selected credit-producing requirements, or include convergence/group planned credits in the floor subtraction before creating 일반선택 slots.

2. **HIGH [REGRESSION] Prerequisite “topological” placement is incomplete**  
   [planner.py:550](/home/carol/kmu_genai/graduation_center/v2/planner.py:550), [planner.py:554](/home/carol/kmu_genai/graduation_center/v2/planner.py:554)  
   A prerequisite only matters if it is already in `selected`. If planned course `A` requires `P`, and `P` is neither completed nor selected, `_try_place()` proceeds and places `A`. That violates the domain rule “선수 지켜 배치”. The deterministic route also never calls `validate_roadmap()`.  
   **Fix:** recursively add missing prerequisites to `selected`, or block with `prereq_unmet`. Then validate the deterministic plan with the same prerequisite rules.

3. **HIGH [REGRESSION] Overflow estimate still undercounts offered-term/prerequisite blockers**  
   [planner.py:398](/home/carol/kmu_genai/graduation_center/v2/planner.py:398), [planner.py:406](/home/carol/kmu_genai/graduation_center/v2/planner.py:406)  
   `_overflow_from_credits()` uses `ceil(unplaced_credits / reg_cap)`. If unplaced courses are all 1학기-only, or require a chain, “3 unplaced credits” can require waiting two regular terms, not one. This directly violates the added focus: unplaced-based is better than `project_overflow`, but the extra-semester projection is still a capacity-only lower bound.  
   **Fix:** run the same scheduler on an extended future term list until all unplaced courses fit; derive `extra_semesters` and `projected_graduation_term` from actual placement, not credit division.

4. **HIGH Existing multi-convergence double-subtract remains**  
   [audit_v2.py:136](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:136), [audit_v2.py:281](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281)  
   `_convergence_checks()` allocates each convergence program independently, then `compute_audit()` subtracts `Σto_fusion_credits` from primary 전공. The same physical course shared by two 융합전공s can be subtracted twice.  
   **Fix:** allocate globally by course prefix/course id across all selected convergence programs; subtract each primary course’s credits at most once.

5. **MEDIUM [REGRESSION] 중복인정 recommendation can exceed cap**  
   [audit_v2.py:191](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:191), [audit_v2.py:195](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:195)  
   `recommend_double_count` stops only when `acc >= cap`, but it appends a course even when `acc + credits > cap`. Allocation at [audit_v2.py:218](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:218) uses `<= cap`, so the visible recommendation can disagree with actual `courses_view.assignment`.  
   **Fix:** build `recommend_double_count` from `alloc == "dup"`, or apply the same `acc + credits <= cap` condition.

6. **MEDIUM [REGRESSION] Frontend group checks do not react to user 3-way assignment**  
   [GraduationV2.jsx:105](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105), [GraduationV2.jsx:141](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:141)  
   `groupsOk` reads backend `cc.group_checks`, which is fixed for the default allocation. If the user changes a course from 제1전공 to 융합전공, `fusionCr` updates but group earned/gap does not. The UI can still show “그룹별 최저 미충족” after the user has fixed it.  
   **Fix:** recompute group earned from `ov + sel + fusion_base` in React, or round-trip assignment changes to the backend.

7. **MEDIUM Required catalog fallback picks ambiguous first hit**  
   [planner.py:445](/home/carol/kmu_genai/graduation_center/v2/planner.py:445), [planner.py:447](/home/carol/kmu_genai/graduation_center/v2/planner.py:447)  
   `hit[0]` is used even when `by_norm` has multiple course ids. Data already has `다학제간캡스톤디자인` ambiguity: [catalog_build_report.json:27](/home/carol/kmu_genai/data/graduation/v2/catalog_build_report.json:27), with one required and one non-required catalog row at [catalog_mirae_mobility.json:639](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639) and [catalog_mirae_mobility.json:781](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781).  
   **Fix:** only accept unique hits, or choose by `is_required`, `required_codes`, and year metadata. Otherwise mark `manual=True`.

8. **LOW malformed `current_term` still creates bogus terms**  
   [planner.py:361](/home/carol/kmu_genai/graduation_center/v2/planner.py:361), [models_v2.py:21](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:21)  
   `26-1` parses as year `26`, producing `26-2`, `27-1`, etc. Missing current term and malformed current term are not cleanly distinguished.  
   **Fix:** validate `current_term` with `^20\d{2}-[12SW]$`; malformed should return `feasible=None` with an explicit format error.

**Round-2 Checks That Look Correct**

`gpa_min_met="no"` now forces D at [risk.py:88](/home/carol/kmu_genai/graduation_center/v2/risk.py:88). `remaining_semesters=0` with a present current term now returns `blocked` plus overflow at [planner.py:631](/home/carol/kmu_genai/graduation_center/v2/planner.py:631). `run_planner()` no longer calls `project_overflow`; it uses unplaced credits at [planner.py:665](/home/carol/kmu_genai/graduation_center/v2/planner.py:665), but the projection remains too weak as noted above.
===== /tmp/codex_r3_4.txt =====
/bin/bash -lc "rg -n 'Python프로그래밍|자동차모빌리티기초|기초선형대수|자료구조및알고리즘|모빌리티실험및실습' data/graduation/v2/catalog_mirae_mobility.json data/graduation/v2/catalog_mobility_data_convergence.json" in /home/carol/kmu_genai
 succeeded in 0ms:
data/graduation/v2/catalog_mobility_data_convergence.json:47:      "name_ko": "Python프로그래밍",
data/graduation/v2/catalog_mobility_data_convergence.json:67:      "name_ko": "자동차모빌리티기초",
data/graduation/v2/catalog_mobility_data_convergence.json:68:      "name_norm": "자동차모빌리티기초",
data/graduation/v2/catalog_mobility_data_convergence.json:188:      "name_ko": "기초선형대수",
data/graduation/v2/catalog_mobility_data_convergence.json:189:      "name_norm": "기초선형대수",
data/graduation/v2/catalog_mobility_data_convergence.json:268:      "name_ko": "자료구조및알고리즘",
data/graduation/v2/catalog_mobility_data_convergence.json:269:      "name_norm": "자료구조및알고리즘",
data/graduation/v2/catalog_mobility_data_convergence.json:351:      "name_ko": "모빌리티실험및실습",
data/graduation/v2/catalog_mobility_data_convergence.json:352:      "name_norm": "모빌리티실험및실습",
data/graduation/v2/catalog_mirae_mobility.json:75:      "name_ko": "Python프로그래밍",
data/graduation/v2/catalog_mirae_mobility.json:95:      "name_ko": "자동차모빌리티기초",
data/graduation/v2/catalog_mirae_mobility.json:96:      "name_norm": "자동차모빌리티기초",
data/graduation/v2/catalog_mirae_mobility.json:317:      "name_ko": "기초선형대수",
data/graduation/v2/catalog_mirae_mobility.json:318:      "name_norm": "기초선형대수",
data/graduation/v2/catalog_mirae_mobility.json:417:      "name_ko": "자료구조및알고리즘",
data/graduation/v2/catalog_mirae_mobility.json:418:      "name_norm": "자료구조및알고리즘",
data/graduation/v2/catalog_mirae_mobility.json:458:      "name_ko": "모빌리티실험및실습",
data/graduation/v2/catalog_mirae_mobility.json:459:      "name_norm": "모빌리티실험및실습",

**Findings**

HIGH [REGRESSION] Primary required overlap courses can be assigned `fusion` only.
[audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:107) says 제1전공/다전공 전공필수 cannot be moved to fusion-only, but flex allocation sends every remaining overlap to `fusion` once `p_need` is zero: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:221). This is reachable: 미래모빌리티 has 15 credits of required overlaps with 모빌리티데이터융합, above the 12-credit cap. Example data: [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:73), [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:45).
Fix: force `primary_required` flex courses to `primary` after cap unless selected as `dup`; never assign them `fusion`.

HIGH [REGRESSION] Required-course name matching falsely accepts ambiguous non-required variants.
Audit checks required completion by normalized name only: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:315). Required 2025 lists `다학제간캡스톤디자인`: [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147), but catalog has both required `다학제간캡스톤디자인` and non-required `다학제간캡스톤디자인+` with the same `name_norm`: [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:638), [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:780). The build report already flags the ambiguity: [catalog_build_report.json](/home/carol/kmu_genai/data/graduation/v2/catalog_build_report.json:27), and overrides specify required code `0693316`: [overrides_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/overrides_mirae_mobility.json:29).
Fix: required checks must use required code when a normalized name is ambiguous; do not satisfy required by name-only unless the name maps uniquely or an explicit alias/code equivalence exists.

HIGH [REGRESSION] General-elective residual double-counts convergence catch-up credits.
Convergence deficits add selected 융합전공 courses first: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:461). Then `general_need` is computed as `total_gap - area_floor_gap`, ignoring those convergence courses: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:510). If a student is 10 total credits short and 12 융합 credits short, the planner schedules 12 융합 plus 10 일반선택, even though the 융합 courses already fill the total-credit gap.
Fix: compute general residual after all non-general planned obligations: `max(0, total_gap - credits_selected_before_general)` with care for area/core duplicate accounting.

HIGH Still open: multiple convergence selections can double-subtract the same primary credits.
`to_fusion_total` blindly sums each convergence check’s `to_fusion_credits`: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281). `_convergence_checks` treats every other selected convergence catalog as overlap: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137). If one completed course appears in two convergence catalogs and is assigned fusion in both, primary major credit is subtracted twice.
Fix: allocate globally by course prefix/id across all selected convergence programs, then subtract each physical course from primary at most once.

MEDIUM [REGRESSION] Frontend group checks are stale after 3-way changes.
`fusionCr` and `primaryCr` recompute from UI state, but `groupsOk` and the group-shortage message read backend `cc.group_checks` only: [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:106). Changing an overlap from `primary` to `fusion` can fix a group, but the UI still says group shortage; changing away from a group can also falsely keep “fits”.
Fix: recompute per-group earned from `cc.fusion_base` plus selected `dup/fusion` overlap courses by group, and base `groupsOk`, messages, and suggestions on that derived state.

MEDIUM [REGRESSION] Overflow estimate can undercount extra semesters when unplaced is caused by offering/prereq sequence, not raw capacity.
`_overflow_from_credits` converts unplaced credits to `ceil(unplaced / cap)`: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:398). That ignores courses offered only in one regular term and chains that require different future offerings. A 6-credit two-course chain both offered only in spring can need two extra years, not `ceil(6/18)=1` semester.
Fix: extend the actual term list and rerun the same greedy placement until all unplaced courses fit; report the number of added regular terms from that simulation.

MEDIUM Required fallback marks metadata-only courses as `catalog_verified` and bypasses prereqs.
For missing required names, `known = bool(terms)` makes a course catalog-verified even when no `course_id` was found: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:440), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455). 2023 capstone I/II exist only as required-name metadata: [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133). With no course id/prereq, `plan_greedy` has no topological constraint to enforce I before II: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:551).
Fix: split `offering_known` from `catalog_verified`; no `course_id` should remain manual/name-only. Add required-meta prerequisites for sequenced required names or fail to manual-check rather than silently scheduling.

LOW [REGRESSION] Malformed `current_term` is treated as “missing current term.”
`_ordered_terms` returns `[]` for parse failure: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:360). `run_planner` then falls into the “현재 학기 미입력” feasible-null path unless `remaining_semesters <= 0`: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631). A value like `26-1` is not missing; it is invalid.
Fix: validate `current_term` in `StudentContext` with `^20\d{2}-(1|2|S|W)$`, or return a validation error/blocked reason for malformed input.

LOW Demo blocker in this environment: tests do not collect under the default Python.
`pytest tests/test_v2_pipeline.py -q` fails during collection because the active Python is 3.8.5 while imported models use `str | None`: [models.py](/home/carol/kmu_genai/graduation_center/models.py:24), imported through [__init__.py](/home/carol/kmu_genai/graduation_center/__init__.py:3). No Python version is pinned in `requirements.txt`.
Fix: use/pin Python >=3.10 for demo and CI, or rewrite annotations/install `eval_type_backport`.

Verified static positives: `gpa_min_met == "no"` now grades D at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88); `remaining_semesters=0` with valid `current_term` now returns blocked + overflow at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:633); `project_overflow` is no longer used by `run_planner` for blocked overflow.
===== /tmp/codex_r3_5.txt =====
   161	    term: str
   162	    courses: list[RoadmapCourse] = Field(default_factory=list)
   163	    term_credits: float = 0.0
   164	    term_risk: Literal["low", "medium", "high"] = "low"
   165	    notes: list[str] = Field(default_factory=list)
   166	
   167	
   168	class OverflowScenario(BaseModel):
   169	    """잔여 학기로 졸업이 불가능할 때의 초과학기 예상(결정론 산출)."""
   170	    shortfall_credits: float                          # 부족 학점(총 졸업학점 대비)
   171	    per_term_credit_cap: float                        # 학기당 이수학점 상한(제32조)
   172	    remaining_semesters: int                          # 현재 잔여 정규학기
   173	    total_semesters_needed: int                       # 졸업까지 필요한 총 정규학기
   174	    extra_semesters: int                              # 초과학기 수(= 필요 - 잔여)
   175	    projected_graduation_term: str | None = None      # 예상 졸업 학기 라벨

**Findings**

1. **HIGH [REGRESSION] 일반선택 residual is still mathematically wrong.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:461) adds 융합전공 부족 candidates, and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:510) computes 일반선택 as `total_gap - sum(area_gaps)`. 융합전공, 핵심교양 세부영역, 미이수 필수처럼 `area_gaps` 밖에서 추가 수강하는 과목도 총학점을 올리는데 residual에서 빠지지 않습니다. Example: `total_gap=12`, 융합 gap `12`, area gap `0` -> planner selects 12학점 융합 + 12학점 일반선택 = 24학점.  
   **Fix:** build all non-general selected obligations first, sum their physical credits, then `general_need = max(0, audit.total_gap - non_general_selected_credits)`.

2. **HIGH [REGRESSION] Frontend group fit is stale after 3-way allocation changes.**  
   `fusionCr` recomputes from current `sel` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), but `groupsOk` uses backend default `cc.group_checks` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:106). If the user moves an A/B-group overlap course from 융합 to 제1전공, the group shortage message remains based on the old allocation.  
   **Fix:** recompute current group earned/gap in `ConvergenceBlock` from `cc.courses`, `ov`, and `sel`; use that for `fits`, shortage text, and suggestions.

3. **HIGH Known remaining bug: multiple convergence programs double-subtract the same course from 전공.**  
   `_convergence_checks` treats overlaps against every other selected program at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:138), then `compute_audit` blindly sums every convergence `to_fusion_credits` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281). The same physical course can appear in both 데이터사이언스융합 and 모빌리티데이터분석융합, so it can be subtracted twice from 제1전공.  
   **Fix:** allocate globally by course prefix across all convergence selections, and subtract each physical course from 전공 at most once.

4. **MEDIUM [REGRESSION] Overflow estimate still ignores why courses were unplaced.**  
   `_overflow_from_credits` just does `ceil(unplaced_credits / reg_cap)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405). But `unplaced` may be caused by offered-term or prerequisite constraints from [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:567). A 2학기-only course unplaced after `2026-2` with no remaining semesters gets projected as `2027-1`, although earliest is `2027-2`.  
   **Fix:** simulate future terms with the same greedy/constraint logic until all unplaced courses place; compute extra semesters from the actual last placed term.

5. **MEDIUM [REGRESSION] `recommend_double_count` can exceed the cap and diverge from actual allocation.**  
   Recommendation appends before checking `acc + credits <= cap` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:193). Actual allocation enforces the cap at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:218). The UI can recommend more 중복인정 than the allocation uses.  
   **Fix:** derive `recommend_double_count` from `alloc == "dup"` or apply the same `acc + credits <= cap` condition.

6. **MEDIUM UX/demo risk: raw total credits and effective 전공 credits are shown without reconciliation.**  
   Backend keeps total as raw physical credits at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:334), while 전공 uses allocation-adjusted credits at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:296). Frontend shows “총 144/136” at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:553) and adjusted area gauges at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:585). Users will read this as contradictory.  
   **Fix:** label total as “실제 취득학점” and 전공 as “배정 반영 인정학점”; expose `major_raw`, `major_effective`, and `to_fusion_credits` in the summary.

7. **LOW Required fallback has unsafe first-hit behavior.**  
   `cat["by_norm"][...][0]` is used at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445). 미래모빌리티 has two normalized capstone hits: [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:640) and [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:782). Historical required names include 캡스톤Ⅰ/Ⅱ at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133), which may not map to a real catalog id/prereq.  
   **Fix:** prefer exact `name_ko`, `is_required`, matching credits/terms; if still ambiguous, leave `course_id=""` and mark manual check.

8. **LOW [REGRESSION] malformed `current_term` is treated like missing current term.**  
   `_ordered_terms` returns `[]` both for missing and malformed terms at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:357), and `run_planner` falls into “현재 학기 미입력” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:640).  
   **Fix:** validate `current_term` with a Pydantic pattern or return parse status so malformed input becomes a clear validation error.

**Verified OK**

- GPA `no` now forces grade D: [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88).
- Single-convergence backend default allocation mostly matches frontend default order: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215), [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:85).
- Backend default `group_checks` are recomputed from fusion-effective courses: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:231).
- `remaining_semesters=0` with valid current term blocks honestly: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631).

**Demo Blocker**

The repo’s default `python`/`python3` is 3.8.5 here, and `pytest` fails during collection on modern typing syntax. Either require/run Python 3.10+ explicitly or backport annotations.
===== /tmp/codex_r3_6.txt =====
   142	          "terms": [
   143	            "2"
   144	          ]
   145	        }
   146	      ],
   147	      "2025": [
   148	        "S-TEAM Class",
   149	        "일반물리Ⅰ",
   150	        "일반물리실험Ⅰ",
   151	        "공학기초수학",
   152	        "Python프로그래밍",
   153	        "자동차모빌리티기초",
   154	        "일반물리Ⅱ",
   155	        "일반물리실험Ⅱ",
   156	        "공학수학Ⅰ",
   157	        "정역학",
   158	        "자동차모빌리티 Adventure Design",
   159	        "기초선형대수",
   160	        "회로이론",
   161	        "확률및통계",
   162	        "동역학",
   163	        "전자회로",
   164	        "자료구조및알고리즘",
   165	        "모빌리티실험및실습",
   166	        "다학제간캡스톤디자인"
   167	      ]
   168	    }

The capstone fallback risk is real in the data, not just theoretical: the build report records `다학제간캡스톤디자인` as an ambiguous normalized name, while the planner fallback takes the first hit. I’m doing one more pass over exact line references, then I’ll give the ranked review.
**Findings**

- **HIGH [REGRESSION]** [planner.py:551](/home/carol/kmu_genai/graduation_center/v2/planner.py:551): `plan_greedy` allows a course whose prerequisite is neither completed nor scheduled if that prerequisite is not already in `selected`. It only defers when `p in sel_pref`, then proceeds as if unmet external prerequisites are okay. This breaks the “prereq topological works” round-2 claim.
  Fix: expand `selected` with prerequisite closure before scheduling, or mark the dependent item unplaced when any prereq is not in `completed` or `placed_at`.

- **HIGH [REGRESSION]** [planner.py:510](/home/carol/kmu_genai/graduation_center/v2/planner.py:510): `general_need = total_gap - area_floor_gap` ignores other credit-bearing planned obligations, especially convergence gaps and 핵심교양 세부영역 gaps. If `total_gap=6` and 융합전공 부족=6 with no area gap, the planner adds both 융합 6 and 일반선택 6, overplanning 12 credits.
  Fix: compute residual after all credit-bearing requirements selected, or subtract convergence/group/core-subarea planned credits from `total_gap` before adding 일반선택 slots.

- **MEDIUM [REGRESSION]** [planner.py:398](/home/carol/kmu_genai/graduation_center/v2/planner.py:398): `_overflow_from_credits` uses `ceil(unplaced_credits / cap)` only. It does not simulate offered terms or prerequisite ordering over extended semesters, so a 2학기-only course after `current_term="2026-2"` can be projected to `2027-1`, which is impossible.
  Fix: estimate overflow by rerunning the same placement algorithm on progressively extended terms until all unplaced courses fit, preserving 개설학기 and prerequisites.

- **MEDIUM [REGRESSION]** [GraduationV2.jsx:105](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105): frontend `groupsOk` uses backend `cc.group_checks`, which reflects only the backend default allocation. When the user changes 3-way overlap assignment, `primaryCr` and `fusionCr` update, but group earned/gaps do not. The UI can still report group shortage after the user moves the right group courses into 융합, or report fit after moving them out.
  Fix: recompute group totals from `cc.fusion_base` plus current `sel` overlap assignments grouped by `ov[i].group`.

- **MEDIUM [REGRESSION]** [planner.py:445](/home/carol/kmu_genai/graduation_center/v2/planner.py:445): required-course catalog fallback picks `hit[0]` on normalized-name collisions. The data explicitly has ambiguous `다학제간캡스톤디자인` in [catalog_build_report.json:27](/home/carol/kmu_genai/data/graduation/v2/catalog_build_report.json:27), while [required_names_by_year.json:166](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:166) uses that ambiguous name. This can attach the wrong code/credits/terms/prereqs.
  Fix: store course_id in `required_names_by_year` items where names are ambiguous, or refuse fallback when `len(hit) > 1` and mark manual.

- **MEDIUM [REGRESSION]** [audit_v2.py:215](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215): convergence overlap allocation is greedy by required-first and credit-desc, with no optimization for cap packing or group minimums. It can choose `6+6` under cap 12 and leave group mins impossible when `4+4+4` or a different group mix would satisfy both.
  Fix: solve overlap allocation as a small constrained search/DP: maximize primary/fusion feasibility subject to double cap, primary required preservation, and group minima.

- **MEDIUM** [risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62): risk capacity defaults to `18`, not the Article 32 cap derived from the student’s total requirement. A 136-credit program should default to 19, but API callers that do not set `max_credits_per_term` get undercounted capacity.
  Fix: use `regular_term_cap(audit.total_required)` or pass `profile` into `compute_risk`.

- **LOW** [pipeline.py:94](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:94): the report shows raw `total_earned`, while 전공 area shows convergence-adjusted effective credits. That is mathematically defensible, but unexplained and likely to look contradictory in demo cases with overlap.
  Fix: label total as “총 이수학점(원합계)” and area as “전공 인정학점(융합 배정 반영)”.

**Round-2 Checks**

- GPA `no → D` is correctly implemented at [risk.py:88](/home/carol/kmu_genai/graduation_center/v2/risk.py:88).
- `remaining_semesters=0` with a valid `current_term` now blocks with overflow at [planner.py:631](/home/carol/kmu_genai/graduation_center/v2/planner.py:631), while missing `current_term` returns `feasible=null`. Malformed truthy terms like `26-1` are still misclassified as “현재 학기 미입력”.
- Convergence `courses_view` default assignment mostly matches frontend default ordering, but the allocation is still not complete because it ignores group/cap optimization.
===== /tmp/codex_r3_7.txt =====
for n in req:
    print(n, normalize_name(n), cat['by_norm'].get(normalize_name(n), []))
PY" in /home/carol/kmu_genai
exec
/bin/bash -lc "/home/carol/exit/envs/kmu-agent/bin/python - <<'PY'
from graduation_center.v2.models_v2 import *
from graduation_center.v2.audit_v2 import compute_audit
from graduation_center.v2.planner import build_unified_candidates
# Synthetic: total gap 6, convergence gap 6. General slot should be 0 because convergence courses fill total credits too.
verified=VerifiedTranscript(confirmed_courses=[], earned_by_area={'전공':64,'기초교양':20,'핵심교양':20,'자유교양':20,'일반선택':0}, total_earned=124)
profile=RequirementProfile(program_id='ai_bigdata', department_name_ko='AI', total_credits_min=130, area_min={'전공':64,'기초교양':0,'핵심교양':0,'자유교양':0}, required_course_ids=[])
audit=compute_audit(verified, profile, convergence_program_ids=['dsci_convergence'], convergence_tracks={'dsci_convergence':'다전공'})
sel, reqs=build_unified_candidates(audit, profile, verified)
print('total_gap', audit.total_gap, 'area_gaps', [(g.area,g.gap) for g in audit.area_gaps], 'conv', [(c['name'],c['gap']) for c in audit.convergence_checks])
print('reqs', [(r['label'],r.get('need'), r.get('area')) for r in reqs])
print('selected credits', sum(x['credits'] for x in sel), [x['name_ko'] for x in sel[:10]])
PY" in /home/carol/kmu_genai
 succeeded in 108ms:
 succeeded in 109ms:
 succeeded in 482ms:
..........                                                               [100%]
10 passed in 0.26s

**Findings**

1. **HIGH [REGRESSION] General elective residual double-counts convergence and required-credit work.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:508) computes `general_need = total_gap - sum(audit.area_gaps)`, but convergence requirements are added separately at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:460) and also count toward total graduation credits. Same issue exists when total credits are short and a missing required course is added while the major area floor is already met. Result: roadmap can over-plan credits and create false overflow.  
   **Fix:** build non-general obligations first, then compute 일반선택 as `max(0, total_gap - credits_from_selected_real_courses_that_also_raise_total)`, de-duping shared courses carefully.

2. **HIGH [REGRESSION] Overflow still ignores why courses were unplaced.**  
   `_overflow_from_credits()` uses only `ceil(unplaced_credits / cap)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:398). If a remaining course is offered only in `2학기`, the overflow projection can say one extra semester ending in `2027-1`, even though the course cannot be taken until `2027-2`. This violates the roadmap domain rule: 개설학기 and 선수 must be respected when estimating 초과학기.  
   **Fix:** extend terms and re-run the same greedy/validation placement until all unplaced courses are placed, preserving offered-term, prereq, seasonal, and cap constraints. Base overflow on that simulated placement, not raw credits.

3. **HIGH [REGRESSION] Frontend group checks become stale after 3-way allocation changes.**  
   `ConvergenceBlock` recomputes `primaryCr`/`fusionCr` from `sel` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), but `groupsOk` still uses backend static `cc.group_checks` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105). If the user moves an A/B-group overlap course from `dup` to `primary` or `fusion`, the group minimum display and `fits` verdict can be wrong.  
   **Fix:** recompute dynamic group earned/gap from `cc.courses`, `ov`, and current `sel`; use that for `groupsOk`, warning text, and suggestions.

4. **MEDIUM [REGRESSION] Duplicate-recognition allocation is greedy, not cap-optimal.**  
   Backend selects overlap courses by required-first, credit-descending order and only adds when `dup_cr + credits <= cap` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215). With mixed credits, this can leave cap unused even when another subset fills it exactly. It also reports `double_recognizable = min(overlap_cr, cap)` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:163), which may exceed actual `double_used`.  
   **Fix:** use a bounded subset/knapsack pass: preserve 전공필수 priority, then maximize recognized credits under cap; expose both legal max and chosen allocation consistently.

5. **MEDIUM Required-name catalog fallback silently picks ambiguous hits and drops prereqs for name-only requireds.**  
   Missing required fallback takes `hit[0]` from `cat["by_norm"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445). The 2025 required list contains `다학제간캡스톤디자인` at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147), while the catalog has two normalized hits: required `다학제간캡스톤디자인` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:638) and non-required `다학제간캡스톤디자인+` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:780). Also, 2023 `다학제간캡스톤디자인Ⅰ/Ⅱ` names at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133) have no catalog hit, so planner emits name-only items without course_id/prereq enforcement.  
   **Fix:** required metadata should carry `course_id` and prereqs where possible. If `by_norm` has multiple hits, select `is_required` + year/grade match or mark manual instead of first-hit.

6. **MEDIUM Risk still uses an older capacity model inconsistent with the new planner.**  
   `compute_risk()` uses `gap = audit.total_gap` at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:26), default cap `18` at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62), and adds only one seasonal cap at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:66). It ignores planner overflow/unplaced reasons except downgrading blocked roadmap to C at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:95). A student with total credits met but remaining required/convergence courses impossible in remaining semesters can stay C instead of D.  
   **Fix:** pass `profile` and `plan.overflow`/unplaced status into risk; use the same `_ordered_terms` capacity model and make `remaining=0 + unmet obligations` or `extra_semesters>0` a D trigger.

7. **LOW Malformed `current_term` is treated like missing current term.**  
   `_ordered_terms()` returns `[]` both for absent and malformed terms at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:357). `run_planner()` then treats malformed truthy values like `"26-1"` with remaining semesters > 0 as “현재 학기 미입력” and returns `feasible=None` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631).  
   **Fix:** validate `current_term` in `StudentContext` with `YYYY-(1|2|S|W)` or return a distinct `bad_current_term` blocked/validation error.

**Verified OK**

`gpa_min_met == "no"` now correctly forces D in [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88). Backend convergence `group_checks` are recomputed from `fusion_courses`, and `major_effective` subtracts backend `to_fusion_total`.

**Test Note**

`/home/carol/exit/envs/kmu-agent/bin/python -m pytest tests/test_v2_pipeline.py -q` passed: `10 passed`. The default `python`/`python3` on this shell is 3.8 and is not usable for this codebase.
===== /tmp/codex_r3_8.txt =====
   136	            "1"
   137	          ]
   138	        },
   139	        {
   140	          "name": "다학제간캡스톤디자인Ⅱ",
   141	          "credits": 3,
   142	          "terms": [
   143	            "2"
   144	          ]
   145	        }
   146	      ],
   147	      "2025": [
   148	        "S-TEAM Class",
   149	        "일반물리Ⅰ",
   150	        "일반물리실험Ⅰ",
   151	        "공학기초수학",
   152	        "Python프로그래밍",
   153	        "자동차모빌리티기초",
   154	        "일반물리Ⅱ",
   155	        "일반물리실험Ⅱ",
   156	        "공학수학Ⅰ",
   157	        "정역학",
   158	        "자동차모빌리티 Adventure Design",
   159	        "기초선형대수",
   160	        "회로이론",
   161	        "확률및통계",
   162	        "동역학",
   163	        "전자회로",
   164	        "자료구조및알고리즘",
   165	        "모빌리티실험및실습",
   166	        "다학제간캡스톤디자인"
   167	      ]
   168	    }
   169	  },
   170	  "aliases": {

**Findings**
1. HIGH [REGRESSION] Frontend 3-way allocation lies after user edits. [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:97), [line 106](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:106), [line 187](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:187) keep the 3-way choice purely local and reuse backend `cc.group_checks`. If a user changes a course from `primary` to `fusion`, `fusionCr` changes but group earned/gap does not. The UI can say “그룹별 최저 미충족” after the edit actually fixes it, or “충족” after the edit breaks it. Fix: recompute group earned/gaps from `sel` and `ov.group` in `ConvergenceBlock`, or make the control a non-authoritative scenario explorer with explicit “백엔드 미반영” wording.

2. HIGH [REGRESSION] Malformed `current_term` with `remaining_semesters=0` is misclassified as a real no-remaining-semester block. `_ordered_terms()` returns `[]` both for missing/invalid term and for true zero remaining terms ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:357)). `run_planner()` then treats any truthy `current_term` plus `remaining_semesters <= 0` as blocked ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:631)). `current_term="26-1"` therefore becomes “잔여 학기 0” instead of “현재 학기 형식 오류/배치 불가 미상.” Fix: parse `current_term` into an explicit status enum; only block when parse is valid and remaining is zero.

3. HIGH Multi-convergence selection double-subtracts the same primary credits. Each selected convergence program computes overlap independently ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:136)), then `compute_audit()` sums every program’s `to_fusion_credits` and subtracts that from primary major once per program ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281)). One shared course can be assigned to fusion in two convergence checks and remove 6 credits from the primary total for one 3-credit course. Fix: do a global allocation keyed by course id/prefix across all selected convergence programs, enforce one non-primary owner, and subtract each physical course at most once.

4. MEDIUM [REGRESSION] Double-count recommendation can exceed the cap. The displayed “중복인정 신청 권장” loop appends while `acc < cap`, but never checks `acc + c.credits <= cap` ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:193)). With cap 6 and courses 4+4, it recommends 8/6 credits even though the actual allocator later enforces the cap. Fix: use the same cap-fit predicate as allocation, or return exact `alloc == "dup"` courses as the recommendation.

5. MEDIUM [REGRESSION] Greedy cap allocation is not optimal. The allocator sorts by required-first/credits-desc and accepts only if the current item fits ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215)). For caps and non-3-credit courses, large-first can underfill the double-count cap where a smaller combination would fit exactly, causing artificial primary/fusion gaps. Fix: use a small bounded knapsack per overlap set, maximizing required-course priority first, then used credits under cap, then deterministic tie-breakers.

6. MEDIUM [REGRESSION] General-choice residual still double-counts core-area shortage. `general_need` subtracts only `audit.area_gaps` from `total_gap` ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:510)), but step 5 separately adds `core_area_gaps` slots ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:499)). If broad 핵심교양 is already full, total gap is 6, and two core subareas are short by 6, planner adds 6 core credits plus 6 일반선택 credits. Fix: compute residual after all non-general selected credits that also raise total credits, not just broad area gaps.

7. MEDIUM Overflow underestimates when unplaced courses are blocked by future offering/prerequisite cadence, not raw capacity. `_overflow_from_credits()` uses `ceil(unplaced_credits / reg_cap)` only ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:398)). A 1학기-only prerequisite chain can need two spring terms, but the overflow card reports one extra semester. Fix: rerun the greedy scheduler on extended future terms until all unplaced items place, then derive extra regular semesters from the simulated placement.

8. MEDIUM Risk capacity disagrees with planner seasonal capacity. Risk adds only one seasonal 6-credit block regardless of remaining timeline ([risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62)), while `_ordered_terms()` can create every S/W between remaining regular terms ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:371)). A feasible plan using two seasonal terms can still be graded D by risk. Fix: reuse `_ordered_terms()` capacity or count seasonal terms over the actual allowed term list.

9. LOW Required metadata year fallback is inconsistent for admissions earlier than available data. Audit picks the earliest available 요람 when `year < min(avail)`; planner `_required_meta()` falls back to latest (`avail[-1]`) ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:388)). Fix: share one year-selection helper across audit/catalog/planner.

10. LOW UI total/raw vs effective major can look contradictory. The hero shows raw `total_earned` ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:553)), while area gauges show fusion-adjusted major credits from `area_gaps` ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:585)). That is mathematically defensible, but the demo will look inconsistent when total is high and 전공 is lowered. Fix: add a short “총학점은 원이수 합계, 전공은 융합 배정 차감 후” note near the gauges/hero.

**Verified OK**
- `gpa_min_met == "no"` now correctly forces D risk: [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:88).
- `project_overflow()` is not used by `run_planner()`; overflow now comes from actual unplaced credits, though the semester estimate is still too crude.
===== /tmp/codex_r3_9.txt =====
    44	    return s
    45	
    46	
    47	def normalize_code(value: str | int | None) -> str:
    48	    """교과목코드를 7자리 문자열로 정규화 (leading-zero·문자 보존).
    49	
    50	    엑셀이 '0118810'을 숫자 118810으로 읽는 경우를 7자리로 복원.
    51	    문자가 섞인 코드(예: '003290F')는 그대로 둔다.
    52	    """
    53	    if value is None:
    54	        return ""
    55	    s = str(value).strip()
    56	    if not s:
    57	        return ""
    58	    # 숫자로만 이뤄졌고 7자리 미만이면 zero-pad
    59	    if s.isdigit() and len(s) < 7:
    60	        s = s.zfill(7)
    61	    return s
640:      "name_ko": "다학제간캡스톤디자인",
641:      "name_norm": "다학제간캡스톤디자인",
782:      "name_ko": "다학제간캡스톤디자인+",
783:      "name_norm": "다학제간캡스톤디자인",

exec
/bin/bash -lc "python - <<'PY'
import json
cat=json.load(open('data/graduation/v2/catalog_mirae_mobility.json',encoding='utf-8'))
for c in cat['courses']:
 if c['name_norm']=='다학제간캡스톤디자인': print(c)
PY" in /home/carol/kmu_genai
 succeeded in 0ms:
{'course_id': '0693316', 'name_ko': '다학제간캡스톤디자인', 'name_norm': '다학제간캡스톤디자인', 'aliases': [], 'credits': 4.0, 'requirement_area': '전공', 'is_required': True, 'prerequisites': [], 'prereq_external': [], 'grade_level': 4, 'offered_terms': ['1', '2'], 'group': None, 'source': {'doc': '2025-2 교육과정 교과목코드 현황', 'dept': '미래모빌리티학과'}}
{'course_id': '7159803', 'name_ko': '다학제간캡스톤디자인+', 'name_norm': '다학제간캡스톤디자인', 'aliases': [], 'credits': 4.0, 'requirement_area': '전공', 'is_required': False, 'prerequisites': [], 'prereq_external': [], 'grade_level': 4, 'offered_terms': ['1', '2'], 'group': None, 'source': {'doc': '2025-2 교육과정 교과목코드 현황', 'dept': '미래모빌리티학과'}}

**Findings**

- HIGH [REGRESSION] [graduation_center/v2/planner.py:510](/home/carol/kmu_genai/graduation_center/v2/planner.py:510): `general_need = total_gap - area_floor_gap` ignores planned 융합전공 credits. If `total_gap=10`, area gaps are 0, and 융합 gap is 6, the planner selects 6 융합 credits plus 10 일반선택 credits, over-planning by 6. Fix: compute 일반선택 residual after all specific selected credits that count toward total, including 융합/필수/교양/전공 candidates, with de-duplication.

- HIGH [REGRESSION] [graduation_center/v2/audit_v2.py:218](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:218): duplicate-recognition allocation is greedy-fit, not optimal. It skips any course that would exceed cap and never revisits, so cases like cap 6 with credits `4,3,3` use 4 instead of optimal 6. `recommend_double_count` is worse: [audit_v2.py:194](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:194) appends before checking `acc + credits <= cap`, so recommendations can exceed the cap. Fix: use one deterministic bounded knapsack shared by allocation and recommendation, with tie-breakers for 전공필수, credits, then course_id/name.

- HIGH [REGRESSION] [graduation_center/v2/planner.py:461](/home/carol/kmu_genai/graduation_center/v2/planner.py:461): convergence group shortages are converted to one pooled `need`, then [planner.py:527](/home/carol/kmu_genai/graduation_center/v2/planner.py:527) fills by total credits only. If A/B groups are both short, the greedy selector can fill all credits from A and still leave B below minimum while reporting a roadmap. Fix: build per-group quotas first, select enough candidates for each short group, then add extra candidates only for remaining total 융합 gap.

- HIGH [known-unfixed] [graduation_center/v2/audit_v2.py:281](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281): multiple selected 융합전공s can double-subtract the same primary course from 전공. `_convergence_checks` is run independently per convergence, and `compute_audit` blindly sums each `to_fusion_credits`. Fix: introduce a global per-course allocation map across all selected convergence programs, subtract each primary course at most once, and enforce each program’s cap/group constraints against that shared allocation.

- MEDIUM [REGRESSION] [graduation_center/v2/planner.py:631](/home/carol/kmu_genai/graduation_center/v2/planner.py:631): malformed `current_term` such as `"26-1"` returns the same branch as missing current term when `remaining_semesters > 0`: “현재 학기 미입력”. That hides bad input during the demo. Fix: validate `current_term` with `^20\d{2}-(1|2|S|W)$` in `StudentContext` or return an explicit `invalid_current_term` blocked/validation error.

- MEDIUM [REGRESSION] [graduation_center/v2/planner.py:398](/home/carol/kmu_genai/graduation_center/v2/planner.py:398): `_overflow_from_credits` still estimates extra semesters by `ceil(unplaced_credits / reg_cap)`, ignoring offered-term constraints. A `2학기`-only unplaced course after the last allowed `2학기` can require waiting until the next year, but this model can project one regular term too early. Fix: simulate additional future terms through the same greedy placement until all unplaced courses fit, then derive overflow from that result.

- MEDIUM [frontend/src/components/GraduationV2.jsx:105](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105): frontend 3-way reassignment recomputes total primary/fusion credits, but `groupsOk` and shortage messages use stale backend `cc.group_checks`. After the user changes an overlap course from 융합전공 to 제1전공, the UI can still say group minimum is satisfied. Fix: recompute group earned/gap from `sel` and `ov.group` client-side, or disable interactive “fits” claims unless recomputed.

- MEDIUM [graduation_center/v2/planner.py:624](/home/carol/kmu_genai/graduation_center/v2/planner.py:624): if `reqs` is nonempty but every pool is empty or de-duped away, `selected` is empty and the planner returns “졸업요건을 모두 충족했습니다.” This is a false pass for exhausted catalogs or assignment-only convergence shortages. Fix: branch on `reqs`, not just `selected`; return blocked with `no_candidates` when obligations exist but no candidate can close them.

- HIGH environment risk: `pytest -q` fails during collection in the current workspace Python 3.8. `graduation_center/models.py:24` and `graduation_center/v2/models_v2.py:20` use `str | None` / `list[...]`, and dependencies like FastAPI are also missing. Fix: either pin `python_requires >=3.10` and document/use that interpreter for demo, or backport typing plus install requirements in the demo env.

**Verified Round-2 Items**

- GPA `gpa_min_met == "no"` now correctly forces D at [risk.py:88](/home/carol/kmu_genai/graduation_center/v2/risk.py:88).
- 전공 effective subtraction exists at [audit_v2.py:281](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:281), but is unsafe for multiple convergence programs.
- Frontend includes `group_checks` in `fits`, but only for the initial backend allocation; interactive changes are stale.
- `remaining_semesters=0` with valid `current_term` now blocks with overflow at [planner.py:633](/home/carol/kmu_genai/graduation_center/v2/planner.py:633), but malformed current terms are still misclassified.
===== /tmp/codex_r3_findings.txt =====
