===== /tmp/codex_r5_0.txt =====
   329	                errors.append(ValidationError(code="bad_satisfies",
   330	                              detail=f"{c.name_ko} satisfies={c.satisfies}≠{cc['requirement_area']}", course_id=c.course_id))
   331	            if sem and sem not in cc["offered_terms"]:
   332	                errors.append(ValidationError(code="not_offered", detail=f"{c.name_ko} {t.term} 미개설", course_id=c.course_id))
   333	            # 선수과목: 이미 이수 or 앞 학기에 계획돼야 (같은 학기/뒤 학기 불가)
   334	            for pre in cc.get("prerequisites", []):
   335	                if pre not in completed and pre not in prior_planned:
   336	                    errors.append(ValidationError(code="prereq_unmet",
   337	                                  detail=f"{c.name_ko} 선수과목 미충족", course_id=c.course_id))
   338	            if any(sid not in src_ids for sid in c.source_ids):
   339	                errors.append(ValidationError(code="bad_source", detail=c.name_ko, course_id=c.course_id))
   340	            planned_by_area[cc["requirement_area"]] = planned_by_area.get(cc["requirement_area"], 0.0) + cc["credits"]
   341	        # term_credits는 카탈로그 학점 합과 일치해야
   342	        if abs(round(catalog_credit_sum, 1) - float(t.term_credits)) > 0.01:
   343	            errors.append(ValidationError(code="term_credits_mismatch", detail=f"{t.term} 학점합 불일치"))
   344	        prior_planned |= set(cur_term_ids)
   345	

**Findings**

HIGH [REGRESSION] Future shared 융합/전공 courses can create false 부족 or false unfillable.
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:462) builds 융합 부족 first, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:489) builds 전공 부족 later, then [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:524) uses one global `seen` set and skips duplicate names without crediting the later quota. That verifies round-4 “skip no-credit” narrowly, but it is still wrong for future courses that legally double-count under 제77조 cap. Example: 모빌리티데이터분석 has shared primary courses like `Python프로그래밍`, `자동차모빌리티기초`, `기초선형대수` in [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:45), [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:66), [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:187). If selected for 융합 first, they are unavailable to 전공 quota, even though up to 12 credits can satisfy both. This can make the grader see “전공 부족 미해소” or too many planned credits.
Fix: replace global `seen` quota accounting with a physical-course allocation model: place each course once, but allow `requirement_credits` to close multiple requirements up to `double_cap`; run unfillable after that allocation, not before it.

HIGH Demo environment currently cannot collect v2 tests.
`pytest tests/test_v2_pipeline.py -q` fails during collection under the repo’s current `python`/`pytest` with Pydantic unable to evaluate `str | None` from [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24). This is a live-demo blocker if the grader uses the advertised `pytest` command or this Python 3.8 environment.
Fix: either require Python 3.10+ explicitly and run the demo there, or convert annotations to `Optional[...]`/`Dict[...]`/`List[...]`, or add the needed `eval_type_backport` dependency for Pydantic.

MEDIUM [REGRESSION] Unfillable is correctly separated in the roadmap text, but the workflow trace still says 초과학기 필요.
[pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61) labels every blocked plan as `실현불가(초과학기 필요)`. But [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:724) explicitly says 후보 고갈 is “초과학기로 해결 불가”. In a blocked-by-pool-exhaustion case, the screen can show both “초과학기 필요” and “초과학기로 해결 불가”.
Fix: set `plan_branch` from `plan.overflow`: overflow present → `초과학기 필요`; only `pool_exhausted`/unfillable → `후보 없음(학과 확인)`.

MEDIUM 초과학기 count overestimates when 계절학기 is allowed.
The planner’s term capacity includes seasonal slots at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:375), but overflow divides remaining unplaced credits only by regular cap at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405). With 계절 허용, an extra regular semester can be accompanied by seasonal capacity, so `ceil(unplaced / reg_cap)` can show too many extra semesters.
Fix: make overflow use the same `_ordered_terms` capacity model for added semesters, or explicitly state overflow ignores future seasonal terms.

LOW [REGRESSION] Backend `to_fusion` dedup is fixed, frontend note is not.
Backend dedups by prefix in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292), but the UI sums per convergence check at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:591). With multiple convergence programs sharing the same physical course, the 전공 게이지 is deduped but the note can display a larger deducted credit number.
Fix: expose backend `to_fusion_total` or `to_fusion_course_credits` union and render that, not `sum(c.to_fusion_credits)`.

**Round-4 Fix Check**

1. Seen skip-no-credit: implemented, but incomplete for legal future double-recognition.  
2. `gap_not_closed`: implemented at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704).  
3. Seasonal risk capacity: implemented at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68).  
4. Required aliases: implemented in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175).  
5. 기초교양 only when gap > 0: implemented at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:500).  
6. Prereq soft flag: implemented in greedy planner, but old validator still hard-blocks at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:333).  
7. Overflow/unfillable split: backend planner fixed, workflow trace incomplete.  
8. `to_fusion` backend dedup fixed, frontend note incomplete.
===== /tmp/codex_r5_1.txt =====
    40	        s = pat.sub(rep, s)
    41	    s = s.lower()
    42	    # 공백·구두점·괄호 제거 (한글/영숫자만 남김)
    43	    s = re.sub(r"[^0-9a-z가-힣]", "", s)
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

**Findings**

1. **HIGH - 2023 capstone requirements can be shown as catalog-verified invented courses.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455) sets `known = bool(terms)`, then [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:456) emits the item as `catalog_verified` even when no catalog `hit` exists. For 2023 미래모빌리티, required names include `다학제간캡스톤디자인Ⅰ/Ⅱ` at 3 credits each in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133), while the current catalog only has unnumbered `다학제간캡스톤디자인` at 4 credits in [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:640). Since round 4 intentionally did not add `캡스톤Ⅰ/Ⅱ↔무번호`, the roadmap can present uncertain/non-current course names and wrong credits without `manual_check`.  
   Fix: only mark `catalog_verified` when a unique catalog course was matched. For required-meta-only items, use `confidence="name_only"`, `manual=True`, and show “현행 개설명/동등인정 확인 필요”; do not let them silently look catalog-backed.

2. **MEDIUM [REGRESSION] - `gap_not_closed` can be suppressed by an unrelated 융합전공 pool exhaustion.**  
   The area-coverage check in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:705) suppresses `gap_not_closed` if `g.area in u["label"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:706). A label like `모빌리티데이터분석융합전공 부족` contains `전공`, so an unfillable fusion requirement can hide an unresolved 제1전공 floor gap. The plan is still blocked by `pool_exhausted`, but the displayed blocked reason can omit the actual 전공 shortage.  
   Fix: store `area` in each `unfillable` entry at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:544), then suppress only on `u["area"] == g.area`, or simpler, always emit `gap_not_closed` alongside `pool_exhausted`.

3. **MEDIUM [REGRESSION] - backend deduped multi-convergence `to_fusion`, frontend display did not.**  
   Backend correctly dedups by course prefix in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). But the frontend note sums `c.to_fusion_credits` directly at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592), so with two convergence programs sharing the same course, the 전공 gauge can subtract the deduped value while the note says a larger number was excluded.  
   Fix: render the note from the union of `to_fusion_course_credits` prefixes, matching backend logic.

4. **MEDIUM - 3-way convergence controls create local numbers that do not update the rest of the screen.**  
   `ConvergenceBlock` recomputes `primaryCr`/`fusionCr` locally in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:103), but parent gauges, risk, remaining chips, and roadmap still use backend static `audit` values at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:589) and [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673). A grader changing a 3-way selection can see “둘 다 충족” inside the block while the global roadmap still plans a 부족분, or vice versa.  
   Fix: either make 3-way controls explicitly read-only/default allocation display, or lift allocation state and recompute all dependent gauges/remaining chips/roadmap via a backend recompute.

5. **LOW - prereq soft-flag is technically fixed but the course badge is misleading.**  
   Missing prereq not completed/not in pool is softened in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579) and assumptions mention 선수 확인 at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:637). But the frontend badge always says `개설학기 확인필요` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:698).  
   Fix: add a `manual_reason` field or distinct badges for `선수과목 확인필요`, `개설학기 확인필요`, and `이름기준 확인필요`.

**Round-4 Status**

Pass: 1, 3, 4 for required-name audit aliases, 5, 6 backend, 7.  
Partial/regression: 2 due label substring suppression; 8 backend fixed but frontend display still double-counts.  
Could not run executable scenario tests in this workspace because `python` is 3.8 with incompatible annotations, while `python3.10` lacks installed dependencies.
===== /tmp/codex_r5_10.txt =====
     2	uvicorn[standard]>=0.27.0
     3	pydantic>=2.6.0
     4	pytest>=8.0.0
     5	requests>=2.31.0
     6	beautifulsoup4>=4.12.0
     7	chromadb>=0.4.24
     8	openai>=1.68.0
     9	pdfplumber>=0.11.0
    10	pypdf>=5.0.0
    11	pillow>=10.0.0
    12	numpy>=1.26.0
    13	python-multipart>=0.0.9
    14	python-dotenv>=1.0.0
    15	openpyxl>=3.1.0
    16	xlrd>=2.0.1
    21	class TranscriptSummary(BaseModel):
    22	    """Sanitized transcript summary returned to the UI."""
    23	
    24	    masked_name: str | None = None
    25	    masked_student_id: str | None = None
    26	    department: str = Field(default="미확인", max_length=120)
    27	    admission_year: int | None = Field(default=None, ge=1900, le=2100)
    28	    total_credits: float = Field(default=0, ge=0, le=300)
    29	    category_credits: dict[str, float] = Field(default_factory=dict)
    30	    gpa_minimum_met: GpaMinimumStatus = "unknown"
    31	    courses: list[CourseSummary] = Field(default_factory=list, max_length=300)
    32	    parse_method: str = "text"
    33	    warnings: list[str] = Field(default_factory=list)

**Findings**

HIGH [REGRESSION #7] [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:724): `unfillable` correctly says “초과학기로 해결 불가”, but [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:729) still sets the hint to “잔여 학기를 늘리거나 계절학기를 활용하세요.” The frontend prints both, so the screen can literally say “초과학기로 해결 불가” and “학기를 늘리세요” in one blocked message.  
Fix: when `unfillable` exists and `ov is None`, set `relaxation_hint` to 학과 확인/후보 데이터 보강 only. Do not suggest extra semesters or seasonal terms for `pool_exhausted`.

HIGH [REGRESSION #4] Aliases are used for required-course audit, but not for roadmap candidate resolution. Audit accepts 2023 `미래모빌리티기초` via alias to `자동차모빌리티기초` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331), [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:337), with aliases in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175). But planner only looks up the raw missing name in `cat["by_norm"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445), so missing `미래모빌리티기초` / `미래모빌리티AD` becomes an old-name, empty-code roadmap item even though current catalog rows exist at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:94) and [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:236).  
Fix: planner required-item lookup must try alias normalized names too, and emit the current catalog course id/name while noting the 요람 name if needed.

MEDIUM [REGRESSION #8 frontend] Backend dedups multi-convergence `to_fusion` subtraction by prefix at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292), but the frontend note sums per-program `to_fusion_credits` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592). With two convergence programs sharing the same physical course, the 전공 gauge uses deduped subtraction while the note can show a larger excluded-credit number.  
Fix: expose backend `to_fusion_total`, or in React union `to_fusion_course_credits` keys before summing.

MEDIUM [frontend] Blocked roadmap text is rendered twice. `status === "blocked"` prints at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655), then `feasible === false && blocked_reason` prints the same blocker again at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707). In a live demo, any blocked/partial plan looks noisy and contradictory.  
Fix: keep one blocked banner; make the second block `audit.roadmap.status !== "blocked"` or remove it.

LOW verification blocker: `pytest tests/test_v2_pipeline.py -q` does not collect under current `python` 3.8.5 because Pydantic evaluates `str | None` annotations, while [requirements.txt](/home/carol/kmu_genai/requirements.txt:3) does not require Python >=3.10 or `eval_type_backport`. `python3.10` exists but has no pytest installed.  
Fix: pin demo/test runtime to Python >=3.10 and document it, or add `eval_type_backport`.

