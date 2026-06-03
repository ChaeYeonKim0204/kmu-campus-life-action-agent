===== /tmp/codex_r2_0.txt =====
graduation_center/v2/catalog.py:82:    progs = load_programs()
graduation_center/v2/catalog.py:107:    by_year = (json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}).get(program_id)
./docs/review_subagents_adversarial.md:35:- 문제: run_planner의 report는 over_credit_cap만으로 errors를 채운다(557-561행). plan_greedy가 후보를 다 못 넣어 unplaced가 생기면 plan.feasible=False·blocked_reason은 설정되지만 report.ok는 여전히 True다(unplaced를 errors에 안 넣음). validate_roadmap(266-353행, 선수·not_offered·중복·gap_not_closed·required_not_planned 검사)은 결정론 경로에서 호출되지 않는 죽은 코드다. pipeline.py:72-77 '검증/repair' 노드는 vrep.ok로 branch_taken을 정하므로 실현 불가 로드맵인데도 검증 노드가 '통과'로 점등된다 — 교수가 채점하는 Dify식 노드 그래프에 '로드맵 blocked인데 검증은 통과'라는 거짓 통과가 표시된다.
./docs/review_codex_adversarial.md:2507:tests/test_v2_pipeline.py:136:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./docs/review_codex_adversarial.md:2510:tests/test_v2_pipeline.py:154:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./docs/review_codex_adversarial.md:2513:tests/test_v2_pipeline.py:173:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./docs/review_codex_adversarial.md:2531:tests/test_v2_pipeline.py:232:    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
./docs/review_codex_adversarial.md:2590:graduation_center/v2/planner.py:211:def plan_roadmap(planning_context: dict, client=None) -> RoadmapPlan:
./docs/review_codex_adversarial.md:2594:graduation_center/v2/planner.py:266:def validate_roadmap(plan: RoadmapPlan, ctx: dict, context: StudentContext) -> ValidationReport:
./docs/review_codex_adversarial.md:2608:graduation_center/v2/planner.py:528:def run_planner(
./docs/review_codex_adversarial.md:2642:graduation_center/v2/pipeline.py:53:    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
./docs/review_codex_adversarial.md:2743:./tests/test_v2_pipeline.py:232:    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
./docs/review_codex_adversarial.md:2817:./graduation_center/v2/planner.py:528:def run_planner(
./docs/review_codex_adversarial.md:2829:./graduation_center/v2/pipeline.py:53:    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
./docs/review_codex_adversarial.md:5342:1. [graduation_center/v2/planner.py:556](/home/carol/kmu_genai/graduation_center/v2/planner.py:556) `run_planner()` never calls `validate_roadmap()`. It only rechecks credit caps at [557-562](/home/carol/kmu_genai/graduation_center/v2/planner.py:557), so the real validator’s checks for prerequisites, required inclusion, duplicate courses, term range, offered terms, sources, and gap closure are bypassed. This is demo-breaking because the trace says “검증/repair 통과” even when no real validation ran.  
./tests/test_v2_pipeline.py:136:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./tests/test_v2_pipeline.py:154:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./tests/test_v2_pipeline.py:173:    rep = planner.validate_roadmap(plan, pctx, StudentContext.model_validate(ctx))
./tests/test_v2_pipeline.py:232:    plan, rep, ctxd = planner.run_planner(au, prof, ctx, vt)
./graduation_center/v2/planner.py:211:def plan_roadmap(planning_context: dict, client=None) -> RoadmapPlan:
./graduation_center/v2/planner.py:266:def validate_roadmap(plan: RoadmapPlan, ctx: dict, context: StudentContext) -> ValidationReport:
./graduation_center/v2/planner.py:573:def run_planner(
./graduation_center/v2/pipeline.py:53:    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
The above exception was the direct cause of the following exception:
The local default `python` is 3.8 and cannot import this codebase’s `str | None` annotations, so that probe failed before reaching the planner. I’ll avoid spending time on environment setup; the static control-flow is already conclusive.
   293	        if not fn.lower().endswith((".xls", ".xlsx")):
**HIGH Findings**
1. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:512): `plan_greedy()` still permits courses whose prerequisite is neither completed nor selected. It only defers when the prereq prefix is in `sel_pref`; if the prerequisite is missing from the selected set, placement proceeds. `run_planner()` then only checks caps/unplaced at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:604), so it can return `feasible=True` with an impossible roadmap. Real catalog prereqs exist, e.g. `수리통계` requires `0029011` in [catalog_ai_bigdata.json](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:261).  
2. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:591) and [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62): statutory 학기당상한 is user-bypassable. The frontend exposes editable `max_credits_per_term` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444), then planner/risk trust it. A user can set 30 and get a “feasible” plan violating 제32조.  
Fix: compute legal cap from `regular_term_cap(profile.total_credits_min)` and use user input only as a lower personal preference, never above legal cap.
3. [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:138): multiple convergence programs corrupt primary allocation. `other_prefixes` includes other convergence programs, `overlap_cr` then subtracts from `primary_major_earned` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:213), and `compute_audit()` sums all `to_fusion_credits` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268). A course shared between two convergence catalogs can be subtracted from 제1전공 even if it was never 제1전공, or subtracted twice.  
4. [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160): `group_checks` still count all designated courses, not allocation-effective credits. If overlap above cap is assigned to 제1전공, the group can still show satisfied because [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:165) uses raw designated earned. Risk/planner/frontend then trust that stale group gap.  
5. [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102) vs [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42): year resolution is inconsistent. Area minima use exact-only, while required names use nearest-prior. Data has only 2023 minima for 미래모빌리티 in [requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:5), but required names have 2023 and 2025 in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:5). A 2024 student can get 2025 area minima but 2023 required courses, with `applied_yoram` later overwritten to 2023 at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:314).  
6. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:422): missing-required credit math is wrong for 2025 string entries. `_required_meta()` only reads dict entries; 2025 required names are plain strings at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147). Planner defaults every missing required course to 3 credits, then subtracts those credits from major gap at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:448). This overstates 1-credit/2-credit required courses and can suppress real 전공-gap planning.  
**MEDIUM Findings**
7. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:488): candidate selection happens before placement and has no backfill. The planner selects only enough pool courses to meet `need`; if one selected course cannot be placed due to term/prereq/cap, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:610) blocks instead of trying the next valid course from the pool.  
8. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:266): the old full validator is now effectively dead code for the deterministic path. `pipeline.py` only receives `run_planner()`’s lightweight `vrep` at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:53). That `vrep` omits unknown course, duplicate, source, prereq, gap-closure, and offered-term validation.  
**LOW Findings**
9. [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:348) and [app.py](/home/carol/kmu_genai/app.py:276): demo copy still claims LLM roadmap behavior even though `run_planner()` is deterministic. This contradicts the fixed workflow trace.  
10. [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:241): privacy fix is mostly effective, but the field is still named `student_id` locally and accepts any string containing `20xx`.  
===== /tmp/codex_r2_1.txt =====
   172	        "term_credits": 3, "term_risk": "low", "notes": []}])
   293	        if not fn.lower().endswith((".xls", ".xlsx")):
