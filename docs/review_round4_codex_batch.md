===== /tmp/codex_r4_0.txt =====
   595	    pending = list(items)
   596	    progress = True
   597	    while pending and progress:
   598	        progress = False
   599	        still = []
   600	        for it in pending:
   601	            r = _try_place(it)
   602	            if r is True:
   603	                progress = True
   604	            elif r is None:
   605	                still.append(it)                        # 선수 미배치 → 다음 패스
   606	            else:
   607	                unplaced.append(it)
   608	        pending = still
   609	    unplaced.extend(pending)                            # 교착(순환/충족불가) → 미배치
   610	    out = []
   611	    for lab, cap in terms:
   612	        if not bucket[lab]:
   613	            continue
   614	        courses = [RoadmapCourse(course_id=it.get("course_id", "") or "", name_ko=it["name_ko"],
   615	                                 credits=it["credits"], satisfies=it.get("satisfies", ""),
   616	                                 assignment=it.get("assignment", ""),
   617	                                 offered_terms=(it.get("offered_terms") or []) if it.get("confidence") == "catalog_verified" else [],
   618	                                 confidence=it.get("confidence", "catalog_verified"),
   619	                                 manual_check=it.get("manual", False)) for it in bucket[lab]]
   620	        out.append(RoadmapTerm(term=lab, courses=courses, term_credits=round(used[lab], 1),
   621	                               term_risk="medium" if used[lab] > cap - 3 else "low"))
   622	    assumptions = []
   623	    if any(it.get("manual") for it in selected):
   624	        assumptions.append("이름기준·교양 슬롯 과목은 개설학기·학점을 수강신청 전 확인하세요.")
   625	    return out, assumptions, unplaced

**Findings**

1. **HIGH [REGRESSION] Required fallback can falsely clear a 필수 course by same name but different code.**  
[audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:338) builds `confirmed_full`, but then [audit_v2.py:340](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:340) accepts a required course as taken if the catalog required name appears anywhere in `confirmed_norm2`. That defeats the 7-digit-code fix whenever another department has the same name. This is reachable: `required_names_by_year.json` only has `mirae_mobility`, so `ai_bigdata` uses fallback; AI requires `0365007 S-TEAM Class` at [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:99), while 미래모빌리티 has different-code `1621601 S-TEAM Class` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:114).  
**Fix:** name fallback must be constrained. Only accept name fallback when transcript code is absent, or when an explicit equivalence/alias map declares the code drift. If a transcript has a nonmatching 7-digit code, do not satisfy the required course by name alone.

2. **HIGH [REGRESSION] `pool_exhausted` is still incomplete: duplicate-name candidates are counted as quota even when they are different courses/requirements.**  
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:525) dedupes by normalized name, and [planner.py:535](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) increments `acc` for a later requirement if the name was already selected. That treats “same name” as “same course satisfies this quota.” Real data disproves that: AI has `0155708 선형대수` at [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:323), while DSCI has `0155707 선형대수` at [catalog_dsci_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_dsci_convergence.json:88). Since 융합 requirements are priority 2 and 전공 gap is priority 3, a DSCI 선형대수 can suppress the AI-major 선형대수 and still count toward the major quota. `run_planner` then only checks caps/unplaced/pool_exhausted at [planner.py:674](/home/carol/kmu_genai/graduation_center/v2/planner.py:674), not actual gap closure.  
**Fix:** dedupe by stable identity, preferably `course_id`, not name. Only credit a selected item into another quota when the `course_id` matches and a policy permits double recognition; track remaining duplicate cap for shared future courses.

3. **HIGH Prerequisites are still not enforced when the prerequisite is neither completed nor selected.**  
`plan_greedy()` only defers a course if its prerequisite is in the selected set but not yet placed: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:568)-[planner.py:572]. If the prerequisite is missing entirely, placement proceeds at [planner.py:588](/home/carol/kmu_genai/graduation_center/v2/planner.py:588). Real catalog prerequisites exist, e.g. `수리통계` requires `0029011` at [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:261), and `공학수학Ⅰ` requires `0533411` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:181).  
**Fix:** if any prerequisite is not completed and not scheduled earlier, either auto-add the prerequisite candidate before the dependent course or mark the dependent course `unplaced`/blocked with `prereq_unmet`.