**Round-4 Status**

Verified: #1, #2, #3, #5, #6 are present in the live deterministic planner path.  
Partial/regressed: #4 audit-only alias use, #7 contradictory unfillable hint, #8 backend dedup present but frontend display still sums duplicates.
===== /tmp/codex_r5_11.txt =====
   318	        "doc": "2025-2 교육과정 교과목코드 현황",
   319	        "dept": "AI빅데이터융합경영학과"
   320	      }
   321	    },
   322	    {
   323	      "course_id": "0155708",
   324	      "name_ko": "선형대수",
   325	      "name_norm": "선형대수",
   326	      "aliases": [],
   327	      "credits": 3.0,
   328	      "requirement_area": "전공",
   329	      "is_required": false,
   330	      "prerequisites": [],
   331	      "prereq_external": [],
   332	      "grade_level": 2,
   333	      "offered_terms": [
   334	        "2"
   335	      ],
   336	      "group": null,

**Findings**

1. **HIGH [REGRESSION] Alias fix is audit-only; planner can schedule obsolete required names and double-plan their current aliases.**  
   [required_names_by_year.json:42](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:42) lists 2023 `미래모빌리티기초`, while the current catalog has `자동차모빌리티기초` at [catalog_mirae_mobility.json:94](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:94), with aliases declared at [required_names_by_year.json:175](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175). Audit uses those aliases at [audit_v2.py:331](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331), but planner only looks up the raw missing name in `cat["by_norm"]` at [planner.py:445](/home/carol/kmu_genai/graduation_center/v2/planner.py:445). If no raw hit exists, it emits a “catalog_verified” name-only item with empty `course_id` at [planner.py:456](/home/carol/kmu_genai/graduation_center/v2/planner.py:456).  
   Why this matters: a 2023 미래모빌리티 demo can show `미래모빌리티기초`/`미래모빌리티AD`/`미래모빌리티실험` as plan courses even though the available catalog courses are renamed. Worse, dedup is by raw normalized name at [planner.py:536](/home/carol/kmu_genai/graduation_center/v2/planner.py:536), so the later convergence pool can still select `자동차모빌리티기초` as a second physical course.  
   Fix: build a canonical alias resolver shared by audit and planner. When a missing required name has an alias that exists in the current catalog, fill `course_id`, current `name_ko`, credits, terms, prerequisites from that catalog course, and dedupe by `course_id`/canonical alias group, not only raw name.

2. **HIGH [REGRESSION] Candidate-exhaustion messaging still contradicts itself.**  
   Planner correctly keeps unfillable pool exhaustion separate from overflow at [planner.py:719](/home/carol/kmu_genai/graduation_center/v2/planner.py:719), and says “초과학기로 해결 불가” in `blocked_reason` at [planner.py:725](/home/carol/kmu_genai/graduation_center/v2/planner.py:725). But if there is no `ov`, it still sets `relaxation_hint` to “잔여 학기를 늘리거나 계절학기를 활용하세요” at [planner.py:729](/home/carol/kmu_genai/graduation_center/v2/planner.py:729). The frontend prints both strings together at [GraduationV2.jsx:655](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655).  
   Why this matters: the screen can literally say “초과학기로 해결 불가” and “학기를 늘리세요” in one sentence.  
   Fix: if `unfillable` exists and `unplaced` is empty, set the hint to “후보 데이터 없음: 학과 확인/수동 계획 필요”. If both exist, split hints by cause.

3. **HIGH Required-name and name-fallback matching can clear primary-major requirements with the wrong physical course.**  
   `match_course()` falls back to unique name matching after a code miss at [catalog.py:166](/home/carol/kmu_genai/graduation_center/v2/catalog.py:166), and `compute_audit()` treats required names as taken by normalized name across all confirmed courses at [audit_v2.py:330](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:330). Current data has same-name/different-code cases: AI `0365007 S-TEAM Class` at [catalog_ai_bigdata.json:98](/home/carol/kmu_genai/data/graduation/v2/catalog_ai_bigdata.json:98) versus 미래모빌리티 `1621601 S-TEAM Class` at [catalog_mirae_mobility.json:114](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:114). It also has required `다학제간캡스톤디자인` and non-required `다학제간캡스톤디자인+` sharing `name_norm` at [catalog_mirae_mobility.json:639](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639) and [catalog_mirae_mobility.json:781](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781).  
   Why this matters: violates “전공=해당전공 과목만” and can hide a missing 필수지정 course.  
   Fix: if a transcript has a nonempty course code that is not in the selected primary catalog, do not promote it to primary-major by name unless a curated equivalence table says that code/name is the same physical course. For required-name checks, prefer exact primary catalog code or curated alias/equivalence; do not let normalized punctuation stripping make `+` courses satisfy non-`+` required courses.

4. **MEDIUM [REGRESSION] Backend dedups multi-convergence `to_fusion`, but the frontend note still sums duplicates.**  
   Backend now dedups `to_fusion_course_credits` by course prefix at [audit_v2.py:292](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). The frontend note, however, sums `c.to_fusion_credits` across checks at [GraduationV2.jsx:592](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592).  
   Why this matters: with two convergence programs, the 전공 gauge can be based on deduped subtraction while the explanatory note says a larger number was excluded.  
   Fix: expose `to_fusion_total_dedup` from the backend, or have the frontend union `to_fusion_course_credits` keys and sum that union.

5. **MEDIUM The 3-way convergence selector creates local-only numbers that do not update audit, roadmap, or risk.**  
   `ConvergenceBlock` recomputes `primaryCr`/`fusionCr` in local React state at [GraduationV2.jsx:100](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), then displays pass/fail text at [GraduationV2.jsx:139](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:139). But the area gauges, roadmap, risk, and backend allocation remain unchanged.  
   Why this matters: a grader can click a 3-way option and see the convergence block say one thing while the 전공 gauge and roadmap still reflect the original backend allocation.  
   Fix: either make the selector read-only for the prototype, or send assignment overrides back through audit/planner and recompute the whole response.

**Round-4 Verification Summary**

Fixes 1, 2, 3, 5, 6, and the backend part of 8 are present in the live code. Fix 4 is incomplete because aliases are not used by planner candidate resolution. Fix 7 is numerically improved, but the remaining hint text still contradicts the “초과학기로 해결 불가” message.
===== /tmp/codex_r5_12.txt =====
    76	            core_area=m.core_area,
    77	            term_label=ln.term_label,
    78	            included=included,
    79	            exclude_reason=reason,
    80	            aggregate_only=(m.status == "aggregate_only"),
    81	        ))

exec
/bin/bash -lc "nl -ba graduation_center/v2/verification.py | sed -n '17,31p'" in /home/carol/kmu_genai
 succeeded in 0ms:
    17	def _term_order(label: str) -> tuple[int, int]:
    18	    """학기 라벨('2023학년도 1학기'/'하계'/'동계') → 정렬 키. 클수록 최신."""
    19	    m = re.search(r"(\d{4})", label or "")
    20	    year = int(m.group(1)) if m else 0
    21	    if "1학기" in label:
    22	        sem = 1
    23	    elif "하계" in label:
    24	        sem = 2
    25	    elif "2학기" in label:
    26	        sem = 3
    27	    elif "동계" in label:
    28	        sem = 4
    29	    else:
    30	        sem = 0
    31	    return (year, sem)

**Findings**

HIGH: same-name, different-code courses can be counted as the primary major and clear required courses.
[file](/home/carol/kmu_genai/graduation_center/v2/catalog.py:165) promotes any unique normalized name match to `matched`, even when the uploaded code did not match the primary catalog. Then [verification.py](/home/carol/kmu_genai/graduation_center/v2/verification.py:54) treats it as `전공`, and [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:330) checks required names against all confirmed courses. Result: a 타과/일반선택/double-major `Python프로그래밍` with a different code can inflate 전공 and erase `필수지정` gaps. This violates “전공=해당전공 과목만.”
Fix: only allow name fallback as primary when `raw.area_raw` is clearly primary-major 전공 and not 다전공/부전공/융합/연계/일반선택; otherwise return `aggregate_only`. Also filter required-name satisfaction to confirmed primary-major courses, preferably `requirement_area == "전공" and not aggregate_only`.

MEDIUM [REGRESSION]: prereq softening is only in greedy placement, not in the remaining validator.
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:333) still emits hard `prereq_unmet` whenever a prereq is neither completed nor prior planned. The round-4 soft behavior exists separately in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579), but `validate_roadmap()` is now inconsistent with `run_planner()`.
Fix: in `validate_roadmap`, treat prereqs absent from both completed and candidate pool as warning/manual-check, not `ValidationError`; keep hard errors only when the prereq is in-plan/candidate but ordered incorrectly or omitted.

MEDIUM [REGRESSION]: backend dedupes multi-convergence `to_fusion`, frontend displays the non-deduped sum.
Backend correctly dedupes by prefix in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292), but the UI note sums `to_fusion_credits` per convergence check at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592). With two convergence programs sharing the same physical course, the 전공 gauge subtracts 3 but the note can say 6.
Fix: expose `to_fusion_total` / `major_deduction_credits` from `AuditResult`, or union `to_fusion_course_credits` keys in the frontend before summing.

LOW: retake “latest term” is order-sensitive for common `YYYY-1` / filename-style labels.
[verification.py](/home/carol/kmu_genai/graduation_center/v2/verification.py:17) only recognizes Korean labels like `1학기`, `2학기`, `하계`, `동계`; labels like `2025-1` fall to semester `0`. Duplicate-code inclusion can then depend on upload/file order.
Fix: extend `_term_order()` to parse `YYYY-1`, `YYYY-S`, `YYYY-2`, `YYYY-W` before the Korean substring checks.

**Round-4 Status**

Verified OK: 1, 2, 3, 4, 5, 7, and backend side of 8.  
Incomplete/regression: 6 in `validate_roadmap`; frontend side of 8.

I attempted `pytest tests/test_v2_pipeline.py -q`, but collection fails in this environment on Python 3.8/Pydantic annotation evaluation for `str | None`. So tests did not run.
===== /tmp/codex_r5_13.txt =====
   282	    convergence_program_ids=(), convergence_tracks=None,
   283	) -> AuditResult:
   284	    earned = verified.earned_by_area
   285	    # 연계융합 배정을 먼저 계산 — 겹침학점 중 '융합으로 배정'된 분은 제1전공(전공)에서 차감해
   286	    # 이중집계를 막고 전공/융합/risk를 한 배정으로 정합. (배정은 _convergence_checks가 결정론 산출)
   287	    conv_checks = _convergence_checks(verified, convergence_program_ids, convergence_tracks,
   288	                                      profile.program_id, float(profile.area_min.get("전공", 0)),
   289	                                      float(earned.get("전공", 0)))
   290	    # 다중 융합 선언 시 같은 물리 과목이 두 프로그램에서 to_fusion으로 잡혀 이중 차감되지 않게
   291	    # 과목(앞5자리) 단위로 dedup해 전공 차감(라운드3·4 지적)
   292	    to_fusion_by_course: dict = {}
   293	    for cc in conv_checks:
   294	        for pfx, cr in (cc.get("to_fusion_course_credits") or {}).items():
   295	            to_fusion_by_course[pfx] = cr
   296	    to_fusion_total = round(sum(to_fusion_by_course.values()), 1)
   297	    major_effective = max(0.0, round(float(earned.get("전공", 0)) - to_fusion_total, 1))
   298	
   299	    # 핵심교양 영역별 최저(별표5 단과대 override 반영 — 예: 미래모빌리티 소통 5)
   300	    gen = load_gen_ed().get("core_liberal", {})

exec
/bin/bash -lc 'python3.10 -m pytest tests/test_v2_pipeline.py -q' in /home/carol/kmu_genai
 exited 1 in 0ms:
/usr/bin/python3.10: No module named pytest

**Findings**

1. **HIGH - demo command currently fails under default Python**
   [requirements.txt](/home/carol/kmu_genai/requirements.txt:1) does not declare Python >=3.10, but models use `str | None` syntax such as [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24). In this workspace `python`/`python3` are 3.8.5, and `python -m pytest tests/test_v2_pipeline.py -q` fails during collection before v2 runs.
   Fix: pin `python_requires >=3.10` / add `.python-version`, or rewrite annotations to `Optional[...]`/`List[...]`; install pytest in the actual 3.10 demo env.