The above exception was the direct cause of the following exception:
print('remaining0:', plan.status, plan.feasible, len(plan.terms), rep.ok, plan.why_this_plan, plan.blocked_reason, plan.overflow)
The above exception was the direct cause of the following exception:
The above exception was the direct cause of the following exception:
  ctx=StudentContext(program_id='ai_bigdata', remaining_semesters=rem, max_credits_per_term=999, seasonal_semester_allowed=False)
The above exception was the direct cause of the following exception:
docs/archive/KMU_재설계_기획문서.md:268:| **설명** | `Dockerfile` 작성 (Python 3.11 베이스). 데이터 디렉토리 볼륨 마운트 포함(`data/processed/`, `data/state/`). `docker-compose.yml`로 로컬 실행 환경 구성 |
docs/archive/KMU_재설계_기획문서.md:302:| **설명** | `print()` 기반 로그를 Python `logging` 모듈로 교체. 로그 레벨(INFO/WARNING/ERROR) 구분. 요청 ID, issue_type, 처리 시간 포함 |
docs/archive/KMU_신규구축_기획문서.md:85:| **백엔드** | FastAPI (Python 3.11) | pydantic-settings로 환경변수 관리 |
docs/archive/KMU_신규구축_기획문서.md:429:| **설명** | `Dockerfile` 작성 (Python 3.11 slim 베이스, Gunicorn + Uvicorn workers). `docker-compose.yml`로 백엔드 + 볼륨 마운트(`data/`) 구성. `.env` 파일 주입 방식 |
docs/archive/KMU_신규구축_기획문서.md:440:| **설명** | Python `logging` 모듈로 통일. 로그 레벨: INFO(요청 처리), WARNING(소스 없음), ERROR(예외). 로그 항목: 요청 ID, issue_type, 처리 시간, LLM 사용 여부 |
/bin/bash -lc 'pytest -q tests/test_v2_pipeline.py' in /home/carol/kmu_genai
__________________ ERROR collecting tests/test_v2_pipeline.py __________________
The above exception was the direct cause of the following exception:
tests/test_v2_pipeline.py:15: in <module>
ERROR tests/test_v2_pipeline.py - TypeError: Unable to evaluate type annotati...
One concrete verification result: `pytest -q tests/test_v2_pipeline.py` does not even collect in this workspace because the default Python is 3.8 and the codebase uses PEP 604 type syntax. I’ll include that as a demo-blocking environment finding unless the demo runner is explicitly pinned to Python 3.11.
**HIGH Findings**
1. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:593) treats `remaining_semesters=0` exactly like missing/malformed `current_term`.
Fix: distinguish `not context.current_term`/malformed from `remaining_semesters <= 0`; return `status="blocked", feasible=False`, add `unplaced` validation errors, and compute overflow.
2. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:516) still allows unmet prerequisites when the prerequisite is not in the selected candidate set.
`plan_greedy()` defers only if prereq is in `sel_pref`; if prereq is neither completed nor selected, the course is placed anyway. The full validator would catch this at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:334), but `run_planner()` only checks caps/unplaced at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:604). Result: `generated/feasible=true` plans can violate 선수과목.
3. [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137) mixes “primary overlap” with “other convergence overlap”, then subtracts all `to_fusion_credits` from 제1전공 at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268).
4. [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160) computes `group_checks` before allocation and counts all designated credits, including over-cap credits later assigned back to 제1전공.
That can show a convergence group as 충족 while the recognized 융합 allocation for that group is short. The planner then consumes those stale group gaps at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:431), so it may recommend the wrong additional convergence courses.
5. [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:110) applies year-specific area requirements only on exact-year match, while required names use nearest-prior at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42).
For `mirae_mobility` 2024, `requirements_by_year.json` has only 2023 ([requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4)), so area minima fall back to latest/default, but required courses use 2023. `compute_audit()` then rewrites the label to 2023 at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313), hiding the mixed-yŏram calculation.
6. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:424) defaults missing required-name credits to `3.0` when metadata is absent, and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:448) subtracts those guessed credits from the major gap.
`pytest -q tests/test_v2_pipeline.py` fails during collection under the default `python`/`python3` 3.8.5 because models use `str | None` syntax, e.g. [models.py](/home/carol/kmu_genai/graduation_center/models.py:24). `requirements.txt` does not pin Python 3.10/3.11 or include `eval_type_backport`.
**MEDIUM Findings**
8. [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62) uses user-editable `context.max_credits_per_term` as legal capacity.
Frontend lets the user type any number at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444). A user can enter `99`, suppressing remaining-semester risk and letting the planner use unlawful caps. This violates 제32조.
9. [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:75) marks roadmap placement `ok` for `feasible=None`, and [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78) marks validation `ok` even when no term placement was attempted.
Frontend no longer shows green for `feasible=null`, but the workflow graph can still show green “통과” for an unvalidated/no-placement path.
10. [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:85) recomputes convergence allocation locally instead of rendering backend `primary_effective`/`fusion_effective`.
**LOW Findings**
11. Stale LLM/repair wording remains after the deterministic rewrite: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:1), [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:4), [WorkflowGraph.jsx](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:9), and [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:349).
Verified as actually fixed: frontend no longer sends raw `student_id` in `contextPayload()` ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:248)), `feasible === null` has a warning path ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:646)), and the workflow node list no longer contains explicit LLM/repair nodes ([WorkflowGraph.jsx](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:12)).
===== /tmp/codex_r2_2.txt =====
frontend/src/components/GraduationV2.jsx:409:                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
frontend/src/components/GraduationV2.jsx:425:            {ctx.convergence_program_ids.length === 0 && otherMajors.length === 0 && (
frontend/src/components/GraduationV2.jsx:617:              {audit.audit.missing_required_names.length > 0 && (
frontend/src/components/GraduationV2.jsx:618:                <p style={{ color: C.danger, fontSize: 13, margin: "8px 0 0" }}>미이수 필수지정: {audit.audit.missing_required_names.join(", ")}</p>
frontend/src/components/GraduationV2.jsx:626:            {audit.audit.convergence_checks?.length > 0 && (
frontend/src/components/GraduationV2.jsx:629:                {audit.audit.convergence_checks.map((cc, i) => (
frontend/src/components/GraduationV2.jsx:655:                if (audit.audit.missing_required_names?.length) rem.push(`필수지정 ${audit.audit.missing_required_names.length}과목`);
frontend/src/components/GraduationV2.jsx:657:                (audit.audit.convergence_checks || []).forEach((cc) => { if (cc.gap > 0) rem.push(`${cc.name} ${cc.gap}학점`); });
/bin/bash -lc "nl -ba tests/test_v2_pipeline.py | sed -n '1,320p'" in /home/carol/kmu_genai
   111	                "term_credits": acc, "term_risk": "low", "notes": []}]}
   135	        "term_credits": 3, "term_risk": "low", "notes": []}])
   153	        "term_credits": 48, "term_risk": "low", "notes": []}])
   172	        "term_credits": 3, "term_risk": "low", "notes": []}])
/bin/bash -lc 'pytest tests/test_v2_pipeline.py -q' in /home/carol/kmu_genai
__________________ ERROR collecting tests/test_v2_pipeline.py __________________
The above exception was the direct cause of the following exception:
tests/test_v2_pipeline.py:15: in <module>
ERROR tests/test_v2_pipeline.py - TypeError: Unable to evaluate type annotati...
   619	        ov = overflow or project_overflow(audit, profile, context)
   624	                           assumptions=assumptions, overflow=ov,
   629	                           why_this_plan=why, assumptions=assumptions, overflow=None)
    23	    seasonal_semester_allowed: bool = False
