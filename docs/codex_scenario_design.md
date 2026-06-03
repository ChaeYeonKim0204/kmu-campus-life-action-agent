**Recommendation**
Build a deterministic unified planner for the demo. Do not depend on the LLM for semester placement. The LLM adds risk without adding much value for near-graduation cases where the plan is usually 1-4 items. Keep the current “LLM roadmap + validator” story only as optional/secondary. For the live demo, the impressive part should be: “all remaining obligations are normalized into one candidate pool, placed into semesters, then revalidated.”

The key shift: stop treating “course catalog candidate” as the only plannable unit. Treat every remaining obligation as a `PlanCandidate`, including name-only required courses, convergence courses, and 교양 slots.

**1. Unified Candidate Schema**
Add an internal schema, either as Pydantic models in [models_v2.py](/home/carol/kmu_genai/graduation_center/v2/models_v2.py) or as typed dicts in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py):

```python
class PlanCandidate(BaseModel):
    candidate_id: str               # stable synthetic id: major:1234567, req-name:<norm>, conv:<pid>:<norm>, gen-core:<area>:1
    kind: Literal[
        "major_catalog",
        "required_name",
        "convergence_course",
        "gen_basic_required",
        "gen_core_slot",
        "gen_free_slot",
        "free_credit_slot",
    ]

    name_ko: str
    course_id: str | None = None
    credits: float

    requirement_area: str           # 전공, 기초교양, 핵심교양, 자유교양, 융합전공, 일반선택
    satisfies: list[str]            # ["전공 부족", "필수지정", "융합전공 A그룹", "핵심교양-소통"]
    priority: int                   # lower first: 필수 > 융합그룹부족 > 전공부족 > 교양 > 총학점

    program_id: str | None = None
    convergence_group: str | None = None
    assignment: Literal["제1전공", "융합전공", "중복인정", "교양", "일반선택"] | None = None

    offered_terms: list[str] = ["1", "2"]
    offered_terms_certainty: Literal["known", "unknown", "flexible"] = "unknown"
    prerequisites: list[str] = []
    prereq_certainty: Literal["known", "unknown"] = "unknown"

    source_ids: list[str] = []
    confidence: Literal["catalog_verified", "name_only", "generic_slot"]
    manual_check_required: bool = False
```

How to handle weak data:

- **major-by-code**: `confidence="catalog_verified"`, hard validate offered terms/prereqs.
- **required-by-name**: create `kind="required_name"`, `course_id=None`, `confidence="name_only"`. For demo, add credits to `required_names_by_year.json` if possible. If no credit data exists, assume `3.0` only with `manual_check_required=True` and show “학점/개설학기 확인 필요”.
- **convergence-by-name+group**: create real candidates from `audit.convergence_checks[].courses` where `taken=False`. You know `name_ko`, `group`, `credits`; set `offered_terms=["1", "2"]`, `offered_terms_certainty="unknown"`.
- **교양 gaps**: do not invent course names. Create slots:
  - `핵심교양-소통 3학점 선택`
  - `기초교양 필수: 글로벌영어`
  - `자유교양 3학점 선택`
  These are plannable credit blocks, not fake courses.

Validator change: unknown/flexible offered terms should not hard-fail. It should produce assumptions/warnings. Hard validation only applies where `offered_terms_certainty=="known"`.

**2. Convergence Allocation**
Decide default convergence allocation **before planning**, deterministically. The roadmap needs to know whether a convergence course is being used as `융합전공`, `제1전공`, or `중복인정`.

Use this default rule:

1. Already-taken overlap courses: assign `중복인정` up to cap, prioritizing primary-required overlap first, then higher credits.
2. If primary major gap remains, assign remaining overlap to `제1전공`.
3. If convergence gap remains, assign remaining overlap or untaken convergence courses to `융합전공`.
4. Future overlap courses may be `중복인정` only if cap remains and they help both primary/convergence.
5. Never move a primary required course away from primary; allow `중복인정` if cap allows.

Make it user-adjustable, but not LLM-adjustable. Current `ConvergenceBlock` already has local 3-way selection. Change it so the selected allocation is sent back to the backend as `convergence_allocation_overrides`, then re-run audit/planning. Until that is implemented, use deterministic defaults only.

Important: convergence should stop being a separate static “미이수 시나리오.” It should feed candidates into the same roadmap.