2. **HIGH - risk capacity trigger still uses only `total_gap`, not actual remaining obligations**
   [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:26) sets `gap = audit.total_gap`, then capacity is checked only against that at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:72). But planner obligations include area/convergence/core/basic/general candidates and only subtract selected credits from total gap at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:546). A student with enough total credits but remaining 전공/융합/core obligations can show a blocked/overflow roadmap while risk lacks the matching 잔여학기 capacity reason.
   Fix: compute risk capacity from the same remaining-credit model as `build_unified_candidates`, or pass planner `unplaced/overflow.shortfall_credits` into `compute_risk`; avoid double-counting severity.

3. **MEDIUM [REGRESSION #8 - UI incomplete] - multi-convergence 전공 차감 note can show the old double-counted number**
   Backend dedupes `to_fusion_course_credits` by prefix at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292), but the frontend note sums per-program `to_fusion_credits` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592). With two convergence programs sharing the same physical course, the 전공 gauge is deduped but the note says more credits were excluded.
   Fix: expose `to_fusion_total_deduped` from backend, or send the prefix map and union it in UI.

4. **MEDIUM [REGRESSION #6 - UI incomplete] - prereq soft flag is mislabeled as 개설학기 확인**
   Planner correctly soft-flags missing prereqs at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:581), but the course chip renders every `manual_check` as `개설학기 확인필요` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:698). That contradicts the assumption text “선수과목 이수 여부 확인 필요.”
   Fix: add `manual_reason`/`warnings` to `RoadmapCourse`, render “선수과목 확인필요” separately.

5. **LOW - blocked roadmap reason is printed twice**
   The roadmap card prints `blocked_reason` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) and again at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707). In a blocked partial-plan demo, this looks like duplicate warnings or two separate failures.
   Fix: keep one blocked banner; use the lower one only when partial terms are shown, or remove line 655.

**Round-4 Check**

Backend fixes 1, 2, 3, 4, 5, 6, 7, and 8 are mostly present in the live deterministic path. The remaining regressions are UI/reporting consistency around #6 and #8, plus risk capacity still not using the same obligation model as the planner.
===== /tmp/codex_r5_14.txt =====
     6	beautifulsoup4>=4.12.0
     7	chromadb>=0.4.24
     8	openai>=1.68.0
     9	pdfplumber>=0.11.0
    10	pypdf>=5.0.0
    11	pillow>=10.0.0
    12	numpy>=1.26.0
    13	python-multipart>=0.0.9
    14	python-dotenv>=1.0.0
    15	openpyxl>=3.1.0
    16	xlrd>=2.0.1

I have enough to rank the remaining risks. The major issues are not that the round-4 backend patches are absent; they are that the fixes are only applied in some paths, while the UI and alias-planning paths can still produce contradictory numbers.
  ✓ Inspect backend graduation v2 files and data shapes
  ✓ Verify each round-4 fix explicitly
  ✓ Review frontend GraduationV2/WorkflowGraph rendering edges
  → Rank findings with file:line fixes
**Findings**

HIGH - Demo may not start under documented commands.  
`pytest tests/test_v2_pipeline.py -q` fails during collection on this workspace’s Python 3.8 because Pydantic evaluates `str | None`. The README/AGENTS command says only `pip install -r requirements.txt`; [requirements.txt](/home/carol/kmu_genai/requirements.txt:1) does not pin Python or include `eval_type_backport`, while [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24) uses 3.10 union syntax.  
Fix: pin Python `>=3.10` explicitly in docs/runtime, or make annotations 3.8-compatible/add `eval_type_backport`.

HIGH - [REGRESSION] Alias fix is incomplete in planner dedup, so 2023 미래모빌리티 can plan the same physical course twice.  
Aliases exist in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175), and audit uses them for taken detection in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331). But planner builds missing required items by raw required name and only exact normalized-name dedups candidates in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:527). A missing `미래모빌리티기초` can coexist with convergence candidate `자동차모빌리티기초`, then both get selected/credited. Same risk for `미래모빌리티AD`.  
Fix: canonicalize candidate identity by course id/prefix plus alias groups, and resolve required-name aliases to catalog entries before selection.

HIGH - Frontend audits stale context after verification.  
`runAudit` posts `verify.context`, not the current form state, in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:328). If a grader changes 남은 학기, 성적우수, 평점, or adds 모빌리티데이터분석 after running verify, the screen inputs say one thing while audit/risk/roadmap use the old values.  
Fix: either invalidate verification when audit-affecting fields change, or merge current `contextPayload()` into audit while preventing primary-program changes without re-verify.

HIGH - 3-way controls locally change StatBoxes but not the rest of the report.  
The 3-way state is local to `ConvergenceBlock` in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100), and only recomputes local `primaryCr/fusionCr` in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:103). Global gauges, 차감설명, 남은요건, risk, and roadmap still use backend defaults in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:589) and [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:668). A clicked 3-way can make the screen contradict itself.  
Fix: lift allocation state and recompute audit/roadmap server-side, or label 3-way as isolated simulation and keep global claims unchanged.

MEDIUM - [REGRESSION] Backend deduped `to_fusion`, frontend note re-double-counts it.  
Backend subtracts by course-prefix union in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). Frontend displays 차감설명 by summing scalar `cc.to_fusion_credits` across programs in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592), so multi-convergence can show a larger excluded-credit explanation than the major gauge actually used.  
Fix: sum the union of `to_fusion_course_credits` maps on the frontend, or have backend expose one deduped display number.

MEDIUM - Group-gap suggestions disappear when total fusion credits are enough.  
Frontend only builds 추가 이수 suggestions when `fusionGap > 0` in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:117), but it can warn on group shortfall separately in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144). Result: “그룹별 최저 미충족” with no suggested courses.  
Fix: trigger suggestions when `fusionGap > 0 || shortGroups.size > 0`, and accumulate per-group gaps.

LOW - Blocked roadmap reason renders twice.  
Blocked text is printed once at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) and again at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707). In overflow cases this makes the card noisy and easier to misread.  
Fix: keep one blocked summary, then the overflow card.

**Round-4 Verification**

Exact-name seen-dedup, area `gap_not_closed`, seasonal risk capacity, 기초교양 gap gating, deterministic prereq soft flag, unplaced-only overflow, and backend `to_fusion` union are present. The two incomplete hardening points are alias-aware planner dedup and frontend display consistency for `to_fusion`/3-way state.
===== /tmp/codex_r5_15.txt =====
   404	        return None
   405	    cap = float(reg_cap)
   406	    extra = int(math.ceil(unplaced_credits / cap)) if cap > 0 else 0
   407	    total_needed = context.remaining_semesters + extra
   408	    return OverflowScenario(
   409	        shortfall_credits=round(unplaced_credits, 1), per_term_credit_cap=cap,
   410	        remaining_semesters=context.remaining_semesters, total_semesters_needed=total_needed,
   411	        extra_semesters=extra, projected_graduation_term=_nth_regular_term(context.current_term, total_needed),
   412	        note=f"잔여 {context.remaining_semesters}학기에 다 배치하지 못한 {unplaced_credits:.0f}학점 → "
   413	             f"초과학기 약 {extra}학기 추가 필요(총 {total_needed}학기).")

exec
/bin/bash -lc "nl -ba graduation_center/v2/risk.py | sed -n '60,75p'" in /home/carol/kmu_genai
 succeeded in 0ms:
    60	    # 잔여학기 수용량(결정론): 학사규정 제32조 학기당 이수학점 상한 기반
    61	    # 사용자 override는 법정 상한(졸업학점 기반) 이내로 클램프 (계절 6, 직전 3.75↑ +3 한 번)
    62	    from graduation_center.v2.catalog import regular_term_cap
    63	    legal = regular_term_cap(audit.total_required)
    64	    term_cap = min(float(context.max_credits_per_term or legal), legal)
    65	    capacity = context.remaining_semesters * term_cap
    66	    if context.prev_term_gpa_ge_375:
    67	        capacity += PREV_GPA_BONUS
    68	    if context.seasonal_semester_allowed:
    69	        # 플래너(_ordered_terms)와 동일 모델: 정규학기마다 계절학기 1개 — 1회(+6)만 더하면
    70	        # 플래너 feasible인데 risk D가 뜨는 모순(라운드4 검증)
    71	        capacity += context.remaining_semesters * SEASONAL_TERM_CAP
    72	    if gap > 0 and capacity > 0 and gap > capacity:
    73	        grade = _worse(grade, "D")
    74	        reasons.append(RiskReason(factor="잔여학기",
    75	                      detail=f"부족 {gap:.0f}학점 > 잔여 {context.remaining_semesters}학기 수용량(~{capacity:.0f})", severity=20))

No HIGH findings. Round-4 backend fixes mostly hold. The remaining demo risks are display/state mismatches that can show a wrong number or a graph node that never actually ran.

**MEDIUM [REGRESSION] Multi-convergence deduction is deduped in backend, but the UI note still double-counts it.**  
[file](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292) correctly unions `to_fusion_course_credits` by course prefix before subtracting from 전공. But [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592) displays `sum(c.to_fusion_credits)`, which is not deduped. With two convergence programs sharing the same physical course, the 전공 gauge is correct but the explanatory note says the wrong excluded 학점.  
Fix: in the frontend, sum the union of `cc.to_fusion_course_credits` maps, or expose `to_fusion_total_dedup` from backend and render only that.

**MEDIUM: 3-way convergence toggles can contradict the audited/risk/roadmap numbers.**  
[GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:103) recomputes `primaryCr`/`fusionCr` locally from `sel`, and [line 140](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:140) can say “현재 배정으로 ... 충족”. But the area gauges, risk, remaining requirements, and roadmap still use the server’s original default allocation from [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:213). A grader clicking the toggles can make the convergence panel say one thing while the rest of the screen says another.  
Fix: either make the 3-way selector explicitly read-only/what-if, or send selected assignments back through audit and recompute audit/risk/roadmap.

**MEDIUM: Overflow extra-semester count uses a different capacity model than planner/risk.**  
Planner adds seasonal capacity when allowed at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:375), and risk does the same at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68). But overflow converts unplaced credits to extra semesters using only regular cap at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405). If 계절 허용 is on, blocked plans can overstate “초과학기 약 N학기”.  
Fix: compute extra regular semesters with the same marginal capacity model as planner: `reg_cap + SEASONAL_TERM_CAP` per added regular semester when seasonal is allowed.

**LOW: WorkflowGraph has a synthetic `리포트` node that is not in backend trace.**  
Backend emits trace through `리스크 산정` only at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:68). The graph hardcodes `리포트` at [WorkflowGraph.jsx](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:21) and appends it at [line 37](/home/carol/kmu_genai/frontend/src/components/WorkflowGraph.jsx:37). This violates NODES/trace consistency and makes a node light up without summary/status.  
Fix: either emit a real `NodeTraceEvent(node="리포트")` after markdown assembly, or remove the synthetic node.

Round-4 verification: #1, #2, #3, #4, #5, #6, #7 are present in backend. #8 is backend-correct but frontend-incomplete as noted above.
===== /tmp/codex_r5_16.txt =====
    from graduation_center.models import GraduationAnalysisResponse, TranscriptSummary
graduation_center/models.py:21: in <module>
    class TranscriptSummary(BaseModel):
../exit/lib/python3.8/site-packages/pydantic/_internal/_model_construction.py:219: in __new__
    set_model_fields(cls, bases, config_wrapper, ns_resolver)
../exit/lib/python3.8/site-packages/pydantic/_internal/_model_construction.py:537: in set_model_fields
    fields, class_vars = collect_model_fields(cls, bases, config_wrapper, ns_resolver, typevars_map=typevars_map)