4. **LOW [REGRESSION] Cap clamp is fixed in the deterministic main path, but stale legacy planner paths still violate it.**  
Main `run_planner()` clamps with `min(user, legal)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:640), and risk does the same at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:63). But `build_planning_context()` still sends raw `context.max_credits_per_term` at [planner.py:136](/home/carol/kmu_genai/graduation_center/v2/planner.py:136), and `validate_roadmap()` trusts that raw cap through `ctx["caps"]` at [planner.py:277](/home/carol/kmu_genai/graduation_center/v2/planner.py:277). This is mostly dead/legacy today, but it is a trap if the LLM planner path is re-enabled.  
**Fix:** centralize cap calculation in one helper and use it in `run_planner`, `build_planning_context`, `validate_roadmap`, and overflow helpers.

**Verified OK**

Round-3 fixes for group coverage separation, 전공필수 fusion-only disabling, 일반선택 residual, Mirae 핵심교양 17, and frontend group display are directionally correct in the inspected main path. I do **not** see the feared general residual “과차감” as the primary bug; future 전공/융합 courses do add to total graduation credits once, so subtracting selected credits from `audit.total_gap` is conceptually right. The remaining failure is that the selected set itself can be wrong due to name-based quota reuse.

I could not run pytest cleanly: default `python`/`python3` is 3.8 and fails on `str | None`; `python3.10` exists but has no `pytest`/deps installed.
===== /tmp/codex_r4_1.txt =====
0910501 인공지능수학
1566902 유레카프로젝트
7188901 AI빅데이터프로그래밍Ⅰ
7189001 AI빅데이터프로그래밍Ⅱ
0365008 사제동행세미나
mirae_mobility
0118810 일반물리실험I
0119410 일반물리I
0533411 공학기초수학
0547210 Python프로그래밍
0733010 자동차모빌리티기초
1621601 S-TEAM Class
0053010 정역학
0533010 공학수학Ⅰ
0533710 일반물리II
0533910 일반물리실험II
0590915 자동차모빌리티 Adventure Design
0056110 회로이론
1620901 기초선형대수
0579306 동역학
0624509 확률및통계
1027102 전자회로
1152803 자료구조및알고리즘
1621102 모빌리티실험및실습
0693316 다학제간캡스톤디자인

**Findings**

1. **HIGH [REGRESSION] Group quota can be falsely satisfied by wrong-group courses.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463) computes one scalar `need`, then [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:475) appends all remaining untaken courses after the short-group-first pass. The later selection loop only checks scalar `acc` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:530). If A그룹 is short but only B그룹 candidates remain, B그룹 courses can fill `need`, no `pool_exhausted` is raised, and the roadmap can become feasible while A그룹 is still short.  
   Fix: make each group gap its own quota requirement with a pool restricted to that group. If `acc_g < ggap`, record `group_pool_exhausted`; only use non-short-group/rest courses for the remaining total-credit gap after all group quotas are satisfied.

2. **HIGH [REGRESSION] `seen` duplicate crediting can hide an unfilled requirement.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) treats any globally-seen normalized name as quota credit for the current requirement. That is not valid across unrelated requirements. Example: a shared course selected earlier as `융합전공` can later be counted toward `전공 부족` without changing its assignment to 제1전공/중복인정. This directly matches the requested unfillable/quota concern: another requirement’s selected course can falsely satisfy this requirement.  
   Fix: track selected courses by `course_id` plus legal satisfaction set. Only increment `acc` for a seen item if the previous selection is legally allowed to satisfy the current requirement, and update/display that dual satisfaction. Otherwise skip without credit or select another eligible course.

3. **HIGH [REGRESSION] `pool_exhausted` is ignored when `current_term` is missing.**  
   `build_unified_candidates()` returns `unfillable` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:634), but if `_ordered_terms()` returns no terms, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:656) returns before `pool_exhausted` errors are added at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:682). A request with partial candidates plus exhausted quota becomes `generated, feasible=None` instead of `blocked`.  
   Fix: handle `unfillable` before the `not terms` branch, or make that branch return `blocked` when `unfillable` is non-empty.

4. **HIGH [REGRESSION] 7-digit fallback still has name-only false positives.**  
   Code exactness was improved, but name fallback still treats distinct 7-digit courses as equivalent. [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:165) name-matches even when the transcript has a nonmatching code; [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:340) lets required courses be satisfied by catalog name; [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:494) excludes major-pool courses by name. The shipped catalogs contain collisions: `S-TEAM Class` is `0365007` vs `1621601`, `선형대수` is `0155707` vs `0155708`, and `객체지향프로그래밍` is `0156812` vs `1152701`.  
   Fix: if a transcript row has a code, do not name-match it to a different catalog code unless an explicit equivalence/alias table maps those exact IDs. Use name fallback only for code-missing rows or curated same-course aliases.

5. **MEDIUM Inconsistent 요람 fallback for years before the first data year.**  
   Required names use earliest available year when admission year is too old at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42), but area requirements return `None` at [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:113), falling back to generic 2025 data. Planner metadata separately picks latest at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:388). A 2022 `mirae_mobility` student can get 2023 required names, 2025 area minima, and 2025/default planner metadata.  
   Fix: centralize year resolution and use the same policy everywhere: exact year, else nearest lower, else earliest available.

6. **MEDIUM Frontend gives no course suggestions for group-only convergence shortages.**  
   [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:115) computes short groups, but suggestions are rendered only when `fusionGap > 0` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117). If total 융합 credits are enough but A/B group minimum is short, the UI warns but does not suggest the missing-group courses.  
   Fix: compute suggestion need as `max(fusionGap, sum(group gaps))`, and render group-specific suggestions even when total gap is zero.

**Verified OK, With Above Caveats**

Round-3 fixes for coverage-based `group_checks`, 전공필수 융합전용 금지, general residual after selection, Mirae 핵심교양 17, and the frontend 전공 게이지 note are present in the expected places. The remaining blockers are mostly in quota enforcement and code/name equivalence, not in the basic display plumbing.
===== /tmp/codex_r4_2.txt =====
/bin/bash -lc "python - <<'PY'
import json
p='data/graduation/graduation_requirements.json'
d=json.load(open(p))['departments']
for k,v in d.items():
 if '미래모빌리티' in k or '자동차융합대학' in k:
  print(k, v.get('교양'), v.get('핵심교양_영역최저'), v.get('졸업_최저합계'))
PY" in /home/carol/kmu_genai
 succeeded in 0ms:
자동차융합대학_자동차IT융합학과 {'기초교양': 7, '핵심교양': 15, '자유교양': 2, '소계': 24} None 136
자동차융합대학_미래모빌리티학과 {'기초교양': 7, '핵심교양': 15, '자유교양': 2, '소계': 24} {'소통': 5} 136

exec
/bin/bash -lc "python - <<'PY'
import json, pathlib, collections
for fn in ['catalog_dsci_convergence.json','catalog_mobility_data_convergence.json']:
 d=json.load(open('data/graduation/v2/'+fn)); print(fn)
 sums=collections.defaultdict(float); counts=collections.defaultdict(int)
 for c in d['courses']:
  sums[c.get('group')]+=c['credits']; counts[c.get('group')]+=1
 print(sums, counts)
PY" in /home/carol/kmu_genai
 succeeded in 0ms:
catalog_dsci_convergence.json
defaultdict(<class 'float'>, {'A그룹': 36.0, 'B그룹': 33.0}) defaultdict(<class 'int'>, {'A그룹': 12, 'B그룹': 11})
catalog_mobility_data_convergence.json
defaultdict(<class 'float'>, {'B그룹': 39.0, 'A그룹': 39.0}) defaultdict(<class 'int'>, {'B그룹': 13, 'A그룹': 13})

**Findings**

HIGH [REGRESSION] Future 전공필수 overlap courses can still be planned as `융합전공` and counted toward another quota without legal duplicate allocation.
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:467) builds convergence candidates from every untaken convergence course, then [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:477) hard-codes `assignment: "융합전공"` while dropping `overlap` / `primary_required` from the backend course view. Worse, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) counts a globally-seen course toward a later quota just because the name matches. So a missing 제1전공 전공필수 that also appears in a convergence catalog can be selected as 필수/전공 first, silently counted for 융합 later, and never checked against remaining duplicate cap or the “전공필수는 융합 전용 불가” rule.
Fix: carry `overlap`, `primary_required`, `conv_type`, and remaining duplicate cap into planner candidates. A seen duplicate should satisfy the second requirement only through an explicit legal `중복인정` allocation; if cap is exhausted or cap=0, it must not count for 융합. Never emit `assignment: "융합전공"` for primary-required overlap.

HIGH [REGRESSION] Real 5-digit prefix collisions still falsely mark different courses as taken for convergence.
[audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:149) keys convergence catalogs by `course_id[:5]`, and [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:152) treats any transcript course with that prefix as designated. This collides in current data: 미래모빌리티 `0156810` C프로그래밍 at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:154) and 데이터사이언스융합 `0156812` 객체지향프로그래밍 at [catalog_dsci_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_dsci_convergence.json:46). A student who took C프로그래밍 can be credited as having taken 객체지향프로그래밍 in the convergence audit.
Fix: use exact 7-character course IDs for designated/taken/overlap matching. If KMU has known equivalent-renumbered courses, add an explicit equivalence table keyed by full code and name, not prefix truncation.

MEDIUM [REGRESSION] Group-shortage recommendation in the frontend disappears when total fusion credits are enough.
The UI detects group failure via backend `group_checks` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:108), but suggestions are only generated when `fusionGap > 0` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117). If total 융합 36/18 is satisfied but A/B group minimum is short, the UI says “그룹별 최저 미충족” at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) but shows no “which courses fix it” scenario.
Fix: compute suggestion need as group gaps first, independent of total `fusionGap`; recommend untaken courses from `shortGroups` until each group gap is closed.

MEDIUM Group pool exhaustion is global, not per-group.
The planner prioritizes group gaps at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463), but it records `unfillable` only if global `acc < r["need"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:539). If one deficient group has no usable remaining candidates but other groups can fill the total need, the roadmap can avoid `pool_exhausted` even though the group minimum remains impossible.
Fix: track `acc_g` per deficient group and append `pool_exhausted` for each group whose pool cannot cover its own gap. Then separately fill remaining total-gap candidates.