**HIGH**
1. [audit_v2.py:268](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268) double-subtracts convergence overlap across multiple 융합 programs.
`compute_audit()` sums every `cc["to_fusion_credits"]` and subtracts it from 전공 once per convergence check. But `_convergence_checks()` is computed independently per program, and `other_prefixes` includes other convergence programs too at [audit_v2.py:136](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:136). The same physical course can therefore be allocated to fusion twice, making `major_effective` too low or even negative.
2. [planner.py:516](/home/carol/kmu_genai/graduation_center/v2/planner.py:516) lets a course with an unmet prerequisite be placed if the prerequisite is not in the selected pool.
`_try_place()` defers only when the prereq is selected but unplaced. If the prereq is neither completed nor selected, placement proceeds. The deterministic `run_planner()` then only checks caps/unplaced at [planner.py:604](/home/carol/kmu_genai/graduation_center/v2/planner.py:604), so it can return `status="generated", feasible=True` at [planner.py:628](/home/carol/kmu_genai/graduation_center/v2/planner.py:628) with an invalid prerequisite chain.
3. [audit_v2.py:160](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160) group checks ignore the backend allocation.
`group_checks` counts all designated courses before cap/allocation, while `cc.earned/gap` uses allocated `fusion_eff` at [audit_v2.py:236](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:236). Then planner and risk consume stale group gaps at [planner.py:430](/home/carol/kmu_genai/graduation_center/v2/planner.py:430) and [risk.py:78](/home/carol/kmu_genai/graduation_center/v2/risk.py:78). A group can appear satisfied using credits actually assigned to 제1전공.
4. [catalog.py:102](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102) and [audit_v2.py:42](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42) select different 요람 years.
`requirements_by_year` is exact-only, but required names use nearest-prior. For `mirae_mobility` 2024, area credits fall back to latest/default 2025 while required names use 2023; the report may label `2023 요람` at [audit_v2.py:314](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:314). Data confirms the mismatch: [required_names_by_year.json:5](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:5) has 2023 and 2025, while [requirements_by_year.json:5](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:5) has only 2023.
**MEDIUM**
5. [planner.py:591](/home/carol/kmu_genai/graduation_center/v2/planner.py:591) treats “no legal terms” as “current term missing.”
If `remaining_semesters=0` or `current_term` is malformed, `_ordered_terms()` returns `[]`; `run_planner()` returns `status="generated", feasible=None`, `ValidationReport(ok=True)` at [planner.py:596](/home/carol/kmu_genai/graduation_center/v2/planner.py:596). Pipeline then shows roadmap validation as passed at [pipeline.py:78](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78).
6. [models_v2.py:25](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:25) allows arbitrary `max_credits_per_term`, and planner/risk trust it.
The frontend explicitly lets users edit it at [GraduationV2.jsx:444](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444). Planner uses it for legal capacity at [planner.py:591](/home/carol/kmu_genai/graduation_center/v2/planner.py:591), and risk uses it at [risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62). A user can enter 30 and get an illegal roadmap despite 제32조 caps.
**Verified OK / No Finding**
Frontend privacy fix is substantially correct: `contextPayload()` strips `student_id` before POST and sends only `admission_year` plus masked display at [GraduationV2.jsx:248](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:248).
Workflow trace no longer contains fake LLM/repair nodes: backend emits `로드맵 배치`/`로드맵 검증`, and frontend nodes match.
Test note: `pytest tests/test_v2_pipeline.py -q` did not collect under the available Python 3.8 runtime because the project uses `str | None` annotations. I could not use the test suite as verification in this environment.
===== /tmp/codex_r2_3.txt =====
graduation_center/v2/pipeline.py:58:    conv_n = len(audit.convergence_checks)
graduation_center/v2/pipeline.py:99:    if audit.convergence_checks:
graduation_center/v2/pipeline.py:101:        for cc in audit.convergence_checks:
graduation_center/v2/pipeline.py:138:              + (f" · 예상 졸업: **{o.projected_graduation_term}**" if o.projected_graduation_term else "")]
graduation_center/v2/audit_v2.py:4:필수과목 누락을 계산한다. 카테고리 총계 요건은 graduation_requirements.json에서 온
graduation_center/v2/audit_v2.py:16:from graduation_center.v2.models_v2 import (
graduation_center/v2/audit_v2.py:19:from graduation_center.v2.catalog import V2_DIR, load_catalog, load_gen_ed
graduation_center/v2/audit_v2.py:20:from graduation_center.v2.text_norm import normalize_name
graduation_center/v2/audit_v2.py:98:def _admission_year(profile: RequirementProfile, verified: VerifiedTranscript) -> int | None:
graduation_center/v2/audit_v2.py:99:    """입학연도 — context.admission_year 우선, 없으면 수강내역 최초 학기 연도에서 추정."""
graduation_center/v2/audit_v2.py:100:    if profile.admission_year:
graduation_center/v2/audit_v2.py:101:        return int(profile.admission_year)
graduation_center/v2/audit_v2.py:114:def _convergence_checks(verified: VerifiedTranscript, program_ids, tracks, primary_program_id,
graduation_center/v2/audit_v2.py:260:    convergence_program_ids=(), convergence_tracks=None,
graduation_center/v2/audit_v2.py:264:    # 이중집계를 막고 전공/융합/risk를 한 배정으로 정합. (배정은 _convergence_checks가 결정론 산출)
graduation_center/v2/audit_v2.py:265:    conv_checks = _convergence_checks(verified, convergence_program_ids, convergence_tracks,
graduation_center/v2/audit_v2.py:299:    year = _admission_year(profile, verified)
graduation_center/v2/audit_v2.py:335:        convergence_checks=conv_checks,
/bin/bash -lc "sed -n '1,280p' tests/test_v2_pipeline.py" in /home/carol/kmu_genai
                "term_credits": acc, "term_risk": "low", "notes": []}]}
        "term_credits": 3, "term_risk": "low", "notes": []}])
        "term_credits": 48, "term_risk": "low", "notes": []}])
        "term_credits": 3, "term_risk": "low", "notes": []}])
   390	                <div style={{ position: "absolute", zIndex: 5, left: 0, right: 0, top: "100%", maxHeight: 190, overflow: "auto",
    63	def project_overflow(audit: AuditResult, profile: RequirementProfile, context: StudentContext):
    69	    from graduation_center.v2.models_v2 import OverflowScenario
**HIGH Findings**
`graduation_center/v2/planner.py:512-521` only defers a prerequisite if that prereq is also in `selected`; if the prereq is neither completed nor selected, the course is placed anyway. That violates the roadmap rule. Also, missing required courses are built from names at `planner.py:417-428`, so programs using `missing_required_course_ids` lose catalog `course_id`, `prerequisites`, and `offered_terms`.
`graduation_center/v2/audit_v2.py:160-166` computes `group_checks` from all designated courses before default allocation. Courses later assigned `제1전공` only at `audit_v2.py:229-237` still satisfy 융합 group minima. `planner.py:430-432` then trusts those group gaps, so the roadmap may omit required group-filling courses.
`audit_v2.py:136-139` treats every other selected program as overlap, then each convergence check independently computes `to_fusion_credits` at `audit_v2.py:223-238`. `compute_audit` sums them blindly at `audit_v2.py:268-269`. If the same course appears in two convergence programs, the first-major earned value can be reduced twice.
`catalog.py:102-111` applies `requirements_by_year` only on exact year. But required names use nearest-prior fallback in `audit_v2.py:300-314`, with data only for `2023` and `2025` in `required_names_by_year.json`, while `requirements_by_year.json:4-11` only has `2023`. A 2024 미래모빌리티 student can get 2025/default area minima but 2023 required-course names and a 2023 applied-yỏ람 label.
`planner.py:76`, `planner.py:591`, and `risk.py:62` use `context.max_credits_per_term` directly. The frontend exposes it as editable at `GraduationV2.jsx:373-374` context flow and the later max-credit input, so a typo like `30` can make an impossible roadmap feasible.
**MEDIUM Findings**
`GraduationV2.jsx:105` defines `fits` using only primary total and fusion total. It ignores `cc.group_checks`, so `GraduationV2.jsx:134-139` can render a green “둘 다 졸업요건 충족” message even when a group is short.
`risk.py:68` only compares `audit.total_gap` to remaining capacity. But `project_overflow` correctly uses `max(total_gap, area_shortfall)` at `planner.py:72-73`. A student with enough total credits but remaining 전공/융합 credits beyond capacity can avoid the capacity-specific D trigger unless roadmap later blocks.
Fix: share the same shortfall calculation between risk and overflow, including allocated area gaps and convergence/group gaps.
**LOW Findings**
8. Workflow validator trace overclaims verification for name-only/generic slots.
`pipeline.py:78-81` always says “통과(선수·개설학기·학점상한)” when `vrep.ok`, but `planner.py:559-564` can emit `name_only` or `generic_slot` courses with `manual_check=True`. Those are not actually source/catalog verified.
The prior frontend `feasible === null` rendering fix looks correct at `GraduationV2.jsx:641-649`, and the workflow graph no longer shows the old LLM/repair loop. The remaining blockers are backend allocation consistency and prerequisite correctness.
===== /tmp/codex_r2_4.txt =====
graduation_center/v2/audit_v2.py:29:    return json.loads(p.read_text(encoding="utf-8")).get("programs", {}) if p.exists() else {}
graduation_center/v2/audit_v2.py:98:def _admission_year(profile: RequirementProfile, verified: VerifiedTranscript) -> int | None:
graduation_center/v2/audit_v2.py:99:    """입학연도 — context.admission_year 우선, 없으면 수강내역 최초 학기 연도에서 추정."""
graduation_center/v2/audit_v2.py:100:    if profile.admission_year:
graduation_center/v2/audit_v2.py:101:        return int(profile.admission_year)
graduation_center/v2/audit_v2.py:299:    year = _admission_year(profile, verified)
    """Request body for starting a follow-up action."""
    """Request body for continuing a follow-up action."""
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    if not filename.lower().endswith(".pdf"):
707:                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
**Findings**
- **HIGH: Backend/tests do not start in the current documented environment.**  
  `pytest tests/test_v2_pipeline.py -q` fails during collection because the active `python` is 3.8, while startup imports [app.py](/home/carol/kmu_genai/app.py:31) → [models.py](/home/carol/kmu_genai/graduation_center/models.py:24), which uses `str | None`. `uvicorn app:app` will hit the same import path.  
  **Fix:** pin/use Python >=3.10 for the project environment and CI/demo, or rewrite annotations/install `eval_type_backport` and verify all Pydantic models import under 3.8. For demo, the safer fix is a Python >=3.10 venv.
- **HIGH: `run_planner` can mark a roadmap feasible even when a prerequisite is unmet.**  
  In [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:512), `_try_place` only defers when a prerequisite prefix is in the selected set but not yet placed. If the prerequisite is neither completed nor selected, it falls through and places the dependent course. The “validator” in `run_planner` only checks cap/unplaced at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:604), so status can be `generated`, `feasible=True` with an unmet prerequisite.  
  **Fix:** when `pre not in completed` and `pre not in placed_at`, either auto-add the prerequisite candidate or return `False`/blocked with a `prereq_unmet` validation error. Also make `run_planner` run a real prerequisite validation over placed terms.
- **HIGH: Multi-convergence allocation is not globally unique and can double-count/double-subtract overlaps.**  
  `_convergence_checks` treats overlap as “all other selected programs” at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137), not just first-major overlap. Then `compute_audit` blindly sums every program’s `to_fusion_credits` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268). With two convergence programs sharing the same first-major courses, the same course credits can be allocated to fusion twice and subtracted from 전공 twice. Real data has 8 AI/DSCI/Mobility shared prefixes.  
  **Fix:** create one global allocation keyed by course prefix/course instance. Separate “primary-major overlap” from “other convergence overlap”, and subtract each first-major course from 전공 at most once.