../exit/lib/python3.8/site-packages/pydantic/_internal/_fields.py:112: in collect_model_fields
    type_hints = _typing_extra.get_model_type_hints(cls, ns_resolver=ns_resolver)
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:509: in get_model_type_hints
    hints[name] = try_eval_type(value, globalns, localns)
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:558: in try_eval_type
    return eval_type_backport(value, globalns, localns), True
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:609: in eval_type_backport
    return _eval_type_backport(value, globalns, localns, type_params)
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:641: in _eval_type_backport
    raise TypeError(
E   TypeError: Unable to evaluate type annotation 'str | None'. If you are making use of the new typing syntax (unions using `|` since Python 3.10 or builtins subscripting since Python 3.9), you should either replace the use of new syntax with the existing `typing` constructs or install the `eval_type_backport` package.
=========================== short test summary info ============================
ERROR tests/test_v2_pipeline.py - TypeError: Unable to evaluate type annotati...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.40s ===============================

**Findings**

1. **HIGH [REGRESSION] Round-4 #7: `pool_exhausted` is still surfaced as “use extra semester.”**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:726) correctly says 후보 없음 is “초과학기로 해결 불가”, but [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:729) sets the fallback hint to “잔여 학기를 늘리거나 계절학기를 활용하세요.” The UI and markdown print both together at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) and [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:123). The workflow trace also labels every blocked plan as “초과학기 필요” / “미배치 → 초과학기” at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61) and [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:81).  
   **Fix:** branch on validation codes. `unplaced` gets overflow/extra-semester hint; `pool_exhausted` gets “후보 데이터 없음/학과 확인 필요”; mixed cases must show both separately. Do not use the generic extra-semester hint when `unplaced_cr == 0`.

2. **HIGH: 2023 capstone uncertainty can still become a confident, wrong roadmap.**  
   2023 요람 has `다학제간캡스톤디자인Ⅰ/Ⅱ` as 3+3 credits at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:132), while the current catalog only has unnumbered `다학제간캡스톤디자인` as 4 credits at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:638). The aliases intentionally do not equate these at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170). But [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455) marks any required-name item with year-file `terms` as `catalog_verified` and `manual=False`, even when no current catalog hit exists. A 2023 미래모빌리티 demo can therefore recommend old numbered capstones as if current offering/equivalence is verified.  
   **Fix:** only set `catalog_verified` when `hit` resolves to current catalog. If no hit, keep `name_only`, `manual=True`, and label “대체/개설 확인 필요”; optionally make unresolved capstone requirements `pool_exhausted` instead of confidently scheduling them.

3. **MEDIUM [REGRESSION] Round-4 #8 backend dedup is not reflected in the UI note.**  
   Backend dedups `to_fusion_course_credits` by prefix before subtracting from 전공 at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). The frontend note instead sums each convergence block’s scalar `to_fusion_credits` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592), so multi-convergence can display a larger excluded-credit number than the actual 전공 gauge subtraction.  
   **Fix:** expose `to_fusion_total` from the audit, or compute a client-side union from `to_fusion_course_credits` prefixes.

4. **MEDIUM: multi-convergence overlap math can subtract non-primary overlaps from 제1전공.**  
   For each convergence program, `other_prefixes` includes primary plus every other declared convergence at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:137). Then all such overlaps are subtracted from `primary_major_earned` at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:207). If two convergence programs overlap with each other on a course that is not actually a first-major course, the “제1전공 전공” number is wrong.  
   **Fix:** split overlap classes: `primary_overlap_prefixes` vs `other_convergence_overlap_prefixes`. Only primary overlaps should affect `primary_base`/`primary_effective`.

5. **LOW [INCOMPLETE] Round-4 #6 soft prereq is only fixed in the active greedy planner.**  
   Active `plan_greedy` soft-flags orphan prereqs at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579), but legacy `validate_roadmap` still hard-errors `prereq_unmet` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:333). If the LLM path is re-enabled, behavior regresses.  
   **Fix:** mirror the soft/manual-check semantics in `validate_roadmap`, or delete/guard the legacy path.

**Round-4 Verification**

#1, #2, #3, #4, #5, and the active-path part of #6 are implemented. #7 is internally split but regresses in hint/trace/markdown. #8 is correct in backend subtraction but regresses in frontend display.

Test note: `pytest tests/test_v2_pipeline.py` did not collect because the environment is Python 3.8 and the repo uses `str | None` annotations without `eval_type_backport`.
===== /tmp/codex_r5_17.txt =====

The local test run does not get past collection on this machine: Python is 3.8.5 and Pydantic cannot evaluate the project’s `| None` annotations; FastAPI is also missing for API tests. I’ll include that as a demo-readiness crash risk unless the deployment is explicitly pinned to Python 3.10+.
exec
/bin/bash -lc "nl -ba requirements.txt | sed -n '1,80p'" in /home/carol/kmu_genai
 succeeded in 0ms:
     1	fastapi>=0.110.0
     2	uvicorn[standard]>=0.27.0
     3	pydantic>=2.6.0
     4	pytest>=8.0.0
     5	requests>=2.31.0
     6	beautifulsoup4>=4.12.0
     7	chromadb>=0.4.24
     8	openai>=1.68.0
     9	pdfplumber>=0.11.0
    10	pypdf>=5.0.0
    11	pillow>=10.0.0
    12	numpy>=1.26.0
    13	python-multipart>=0.0.9
    14	python-dotenv>=1.0.0
    15	openpyxl>=3.1.0
    16	xlrd>=2.0.1

**Round-4 Verification**
Round-4 fixes 1, 2, 3, 4, 5, and 7 look implemented in the reviewed code. Fix 6 is incomplete. Fix 8 is backend-correct but frontend display is still not deduped.

**Findings**

1. **HIGH — demo can fail at import/test collection under current Python 3.8**
   [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24) and [graduation_center/v2/models_v2.py](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:20) use `str | None`, `list[...]`, etc. The local `python` is 3.8.5, and `pytest tests/test_v2_pipeline.py -q` fails during collection because Pydantic cannot evaluate `str | None`.
   Fix: pin runtime to Python >=3.10/3.11 in project metadata/deploy docs, or convert annotations to `Optional[...]`/`List[...]` and add `eval_type_backport` if staying on 3.8.

2. **HIGH — 0/negative max credits produces wrong capacity and impossible overflow numbers**
   [models_v2.py](/home/carol/kmu_genai/graduation_center/v2/models_v2.py:25) allows any float for `max_credits_per_term`. [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:654) treats `0` as “use legal cap” because of `or`, while negative values become negative caps. Then [_overflow_from_credits](/home/carol/kmu_genai/graduation_center/v2/planner.py:405) can report `extra=0` even with unplaced credits, and [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:64) can skip capacity risk because capacity is negative.
   Fix: `max_credits_per_term: float | None = Field(default=None, gt=0)`, clamp with `if value is not None`, and reject invalid UI/API input with 422.

3. **MEDIUM [REGRESSION] — round-4 #8 dedup is not reflected in frontend note**
   Backend dedups `to_fusion` by course prefix in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). But the UI note sums per-convergence `to_fusion_credits` in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:591), so two convergence programs sharing the same physical course can display a larger excluded-credit number than the actual 전공 gauge deduction.
   Fix: compute the frontend note from the union of `to_fusion_course_credits` prefixes, or expose a backend `to_fusion_total_dedup` field and render that.

4. **MEDIUM — overflow extra-semester math ignores seasonal capacity**
   [_overflow_from_credits](/home/carol/kmu_genai/graduation_center/v2/planner.py:405) divides unplaced credits only by `reg_cap`. With `seasonal_semester_allowed=true`, the planner capacity model includes seasonal 6-credit slots, but overflow can overstate extra semesters.
   Fix: use `reg_cap + SEASONAL_TERM_CAP` as the per-added-regular-term capacity when seasonal is allowed, or share one capacity helper between planner/risk/overflow.

5. **MEDIUM [REGRESSION] — round-4 #6 soft prereq rule is too broad**
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:575) defines the prereq “pool” as only already selected items, not the full available catalog/candidate pool. A known prerequisite that exists in the catalog but was not selected due quota can be downgraded to a manual soft flag at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:581), and the final verification path does not recheck prereq ordering.
   Fix: distinguish “known prereq exists but not completed/selected” from “unknown/year-drift prereq.” Add the known prereq as a required candidate or block placement; reserve soft `manual_check` only for genuinely unresolved drift.

6. **LOW — malformed current term is silently treated as missing**
   [_ordered_terms](/home/carol/kmu_genai/graduation_center/v2/planner.py:361) returns `[]` on bad formats, then [run_planner](/home/carol/kmu_genai/graduation_center/v2/planner.py:678) says “현재 학기 미입력” even if the user entered malformed text.
   Fix: add a `StudentContext.current_term` regex validator for `YYYY-(1|2|S|W)` and return a clear 422/error message.
===== /tmp/codex_r5_18.txt =====
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

**Round-4 Verification**
- Fixes 1, 2, 5, 6, 7 look implemented in the planner path.
- Fix 3 has an edge regression.
- Fix 4 aliases are present, but a related planner confidence bug remains.
- Fix 8 is fixed in backend subtraction, but not in the frontend explanatory number.

**Findings**

**HIGH [REGRESSION] Seasonal capacity does not always match planner capacity**  
`graduation_center/v2/risk.py:65-71` always adds `remaining_semesters * SEASONAL_TERM_CAP`. But `graduation_center/v2/planner.py:367-376` only creates seasonal terms encountered before consuming the requested number of regular semesters. Example: `current_term="2026-S"`, `remaining_semesters=2` yields planner terms `2026-2`, `2026-W`, `2027-1`: only one seasonal slot, while risk counts two.  
Why it matters: risk can say the remaining capacity is enough while roadmap blocks, producing a visible contradiction.  
Fix: compute risk capacity from the same `_ordered_terms()` output or a shared helper, summing actual generated term caps.

**HIGH Capstone no-alias uncertainty is hidden as “catalog_verified”**  
`data/graduation/v2/required_names_by_year.json:133-145` has 2023 `다학제간캡스톤디자인Ⅰ/Ⅱ`, while `data/graduation/v2/required_names_by_year.json:147-166` has 2025 unnumbered `다학제간캡스톤디자인`; no alias is intentionally present. But `graduation_center/v2/planner.py:441-458` treats rmeta-only terms as `catalog_verified` when `terms` exists, even if no current catalog `course_id` matched.  
Why it matters: the demo can recommend numbered capstone courses as confidently offered, despite the stated uncertain equivalence.  
Fix: set `known = bool(cid)` or otherwise require a current catalog match for `catalog_verified`; rmeta-only required names should be `name_only`, `manual=True`, and shown as “학과 확인 필요”.

**MEDIUM [REGRESSION] Backend deduped `to_fusion`, frontend still double-counts the note**  
Backend dedups by prefix in `graduation_center/v2/audit_v2.py:292-297`, but frontend sums scalar per-check credits in `frontend/src/components/GraduationV2.jsx:591-595`.  
Why it matters: with multiple convergence programs, the 전공 gauge is based on deduped subtraction, but the explanatory note can show a larger deducted number.  
Fix: return a backend `major_to_fusion_deducted_credits` field, or have frontend union `to_fusion_course_credits` by prefix before displaying.

**MEDIUM 기초교양 택1 alternatives are displayed as separate missing required courses**  
`data/graduation/v2/required_names_by_year.json:184-199` explicitly says the list includes 택1, but `graduation_center/v2/audit_v2.py:83-94` evaluates each name independently and `frontend/src/components/GraduationV2.jsx:621-629` labels them “기초교양 필수 과목”.  
Why it matters: a fulfilled 기초교양 gauge can sit next to unchecked “필수” chips, which looks contradictory in a live demo.  
Fix: encode alternative groups with `take: 1`, compute group-level status, and suppress unchecked alternatives when the group or area is already satisfied.