LOW Required-name checks can be falsely satisfied by same-name non-major courses.
When year-specific required names exist, [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:322) builds `confirmed_norm` from all confirmed courses, regardless of area or whether the course matched the primary catalog. [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:325) then marks a required major course taken by name alone. A 타과/일반선택 course with the same name can clear a 전공필수.
Fix: for required names, count only confirmed courses that are primary-program matched or at least `requirement_area == "전공"` and not `aggregate_only`; use full-code equivalence when available.

**Round-3 Status**

Fixes 1, 3, 7, 8, and 9 look directionally implemented in the reviewed paths. Fix 2 is incomplete in the planner path. Fixes 4 and 5 are incomplete for per-group pool exhaustion and frontend group-only suggestions.

I could not run the v2 tests cleanly in this workspace: the default Python has deps but is 3.8, while `/usr/bin/python3.10` lacks `pydantic`.
===== /tmp/codex_r4_3.txt =====
   122	        {
   123	          "name_ko": "소통과토론",
   124	          "name_norm": "소통과토론",
   125	          "credits": 3
   126	        },
   127	        {
   128	          "name_ko": "시민사회와경제",
   129	          "name_norm": "시민사회와경제",
   130	          "credits": 3
   131	        },
   132	        {
   133	          "name_ko": "시민사회의법과소통",
   134	          "name_norm": "시민사회의법과소통",
   135	          "credits": 3
   136	        },
   137	        {
   138	          "name_ko": "정치와공론",
   139	          "name_norm": "정치와공론",
   140	          "credits": 3

**Findings**

1. **HIGH — test/demo command is broken in this workspace**
   [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24), [requirements.txt](/home/carol/kmu_genai/requirements.txt:1)  
   `pytest tests/test_v2_pipeline.py -q` fails during collection under the repo’s current `python` 3.8.5 because annotations like `str | None` are evaluated by Pydantic without `eval_type_backport`. The documented commands do not declare Python >=3.10.  
   Fix: pin/declare Python `>=3.10` for the demo environment, or replace PEP 604 annotations / add `eval_type_backport`.

2. **HIGH [REGRESSION] — `seen` quota accounting can falsely satisfy a different requirement**
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535)  
   When a course name is already selected, the later requirement blindly does `acc += it["credits"]`. That is only valid when the same selected course legally satisfies the later requirement. It is not generally valid across 융합전공, 제1전공, group quota, and duplicate-recognition caps. A course selected as `"융합전공"` can be counted toward a later 전공 quota just because the name matches.  
   Fix: track selected course applicability explicitly, e.g. `{course_id, counts_for: {"전공": 3, "융합:pid": 3, "group:A": 3}}`, and only increment `acc` for the current requirement if that exact requirement is covered under cap/allocation rules.

3. **HIGH [REGRESSION] — group quota pool ordering is not quota enforcement**
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:530)  
   The pool is ordered by deficient groups, but the selector stops on one scalar `acc >= need`. If A and B are both short and the first A course overshoots the numeric need, B can be skipped while the planner reports success. Current catalogs are all 3-credit, but the logic is still wrong for changed-credit/history/import cases.  
   Fix: select until both conditions hold: total need closed and every deficient group’s remaining quota is closed. Use per-group counters, not just sorted pool order.

4. **MEDIUM — group-only convergence shortage is hidden in frontend recommendations**
   [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117), [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:672)  
   The UI only builds `suggest` when `fusionGap > 0`, and roadmap “남은 요건” only adds convergence when `cc.gap > 0`. If total 융합 credits are enough but one group is short, the UI warns in text but gives no concrete recommended untaken group courses and omits the group shortage from the roadmap chips.  
   Fix: drive suggestions and remaining chips from `max(cc.gap, sum(group gaps))`, prioritizing deficient groups.

5. **MEDIUM — risk understates simultaneous group shortages**
   [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:80)  
   `eff_gap = max(cc.gap, *(group gaps))` uses the largest single group gap, not the sum. Two groups short 6+6 are treated like 6, while the planner correctly treats them closer to 12 credits of obligation.  
   Fix: use `max(cc.gap, sum(gc["gap"] for group_short))` to align risk with planner need.

6. **MEDIUM — risk capacity still disagrees with planner seasonal capacity**
   [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:65), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:367)  
   Planner adds every allowed seasonal term between remaining regular terms; risk adds `SEASONAL_TERM_CAP` once. With `remaining_semesters=2`, planner may use two seasonal terms, while risk only counts one, causing possible “D risk” despite a feasible roadmap.  
   Fix: compute risk capacity from the same `_ordered_terms()` term list or a shared capacity helper.

**Round-3 Verification Notes**

The obvious fixes are present for coverage-based `group_checks`, 전공필수 fusion disable, post-selection general residual, 7-digit fallback, Mirae 핵심교양 17, cap clamp in the live planner/risk path, and overflow/opening-term notes. The incomplete fixes are the quota selection/enforcement pieces above.
===== /tmp/codex_r4_4.txt =====
   360	        return []
   361	    try:
   362	        y, s = context.current_term.split("-"); y = int(y); so = {"1": 1, "S": 2, "2": 3, "W": 4}[s]
   363	    except Exception:
   364	        return []
   365	    label = {1: "1", 2: "S", 3: "2", 4: "W"}
   366	    out, reg, steps, first = [], 0, 0, True
   367	    while reg < context.remaining_semesters and steps < 40:
   368	        steps += 1; so += 1
   369	        if so > 4:
   370	            so = 1; y += 1
   371	        lab = f"{y}-{label[so]}"
   372	        if so in (1, 3):
   373	            cap = reg_cap + (PREV_GPA_BONUS if (first and context.prev_term_gpa_ge_375) else 0.0)
   374	            out.append([lab, cap]); reg += 1; first = False
   375	        elif context.seasonal_semester_allowed:
   376	            out.append([lab, SEASONAL_TERM_CAP])
   377	    return out
   378	
   379	
   380	def _required_meta(program_id: str, year: int | None) -> dict:
   381	    """학번 요람 필수 과목의 학점·개설학기 메타 {정규화이름: {credits, terms}}."""
   382	    import json
   383	    p = V2_DIR / "required_names_by_year.json"
   384	    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
   385	    if not by_year:
   386	        return {}
   387	    avail = sorted(int(y) for y in by_year)
   388	    pick = year if (year and str(year) in by_year) else (

**HIGH [REGRESSION]** Group-quota exhaustion can be hidden by other groups.  
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463) builds a shortage-group-first pool, but [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:530) uses one global `acc` for the whole requirement. If A그룹 is short 6 credits but only 3 A credits remain, the next B/기타 course can push `acc >= need`, so no `pool_exhausted` is emitted even though A그룹 remains impossible.  
Fix: model each deficient group as its own requirement with `pool` limited to that group, or track `group_acc` and emit `pool_exhausted` per group before letting non-shortage courses satisfy total residual.