- **MEDIUM: 2024 미래모빌리티 mixes 요람 years and can display the wrong applied 요람.**  
  Area minima use exact-only `requirements_by_year` at [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102), but required names use nearest-prior at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:32), and planner metadata uses another nearest-prior resolver at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:380). Data has only 2023 area minima in [requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4), but required names have 2023 and 2025 in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:4). A 2024 student gets latest/default area requirements but 2023 required names, then `applied_yoram` is overwritten to “2023 요람 (학번 2024 기준)” at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313).  
  **Fix:** implement one shared effective-year resolver returning explicit `area_year`, `required_year`, and `metadata_year`, or add complete 2024/2025 `requirements_by_year` data. Do not show one `applied_yoram` label unless all requirement paths use that year.
- **MEDIUM: 2025 미래모빌리티 required-course roadmap credits/terms are fabricated defaults.**  
  The 2025 required list is strings only at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147). `_required_meta` only returns credits/terms for dict entries, so `build_unified_candidates` defaults missing required courses to `3.0` credits and `["1","2"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:421). That is wrong for one-credit labs and term-specific required courses.  
  **Fix:** convert 2025 entries to `{name, credits, terms}` or resolve metadata from the catalog/aliases before planning.
- **MEDIUM: User-editable max credits can override Article 32 and produce false feasibility.**  
  The UI labels the cap “수정 가능” at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444). Planner and risk then trust it at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:591) and [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62). A user can enter 24 and get an illegal roadmap/capacity.  
  **Fix:** server-side clamp to `regular_term_cap(profile.total_credits_min)` plus only the first-term GPA bonus. If “what-if” is needed, label it separately and still flag above-regulation plans as infeasible.
- **LOW/MEDIUM: Convergence group checks are allocation-blind.**  
  `group_checks` sums all designated courses before applying duplicate caps/allocation at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160). Risk uses those raw gaps at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:78), and frontend suggestions use them at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:109). This can overstate a group if raw designated credits were later assigned back to 제1전공.  
  **Fix:** compute group earned from the same allocated fusion-effective courses used for `cc.earned/gap`.
**Verified Fixed**
- Frontend `feasible === null` now renders orange, not green: [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:641).  
- Workflow graph removed the fake LLM/repair nodes: [WorkflowGraph.jsx](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:15).  
- Frontend sends only `admission_year`/masked display value, not raw student id: [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:247).  
===== /tmp/codex_r2_5.txt =====
./docs/review_subagents_adversarial.md:76:- 수정: capacity 계산을 공용 헬퍼 term_capacity(context, profile)로 단일화. risk.compute_risk에 profile을 넘겨 regular_term_cap(profile.total_credits_min) 공통 사용(하드코딩 18 제거), 계절학기 가산 정책을 risk·project_overflow가 동일 적용.
./docs/review_subagents_adversarial.md:113:## [MEDIUM] [데이터] 학기당 상한 17/18/19 자동 미작동 — programs.json에 max_credits_per_term 없어 항상 18 전송, 136학점 학과는 실제 cap 19를 못 받음
./docs/review_subagents_adversarial.md:123:## [MEDIUM] [데이터] max_credits_per_term override가 0/빈값일 때 risk(18)와 overflow(요람별 17/19) 폴백 갈림
./docs/review_subagents_adversarial.md:125:- 문제: 프론트는 Number(ctx.max_credits_per_term)를 항상 보내 사용자가 비우면 0 전송. risk.py:62 0 or 18→18, planner.py:76 0 or regular_term_cap→요람별 17/19로 서로 다른 상한. risk의 하드코딩 18은 졸업120(상한17)·136(상한19)에서 틀린 capacity를 만들어 D 트리거 오작동.
./docs/review_subagents_adversarial.md:126:- 수정: 0/None을 모두 regular_term_cap로 폴백하도록 risk·planner 동일 헬퍼 사용, 또는 프론트가 빈값을 안 보내고 서버 모델에서 0→None 정규화. (위 risk/overflow capacity 단일화 finding과 함께.)
./docs/graduation_center_spec_en.md:177:- `len(courses)` ≤ `max_courses_per_term` per term (credit cap only if a separate `max_credits_per_term` is configured); no seasonal term unless `seasonal_semester_allowed`
./docs/review_codex_adversarial.md:2774:./frontend/src/components/GraduationV2.jsx:225:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
./docs/review_codex_adversarial.md:5371:10. [graduation_center/v2/risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62) risk capacity uses `context.max_credits_per_term or 18`, not the applied profile’s `regular_term_cap(profile.total_credits_min)`. Since frontend always sends `max_credits_per_term` at [GraduationV2.jsx:245](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:245), stale/user-edited caps can flip feasibility and risk.  
./graduation_center/v2/risk.py:62:    term_cap = float(context.max_credits_per_term or 18)
./graduation_center/v2/planner.py:13:    PREV_GPA_BONUS, SEASONAL_TERM_CAP, V2_DIR, load_catalog, regular_term_cap,
./graduation_center/v2/planner.py:76:    cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./graduation_center/v2/planner.py:136:    term_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./graduation_center/v2/planner.py:147:            "max_credits_per_term": term_cap,
./graduation_center/v2/planner.py:196:        "학기당 이수학점 상한(student_context.max_credits_per_term, 계절학기는 seasonal_credit_cap, "
./graduation_center/v2/planner.py:591:    reg_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./frontend/src/components/GraduationV2.jsx:212:    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
./frontend/src/components/GraduationV2.jsx:228:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
./frontend/src/components/GraduationV2.jsx:235:          const cap = progs[c.program_id]?.max_credits_per_term;
./frontend/src/components/GraduationV2.jsx:236:          return cap ? { ...c, max_credits_per_term: cap } : c;
./frontend/src/components/GraduationV2.jsx:253:      max_credits_per_term: Number(ctx.max_credits_per_term),
./frontend/src/components/GraduationV2.jsx:262:    const cap = programs[id]?.max_credits_per_term;
./frontend/src/components/GraduationV2.jsx:263:    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
./frontend/src/components/GraduationV2.jsx:445:              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
./graduation_center/v2/catalog.py:48:def regular_term_cap(total_credits_min: float) -> float:
./graduation_center/v2/catalog.py:60:def program_total_min(program_id: str) -> float | None:
   375	        elif context.seasonal_semester_allowed:
**Findings**
1. **HIGH** [planner.py:512](/home/carol/kmu_genai/graduation_center/v2/planner.py:512), [planner.py:604](/home/carol/kmu_genai/graduation_center/v2/planner.py:604)  
2. **HIGH** [audit_v2.py:137](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137), [audit_v2.py:213](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:213), [audit_v2.py:268](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268)  
3. **HIGH** [audit_v2.py:160](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160), [audit_v2.py:247](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:247), [planner.py:431](/home/carol/kmu_genai/graduation_center/v2/planner.py:431), [risk.py:78](/home/carol/kmu_genai/graduation_center/v2/risk.py:78)  
4. **HIGH** [risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62), [planner.py:76](/home/carol/kmu_genai/graduation_center/v2/planner.py:76), [planner.py:357](/home/carol/kmu_genai/graduation_center/v2/planner.py:357), [GraduationV2.jsx:253](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:253)  
   Capacity uses user-editable `max_credits_per_term`, not the applied 요람 cap, and risk/overflow/planner disagree on seasons. Planner can use every seasonal term in `_ordered_terms`; risk adds only one `+6`; overflow adds none. This can show “로드맵 feasible” while risk says D, or the reverse.  
   Fix: create one backend capacity helper from `regular_term_cap(profile.total_credits_min)` plus generated allowed terms. Treat user input as a preference/load limit capped by the legal cap, not as the legal cap itself.
5. **MEDIUM** [planner.py:72](/home/carol/kmu_genai/graduation_center/v2/planner.py:72), [planner.py:430](/home/carol/kmu_genai/graduation_center/v2/planner.py:430), [planner.py:617](/home/carol/kmu_genai/graduation_center/v2/planner.py:617)  
   `project_overflow` only considers total gap and area gaps. It ignores missing 필수지정, 융합 total gaps, 융합 group gaps, and 기초교양 필수 when those do not create area/total shortage. Blocked roadmaps can therefore have no meaningful overflow scenario.  
   Fix: derive overflow shortfall from the unified selected requirements or include `missing_required`, convergence effective gap, group gap, and manual required slots in the shortfall model.
6. **HIGH** [catalog.py:102](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102), [catalog.py:122](/home/carol/kmu_genai/graduation_center/v2/catalog.py:122), [audit_v2.py:313](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313), [requirements_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4), [required_names_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:4)  
7. **MEDIUM** [GraduationV2.jsx:85](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:85), [GraduationV2.jsx:100](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100)  
8. **LOW** [models_v2.py:20](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:20), [requirements.txt:1](/home/carol/kmu_genai/requirements.txt:1)  
Verified as actually fixed: raw student ID is not sent to the backend, `feasible === null` is no longer rendered as green, and the workflow graph no longer shows fake LLM/repair nodes.
===== /tmp/codex_r2_6.txt =====
graduation_center/v2/planner.py:500:def plan_greedy(selected: list[dict], terms: list[list],
graduation_center/v2/planner.py:573:def run_planner(
graduation_center/v2/planner.py:602:    placed, assumptions, unplaced = plan_greedy(selected, terms, completed)
graduation_center/v2/catalog.py:98:            "convergence_required": progs[program_id].get("convergence_required"),
graduation_center/v2/catalog.py:102:def _requirements_by_year(program_id: str, year: int | None) -> dict | None:
graduation_center/v2/catalog.py:106:    p = V2_DIR / "requirements_by_year.json"
graduation_center/v2/catalog.py:117:    학번(입학연도) 요람 별표5(requirements_by_year.json)가 있으면 영역 최저학점은 그것을 우선.
graduation_center/v2/catalog.py:122:    yr = _requirements_by_year(context.program_id, context.admission_year)
   327	      // 워크플로우 전용 페이지(#workflow)가 읽도록 trace 저장
   329	        localStorage.setItem("v2_workflow_trace",
   339	    <div style={{ background: C.bg, height: "100vh", overflowY: "auto", padding: "0 0 60px",
/bin/bash -lc "nl -ba frontend/src/components/WorkflowGraph.jsx | sed -n '1,45p'" in /home/carol/kmu_genai
    29	export default function WorkflowGraph({ trace, compact = false }) {
/bin/bash -lc "sed -n '1,280p' tests/test_v2_pipeline.py" in /home/carol/kmu_genai
                "term_credits": acc, "term_risk": "low", "notes": []}]}
        "term_credits": 3, "term_risk": "low", "notes": []}])
        "term_credits": 48, "term_risk": "low", "notes": []}])
        "term_credits": 3, "term_risk": "low", "notes": []}])
The above exception was the direct cause of the following exception:
The local `python` command is Python 3.8 here and cannot import this codebase’s `str | None` annotations, so I’m not relying on ad hoc execution. The findings below are from static trace through the checked files.
   375	        elif context.seasonal_semester_allowed:
**Findings**
1. **HIGH**: Total-credit-only shortfall can be falsely marked complete.  
   In [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:586), `run_planner()` returns `feasible=True` when `selected` is empty. But `build_unified_candidates()` never creates a candidate for pure `audit.total_gap` / 일반선택 shortage after hard areas are satisfied. Result: a student at 127/130 with all area minima satisfied gets “졸업요건을 모두 충족했습니다.”  
2. **HIGH**: Roadmap can schedule a course with an unmet prerequisite.  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:516) only defers a prerequisite if that prereq is also in the selected set. If a selected advanced course has a prereq that is neither completed nor selected, `_try_place()` proceeds and places it. The later “validation” in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:604) checks only caps and unplaced items, not prereqs.  
3. **HIGH**: Multiple convergence programs can double-subtract the same primary-major credits.  
   `_convergence_checks()` computes allocation independently per convergence program, then `compute_audit()` sums all `to_fusion_credits` in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268). If the same primary course overlaps two convergence programs, it can be assigned away from 전공 twice.  
4. **HIGH**: 2025 Future Mobility required-course roadmap credits are wrong.  
   `_required_meta()` only reads metadata for object entries, but 2025 required names are bare strings in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147). Missing required courses then default to `3.0` credits and unknown terms in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:424). This turns 1-credit `S-TEAM Class` and physics labs into 3-credit roadmap items.  
5. **HIGH**: Older Future Mobility transcripts are demoted from 전공 to 일반선택.  
6. **MEDIUM**: Convergence group checks ignore allocation caps.  
   `group_checks` are computed from all designated courses in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:161), before over-cap overlap is assigned to 제1전공/융합 in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:223). A group can show satisfied even when its credits were assigned to 제1전공 and should not count toward fusion group minimum.  
7. **MEDIUM**: Applied-year selection is internally inconsistent for 2024.  
   Required names use nearest-prior year in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42), but area requirements require exact year in [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:110). Since `requirements_by_year.json` only has 2023 [requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4), a 2024 Future Mobility student can get 2023 required names with 2025 area minima.  
8. **MEDIUM**: Risk capacity uses user-editable cap instead of statutory/profile cap.  
   [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62) uses `context.max_credits_per_term or 18`, while planner uses `regular_term_cap(profile.total_credits_min)`. A direct API request or edited UI value can understate/overstate capacity.  
9. **LOW**: 기초교양 필수 matching has substring false positives.  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:93) treats `key in taken_name` as completed. `글쓰기` can match unrelated longer course names.  
Verified fixes that look directionally correct: privacy no longer sends raw `student_id`, `feasible === null` renders orange, progress bars guard zero required values, and workflow nodes no longer include fake LLM/repair nodes. I did not run the test suite because the local `python` is 3.8 and fails importing this codebase’s `str | None` annotations.
===== /tmp/codex_r2_7.txt =====
./docs/graduation_center_spec_en.md:177:- `len(courses)` ≤ `max_courses_per_term` per term (credit cap only if a separate `max_credits_per_term` is configured); no seasonal term unless `seasonal_semester_allowed`
./docs/review_codex_adversarial.md:2774:./frontend/src/components/GraduationV2.jsx:225:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
./docs/review_codex_adversarial.md:5371:10. [graduation_center/v2/risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62) risk capacity uses `context.max_credits_per_term or 18`, not the applied profile’s `regular_term_cap(profile.total_credits_min)`. Since frontend always sends `max_credits_per_term` at [GraduationV2.jsx:245](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:245), stale/user-edited caps can flip feasibility and risk.  
./frontend/src/components/GraduationV2.jsx:212:    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
./frontend/src/components/GraduationV2.jsx:228:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
./frontend/src/components/GraduationV2.jsx:235:          const cap = progs[c.program_id]?.max_credits_per_term;
./frontend/src/components/GraduationV2.jsx:236:          return cap ? { ...c, max_credits_per_term: cap } : c;
./frontend/src/components/GraduationV2.jsx:253:      max_credits_per_term: Number(ctx.max_credits_per_term),
./frontend/src/components/GraduationV2.jsx:262:    const cap = programs[id]?.max_credits_per_term;
./frontend/src/components/GraduationV2.jsx:263:    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
./frontend/src/components/GraduationV2.jsx:445:              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
./graduation_center/v2/risk.py:62:    term_cap = float(context.max_credits_per_term or 18)
./graduation_center/v2/planner.py:13:    PREV_GPA_BONUS, SEASONAL_TERM_CAP, V2_DIR, load_catalog, regular_term_cap,
./graduation_center/v2/planner.py:76:    cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./graduation_center/v2/planner.py:136:    term_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./graduation_center/v2/planner.py:147:            "max_credits_per_term": term_cap,
./graduation_center/v2/planner.py:196:        "학기당 이수학점 상한(student_context.max_credits_per_term, 계절학기는 seasonal_credit_cap, "
./graduation_center/v2/planner.py:591:    reg_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
./graduation_center/v2/catalog.py:48:def regular_term_cap(total_credits_min: float) -> float:
**Findings**
1. **HIGH: 2024 미래모빌리티 요람이 섞입니다.**  
   [catalog.py:102](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102) uses exact-year only for `requirements_by_year`, so 2024 falls back to default/latest requirements. But [audit_v2.py:35](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:35) uses nearest-prior for required course names, so 2024 picks 2023 required names. Then [audit_v2.py:313](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313) relabels the profile as `2023 요람`, while area/total credits were not 2023. Data confirms only 2023 exists in [requirements_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:4), while required names have 2023/2025 in [required_names_by_year.json:4](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:4).  
   **Fix:** use the same year-resolution function for both requirements and required names, and set `applied_yoram` once from that resolved year. For 2024, either deliberately choose 2023 for both or block/mark unsupported.
2. **HIGH: multiple convergence programs can double-subtract the same primary course.**  
   [audit_v2.py:268](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268) sums `to_fusion_credits` across convergence checks without course identity. But AI빅데이터 overlaps with both 데이터사이언스융합 and 모빌리티데이터분석, with shared prefixes such as `00290`, `10263`, `11394`, `05896`, etc. A single 3-credit primary course can become `to_fusion` in both checks, then be subtracted twice from `major_effective` at [audit_v2.py:269](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:269). That creates false 전공 부족 and unnecessary roadmap courses.  
   **Fix:** make convergence allocation course-keyed globally. Track allocation per `(course_prefix, course_instance)` across all convergence programs, then compute primary earned from unique courses only once.
3. **HIGH: convergence group checks ignore allocation and cap.**  
   [audit_v2.py:160](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160) computes `group_earned` from all designated courses before applying duplicate caps or primary/fusion assignment. The unchanged `group_checks` are returned at [audit_v2.py:248](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:248), so a group can appear satisfied by courses later assigned to 제1전공 only. `risk.py` then trusts those stale group gaps at [risk.py:78](/home/carol/kmu_genai/graduation_center/v2/risk.py:78).  
   **Fix:** after allocation, recompute group earned from courses that count toward fusion: `dup` plus `fusion`, excluding `primary` only. Use those adjusted group checks for risk, roadmap, markdown, and frontend.
4. **HIGH: planner can generate a feasible roadmap with unmet prerequisites.**  
   `plan_greedy` only defers a prerequisite if that prerequisite is also in the selected set: [planner.py:513](/home/carol/kmu_genai/graduation_center/v2/planner.py:513)-[planner.py:517](/home/carol/kmu_genai/graduation_center/v2/planner.py:517). If a selected course has a prerequisite that is neither completed nor selected, it still gets placed. Example catalog data has `수리통계` requiring `0029011` at [catalog_ai_bigdata.json:261](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:261). Worse, `run_planner` no longer calls the stricter `validate_roadmap`; it only checks caps and `unplaced` at [planner.py:604](/home/carol/kmu_genai/graduation_center/v2/planner.py:604)-[planner.py:612](/home/carol/kmu_genai/graduation_center/v2/planner.py:612), then marks `feasible=True` at [planner.py:626](/home/carol/kmu_genai/graduation_center/v2/planner.py:626).  
   **Fix:** close prerequisite dependencies before selection, or mark any unmet prerequisite not in completed/earlier planned as `unplaced/prereq_unmet`. Re-run a real validator over deterministic plans.
5. **MEDIUM: legal term cap can be bypassed by user-editable frontend value.**  
   The frontend always sends `max_credits_per_term` as a number at [GraduationV2.jsx:253](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:253), and the input is user-editable at [GraduationV2.jsx:444](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444). Backend planner and overflow trust it directly at [planner.py:76](/home/carol/kmu_genai/graduation_center/v2/planner.py:76) and [planner.py:591](/home/carol/kmu_genai/graduation_center/v2/planner.py:591); risk also trusts it at [risk.py:62](/home/carol/kmu_genai/graduation_center/v2/risk.py:62). A user entering `24` can make an illegal roadmap look feasible.  
   **Fix:** compute legal cap from `regular_term_cap(profile.total_credits_min)` server-side and clamp user preference to `min(user_cap, legal_cap)`. Treat the input as a stricter personal preference, not an override of 제32조.
6. **MEDIUM: frontend 3-way convergence clicks desynchronize the page.**  
   `ConvergenceBlock` stores local assignment state at [GraduationV2.jsx:97](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:97) and recalculates only local `primaryCr/fusionCr` at [GraduationV2.jsx:101](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:101)-[GraduationV2.jsx:105](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:105). Clicking a 3-way button at [GraduationV2.jsx:181](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:181) does not update main area gauges [GraduationV2.jsx:581](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:581), risk chips [GraduationV2.jsx:557](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:557), remaining requirements [GraduationV2.jsx:654](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:654), or roadmap.  
   **Fix:** either make 3-way selection a backend input and rerun audit/risk/roadmap, or label it clearly as a local preview and do not present it as changing the actual diagnosis.
**Verified Fixed / Mostly Fixed**
`feasible === null` now renders orange, not green, at [GraduationV2.jsx:646](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:646). Workflow node names match the backend trace: backend emits `로드맵 배치`/`로드맵 검증` at [pipeline.py:75](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:75), and frontend NODES include them at [WorkflowGraph.jsx:18](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:18). `overflow=None` on feasible generated plans is correctly set at [planner.py:626](/home/carol/kmu_genai/graduation_center/v2/planner.py:626).
===== /tmp/codex_r2_8.txt =====
graduation_center/v2/audit_v2.py:277:    core_total_required = sum(float(overrides.get(a, core_min)) for a in gen_areas) or float(profile.area_min.get("핵심교양", 0))
graduation_center/v2/audit_v2.py:282:        req = core_total_required if area == "핵심교양" else float(profile.area_min.get(area, 0))
graduation_center/v2/audit_v2.py:326:        total_required=total_req,
Two fixed items look genuinely fixed: raw student ID is not sent, and the workflow graph nodes now match the deterministic pipeline. I’m now checking data-year selection and edge inputs because those are the easiest places for the demo to pass normal cases but fail a grader’s odd fixture.
   524	        for allow_seasonal in (False, True):
   531	                if not known and sem in ("S", "W") and not allow_seasonal:
   566	                               term_risk="medium" if used[lab] > cap - 3 else "low"))
   579	    overflow = project_overflow(audit, profile, context)
   598	                            assumptions=["현재 학기를 입력하면 학기별 배치를 제공합니다."], overflow=overflow),
   619	        ov = overflow or project_overflow(audit, profile, context)
   624	                           assumptions=assumptions, overflow=ov,
   629	                           why_this_plan=why, assumptions=assumptions, overflow=None)
/bin/bash -lc "nl -ba graduation_center/v2/pipeline.py | sed -n '48,85p'" in /home/carol/kmu_genai
    66	    if context.seasonal_semester_allowed:
   213	    seasonal_semester_allowed: true, gpa_min_met: "unknown",
I’m at the findings stage. The remaining high-risk problems are not cosmetic: prerequisite enforcement, global convergence allocation, and default credit caps can all flip demo outcomes from feasible to infeasible or vice versa.
   176	                    <span style={{ display: "inline-flex", border: `1px solid ${C.border}`, borderRadius: 6, overflow: "hidden" }}>
   186	                              cursor: wouldExceed ? "not-allowed" : "pointer", border: "none",
   159	      <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden", background: "#fff" }}>
**Findings**
1. **HIGH - Unmet prerequisites can be silently ignored.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:512) only defers a prerequisite when that prerequisite is also in the selected roadmap set. If the prereq is not completed and not selected, `_try_place()` proceeds and places the course anyway. `run_planner()` then only checks cap/unplaced errors, not prerequisites.  
2. **HIGH - Multiple convergence programs can double-subtract the same primary-major credits.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:265) computes each convergence program independently, then [line 268](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268) sums all `to_fusion_credits` and subtracts from primary major. Shipped catalogs overlap across both convergence programs, so the same physical course prefix can be allocated to fusion in multiple checks and subtracted twice.  
   Fix: implement one global allocation pass keyed by physical course/prefix across primary + all selected convergence programs. Each course’s allocation must be unique except allowed duplicate recognition within one cap.
3. **HIGH - Convergence group checks are cap/allocation-unaware and can falsely pass.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:160) builds `group_earned` from all designated courses before deciding whether overlap credits become duplicate, primary-only, or fusion-only. Risk and planner then consume those stale group gaps at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:78) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:431). A group can show satisfied even when its overlap courses were assigned to 제1전공.  
4. **HIGH - Default frontend credit cap overrides Article 32 incorrectly for 136-credit programs.**  
   Frontend initializes `max_credits_per_term: 18` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:212), `programs.json` has no per-program cap, and the payload always sends `Number(ctx.max_credits_per_term)` at [line 253](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:253). Backend therefore treats 18 as a user override, bypassing `regular_term_cap(136) == 19`.  
5. **HIGH - Year selection mixes 요람 years for 2024 미래모빌리티.**  
   Required-name data uses nearest-prior at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:300), but area minima use exact-only at [catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:110). Data has required names for 2023/2025 but area minima only for 2023. A 2024 student gets 2023 required courses with default/latest area minima, then [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313) labels it as 2023 요람.  
6. **MEDIUM - 2025 required-course roadmap metadata is mostly missing, causing wrong credits/terms.**  
   `_required_meta()` only reads object rows at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:391). The 2025 미래모빌리티 required list is strings at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147), so [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:424) falls back to 3 credits and both terms for labs/seminars.  
7. **MEDIUM - Risk capacity undercounts seasonal terms.**  
   [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:63) uses `remaining_semesters * term_cap`, then [line 66](/home/carol/kmu_genai/graduation_center/v2/risk.py:66) adds only one 6-credit seasonal term. The planner can schedule multiple seasonal terms across the remaining horizon. This can produce a D risk even when the roadmap can fit.  
8. **LOW - Workflow trace says validation passed when placement was skipped.**  
   For malformed/missing `current_term`, `run_planner()` returns `feasible=None` and `ValidationReport(ok=True)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:593). Pipeline then renders “로드맵 검증 통과” at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78). UI is orange, but workflow graph is misleadingly green.  