**MEDIUM API accepts invalid convergence track strings and silently changes requirements**  
`graduation_center/v2/models_v2.py:29-30` types `convergence_tracks` as `dict[str, str]`; `graduation_center/v2/audit_v2.py:146-148` treats anything other than `"다전공"` as 부전공.  
Why it matters: an API typo can turn a 36-credit 다전공 into an 18-credit 부전공 without an error.  
Fix: validate values as `Literal["다전공", "부전공"]` per program id, or reject unknown track values before audit.
===== /tmp/codex_r5_19.txt =====
-- 다학제간캡스톤디자인
32 {'course_id': '0693316', 'name_ko': '다학제간캡스톤디자인', 'name_norm': '다학제간캡스톤디자인', 'aliases': [], 'credits': 4.0, 'requirement_area': '전공', 'is_required': True, 'prerequisites': [], 'prereq_external': [], 'grade_level': 4, 'offered_terms': ['1', '2'], 'group': None, 'source': {'doc': '2025-2 교육과정 교과목코드 현황', 'dept': '미래모빌리티학과'}}
39 {'course_id': '7159803', 'name_ko': '다학제간캡스톤디자인+', 'name_norm': '다학제간캡스톤디자인', 'aliases': [], 'credits': 4.0, 'requirement_area': '전공', 'is_required': False, 'prerequisites': [], 'prereq_external': [], 'grade_level': 4, 'offered_terms': ['1', '2'], 'group': None, 'source': {'doc': '2025-2 교육과정 교과목코드 현황', 'dept': '미래모빌리티학과'}}

**Ranked Findings**

HIGH [REGRESSION R4-7] `unfillable` still produces a contradictory remediation hint.  
`graduation_center/v2/planner.py:715-729` correctly excludes `unfillable` from overflow, but when only pool exhaustion exists, `ov` is `None` and `hint` falls back to “잔여 학기를 늘리거나 계절학기를 활용하세요.” That appears beside `blocked_reason` saying “초과학기로 해결 불가.” `frontend/src/components/GraduationV2.jsx:655` and `:707-710` display both.  
Fix: if `uf and not unplaced_cr`, set `relaxation_hint` to “수강 후보 데이터가 없어 학과/학사팀 확인 필요” and do not mention extra semesters or seasonal terms.

HIGH Frontend 3-way convergence controls can make numbers contradict the backend audit.  
`frontend/src/components/GraduationV2.jsx:100-110` recomputes 제1전공/융합 학점 locally after user clicks 3-way, but the area gauge and note at `:589-595`, risk chips at `:563-568`, and roadmap at `:652-736` remain backend-default values. A grader can click one button and see “전공 배정 반영” disagree with the 전공 gauge/risk/roadmap.  
Fix: either make 3-way read-only for demo, label it explicitly as “화면상 시뮬레이션, 리스크/로드맵 미반영,” or lift assignment state and recompute audit/risk/roadmap from it.

MED [REGRESSION R4-8] Backend dedups `to_fusion`, frontend note does not.  
Backend correctly dedups by prefix in `graduation_center/v2/audit_v2.py:290-297`, but the UI note sums `cc.to_fusion_credits` across convergence checks at `frontend/src/components/GraduationV2.jsx:591-595`. In multi-convergence cases, the note can say more credits were excluded from 전공 than the 전공 gauge actually excludes.  
Fix: expose `audit.to_fusion_total`/`to_fusion_course_credits_union` from backend and render that, not a per-check sum.

MED [REGRESSION R4-4 partial] Required-name aliases are used for audit, not for missing-required planning.  
Audit applies aliases in `graduation_center/v2/audit_v2.py:331-337`, but planner candidate enrichment only does direct `by_norm` lookup in `graduation_center/v2/planner.py:440-458`. For a 2023 student missing `미래모빌리티기초` or `미래모빌리티AD`, the roadmap may recommend the old 요람 name with empty `course_id`, even though aliases point to current catalog courses.  
Fix: reuse `_required_aliases` in `build_unified_candidates`; if alias maps to a catalog course, use current `course_id/name/offered_terms/prerequisites`, with `satisfies` preserving the 요람 required name.

MED Stale LLM copy contradicts actual deterministic planner.  
`graduation_center/v2/pipeline.py:67` says the integrated planner is deterministic and LLM unused, but UI copy still says “LLM이 로드맵만 계획” at `frontend/src/components/GraduationV2.jsx:356-357`, and workflow labels include “LLM 판단” at `frontend/src/components/WorkflowGraph.jsx:8` / `WorkflowPage.jsx:27`.  
Fix: change demo copy to “결정론 플래너가 로드맵을 만들고 검증기가 재확인” unless LLM is actually wired back in.

LOW The roadmap “남은 요건” chips are pre-plan gaps but look like post-plan residuals.  
`frontend/src/components/GraduationV2.jsx:667-680` renders audit gaps above a roadmap that may fully place those courses. This can read as “still missing 6학점” while the plan below fills 6학점.  
Fix: rename to “로드맵으로 채울 요건” or compute residual after planned courses.

**Round-4 Verification**

1, 2, 3, 5, 6, 7 backend counting, and 8 backend dedup are mostly implemented. Regressions/incompleteness remain for R4-7 UI/hint contradiction, R4-8 frontend display dedup, and R4-4 alias usage in planning.

**Top 3 Demo Screen Risks**

1. Pool-exhausted card says both “초과학기로 해결 불가” and “잔여 학기/계절 활용.”  
2. 3-way convergence clicks change one card’s numbers without changing risk/gauge/roadmap.  
3. “남은 요건” label can look like residual debt after a successful roadmap.

**15-Minute Demo Order**

1. Start with settings: 2023학번, 미래모빌리티, 모빌리티데이터분석융합전공 다전공, 잔여 3학기, 계절 허용.  
2. Run verify, briefly show excluded/retake handling only if clean.  
3. Run audit, show total/area gauges first.  
4. Show convergence card without clicking 3-way controls.  
5. Show roadmap and explain “이 요건을 이 계획으로 채움.”  
6. Open workflow graph last as implementation transparency.

Verification note: I attempted `pytest tests/test_v2_pipeline.py -q`, but collection failed in this environment under Python 3.8/Pydantic on `str | None` annotations before tests ran.
===== /tmp/codex_r5_2.txt =====
   520	    # 풀이 quota를 못 채우면 unfillable로 기록(후보 고갈 → 거짓 '충족' 방지).
   521	    selected: list[dict] = []
   522	    seen: set[str] = set()
   523	    unfillable: list[dict] = []
   524	    for r in reqs:
   525	        if r.get("items") is not None:
   526	            for it in r["items"]:
   527	                key = normalize_name(it["name_ko"])
   528	                if key in seen:
   529	                    continue
   530	                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]})
   531	        else:
   532	            acc = 0.0
   533	            for it in r["pool"]:
   534	                if acc >= r["need"]:
   535	                    break
   536	                key = normalize_name(it["name_ko"])
   537	                if key in seen:
   538	                    # 다른 요건이 이미 선택한 과목 — 이 요건 quota에 '가산하지 않는다'.
   539	                    # (가산하면 융합 과목이 전공 quota를 거짓 충당해 중복인정 한도를 우회하고,
   540	                    #  필수지정은 major_gap_eff에서 이미 차감돼 이중 차감이 됨 — 라운드4 검증)
   541	                    continue
   542	                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]}); acc += it["credits"]
   543	            if acc + 0.01 < r["need"]:
   544	                unfillable.append({"label": r["label"], "shortfall": round(r["need"] - acc, 1)})
   545	

**Findings**
1. **HIGH [REGRESSION] Alias-equivalent courses can still be planned twice and credited as two physical courses.**  
   [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175) defines `미래모빌리티기초 ↔ 자동차모빌리티기초` and [line 178](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:178) defines `미래모빌리티AD ↔ 자동차모빌리티 Adventure Design`. Audit uses these aliases only for “already taken” matching in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331), but planner candidate selection dedups only `normalize_name(it["name_ko"])` in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:527) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536).  
   Why it breaks demo: for 2023 미래모빌리티 + 모빌리티데이터분석, a missing required `미래모빌리티기초` candidate from [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:439) can coexist with 융합 A그룹 `자동차모빌리티기초` from [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:477). The roadmap can show the same course twice, once as 전공 필수 and once as 융합전공, inflating planned credits by 3 and creating a visible contradiction.  
   Fix: move alias canonicalization into planner selection. Build `seen_key` from full course id/prefix when known, else from a canonical alias group. Also use aliases when enriching required-name candidates against the current catalog so `미래모빌리티기초` resolves to `0733010`.

2. **MEDIUM [REGRESSION] Seasonal risk capacity is not exactly equivalent to `_ordered_terms` when `current_term` is `S` or `W`.**  
   Risk uses `remaining_semesters * SEASONAL_TERM_CAP` in [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68). Planner actually enumerates future terms from `current_term` in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:367) and stops once the remaining regular terms are reached. If `current_term="2026-S"` and `remaining_semesters=2`, planner can place only `2026-W` as a future seasonal slot before `2027-1`; risk counts two seasonal slots. Same issue after `2026-W`.  
   Why it matters: edited demo inputs can show risk capacity `~12` seasonal credits while the roadmap can only place `6`, making risk less severe than the planner.  
   Fix: share one capacity helper with planner, e.g. compute risk capacity from `_ordered_terms(context, term_cap)` instead of duplicating the formula.

3. **MEDIUM The frontend 3-way convergence selector can show official-looking numbers that are not re-audited.**  
   `ConvergenceBlock` stores local assignment state in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:100) and recomputes `primaryCr`, `fusionCr`, and `fits` in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:103). But audit execution only posts `context`, `verification_table`, unresolved, and retakes in [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:328); assignment changes never reach backend.  
   Why it matters: a grader can click assignments and see the convergence card say “둘 다 충족” while top-level 전공 gauge, risk, and roadmap remain based on the original backend allocation.  
   Fix: either make the selector read-only/explanatory for demo, or post selected assignments and recompute `audit.area_gaps`, `risk`, and `roadmap` from that allocation.

**Round-4 Verification**
- Fixes 1, 2, 5, 6, 7: implemented for the exact stated paths.
- Fix 3: correct for default `2026-1` happy path, incomplete for seasonal/winter current terms.
- Fix 4: aliases exist and audit uses them, but planner dedup/enrichment does not, causing the HIGH regression above.
- Fix 8: `to_fusion` subtraction is deduped by prefix in [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292).

I could not run pytest cleanly in this environment: default `python` is 3.8 and fails on `str | None`; `/usr/bin/python3.10` exists but lacks installed project deps such as `pydantic`/`pytest`.
===== /tmp/codex_r5_3.txt =====
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:509: in get_model_type_hints
    hints[name] = try_eval_type(value, globalns, localns)
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:558: in try_eval_type
    return eval_type_backport(value, globalns, localns), True
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:609: in eval_type_backport
    return _eval_type_backport(value, globalns, localns, type_params)
../exit/lib/python3.8/site-packages/pydantic/_internal/_typing_extra.py:641: in _eval_type_backport
    raise TypeError(
E   TypeError: Unable to evaluate type annotation 'str | None'. If you are making use of the new typing syntax (unions using `|` since Python 3.10 or builtins subscripting since Python 3.9), you should either replace the use of new syntax with the existing `typing` constructs or install the `eval_type_backport` package.
=========================== short test summary info ============================
ERROR tests/test_v2_pipeline.py - TypeError: Unable to evaluate type annotati...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.40s

**Findings**

HIGH - Demo can schedule the same physical course twice after alias hardening.  
[planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:527) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536) dedup selected candidates only by `normalize_name(name_ko)`. The new aliases live in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170), but planner selection does not canonicalize through that alias graph. In the target demo, a 2023 미래모빌리티 student missing `미래모빌리티기초` can also get `자동차모빌리티기초` from 모빌리티데이터분석융합전공 [catalog_mobility_data_convergence.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mobility_data_convergence.json:66). Those names are aliases, not equal normalized names, so both can be selected and credited/planned.  
Fix: create a canonical course-equivalence key before selection, using 7-digit code where known, prefix where officially shared, and required-name aliases for old/new required names. Resolve old required candidates to current catalog records before adding them to `selected`.

HIGH - Required-name aliases are used for audit matching, but not for roadmap candidate resolution.  
Audit matching is bidirectional and used in `_taken()` [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:333), but missing required candidates are built from the old requirement name and only looked up by exact catalog `by_norm` [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:439). For a 2023 student, `미래모빌리티기초` / `미래모빌리티AD` / `미래모빌리티실험` will not resolve to current catalog names `자동차모빌리티기초`, `자동차모빌리티 Adventure Design`, `모빌리티실험및실습`; the planner can output old course names with blank `course_id` while marking them `catalog_verified` because year metadata has terms [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455). A grader can see non-current course names in the roadmap.  
Fix: in `build_unified_candidates`, when `cat["by_norm"]` misses, try `_required_aliases(profile.program_id)` and resolve to the current catalog course. Display `요람명 / 현행명` if needed, but plan the real current course id/name.