**HIGH [REGRESSION]** Name fallback can falsely satisfy required courses with a different 7-digit code.  
The fallback in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:338) accepts a required course if the required catalog name appears in `confirmed_norm2`, even when the confirmed `course_id` is different. This is not hypothetical: AI has `0365007 S-TEAM Class` at [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:98), while 미래모빌리티 has `1621601 S-TEAM Class` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:114). Same issue exists for `사제동행세미나` with `0365008` vs `1621602`.  
Fix: only allow name fallback when raw code is absent/malformed or when the code is proven an alias/section variant of the same catalog course. Otherwise mark ambiguous/manual, not fulfilled.

**MEDIUM [REGRESSION]** The matching pipeline itself still lets cross-department same-name courses become the selected major’s course.  
[match_course](/home/carol/kmu_genai/graduation_center/v2/catalog.py:166) does unique name matching inside the selected program after code mismatch, and [verification.py](/home/carol/kmu_genai/graduation_center/v2/verification.py:72) preserves the raw mismatched code while using the matched program area. Result: a raw `1621601 / S-TEAM Class` uploaded for `ai_bigdata` is classified as AI 전공 by name, while the stored `course_id` remains `1621601`.  
Fix: if raw code exists and is not in the selected catalog, do not promote by name to `matched` unless the code is an approved equivalent; use `aggregate_only`/manual confirmation.

**MEDIUM [REGRESSION]** Duplicate selected courses are allowed to satisfy later quotas without checking whether they legally satisfy that requirement.  
In [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535), `key in seen` adds credits to `acc` for a later pool solely by normalized name. That can be valid for one shared course, but it ignores area, course_id, group, and future double-recognition cap. It can make a 융합 quota look filled by a course selected earlier as 필수지정/전공, without recording `assignment`, cap use, or group fulfillment.  
Fix: de-duplicate by a structured key and attach the same planned course to all satisfied requirements only after checking code equivalence, group, and double-recognition cap. Otherwise keep both requirements open.

**MEDIUM** Group-only shortage gets no frontend recommendation.  
[GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117) only builds `suggest` when `fusionGap > 0`. If total 융합 credits are enough but `group_checks` has a gap, the UI warns at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) but shows no concrete courses.  
Fix: also suggest when `shortGroups.size > 0`, selecting untaken courses from each deficient group by that group’s remaining gap.

**LOW** Overflow semester estimate ignores the legal +3 GPA bonus.  
Actual placement correctly adds the first regular-term bonus at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:373), and risk capacity adds it at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:66). But overflow uses `ceil(unplaced_credits / reg_cap)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405), so 20 unplaced credits with a 18-credit cap and `prev_term_gpa_ge_375=True` is reported as 2 extra semesters even though 21 credits are legally possible in the first next regular term.  
Fix: compute overflow with first-extra-term capacity `reg_cap + PREV_GPA_BONUS` when applicable, then base cap after that.

Verified as correct or mostly correct: backend group coverage is restored in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:243), 전공필수 fusion-only is blocked in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:222) and [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:188), and general residual is computed after selected candidates in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:542). I could not run Python probes/tests because the local default Python is 3.8 and the repo imports use 3.10+ type syntax.
===== /tmp/codex_r4_5.txt =====
   290	  const toggleConv = (id) => setCtx((c) => {
   291	    const on = c.convergence_program_ids.includes(id);
   292	    const ids = on ? c.convergence_program_ids.filter((x) => x !== id) : [...c.convergence_program_ids, id];
   293	    const tracks = { ...c.convergence_tracks };
   294	    if (on) delete tracks[id]; else tracks[id] = tracks[id] || "다전공";
   295	    return { ...c, convergence_program_ids: ids, convergence_tracks: tracks };
   296	  });
   297	  const setConvTrack = (id, track) => setCtx((c) => ({ ...c, convergence_tracks: { ...c.convergence_tracks, [id]: track } }));
   298	
   299	  const runVerify = async () => {
   300	    if (!files.length) { setError("수강내역 엑셀(.xls/.xlsx)을 업로드하세요."); return; }
   301	    setBusy("verify"); setError(""); setAudit(null);
   302	    try {
   303	      const form = new FormData();
   304	      files.forEach((f) => form.append("files", f));
   305	      form.append("context", JSON.stringify(contextPayload()));
   306	      const r = await fetch(`${apiBase}/graduation/v2/verify`, { method: "POST", body: form });
   307	      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
   308	      const d = await r.json();
   309	      setVerify(d); setTable(d.verification_table);
   310	    } catch (e) { setError(String(e.message || e)); }

**Findings**

1. **HIGH [REGRESSION] Group quota can be “filled” by the wrong group after pool exhaustion.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463) builds a group-priority pool, but after a short group lacks enough untaken courses, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:475) appends all other groups and the scalar quota loop at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:530) counts them toward the same `need`. Result: A그룹 gap 6 with only 3 A credits left plus B courses can avoid `pool_exhausted` even though A remains impossible.  
   Fix: select and validate per-group quotas separately. If `acc_g < ggap`, emit `pool_exhausted` for that group; only after group quotas are satisfied should non-short-group courses fill total fusion gap.

2. **HIGH Remaining multi-convergence bug: same physical overlap can be subtracted from 전공 multiple times.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:285) sums `to_fusion_credits` across all convergence checks and subtracts the sum from primary major credits. The frontend permits multiple convergence majors at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:290). If the same AI빅데이터 course is allocated to fusion in both `dsci_convergence` and `mobility_data_convergence`, the first major loses it twice. I reproduced with all AI catalog courses taken: each convergence check produced `to_fusion=27`, so 전공 was reduced by `54` even though the overlapped physical courses are largely the same.  
   Fix: global allocation over physical course IDs/prefixes. Subtract each course from the primary major at most once, or explicitly block/ask for manual handling when the same course is claimed by multiple convergence programs.

3. **MEDIUM [REGRESSION] `seen` quota crediting assumes cross-requirement duplicate names always satisfy the later requirement.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) increments `acc` when a course name was already selected by an earlier requirement. That can hide `unfillable` even when the earlier selection does not actually satisfy the later convergence requirement because assignment/cap/group constraints differ. This is not hypothetical: 미래모빌리티 필수지정 includes `Python프로그래밍` etc. in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:152), and the same names are convergence A-group courses in [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:46).  
   Fix: de-dupe by a structured candidate ID plus a set of satisfied requirement IDs. A selected course can contribute to another quota only after checking that its assignment is legal for that requirement.

4. **MEDIUM [REGRESSION] Overflow estimate is inconsistent with the legal +3 GPA bonus model.**  
   `_ordered_terms()` correctly adds `PREV_GPA_BONUS` to the first regular term at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:373), and risk capacity also adds it at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:66). But `_overflow_from_credits()` uses `ceil(unplaced / reg_cap)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405), dropping the first-extra-term +3. With `remaining_semesters=0`, `prev_term_gpa_ge_375=True`, `reg_cap=18`, `unplaced=20`, it reports 2 extra semesters even though the next regular term should allow 21.  
   Fix: share one term-capacity iterator for current and overflow terms, including legal cap, first eligible +3, seasonal policy, and offered-term constraints.