**3. Deterministic vs LLM**
For this demo, I would implement deterministic semester placement and either remove the LLM dependency from the demo path or make it optional.

Deterministic planner should own:

- candidate pool creation
- convergence allocation defaults
- term generation
- credit cap packing
- offered-term hard checks when known
- prereq order when known
- overflow calculation
- report rationale

LLM should not write factual rationale. If you must keep an LLM node for the rubric/demo story, use it only for a harmless ordering preference among already-built candidates, then still let deterministic code place and validate. But honestly, near-grad roadmaps are small enough that deterministic greedy will look better and fail less often.

Suggested greedy placement:

1. Build allowed terms from current term + remaining semesters + seasonal flag.
2. Sort candidates:
   - missing required
   - convergence group gaps
   - major area gap
   - gen basic required
   - core/free/general slots
   - total credit fillers
3. Within same priority: known single-term offerings first, prereq depth earlier, higher confidence first.
4. Place each candidate into earliest term that:
   - has capacity
   - matches known offered term
   - comes after known prereqs
5. If candidate cannot fit, run overflow using unified planned shortfall, not just `audit.total_gap`.

Current [project_overflow](/home/carol/kmu_genai/graduation_center/v2/planner.py) misses convergence/name-only pressure because it only sees total/area gaps. Change it to accept `required_candidate_credits` or `planning_shortfall_credits`.

**4. UX**
Make one main card: `졸업까지 학기별 추천 시나리오`.

Structure it like a consulting plan:

1. **남은 요건 요약**
   - `필수지정 1과목`
   - `융합전공 6학점 부족`
   - `핵심교양 소통 3학점 부족`
   - `총학점 0학점 부족`

2. **Timeline**
   - `2026-2`
     - `미래모빌리티실험및실습 · 3학점 · 필수지정 · 이수구분: 제1전공`
     - `융합전공 A그룹 선택 · 3학점 · 이수구분: 융합전공`
   - `2027-1`
     - `핵심교양 소통영역 선택 · 3학점 · 교양 슬롯`

3. **융합 이수구분 배정**
   - compact table showing `중복인정 / 제1전공 / 융합전공`
   - show cap used: `중복인정 9/12학점`
   - show group status after plan

4. **확인 필요**
   - `개설학기 미확인: 이름 기준/융합 요람 과목은 실제 수강신청 전 확인`
   - `교양 슬롯은 과목명이 아니라 영역 충족용 선택 슬롯`

Keep the existing `ConvergenceBlock`, but demote it from “separate scenario” to “allocation detail.” The main story should be the unified timeline.

**5. Implementation Order**
1. Add `PlanCandidate` and update `RoadmapCourse`.
   - Prefer adding `candidate_id`, `assignment`, `confidence`, `manual_check_required`.
   - Do not keep stuffing synthetic IDs into `course_id`.

2. Replace `build_planning_context()` in [planner.py](/home/carol/kmu_genai/graduation_center/v2/planner.py) with `build_unified_candidate_pool()`.
   - Pull from `audit.area_gaps`, `audit.missing_required_names`, `audit.gen_basic_courses`, `audit.core_area_gaps`, and `audit.convergence_checks`.

3. Add deterministic `plan_roadmap_greedy()`.
   - Use current `_allowed_terms`, `_term_key`, credit cap logic, and overflow logic.
   - Make this the default path for demo.

4. Rewrite `validate_roadmap()` around `candidate_id`.
   - Hard-check caps, duplicate candidates, term range.
   - Hard-check offered terms/prereqs only for known catalog-backed candidates.
   - Recompute convergence cap/group satisfaction after planned assignments.

5. Change `project_overflow()`.
   - Use unified required planned credits, including name-only required, convergence shortfall, and 교양 slots.

6. Frontend roadmap card:
   - render pills by `requirement_area` / `assignment`
   - show `개설 확인 필요` badge for `confidence!="catalog_verified"`
   - show one unified timeline before the detailed `ConvergenceBlock`.

7. Remove or stop using the special-case branches in `run_planner()` that say:
   - “필수지정 과목 직접 수강 필요”
   - “교양 직접 확인”
   These should become candidate slots in the roadmap, not terminal fallbacks.

The simplest reliable demo path is: deterministic audit → unified candidate pool → deterministic semester packing → deterministic validation → polished timeline. That will look more intelligent than the current LLM path because it actually plans the demo student’s real remaining obligations.