HIGH - Current test/runtime environment cannot collect the v2 tests.  
`pytest tests/test_v2_pipeline.py -q` fails during collection under Python 3.8 because package import eagerly loads [graduation_center/__init__.py](/home/carol/kmu_genai/graduation_center/__init__.py:3), then Pydantic evaluates `str | None` annotations in [graduation_center/models.py](/home/carol/kmu_genai/graduation_center/models.py:24). `requirements.txt` has no `Requires-Python` guard or `eval_type_backport` [requirements.txt](/home/carol/kmu_genai/requirements.txt:1). If the live demo uses the same env, `/graduation/v2/*` is dead before any audit logic runs.  
Fix: either pin/document Python `>=3.10` and install deps there, or remove eager package import plus convert legacy annotations to `Optional[...]`/`List[...]`/`Dict[...]` or add `eval_type_backport`.

MEDIUM - Capstone 2023-vs-2025 naming will produce a hard “missing required” instead of a safe manual ambiguity.  
2023 requires `다학제간캡스톤디자인Ⅰ` and `Ⅱ` [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133), while 2025 has a single `다학제간캡스톤디자인` [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:166) and the current catalog has `다학제간캡스톤디자인` plus `다학제간캡스톤디자인+` sharing the same normalized key [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639), [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781). Because capstone aliases are intentionally absent [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170), `_taken()` can only exact/alias match [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:333). A 2023 student with 2025-name records will look definitively missing both Ⅰ/Ⅱ.  
Fix: do not silently alias if equivalence is uncertain, but add an `ambiguous_required_matches` / manual-check warning: “2025 현행 캡스톤 이수 기록이 2023 요람 Ⅰ/Ⅱ를 대체하는지 학과 확인 필요,” and keep it out of hard missing until confirmed.

MEDIUM - Backend multi-convergence deduction is deduped, frontend note is not.  
Backend dedupes `to_fusion_course_credits` by prefix before subtracting from 전공 [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:290). The frontend note sums `c.to_fusion_credits` per convergence check [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:591). With two convergence programs sharing the same physical course, the 전공 gauge uses deduped subtraction but the explanatory note can show a larger excluded credit number.  
Fix: expose backend `to_fusion_total_deduped`, or have the frontend union `to_fusion_course_credits` keys instead of summing per-check totals.

LOW - UI still says LLM plans the roadmap, but v2 planner is deterministic.  
The banner says “LLM이 로드맵만 계획” [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:355), while `run_planner` explicitly says LLM is unused [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:641). A grader may read this as architectural inconsistency.  
Fix: change UI/status copy to “결정론 플래너가 로드맵을 배치하고 검증합니다.”

**Round-4 Verification**

1. Literal duplicate-name dedup now skips without crediting later quota: present at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536). Alias-equivalent duplicates remain unfixed.
2. `gap_not_closed` check exists for major floor gaps: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704).
3. Seasonal risk capacity uses `remaining_semesters * SEASONAL_TERM_CAP`: [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68).
4. Required aliases are present and bidirectional in audit: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:58). Planner does not consume them.
5. 기초교양 candidates only when area gap > 0: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:499).
6. Missing prereq outside completed/pool is soft manual flag: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579).
7. Overflow uses unplaced credits only and separates unfillable: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:719).
8. Backend `to_fusion` subtraction is deduped by prefix: [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). Frontend explanatory note still double-counts.
===== /tmp/codex_r5_4.txt =====
   309	        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc
   310	
   311	
   312	@app.post("/graduation/v2/audit")
   313	def graduation_v2_audit(payload: dict) -> dict:
   314	    """사용자 확정 테이블 → 진단 → 로드맵(LLM+검증) → 리스크 → 컨설팅 응답."""
   315	    if "context" not in payload or "program_id" not in payload.get("context", {}):
   316	        raise HTTPException(status_code=400, detail="context.program_id 가 필요합니다.")
   317	    try:
   318	        return v2_pipeline.run_audit(payload).model_dump()
   319	    except KeyError as exc:
   320	        raise HTTPException(status_code=400, detail=f"알 수 없는 program_id: {exc}") from exc
   321	
   322	
   323	_EMPTY_ANSWER_VALIDATION = {"ok": True, "flags": [], "markers": [], "citation_ids": []}
   324	_EMPTY_OUTPUT_PRIVACY = {"ok": True, "flags": []}
654:              {audit.roadmap.status === "not_generated" && <p style={{ color: C.muted, fontSize: 13 }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
655:              {audit.roadmap.status === "blocked" && <p style={{ color: C.danger, fontSize: 13 }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
707:              {audit.roadmap.feasible === false && audit.roadmap.blocked_reason && (

**Findings**

HIGH [REGRESSION] 기초교양 필수 과목 미이수가 “충족”으로 보일 수 있습니다.  
[planner.py:499](/home/carol/kmu_genai/graduation_center/v2/planner.py:499) only plans `gen_basic_courses` when `basic_gap > 0`, and [planner.py:503](/home/carol/kmu_genai/graduation_center/v2/planner.py:503) caps the requirement by the area gap. But [audit_v2.py:367](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:367) stores mandatory basic-liberal misses only as display data, not a hard missing requirement; [risk.py:27](/home/carol/kmu_genai/graduation_center/v2/risk.py:27) only counts `missing_required_names`. Frontend then shows unchecked chips at [GraduationV2.jsx:621](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:621) while the roadmap can still show “졸업요건을 모두 충족했습니다” at [GraduationV2.jsx:657](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:657).  
Fix: add `missing_gen_basic_names` as a hard audit field, include it in risk/remaining requirements, and plan every missing required 기초교양 course independently of area total. Do not label it as an area credit gap; label it “기초교양 필수 미이수”.

HIGH [REGRESSION] alias fix is incomplete: aliases are used for completed-course detection, but not for missing-course planning/dedup.  
Aliases are defined in [required_names_by_year.json:170](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170) and used by audit at [audit_v2.py:331](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331). However planner resolves missing required names only by raw normalized name at [planner.py:439](/home/carol/kmu_genai/graduation_center/v2/planner.py:439), then dedups by raw normalized display name at [planner.py:536](/home/carol/kmu_genai/graduation_center/v2/planner.py:536). For 2023, `미래모빌리티기초` can become a no-code planned item while `자동차모빌리티기초` from the 융합 pool is treated as a separate course. That can double-count/schedule one physical course twice.  
Fix: canonicalize missing required names through the alias group before candidate creation, attach the catalog `course_id`, and dedup by course prefix or alias-group key, not display name.

MEDIUM Risk capacity still only uses total credit gap, not the actual remaining hard obligations.  
[risk.py:26](/home/carol/kmu_genai/graduation_center/v2/risk.py:26) sets `gap = audit.total_gap`; [risk.py:72](/home/carol/kmu_genai/graduation_center/v2/risk.py:72) compares only that to capacity. If total credits are already high but 전공/융합/핵심세부 gaps require more credits than the remaining terms can hold, capacity risk will not explain the impossibility; it only gets a generic roadmap C at [risk.py:99](/home/carol/kmu_genai/graduation_center/v2/risk.py:99).  
Fix: compute capacity against the selected remaining obligation credits, or at least `max(total_gap, sum(area gaps), convergence/group gaps)`.

LOW Blocked roadmap reason is rendered twice.  
[GraduationV2.jsx:655](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) renders blocked status, then [GraduationV2.jsx:707](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707) renders the same `blocked_reason` again because blocked implies `feasible === false`.  
Fix: add `audit.roadmap.status !== "blocked"` to the second block, or remove the first block when partial terms exist.

**Round-4 Verification**

1. Seen-dedup no longer credits skipped duplicates: verified at [planner.py:536](/home/carol/kmu_genai/graduation_center/v2/planner.py:536). Caveat: alias-equivalent names still bypass it.  
2. `gap_not_closed` area check exists: verified at [planner.py:704](/home/carol/kmu_genai/graduation_center/v2/planner.py:704).  
3. Seasonal risk capacity uses `remaining_semesters * SEASONAL_TERM_CAP`: verified at [risk.py:68](/home/carol/kmu_genai/graduation_center/v2/risk.py:68).  
4. Aliases added, but planner does not use them: [REGRESSION].  
5. 기초교양 gap-only candidate rule exists, but masks mandatory-course misses: [REGRESSION].  
6. Missing prereq outside completed/pool is soft manual check: verified at [planner.py:581](/home/carol/kmu_genai/graduation_center/v2/planner.py:581).  
7. Overflow uses unplaced credits and separates unfillable: verified at [planner.py:719](/home/carol/kmu_genai/graduation_center/v2/planner.py:719).  
8. `to_fusion` subtraction deduped by prefix: verified at [audit_v2.py:292](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292).

I could not run backend probes in the active venv because it is Python 3.8 and the code uses 3.10 union annotations.
===== /tmp/codex_r5_5.txt =====
   623	        if not bucket[lab]:
   624	            continue
   625	        courses = [RoadmapCourse(course_id=it.get("course_id", "") or "", name_ko=it["name_ko"],
   626	                                 credits=it["credits"], satisfies=it.get("satisfies", ""),
   627	                                 assignment=it.get("assignment", ""),
   628	                                 offered_terms=(it.get("offered_terms") or []) if it.get("confidence") == "catalog_verified" else [],
   629	                                 confidence=it.get("confidence", "catalog_verified"),
   630	                                 manual_check=it.get("manual", False)) for it in bucket[lab]]
   631	        out.append(RoadmapTerm(term=lab, courses=courses, term_credits=round(used[lab], 1),
   632	                               term_risk="medium" if used[lab] > cap - 3 else "low"))
   633	    assumptions = []
   634	    if any(it.get("manual") for it in selected):
   635	        assumptions.append("이름기준·교양 슬롯 과목은 개설학기·학점을 수강신청 전 확인하세요.")
   636	    if prereq_warn:
   637	        assumptions.append(f"선수과목 이수 여부 확인 필요: {', '.join(sorted(set(prereq_warn))[:6])}")
   638	    return out, assumptions, unplaced

I’m ready to write the review. I will lead with the few items that can actually change displayed numbers or create visible contradictions, and I’ll include a compact verification status for the eight round-4 fixes.
**Findings**

1. **HIGH [REGRESSION] Alias courses can still be planned twice and double-count credits.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:330) applies required-name aliases only when deciding whether a required course was already taken, but [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:527) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536) dedup selected candidates by `normalize_name(name_ko)` only. The aliases exist in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175), but planner candidate hydration at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445) does not use them.  
   Why this breaks demo: a 2023 미래모빌리티 student missing `미래모빌리티기초` can also get `자동차모빌리티기초` from 모빌리티데이터분석융합전공. Those are declared aliases, but the selection pass treats them as two different courses, plans 6 credits, and reduces total/general 부족 twice. Same risk for `미래모빌리티AD` ↔ `자동차모빌리티 Adventure Design`.  
   Fix: create a canonical course key for candidate selection: prefer current catalog `course_id[:5]`, else alias-equivalence key from `required_names_by_year.aliases`, else normalized name. Use that key in `seen`, total selected credits, and unfillable accounting. Add a regression test for 2023 `mirae_mobility` + `mobility_data_convergence`.

2. **HIGH [REGRESSION] Old 요람 required names not found in the current catalog are marked `catalog_verified`.**  
   In [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:440), required metadata supplies credits/terms, and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:455) sets `known = bool(terms)`. That means if no current catalog hit exists, [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:456) still emits `confidence="catalog_verified"` and `manual=False`.  
   Why this breaks demo: 2023 required names include `다학제간캡스톤디자인Ⅰ/Ⅱ` in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:132), while the current catalog has unnumbered `다학제간캡스톤디자인` and `다학제간캡스톤디자인+` at [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639) and [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781). Round 4 intentionally did not alias these, but the roadmap can still present `Ⅰ/Ⅱ` as verified/offered without manual warning.  
   Fix: `catalog_verified` should require an actual catalog hit or accepted alias hit. If only year metadata exists, emit `confidence="name_only"`, `manual=True`, and a clear assumption like `현행 개설명/동등과목 학과 확인 필요`.