5. **MEDIUM Frontend hides the added-course scenario for pure group shortages.**  
   [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117) only builds `suggest` when `fusionGap > 0`. If total fusion credits are enough but `group_checks` has a gap, the UI shows “그룹별 최저 미충족” at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) but no course scenario at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:150).  
   Fix: compute `suggestNeed = max(fusionGap, sum(group gaps))`; for group gaps, select from each short group first and show pool exhaustion if no candidates exist.

6. **LOW Stale non-live planner path still exposes unclamped caps.**  
   The live `run_planner()` clamps at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:640), but `build_planning_context()` still uses raw `context.max_credits_per_term` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:136), and `project_overflow()` does the same at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:76). Grep shows these are not used by `run_audit`, but tests and any re-enabled LLM path can regress.  
   Fix: delete/deprecate the dead path or route both through the same `legal_regular_cap(context, profile)` helper.

**Verified Round-3 Fixes**

The listed fixes are mostly present: group checks are coverage-based at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:243), 전공필수 fusion-only is blocked backend/frontend, general residual is post-selection, Mirae 핵심교양 17 is in [requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:11), and the live planner clamps regular caps before `_ordered_terms()`.

**Test Note**

Default `python` is 3.8.5 and `pytest` fails collection on `str | None` annotations. Using `/home/carol/exit/envs/kmu-agent/bin/python` 3.11, `tests/test_v2_pipeline.py` passes: `10 passed`. Pin Python 3.10+ for demo/CI or the README `pytest` command is misleading.
===== /tmp/codex_r4_6.txt =====
/bin/bash -lc 'python3 --version && command -v python3.11 || true && command -v python3.10 || true' in /home/carol/kmu_genai
 succeeded in 0ms:
Python 3.8.5
/usr/bin/python3.10

There is a Python 3.10 binary available, so I’m using that for the behavioral spot-check instead of the default interpreter.
exec
/bin/bash -lc "python3.10 - <<'PY'
from graduation_center.v2.audit_v2 import _convergence_checks
from graduation_center.v2.models_v2 import VerifiedTranscript, VerifiedCourse
vt=VerifiedTranscript(confirmed_courses=[VerifiedCourse(course_id='0156810', name_ko='C프로그래밍', credits=3, requirement_area='전공')], earned_by_area={'전공':3}, total_earned=3)
cc=_convergence_checks(vt, ['dsci_convergence'], {'dsci_convergence':'다전공'}, 'mirae_mobility', primary_major_required=62, primary_major_earned=3)[0]
row=[c for c in cc['courses'] if c['course_id']=='0156812'][0]
print({'designated_total': cc['designated_total'], 'dsci_0156812_taken': row['taken'], 'earned': cc['earned'], 'gap': cc['gap']})
PY" in /home/carol/kmu_genai
 exited 1 in 0ms:
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/carol/kmu_genai/graduation_center/__init__.py", line 3, in <module>
    from graduation_center.service import GraduationCenterService
  File "/home/carol/kmu_genai/graduation_center/service.py", line 12, in <module>
    from graduation_center.models import GraduationAnalysisResponse, TranscriptSummary
  File "/home/carol/kmu_genai/graduation_center/models.py", line 7, in <module>
    from pydantic import BaseModel, Field
ModuleNotFoundError: No module named 'pydantic'

**Findings**

1. **HIGH [REGRESSION] 7자리 충돌 수정이 융합 판정에는 적용되지 않음.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:149) builds convergence groups by `course_id[:5]`, and [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:152) treats any transcript course with that prefix as designated/taken. Current data has real prefix collisions: 미래모빌리티 `0156810 C프로그래밍` [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:154) vs 데이터사이언스융합 `0156812 객체지향프로그래밍` [catalog_dsci_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_dsci_convergence.json:46). A student who took C프로그래밍 can be credited as having taken the DS 융합 객체지향 course.  
   **Fix:** use exact 7-digit IDs for convergence designated/taken/overlap/group mapping. Only use name/alias fallback through an explicit equivalence table, never prefix.

2. **HIGH [REGRESSION] 필수과목 name fallback can falsely satisfy major-required courses with any same-name course.**  
   The required-name path checks `confirmed_norm` across all confirmed courses, with no primary-major/code/area constraint [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:322), [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:327). The 7-digit fallback also accepts catalog-name equality against all confirmed names [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:338). That violates “전공=해당전공 과목만”; e.g. AI빅데이터 `경영통계` is 전공필수 [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:14), but any unrelated confirmed `경영통계` can clear it. Planner then also excludes major-pool candidates by name globally [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:490).  
   **Fix:** required completion should match exact primary catalog code, or an explicit alias/equivalence entry. If falling back by name, require primary-major matched course or at least `requirement_area == "전공"` and non-aggregate provenance.

3. **HIGH [REGRESSION] `seen` de-dupe can mark a later requirement filled by a course that cannot legally fill it.**  
   In unified candidate selection, a duplicate name increments the later requirement quota without checking allocation, duplicate cap, track type, or assignment [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:523), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535). This can hide `pool_exhausted`: a 필수지정 course selected first can “pay” a 융합/연계 quota even when cap is exhausted, 연계 부전공 cap is 0, or the selected roadmap item is only labeled `필수지정`.  
   **Fix:** de-dupe by physical course ID plus explicit `satisfies[]`/assignment metadata. Only count an already-selected course toward the later quota after legality checks; otherwise keep selecting from the pool or emit `pool_exhausted`.