9. **LOW - Frontend convergence selector matches overlap courses by name only.**  
   [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:164) uses `findIndex((f) => f.name_ko === c.name_ko)`. Duplicate/renamed course names can bind the wrong overlap row.  
Verified fixes: raw student ID is not sent, `feasible === null` now renders orange, total progress has a zero-required guard, and workflow nodes no longer include false LLM/repair nodes.
===== /tmp/codex_r2_9.txt =====
frontend/src/components/GraduationV2.jsx:212:    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
frontend/src/components/GraduationV2.jsx:228:    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
frontend/src/components/GraduationV2.jsx:235:          const cap = progs[c.program_id]?.max_credits_per_term;
frontend/src/components/GraduationV2.jsx:236:          return cap ? { ...c, max_credits_per_term: cap } : c;
frontend/src/components/GraduationV2.jsx:253:      max_credits_per_term: Number(ctx.max_credits_per_term),
frontend/src/components/GraduationV2.jsx:262:    const cap = programs[id]?.max_credits_per_term;
frontend/src/components/GraduationV2.jsx:263:    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
frontend/src/components/GraduationV2.jsx:445:              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
graduation_center/v2/risk.py:62:    term_cap = float(context.max_credits_per_term or 18)
graduation_center/v2/catalog.py:48:def regular_term_cap(total_credits_min: float) -> float:
graduation_center/v2/catalog.py:60:def program_total_min(program_id: str) -> float | None:
graduation_center/v2/planner.py:13:    PREV_GPA_BONUS, SEASONAL_TERM_CAP, V2_DIR, load_catalog, regular_term_cap,
graduation_center/v2/planner.py:76:    cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
graduation_center/v2/planner.py:136:    term_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
graduation_center/v2/planner.py:147:            "max_credits_per_term": term_cap,
graduation_center/v2/planner.py:196:        "학기당 이수학점 상한(student_context.max_credits_per_term, 계절학기는 seasonal_credit_cap, "
graduation_center/v2/planner.py:591:    reg_cap = float(context.max_credits_per_term or regular_term_cap(profile.total_credits_min))
/bin/bash -lc "sed -n '180,260p' tests/test_v2_pipeline.py" in /home/carol/kmu_genai
The above exception was the direct cause of the following exception:
**Findings**
1. **HIGH - prerequisite validation is incomplete in the new deterministic planner**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:512): `_try_place()` only defers a prerequisite when that prerequisite is also in the selected candidate set. If a course has an unmet prerequisite that is neither completed nor selected, it is placed anyway. `run_planner()` then only checks term caps and `unplaced` items, not full prerequisite validity ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:604)).  
2. **HIGH - multiple convergence programs can corrupt first-major credits**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:138) treats overlap as “primary or any other declared program”, but [compute_audit](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:268) subtracts every program’s `to_fusion_credits` from the single `전공` area.  
3. **HIGH - convergence group checks are allocation-blind and can show false group satisfaction**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:161) builds `group_earned` from all designated courses before deciding whether overlap credits go to duplicate, primary, or fusion. The final `earned/gap` uses allocation, but `group_checks` does not ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:247)). Risk and planner then trust these group gaps ([risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:78), [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:431)).  
4. **HIGH - 2024 미래모빌리티 mixes different 요람 years and mislabels the result**  
   `requirements_by_year` has only 2023 for `mirae_mobility` ([requirements_by_year.json](/home/carol/kmu_genai/data/graduation/v2/requirements_by_year.json:5)), so 2024 falls back to latest/default requirements via exact-only lookup ([catalog.py](/home/carol/kmu_genai/graduation_center/v2/catalog.py:102)). But required names use nearest-prior, so 2024 picks 2023 ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:42)) and then overwrites the label to `2023 요람 (학번 2024 기준)` ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:313)).  