3. **MEDIUM The roadmap “남은 요건” summary omits convergence group gaps.**  
   Backend correctly plans group shortages: [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:462) computes `group_gaps`, and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:464) uses `max(total gap, sum(group gaps))`. Risk also reports group gaps at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:82). But the frontend roadmap summary only adds convergence text when `cc.gap > 0` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673).  
   Why this breaks demo: if 모빌리티데이터분석 total 36 is met but A/B group minimum is not, the convergence panel warns and the planner adds courses, but “남은 요건” omits the reason. That is a visible contradiction.  
   Fix: include `cc.group_checks.filter(g => g.gap > 0)` in the roadmap summary, e.g. `모빌리티데이터분석 A그룹 3학점`.

4. **MEDIUM Overflow semester count still ignores seasonal capacity for extra semesters.**  
   `_ordered_terms()` gives each remaining regular semester seasonal capacity when allowed at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:367), and risk uses `remaining_semesters × SEASONAL_TERM_CAP` at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68). But `_overflow_from_credits()` computes extra semesters as `ceil(unplaced_credits / reg_cap)` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:405).  
   Why this breaks demo: with seasonal allowed, 20 unplaced credits and 19 regular cap would display 2 extra semesters, even though one extra regular semester plus seasonal can carry 25 credits. That is a wrong number in the 초과학기 card.  
   Fix: when `seasonal_semester_allowed`, use `reg_cap + SEASONAL_TERM_CAP` for each extra regular-semester block, while keeping projected graduation term based on regular semesters.

**Round-4 Verification**

- Fix 1: exact-name seen-dedup is fixed at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536), but alias-equivalent dedup is not. **[REGRESSION]**
- Fix 2: active `run_planner` now has area `gap_not_closed` check at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704). Verified.
- Fix 3: risk seasonal capacity uses `remaining_semesters × SEASONAL_TERM_CAP` at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68). Verified, with overflow caveat above.
- Fix 4: aliases exist in data at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:175), but planner does not use them. **[REGRESSION]**
- Fix 5: 기초교양 candidates are gated on `basic_gap > 0` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:500). Verified.
- Fix 6: missing prereq not in completed/pool becomes soft manual + assumption at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:636). Same-term prereq/child is blocked when prereq is in pool via [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:577) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:585). Verified.
- Fix 7: overflow input is unplaced credits only, and unfillable is separated in the blocked message at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:719) and [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:725). Verified.
- Fix 8: `to_fusion_course_credits` is deduped by course prefix at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). Verified.
===== /tmp/codex_r5_6.txt =====
    22	  ],
    23	  "prerequisites": {
    24	    "공학수학Ⅰ": [
    25	      "공학기초수학"
    26	    ]
    27	  },
    28	  "aliases": {},
    29	  "required_codes": [
    30	    "0693316"
    31	  ],
    32	  "_note_codes": "다학제간캡스톤디자인은 + 변형과 name_norm 충돌 → 코드 지정"
    33	}

exec
/bin/bash -lc "rg -n '0365007|0365008|다학제간캡스톤디자인\\+' data/graduation/v2/catalog_build_report.json data/graduation/v2/overrides_mirae_mobility.json scripts/build_v2_catalog.py" in /home/carol/kmu_genai
 exited 1 in 0ms:
**Findings**

1. **HIGH: Required-course checks can be falsely cleared by same-name non-required or non-primary courses.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:330) builds `confirmed_norm` from every confirmed course name, then [_taken()](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:333) accepts name equality/alias without checking primary-major code, required flag, or exact catalog identity. This violates “전공=해당전공 과목만.” Concrete live-risk: 2025 required `다학제간캡스톤디자인` is in [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:166), while non-required `다학제간캡스톤디자인+` normalizes to the same key in [catalog_mirae_mobility.json](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:781). Taking `+` can clear the required course.  
   Fix: for required checks, match exact primary catalog course IDs when available; for name-only year data, require the confirmed course to be primary-catalog matched and required, or maintain explicit allowed aliases/codes. Do not use all confirmed names globally.

2. **MEDIUM: Convergence “taken/overlap” still uses 5-digit prefixes, so real 7-digit collisions can credit the wrong course.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:149) keys convergence courses by `course_id[:5]`, and [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:153) treats any transcript course with that prefix as designated. Current data has collisions, e.g. 미래모빌리티 `0156810 C프로그래밍` and DSCI `0156812 객체지향프로그래밍` ([rg evidence] same prefix). This can show wrong 융합 earned/group numbers if the grader switches convergence programs.  
   Fix: use exact 7-digit course IDs for designated/taken/overlap. Only use prefix aliases where an explicit equivalence table says the codes are the same curriculum course.

3. **MEDIUM [REGRESSION]: unfillable-only blocked plans still tell the user to add semesters/seasonal terms.**  
   Round-4 item 7 is only partly fixed: overflow is computed from `unplaced` only at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:719), so `unfillable`-only correctly gives `overflow=None`. But the fallback hint still becomes “잔여 학기를 늘리거나 계절학기를 활용하세요” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:729), while the reason says “초과학기로 해결 불가” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:725). The trace also labels every blocked plan as “초과학기 필요” / “미배치 → 초과학기” in [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61) and [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78).  
   Fix: branch hints/trace by cause. If `unfillable and not unplaced`, use “후보 데이터 없음/학과 확인 필요, 초과학기로 해결 불가”; only mention 초과학기 when `overflow` exists.

4. **MEDIUM: Group-only convergence shortages get no frontend course scenario.**  
   Backend planner correctly builds candidates from `group_gaps` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463). Frontend, however, only creates `suggest` when `fusionGap > 0` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:114), while separately warning about group shortages at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:144). If total 36 is met but A/B group minimum is short, the panel says group 부족 but shows no “졸업 가능 시나리오,” while the roadmap may still add group courses.  
   Fix: compute suggestion need from `max(fusionGap, sum(group gaps))`, and prioritize untaken courses in short groups even when total gap is zero.

5. **LOW: Blocked reason is rendered twice.**  
   For `status === "blocked"`, [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) renders `blocked_reason · relaxation_hint`; then [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707) renders the same text again because blocked plans also have `feasible === false`.  
   Fix: render one blocked banner. For example, make the second block `audit.roadmap.status !== "blocked"` or split empty-plan vs partial-plan blocked cases.

**Round-4 Fix Check**

1. seen-dedup: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536).  
2. major gap coverage: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704).  
3. seasonal risk capacity: verified at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68).  
4. requested aliases present: verified at [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170).  
5. 기초교양 only when gap > 0: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:499).  
6. missing prereq soft flag: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579).  
7. overflow unplaced-only: core calc verified, messaging regression above.  
8. to_fusion prefix dedup: verified at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292).

Could not run `pytest tests/test_v2_pipeline.py` in this shell: it uses Python 3.8, and collection fails on `str | None` annotations under Pydantic.
===== /tmp/codex_r5_7.txt =====
graduation_center/v2/catalog.py:102:def _requirements_by_year(program_id: str, year: int | None) -> dict | None:
graduation_center/v2/pipeline.py:6:from __future__ import annotations
graduation_center/v2/pipeline.py:20:def run_verify(files: list[tuple[bytes, str]], context: dict) -> dict:
graduation_center/v2/audit_v2.py:10:from __future__ import annotations
graduation_center/v2/audit_v2.py:32:def _required_names_for_year(program_id: str, year: int | None) -> list[str] | None:
graduation_center/v2/audit_v2.py:58:    groups: dict[str, set] = {}
graduation_center/v2/audit_v2.py:66:def _gen_basic_names(program_id: str, year: int | None) -> list[str]:
graduation_center/v2/audit_v2.py:83:def _gen_basic_view(verified: VerifiedTranscript, program_id: str, year: int | None) -> list[dict]:
graduation_center/v2/audit_v2.py:98:def _admission_year(profile: RequirementProfile, verified: VerifiedTranscript) -> int | None:
graduation_center/v2/audit_v2.py:115:                        primary_major_required: float = 0.0, primary_major_earned: float = 0.0) -> list[dict]:
graduation_center/v2/audit_v2.py:127:    prog_prefixes: dict[str, set] = {}
graduation_center/v2/audit_v2.py:307:    area_gaps: list[AreaGap] = []
graduation_center/v2/audit_v2.py:317:    core_gaps: list[AreaGap] = []
graduation_center/models.py:3:from __future__ import annotations
graduation_center/models.py:24:    masked_name: str | None = None
graduation_center/models.py:25:    masked_student_id: str | None = None
graduation_center/models.py:27:    admission_year: int | None = Field(default=None, ge=1900, le=2100)
graduation_center/models.py:29:    category_credits: dict[str, float] = Field(default_factory=dict)
graduation_center/models.py:31:    courses: list[CourseSummary] = Field(default_factory=list, max_length=300)
graduation_center/models.py:33:    warnings: list[str] = Field(default_factory=list)
graduation_center/models.py:41:    transcript: TranscriptSummary | None = None
graduation_center/models.py:42:    warnings: list[str] = Field(default_factory=list)
graduation_center/models.py:66:    registered_semesters: int | None = Field(default=None, ge=1, le=20)
graduation_center/models.py:94:    sources: list[dict] = Field(default_factory=list)
graduation_center/models.py:96:    safety_flags: list[str] = Field(default_factory=list)
graduation_center/models.py:98:    warnings: list[str] = Field(default_factory=list)

**Findings**

HIGH [REGRESSION] [graduation_center/v2/pipeline.py:61](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61), [planner.py:725](/home/carol/kmu_genai/graduation_center/v2/planner.py:725): `unfillable` is labeled “초과학기로 해결 불가” in `blocked_reason`, but the workflow branch still says `실현불가(초과학기 필요)` and validation branch says `미배치 → 초과학기`. If `ov` is `None`, `relaxation_hint` also falls back to “잔여 학기를 늘리거나 계절학기를 활용하세요” at [planner.py:729](/home/carol/kmu_genai/graduation_center/v2/planner.py:729). That directly contradicts round-4 fix #7.
Fix: split blocked classes: `unplaced_capacity` vs `pool_exhausted`. For pure `pool_exhausted`, hint/trace should say “대체 인정·개설 여부 학과 확인 필요”, never “초과학기”.

HIGH [REGRESSION] [graduation_center/v2/audit_v2.py:292](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292), [frontend/src/components/GraduationV2.jsx:591](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:591): multi-convergence `to_fusion` dedup is still inconsistent. Backend dedups by prefix with last-write-wins (`to_fusion_by_course[pfx] = cr`), so if two convergence programs report the same prefix with different credits, the 전공 deduction depends on program order. The frontend note separately sums per-program `to_fusion_credits`, so it can display “전공 이수 학점 중 6학점 제외” while backend 전공 gauge only deducted 3.
Fix: compute and expose one global `to_fusion_course_credits` map from backend using deterministic conflict handling, e.g. validate equal credits or take `max` with a warning. Frontend must display the backend global sum, not `reduce(sum cc.to_fusion_credits)`.

HIGH [graduation_center/v2/planner.py:455](/home/carol/kmu_genai/graduation_center/v2/planner.py:455), [data/graduation/v2/required_names_by_year.json:133](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:133), [data/graduation/v2/catalog_mirae_mobility.json:639](/home/carol/kmu_genai/data/graduation/v2/catalog_mirae_mobility.json:639): 2023 요람 required-name metadata is treated as `catalog_verified` when no current catalog course id is found. That can put `다학제간캡스톤디자인Ⅰ/Ⅱ(3학점)` into the roadmap as verified offerings, while current catalog has `다학제간캡스톤디자인(4)` and `다학제간캡스톤디자인+(4)`, and the no-number alias was intentionally not added.
Fix: `known` should require a unique catalog hit (`cid`), not just year metadata `terms`. If no catalog id, mark `confidence="name_only"`, `manual=True`, and phrase it as “요람명, 현행 개설/대체 인정 확인 필요”.

MEDIUM [graduation_center/v2/planner.py:405](/home/carol/kmu_genai/graduation_center/v2/planner.py:405), [planner.py:372](/home/carol/kmu_genai/graduation_center/v2/planner.py:372): overflow extra-semester math ignores seasonal capacity even though the planner uses one seasonal slot per remaining regular semester. With seasonal allowed, `_overflow_from_credits()` divides unplaced credits by only `reg_cap`, overstating extra semesters near boundaries.
Fix: simulate `_ordered_terms()` with increasing `remaining_semesters`, or use `reg_cap + SEASONAL_TERM_CAP` per added regular semester when seasonal is enabled.