4. **HIGH multi-convergence still double-subtracts primary credits.**  
   Each convergence program independently treats other programs as overlap [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137), then `compute_audit` sums all `to_fusion_credits` and subtracts from the primary major [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:288). If the same primary course overlaps two selected convergence programs, it can be assigned away twice. The UI allows multiple convergence selections [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:290).  
   **Fix:** create one global per-course allocation across all selected convergence programs, or at minimum de-duplicate `to_fusion` subtraction by exact course ID.

5. **MEDIUM [REGRESSION] group-coverage shortage is still confusing/under-recommended in the frontend.**  
   Backend planner now triggers on `max(cc.gap, sum(group_gaps))` [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463), but frontend suggestions are gated only by total `fusionGap > 0` [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:114). If total 융합 credits are enough but one group is short, the card warns at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) but shows no “졸업 가능 시나리오”; the remaining chips also omit group-only shortages because they only check `cc.gap > 0` [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673).  
   **Fix:** compute frontend `suggestNeed = max(fusionGap, sum(group gaps))`, always prioritize short-group courses, and add group gaps to the “남은 요건” chips. Label group checks explicitly as “이수 커버리지 기준” because total 인정 uses allocation/cap.

6. **MEDIUM overflow extra-semester math ignores the +3 성적우수 bonus in zero-remaining cases.**  
   `_ordered_terms` correctly adds the bonus to the first regular term [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:373), but `_overflow_from_credits` divides unplaced credits by base `reg_cap` only [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405). With remaining semesters 0, cap 19, prev GPA bonus true, 20 credits should fit in one next regular term at 22 credits; current overflow reports 2 extra terms.  
   **Fix:** compute extra-term capacity with the same helper as `_ordered_terms`, including the first-term bonus when it has not already been consumed.

7. **LOW [REGRESSION] 핵심교양 17 is present in data, but not actually the single source of truth.**  
   `requirements_by_year.json` has 미래모빌리티 핵심교양 17 [requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:11), but `compute_audit` recomputes the total from gen-ed areas plus `graduation_requirements.json` overrides [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:291), [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:145). It happens to equal 17 today because `소통: 5` exists, but the “single source” claim is false.  
   **Fix:** carry year-specific core area minima in `RequirementProfile`, or trust `profile.area_min["핵심교양"]` as the category total while deriving per-area display from the same year profile.
===== /tmp/codex_r4_7.txt =====
   122	    elif plan.status == "blocked":
   123	        L.append(f"- 실현 가능한 계획 없음: {plan.blocked_reason}  · {plan.relaxation_hint or ''}")
   124	    elif not plan.terms:
   125	        L.append(f"- {plan.why_this_plan}")
   126	    else:
   127	        for t in plan.terms:
   128	            courses = ", ".join(f"{c.name_ko}({c.credits:.0f})" for c in t.courses)
   129	            L.append(f"- {t.term}: {courses}")
   130	        if plan.why_this_plan:
   131	            L.append(f"  - 왜 이 계획: {plan.why_this_plan}")
   132	    if plan.overflow:
   133	        o = plan.overflow
   134	        L += ["", "## ⚠️ 초과학기 예상 시나리오",
   135	              f"- 잔여 {o.remaining_semesters}학기로는 부족 {o.shortfall_credits:.0f}학점을 채울 수 없습니다."
   136	              f" (학기당 최대 {o.per_term_credit_cap:.0f}학점)",
   137	              f"- 졸업까지 최소 **{o.total_semesters_needed}학기**(초과학기 **{o.extra_semesters}학기**) 필요"
   138	              + (f" · 예상 졸업: **{o.projected_graduation_term}**" if o.projected_graduation_term else "")]
   139	    return "\n".join(L)

**Findings**
1. **HIGH [REGRESSION] 그룹 quota 보장 still fails in candidate selection.**  
   [planner.py:463-475](/home/carol/kmu_genai/graduation_center/v2/planner.py:463) reserves 부족 그룹 courses, but [planner.py:530-532](/home/carol/kmu_genai/graduation_center/v2/planner.py:530) stops on one global `acc >= need`. If group A has a 9-credit course for a 6-credit gap and group B needs 6, `need=12` can select A9+B3 and stop, leaving B short.  
   **Fix:** select quota-reserved courses per group first and mark them mandatory; only after every group gap is met should global total-gap filling run.

2. **HIGH [REGRESSION] Duplicate `seen` credit can falsely satisfy another requirement.**  
   [planner.py:535-536](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) adds credits to a later requirement when the same normalized name was already selected. That is only valid when the same physical course is legally allowed to satisfy both constraints. Here convergence candidates are assigned `"융합전공"` at [planner.py:476-479](/home/carol/kmu_genai/graduation_center/v2/planner.py:476), but the later major requirement can still be credited by name. This violates “한도초과 겹침 한쪽만” and can hide `pool_exhausted`.  
   **Fix:** dedupe by full `course_id`, and only cross-credit when an explicit allocation says `dup` and cap remains.

3. **HIGH Multiple convergence tracks can double-subtract the same course from primary major.**  
   [audit_v2.py:285-289](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:285) computes each convergence check independently, then sums `to_fusion_credits`. If the same primary overlap is assigned to fusion in two selected convergence programs, primary earned is reduced twice. The UI allows multiple convergence selections.  
   **Fix:** do convergence allocation globally, or at minimum dedupe `to_fusion` by full course id before subtracting from primary major.

4. **MEDIUM [REGRESSION] `pool_exhausted` and general-selection residual can double-plan the same total gap.**  
   Unfillable shortfall is recorded at [planner.py:539-540](/home/carol/kmu_genai/graduation_center/v2/planner.py:539), but `general_need` subtracts only selected credits at [planner.py:544-551](/home/carol/kmu_genai/graduation_center/v2/planner.py:544). If a specific requirement has insufficient pool, generic 일반선택 slots can be added for credits that should belong to the blocked requirement, while the same shortfall is also reported at [planner.py:688-693](/home/carol/kmu_genai/graduation_center/v2/planner.py:688).  
   **Fix:** when a specific requirement is unfillable, either suppress general-slot filling or compute residual from `selected + blocked_specific_obligation`, then report the specific blocker.

5. **MEDIUM [REGRESSION] Frontend gives no course suggestions for group-only convergence shortages.**  
   `groupsOk` correctly uses backend coverage checks at [GraduationV2.jsx:108-110](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:108), but suggestions are gated only by `fusionGap > 0` at [GraduationV2.jsx:114-121](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:114). If total fusion credits are enough but a group minimum is short, the UI says group 부족 at [GraduationV2.jsx:144-146](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) and recommends nothing.  
   **Fix:** build suggestions from `group_checks[].gap` first, then fill any remaining total gap.

6. **MEDIUM Blocked markdown hides partial roadmap and weakens overflow explanation.**  
   When `plan.status === "blocked"`, markdown prints only the blocker at [pipeline.py:122-123](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:122), even though `run_planner` can return partial `terms` at [planner.py:701](/home/carol/kmu_genai/graduation_center/v2/planner.py:701). Overflow markdown also omits `o.note`, so the round-3 “개설학기 제약 가능성” note added at [planner.py:693-696](/home/carol/kmu_genai/graduation_center/v2/planner.py:693) is not rendered.  
   **Fix:** render partial terms for blocked plans, and include `overflow.note` verbatim in markdown.