5. **MEDIUM - 2025 required course credits default to 3, causing wrong roadmap math**  
   2025 required names are bare strings, not `{name, credits, terms}` objects ([required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:147)). Planner then defaults every missing required course to 3 credits ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:421)).  
6. **MEDIUM - frontend convergence controls can diverge when catalog and transcript names differ**  
   Backend `courses_view` uses convergence catalog names ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:188)), while `overlap_courses` uses transcript names ([audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:215)). Frontend matches them by `name_ko` ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:163)).  
7. **MEDIUM - user-editable credit cap can violate Article 32 and understate risk**  
   Frontend says the cap is “수정 가능” ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:444)). Planner and risk both trust `context.max_credits_per_term` ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:591), [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:62)).  
8. **LOW - malformed `current_term` is treated as benign “missing” and validator passes**  
   `_ordered_terms()` returns `[]` on malformed labels ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:361)), and `run_planner()` returns `status="generated", feasible=None` with `ValidationReport(ok=True)` ([planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:593)).  
9. **LOW - blocked roadmap message renders twice**  
   Blocked status renders a red paragraph ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:639)) and `feasible === false` renders a second warning box ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:691)).  
**Verified Fixes**
Privacy frontend fix is correct for the normal UI path: `student_id` is stripped before request payload and only `admission_year`/`masked_student_id` are sent ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:245)). `feasible === null` is no longer green ([GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:646)). Workflow graph nodes now match the deterministic planner better ([WorkflowGraph.jsx](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:12), [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:75)).