MEDIUM [frontend/src/components/GraduationV2.jsx:655](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655), [frontend/src/components/GraduationV2.jsx:707](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707): blocked roadmap messages render twice: once in red at the top of the roadmap card and again in an orange warning box. A grader can see the same `blocked_reason · relaxation_hint` repeated.
Fix: render blocked status in exactly one place, or make the lower block conditional on `audit.roadmap.status !== "blocked"`.

LOW [graduation_center/v2/planner.py:334](/home/carol/kmu_genai/graduation_center/v2/planner.py:334): round-4 prereq softening exists in `plan_greedy`, but the older LLM `validate_roadmap()` path still hard-blocks missing prerequisites. If that path is re-enabled, behavior regresses.
Fix: mirror the greedy policy: prereq not completed and not in candidate pool should create manual-check/assumption, not `prereq_unmet`.

**Round-4 Check**

Fixes 1, 2, 3, 4, 5 are implemented. Fix 6 is implemented only for greedy planning. Fix 7 is incomplete due contradictory hints/trace. Fix 8 is incomplete for multi-convergence/global display; single-convergence is unaffected unless duplicate included transcript rows share a prefix.
===== /tmp/codex_r5_8.txt =====
    79	                       status="ok" if vrep.ok else "fail",
    80	                       summary=("통과(선수·개설학기·학점상한)" if vrep.ok else f"{len(vrep.errors)}건 미충족"),
    81	                       branch_taken=("통과" if vrep.ok else "미배치 → 초과학기")),
    82	        NodeTraceEvent(node="리스크 산정", kind="tool",
    83	                       summary=f"{risk.grade} {risk.label} ({risk.score})", branch_taken=f"{risk.grade} {risk.label}"),
    84	    ]
    85	    md = _markdown(ctx, profile, audit, risk, plan)
    99	    if audit.convergence_checks:
   100	        L += ["", "## 연계·융합전공 (학점 중복인정 반영)"]
   101	        for cc in audit.convergence_checks:
   102	            mark = "✅" if cc["gap"] <= 0 else f"⚠️ {cc['gap']:.0f} 부족"
   103	            L.append(f"- {cc['name']}({cc['track']}·{cc['conv_type']}): {cc['earned']:.0f}/{cc['required']:.0f} {mark}"
   104	                     f"  [제1전공과 겹침 {cc['overlap_credits']:.0f} 중 중복인정 가능 {cc['double_recognizable']:.0f}/{cc['double_cap']:.0f}]")
   105	            for gc in cc.get("group_checks", []):
   106	                gm = "✅" if gc["gap"] <= 0 else f"⚠️ {gc['gap']:.0f} 부족"
   107	                L.append(f"    · {gc['group']}: {gc['earned']:.0f}/{gc['required']:.0f} {gm}")
   108	            if cc["recommend_double_count"]:
   109	                L.append(f"  · 중복인정 신청 권장: {', '.join(cc['recommend_double_count'])}")
   110	            if cc.get("note"):
   111	                L.append(f"  · {cc['note']}")

**Findings**

1. **HIGH — `plan_greedy` can falsely block a feasible roadmap due to first-fit packing.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:565) sorts only by `(priority, -credits)`, then [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:590) first-fits each course into the earliest valid term. It does not place constrained offerings first. A flexible `["1","2"]` course can consume the only 1학기 slot needed by a `["1"]` course, producing `unplaced` and a bogus 초과학기 even though swapping them is feasible.  
   **Fix:** sort by constrainedness before flexibility: `(priority, len(offered_terms), has_prereq_depth, -credits, stable_id)`, and add a repair pass that evicts/moves flexible courses when a constrained course fails. Better: solve as small deterministic bin-packing/matching per term.

2. **HIGH — 융합전공 group minima are not validated after candidate selection.**  
   [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:463) computes `group_gaps`, but candidate selection later only checks aggregate `acc >= r["need"]` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:532). If the 부족 group has insufficient candidates, other-group courses can fill the numeric quota and avoid `pool_exhausted`, while the actual group minimum remains unsatisfied. The later coverage check only covers `MAJOR_AREAS` 전공 at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704), not 융합 group floors.  
   **Fix:** carry `group_gaps` into the req object, track selected/placed credits by `(program_id, group)`, and emit `pool_exhausted` or `gap_not_closed` when any group quota is short. Do not allow wrong-group credits to satisfy group-minimum quota.

3. **HIGH — group-only convergence gaps can be shown as satisfied in the markdown report and hidden from the roadmap summary.**  
   [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:102) marks a convergence program ✅ using only `cc["gap"]`, while group rows can still show 부족 at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:105). Frontend “남은 요건” has the same blind spot: [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673) includes convergence only when `cc.gap > 0`, ignoring `group_checks`. This is likely in the 미래모빌리티 + 모빌리티데이터분석 demo because A/B group minima are independent of the 36학점 total.  
   **Fix:** compute `conv_unmet = max(cc.gap, ...group gaps)` everywhere a convergence status is summarized. Add group gap chips such as `모빌리티데이터분석융합전공 B그룹 6학점`.

4. **MEDIUM [REGRESSION] — round-4 multi-convergence dedup is fixed in backend but not in frontend display.**  
   Backend correctly dedups by prefix at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). But the frontend note sums scalar `to_fusion_credits` across convergence checks at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592). With two convergence programs sharing the same physical course, the 전공 gauge deducts the union, but the note can display a larger number.  
   **Fix:** expose `major_to_fusion_deducted_credits` from backend, or union `to_fusion_course_credits` prefixes in the frontend before summing.

5. **MEDIUM [REGRESSION] — “후보 없음, 초과학기로 해결 불가” still gets contradicted by hints/workflow.**  
   `run_planner` correctly separates `unfillable` in the blocked reason at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:725), but when there is no `overflow`, it still sets `relaxation_hint` to “잔여 학기를 늘리거나 계절학기를 활용하세요” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:729). The workflow also labels every blocked plan as “초과학기 필요” / “미배치 → 초과학기” at [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61) and [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78). That directly contradicts “초과학기로 해결 불가”.  
   **Fix:** branch by validation error codes. If only `pool_exhausted`, hint should be “학과 확인 필요 / 대체 인정 확인 필요”, and workflow branch should say “후보 고갈”.

**Round-4 Verification**

Items 1, 2, 3, 4, 5, 6 are implemented as requested. Item 7 is incomplete because UI/workflow hints still imply 초과학기 can solve candidate exhaustion. Item 8 is backend-fixed but frontend display still regresses via non-deduped summation.

**Test Note**

I attempted targeted tests, but the default environment is Python 3.8 and fails on `str | None`; Python 3.10 exists but has no project dependencies installed.
===== /tmp/codex_r5_9.txt =====
   534	                if acc >= r["need"]:
   535	                    break
   536	                key = normalize_name(it["name_ko"])
   537	                if key in seen:
   538	                    # 다른 요건이 이미 선택한 과목 — 이 요건 quota에 '가산하지 않는다'.
   539	                    # (가산하면 융합 과목이 전공 quota를 거짓 충당해 중복인정 한도를 우회하고,
   540	                    #  필수지정은 major_gap_eff에서 이미 차감돼 이중 차감이 됨 — 라운드4 검증)
   541	                    continue
   542	                seen.add(key); selected.append({**it, "area": r["area"], "priority": r["priority"]}); acc += it["credits"]
   543	            if acc + 0.01 < r["need"]:
   544	                unfillable.append({"label": r["label"], "shortfall": round(r["need"] - acc, 1)})
   545	

**Findings**

1. **HIGH [REGRESSION] Alias-equivalent courses are still double-selectable in the planner.**  
   [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:331) uses `aliases` to treat `미래모빌리티기초 ↔ 자동차모빌리티기초` and `미래모빌리티AD ↔ 자동차모빌리티 Adventure Design` as equivalent, backed by [required_names_by_year.json](/home/carol/kmu_genai/data/graduation/v2/required_names_by_year.json:170). But planner required-course resolution only does `cat["by_norm"].get(normalize_name(n))` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:445), and dedup keys only `normalize_name(it["name_ko"])` at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:527) / [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:536).  
   Why this matters: in the 2023 미래모빌리티 + 모빌리티데이터분석 demo, a missing 2023 요람 required name like `미래모빌리티기초` can be selected as one required item while the convergence pool separately selects `자동차모빌리티기초`. Same physical course, two quotas, wrong roadmap.  
   Fix: share/export the alias canonicalizer used by audit, resolve required names through alias hits into current catalog course IDs, and dedup selected candidates by canonical alias key or course prefix, not display-name norm only.

2. **HIGH [REGRESSION] `unfillable` is separated numerically, but the user-facing hint contradicts it.**  
   The blocked reason correctly says candidate exhaustion is “초과학기로 해결 불가” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:725), but the fallback hint still says “잔여 학기를 늘리거나 계절학기를 활용하세요” at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:729). The frontend then renders both together at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:655) and again at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:707).  
   Why this matters: grader sees “extra semester cannot solve this” and “increase semesters/use seasonal” on the same card.  
   Fix: if `unfillable` exists and `unplaced_cr == 0`, set hint to 학과 대체인정/개설 후보 확인. If mixed, split overflow hint from candidate-exhaustion hint. Also render blocked warning once.

3. **MEDIUM [REGRESSION] Workflow trace collapses all blocked states into “초과학기 필요”.**  
   [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:61) labels every blocked plan as `실현불가(초과학기 필요)`, even when [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:656) returns `no_candidates` or [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:695) reports `pool_exhausted`. [pipeline.py](/home/carol/kmu_genai/graduation_center/v2/pipeline.py:78) similarly maps every failed validation to `미배치 → 초과학기`.  
   Why this matters: this directly violates the requested 6-branch state-machine clarity. The graph can contradict the roadmap text.  
   Fix: branch by validation codes/status: `충족`, `후보없음`, `현재학기미입력`, `잔여0`, `후보고갈/학과확인`, `배치생성`, `초과학기필요`.

4. **MEDIUM [REGRESSION] Backend deduped multi-convergence 전공 차감, frontend still sums it.**  
   Backend correctly unions `to_fusion_course_credits` by prefix at [audit_v2.py](/home/carol/kmu_genai/graduation_center/v2/audit_v2.py:292). The UI note ignores that and reduces raw `c.to_fusion_credits` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:592).  
   Why this matters: with two convergence programs, the 전공 gauge can use a deduped subtraction while the note says a larger duplicated number was excluded.  
   Fix: expose `to_fusion_total_dedup` from backend, or have frontend union `to_fusion_course_credits` maps before displaying.

5. **MEDIUM Interactive 3-way convergence UI can contradict backend roadmap/risk.**  
   `primaryCr`/`fusionCr` recompute locally from `sel` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:103), but `groupsOk` stays static from backend `cc.group_checks` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:108), and roadmap remaining chips still use backend `cc.gap` at [GraduationV2.jsx](/home/carol/kmu_genai/frontend/src/components/GraduationV2.jsx:673).  
   Why this matters: after a user clicks assignment buttons, the convergence block can say one thing while risk/roadmap still reflect the original allocation.  
   Fix: either make 3-way controls read-only/explanatory for demo, or send selected allocation back through audit/planner and recompute all dependent numbers.

**Round-4 Fix Check**

1. Exact-name seen-dedup: mostly verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:522), but alias-equivalent dedup is still broken.  
2. 전공 `gap_not_closed`: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:704).  
3. Seasonal capacity: verified at [risk.py](/home/carol/kmu_genai/graduation_center/v2/risk.py:68).  
4. Aliases added: data verified, planner usage incomplete.  
5. 기초교양 gap guard: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:500).  
6. Missing prereq soft flag: verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:579).  
7. Overflow excludes unfillable: numeric part verified at [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py:719), user-facing hint regressed.  
8. Multi-convergence backend dedup: backend verified, frontend display incomplete.
===== /tmp/codex_r5_findings.txt =====