7. **LOW Required fallback is better, but name fallback can still false-positive duplicate normalized names.**  
   The 7-digit fallback at [audit_v2.py:340-342](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:340) fixes the `0365007/0365008` collision, but “code missing + same normalized name” still counts as taken. The major pool also excludes by normalized name at [planner.py:493-495](/home/carol/kmu_genai/graduation_center/v2/planner.py:493). Data already has a duplicate normalized name: `다학제간캡스톤디자인` and `다학제간캡스톤디자인+`.  
   **Fix:** allow name fallback only when the normalized name is unique in the catalog and credits match; otherwise require user confirmation.

8. **LOW Determinism is mostly okay, but tie-breaks are underspecified.**  
   `id(c)` is not itself causing cross-run output instability because it is only used inside one object list, but equal-credit sorting lacks durable tie-breakers at [audit_v2.py:162](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:162), [audit_v2.py:215](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215), [planner.py:471](/home/carol/kmu_genai/graduation_center/v2/planner.py:471), [planner.py:561](/home/carol/kmu_genai/graduation_center/v2/planner.py:561), and [GraduationV2.jsx:86-87](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:86). Catalog rebuild or equivalent row reorder can change allocation.  
   **Fix:** sort by explicit keys: required flag, credits desc, group, full `course_id`, normalized name.

Verified OK: group coverage is now coverage-based in backend [audit_v2.py:243-251](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:243); required-overlap fusion lock exists in backend/frontend; 7-digit required fallback exists; Mirae 핵심교양 17 is present.

I tried `pytest tests/test_v2_pipeline.py -q`, but collection fails under Python 3.8 because Pydantic cannot evaluate `str | None` annotations. So I could not use the test suite as verification in this environment.
===== /tmp/codex_r4_8.txt =====
/bin/bash -lc "/home/carol/exit/envs/kmu-agent/bin/python - <<'PY'
from graduation_center.v2.planner import build_unified_candidates
from graduation_center.v2.catalog import assemble_requirement_profile
from graduation_center.v2.models_v2 import StudentContext, AuditResult, AreaGap, VerifiedTranscript
ctx=StudentContext(program_id='ai_bigdata')
prof=assemble_requirement_profile(ctx)
au=AuditResult(
 total_required=130,total_earned=127,total_gap=3,
 area_gaps=[], missing_required_names=['경영통계'], missing_required_course_ids=['0029011'],
 convergence_checks=[{
  'name':'데이터사이언스융합전공','gap':3.0,'group_checks':[],
  'courses':[{'name_ko':'경영통계','course_id':'0029011','credits':3.0,'taken':False,'group':'A그룹','offered_terms':['1','2'],'prerequisites':[], 'primary_required': True}]
 }]
)
sel, reqs, unfill=build_unified_candidates(au, prof, VerifiedTranscript())
print('selected:', [(s['name_ko'],s['area'],s.get('assignment'),s['priority']) for s in sel])
print('reqs:', [(r['label'], r.get('need'), len(r.get('pool',[])) if 'pool' in r else len(r.get('items',[]))) for r in reqs])
print('unfillable:', unfill)
PY" in /home/carol/kmu_genai
 succeeded in 0ms:
selected: [('경영통계', '전공', None, 1)]
reqs: [('필수지정 미이수', None, 1), ('데이터사이언스융합전공 부족', 3.0, 1)]
unfillable: []

Reviewed as round 4. I verified against the requested files and ran:

`/home/carol/exit/envs/kmu-agent/bin/python -m pytest tests/test_v2_pipeline.py -q`  
Result: `10 passed`.

**Findings**

1. **HIGH [REGRESSION] Same course can falsely satisfy both a primary-required obligation and a convergence quota.**  
   [planner.py:523](/home/carol/kmu_genai/graduation_center/v2/planner.py:523)-[538](/home/carol/kmu_genai/graduation_center/v2/planner.py:538) de-dupes by normalized name and, if already `seen`, still adds the course credits to the current requirement quota. That is illegal for cases like cap-0 연계전공, exhausted duplicate cap, or 전공필수 overlap that must stay primary-only. The convergence pool is built from untaken courses without checking legal assignment/cap at [planner.py:462](/home/carol/kmu_genai/graduation_center/v2/planner.py:462)-[483](/home/carol/kmu_genai/graduation_center/v2/planner.py:483), while the audit rule says primary-required overlap cannot move to fusion at [audit_v2.py:222](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:222)-[225](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:225).  
   I reproduced this synthetically: missing required `경영통계` plus convergence need `경영통계` selects only the primary item, reports no `unfillable`, and treats convergence as filled.  
   **Fix:** stop using global name `seen` as quota credit. Track candidate identity plus legal assignment, e.g. `(course_id, assignment)`, and only let one planned course satisfy two requirements when the duplicate-recognition cap ledger permits it. Add tests for cap0 연계, cap exhausted, and primary-required overlap.

2. **HIGH [REGRESSION] 7-digit required fallback still accepts wrong-department same-name courses as completed.**  
   `match_course()` falls back from code miss to unique name match at [catalog.py:165](/home/carol/kmu_genai/graduation_center/v2/catalog.py:165)-[170](/home/carol/kmu_genai/graduation_center/v2/catalog.py:170). Then required fallback also treats any confirmed same normalized name as satisfying the required catalog code at [audit_v2.py:338](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:338)-[342](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:342), and major candidate exclusion repeats the same name-only rule at [planner.py:493](/home/carol/kmu_genai/graduation_center/v2/planner.py:493)-[495](/home/carol/kmu_genai/graduation_center/v2/planner.py:495). This fixes `0365007/0365008` prefix collision, but creates a new false positive for homonymous courses from another department. Domain says 전공 is 해당전공 과목 only.  
   **Fix:** if a raw course code exists and does not match the catalog code or an approved same-prefix/alias mapping, do not name-match it as primary-major completion. Name fallback should be reserved for missing code, authoritative alias, or same canonical prefix variants; otherwise mark manual/unresolved.

3. **MEDIUM [REGRESSION] 미래모빌리티 핵심교양 17 is not actually single-source.**  
   `requirements_by_year.json` contains 17 for 2023/2025 at [requirements_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4)-[20](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:20), but `assemble_requirement_profile()` still loads `core_area_min_overrides` from `graduation_requirements.json`, not from the year file, at [catalog.py:125](/home/carol/kmu_genai/graduation_center/v2/catalog.py:125)-[145](/home/carol/kmu_genai/graduation_center/v2/catalog.py:145). `compute_audit()` then recomputes the core total from those overrides at [audit_v2.py:291](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:291)-[297](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:297). With no admission year, the profile says 핵심교양 15 but audit can still require 17 through the old override path.  
   **Fix:** put year-specific core area minima/overrides in `requirements_by_year.json` and make `compute_audit()` consume the assembled profile’s year-selected values only. Also align the no-admission-year policy with required-name selection.

4. **MEDIUM [REGRESSION] Frontend recommends no courses for group-only convergence shortages.**  
   Backend planning correctly includes group gaps in need at [planner.py:463](/home/carol/kmu_genai/graduation_center/v2/planner.py:463)-[475](/home/carol/kmu_genai/graduation_center/v2/planner.py:475). But the UI suggestion block only runs when `fusionGap > 0` at [GraduationV2.jsx:112](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:112)-[121](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:121). If total fusion credits are enough but `groupsOk` is false at [GraduationV2.jsx:108](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:108)-[110](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:110), the UI warns about group shortage but shows no “졸업 가능 시나리오.”  
   **Fix:** compute suggestion need from `max(fusionGap, sum(group gaps))`, prioritize short groups, and render suggestions whenever either total or group shortage exists.

5. **LOW Edge: catalog with group rules but empty group tags silently passes group minima.**  
   Group rules are loaded at [audit_v2.py:158](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:158)-[159](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:159), but `all_groups` is derived only from non-empty course group tags at [audit_v2.py:160](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160). If a convergence catalog has `per_group_min` but all course `group` values are blank, `group_checks` becomes empty and the UI/backend treat group requirements as satisfied.  
   **Fix:** validate catalogs: if group rules exist and no non-empty groups exist, return a blocked/metadata error instead of empty `group_checks`.

**Round-3 Fix Status**

Fixes 1, 2, 3, 5, 7, and the frontend major-gauge note are directionally implemented in the active path. Fix 4 is partially undermined by the `seen` quota bug above. Fix 6 is incomplete due same-name false positives. Fix 8 is value-correct for current data but not single-source. Fix 9’s opening-term note is only conditionally appended for some `unplaced` catalog courses, not for every pool-exhausted/opening-limited case.
===== /tmp/codex_r4_9.txt =====
for fn in glob.glob('data/graduation/v2/catalog_*.json'):
 d=json.load(open(fn))
 if 'courses' not in d: continue
 arr=[(c['course_id'],c['name_ko'],c.get('prerequisites')) for c in d['courses'] if c.get('prerequisites')]
 if arr:
  print('\\n'+fn)
  for x in arr: print(x)
PY" in /home/carol/kmu_genai
 succeeded in 0ms:

data/graduation/v2/catalog_mirae_mobility.json
('0533010', '공학수학Ⅰ', ['0533411'])

data/graduation/v2/catalog_ai_bigdata.json
('1140200', '수리통계', ['0029011'])
('1026501', '경영데이터분석', ['0910501'])
('1139600', '다변량통계분석', ['0029011'])

**Findings**

1. **HIGH [REGRESSION] Cross-requirement dedupe can under-plan 융합 credits.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:522) uses one global `seen` set, and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:535) adds credits to a later quota when the same course was already selected for another requirement. That is not always valid: a 제1전공 필수 겹침과목 can only also satisfy 융합 total if duplicate recognition capacity remains. The audit allocator explicitly forces primary-required overlap to `primary` when not duplicated at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:222).  
   **Fix:** dedupe by `(course_id, requirement)` with compatibility rules. Only let an already-selected primary course count toward 융합 quota if the planner reserves duplicate-recognition capacity for it; otherwise keep selecting 융합 candidates and mark `pool_exhausted` when insufficient.

2. **HIGH Multiple convergence programs can still double-subtract primary credits.**  
   `_convergence_checks()` treats every other selected program as overlap at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:138), computes each convergence allocation independently, then `compute_audit()` blindly sums all `to_fusion_credits` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:288). The same physical primary course can be assigned away from 전공 in two convergence checks.  
   **Fix:** run one global allocation pass keyed by physical course ID/prefix across all selected convergence programs, then subtract each primary course at most once.

3. **HIGH Roadmap still violates prerequisites when the prerequisite is neither completed nor selected.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:568) extracts prerequisites, but [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:571) only defers if the prerequisite is also in `selected`. If the prerequisite is missing and not selected, placement proceeds. Real catalogs contain prerequisites.  
   **Fix:** if a prerequisite is not completed, either add it as a prerequisite candidate or block with `prereq_unmet`; do not place the dependent course.

4. **MEDIUM [REGRESSION] Required-course name matching can falsely satisfy distinct same-normalized-name courses.**  
   The year-based required check is pure normalized-name membership at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:321). In the actual 미래모빌리티 catalog, `다학제간캡스톤디자인` is required at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639), while `다학제간캡스톤디자인+` is a different, non-required course with the same `name_norm` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781). Taking the `+` course can satisfy the required name incorrectly.  
   **Fix:** add course IDs to `required_names_by_year` where available, and reject name-only satisfaction when the catalog has ambiguous `name_norm`.

5. **MEDIUM [REGRESSION] Frontend “졸업 가능 시나리오” ignores pure group gaps.**  
   The backend candidate pool prioritizes group gaps at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463), but the frontend suggestion only runs when `fusionGap > 0` and only fills `fusionGap` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117). If total 융합 credits are met but A/B group minimum is short, the UI says group courses are needed at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144) but shows no actual scenario. The roadmap “남은 요건” summary also only includes `cc.gap`, not group gaps, at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673).  
   **Fix:** compute frontend suggestion need as `max(fusionGap, sum(group_gaps))`, always prioritize short groups, and include group gaps in the remaining-requirements chips.

6. **LOW Roadmap sources are empty in the active deterministic path.**  
   `run_planner()` returns `ctx = {"sources": [], ...}` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:638), and the pipeline exposes that directly. This weakens the “grounded” demo story even though catalog source data exists.  
   **Fix:** attach `Source` entries while building unified candidates, as the old `build_planning_context()` path did.

**Round-3 Verification**

Mostly fixed: group checks now use coverage basis; primary-required fusion-only is blocked; general residual is post-selection; backend group-priority pool exists; active planner/risk clamp legal caps; 미래모빌리티 핵심교양 17 is present; overflow note mentions offered-term constraints.

Incomplete regressions: no-candidate/pool-exhausted is still bypassable through `seen` quota crediting, frontend group suggestions are not aligned with the backend group quota fix, and name-only required matching still has false positives.

**Demo Happy-Path Top 3 Risks**

1. A mobility-data group shortage can be visible in the convergence block but absent from “남은 요건” chips.  
2. A missing 미래모빌리티 required overlap can be counted as 융합 quota without duplicate-cap validation, producing an under-planned roadmap.  
3. Capstone name ambiguity can make a required course look satisfied when only the non-required `+` variant was taken.
===== /tmp/codex_r4_findings.txt =====
