# Graduation Center — Implementation Spec (for coding agents)

> Build target for the KMU "graduation audit consulting agent". Companion to the Korean overview [`graduation_center_direction.md`](./graduation_center_direction.md). When the two conflict, the **scope** here (LEAN) wins.
> Audience: coding agents. Be deterministic where accuracy matters; never let the LLM invent facts.

---

## 1. Goal

Given a student's verified course-registration data + their admission-year/major 요람 (curriculum requirements), the system:
1. **Diagnoses** graduation feasibility (per-area credit gaps, missing required courses).
2. **Grades risk** deterministically (안전 / 주의 / 위험 / 졸업불가 가능성).
3. **Plans a single recommended semester-by-semester roadmap** to graduate safely, grounded in the 요람.
4. **Presents** it as a visual consulting-report dashboard with collapsible citations.

**Differentiation**: grounded accuracy ("정합성") — exact requirements for *this* admission year × major, exact gap math, no hallucinated requirements. This is what a commercial LLM cannot do.

---

## 2. Scope (LEAN — locked)

**IN (build now):**
- Excel registration-history ingest (clean, pre-prepared, real-format) + course-code → catalog match
- User verification step (HITL): exclude 폐강, mark F/retake, confirm → `VerifiedTranscript`
- Deterministic audit (per-area gaps, missing required courses)
- Deterministic risk grade (with reason components)
- **Single recommended semester roadmap** (LLM-planned, deterministically validated)
- Visual-dashboard consulting report (JSON-first) with citations toggle

**DEFERRED (do NOT build yet):**
- Multi-path comparison (substitute vs seasonal vs early-grad vs micro-degree A/B/C scenarios)

**OUT (non-goals):**
- OCR transcript-PDF path, ON국민 download onboarding guide (later if time), Excel format validation/error UX, automatic F/retake detection, all-departments/all-years, free-form tool-choosing ReAct, external actions (no calendar/email/notion — that's the *other* team topic).

**Demo scope**: one department (AI빅데이터융합경영학과), 1–2 admission years, happy path, pre-loaded clean data.

---

## 3. Architecture — "Bounded Audit Agent"

Deterministic code owns **facts**. LLM owns **planning judgment** over those facts. Deterministic code **validates** the LLM output.

```
Excel parse
  → match_courses_to_catalog()        [deterministic]
  → user verification (HITL)           → VerifiedTranscript
  → compute_audit()                    [deterministic]  → AuditResult
  → compute_risk()                     [deterministic]  → RiskAssessment
  → plan_roadmap()                     [LLM]            → RoadmapPlan (proposed)
  → validate_roadmap()                 [deterministic]  → ValidationReport
        if invalid → repair_roadmap()  [LLM, 1 pass max] → re-validate
        if still invalid → honest failure (no fabricated plan)
  → assemble_report()                  [deterministic JSON-first; LLM only drafts prose narrative]
```

**Hard rule**: the LLM may only reference courses/requirements present in the structured facts it is given. The validator re-checks every LLM claim against those facts. Anything unverifiable is dropped or surfaced as "확인 필요" — never asserted.

---

## 4. Modules & responsibilities

| Module | Responsibility | Det / LLM |
|---|---|---|
| `parser_excel.py` | Read ON국민 registration Excel → raw course lines (merge multiple semesters) | Det |
| `catalog.py` | Load catalog; `match_course(line, catalog)` by code → name → alias → fuzzy | Det |
| `verification.py` | Build editable verification table; apply user edits (exclude 폐강, mark F/retake) → `VerifiedTranscript` | Det |
| `requirements.py` | `assemble_requirement_profile(context)` — compose admission-year × major(+minor) rules | Det |
| `audit.py` | `compute_audit(verified, profile)` → per-area gaps, missing required courses | Det |
| `risk.py` | `compute_risk(audit, context)` → grade + reason components | Det |
| `planner.py` | `plan_roadmap(planning_context)` (LLM) + `validate_roadmap()` (Det) + `repair_roadmap()` (LLM, 1×) | LLM+Det |
| `report.py` | Assemble JSON-first response; LLM drafts only the narrative prose | Det(+LLM prose) |

Keep the redesigned core **independent of Chroma/vector search** — it must work from structured JSON. (Current `status()` gates on Chroma; relax that.)

---

## 5. Data schemas (sketch)

```jsonc
// course_catalog.json — one entry per catalog course (hand-verified for the demo dept/years)
{
  "course_id": "2024-AIBIZ-MAJOR-DM",
  "admission_year": 2024,
  "department_id": "ai_bigdata_convergence_management",
  "course_code": "ABM2031",
  "name_ko": "데이터마이닝",
  "aliases": ["데이터 마이닝"],
  "credits": 3,
  "requirement_area": "major_required",   // major_required | major_elective | liberal_basic | liberal_core | liberal_free ...
  "prerequisites": ["ABM1010"],
  "offered_terms": ["2"],                  // which semester(s) offered: "1" | "2" | "summer" | "winter"
  "offering_confidence": "confirmed",      // confirmed | historical_pattern | unknown
  "source": { "doc": "2024 요람", "page": 310 }
}
```

```jsonc
// requirements.json — composable graduation requirements
{
  "profiles": [{
    "profile_id": "2024_ai_bigdata_primary",
    "admission_year": 2024,
    "program_id": "ai_bigdata_convergence_management",
    "track_type": "primary_major",
    "total_credits_min": 130,
    "rules": [
      { "area": "major_required", "min_credits": 18, "required_course_ids": ["..."], "source": {"page": 310} },
      { "area": "major_elective", "min_credits": 30, "source": {"page": 311} }
      // liberal_basic / liberal_core / liberal_free ...
    ]
  }],
  "composition_rules": [
    { "when": {"primary_major": true, "minor": true},
      "effects": [{"target": "minor.min_credits", "set": 21}] }
  ]
}
```

```python
# Pydantic models (v2)
StudentContext        # admission_year, program_id, second_major_ids[], minor_ids[],
                      # remaining_semesters, seasonal_semester_allowed, max_courses_per_term, preferences[]
CatalogCourse         # mirrors course_catalog.json
CourseMatch           # original_line, matched_course_id|None, status, confidence
VerifiedTranscript    # confirmed_courses[] (after 폐강/F/retake exclusion), unresolved[]
RequirementProfile    # composed rules for this student
AuditResult           # gaps[{area, required, earned, gap}], missing_required_course_ids[], total_gap
RiskAssessment        # grade, label, score, reasons[{factor, detail, severity}]
RoadmapPlan           # see §6
ValidationReport      # ok, errors[{code, detail, course_id?}]
```

---

## 6. Roadmap planner contract (the agentic core)

**LLM input** (everything is *given as data* — the LLM relies on nothing from memory):
```jsonc
{
  "student_context": { "admission_year": 2024, "remaining_semesters": 2,
    "seasonal_semester_allowed": false, "max_courses_per_term": 5,
    "preferences": ["데이터분석", "정규학기 우선", "최소 과부하"] },
  "audit_result": { "gaps": [...], "missing_required_course_ids": [...], "total_gap": 12 },
  "candidate_courses": [ /* CatalogCourse subset eligible to fill the gaps, with prerequisites, offered_terms, credits, requirement_area, source */ ],
  "sources": [ { "id": "G2", "page": 311 }, ... ]
}
```

**LLM output schema (strict JSON):**
```jsonc
{
  "feasible": true,
  "roadmap": [
    { "term": "2026-2",
      "courses": [ { "course_id": "...", "credits": 3, "satisfies": "major_required",
                     "reason": "...", "source_ids": ["G2"] } ],
      "term_credits": 15, "term_risk": "low|medium|high", "notes": [] }
  ],
  "why_this_plan": "string (preference-aware rationale)",
  "blocked_reason": null,            // if !feasible: e.g. "2학기 내 불가: 전공필수 2과목이 같은 학기에만 개설"
  "relaxation_hint": null,           // e.g. "잔여 3학기면 가능"
  "assumptions": ["계절학기 미사용", "최대 5과목/학기"]
}
```

**Deterministic validator (`validate_roadmap`) — all must pass:**
- every `course_id` ∈ `candidate_courses`
- no course placed in a term not in its `offered_terms`
- prerequisites appear in an earlier verified term or earlier roadmap term
- `term_credits` ≤ load cap; respects `max_courses_per_term`; `seasonal_semester_allowed`
- planned credits **close every gap** in `audit_result`
- every `source_id` exists; no invented courses/requirements/credits/terms
- roadmap length ≤ `remaining_semesters`

**On failure**: pass `errors` back once → `repair_roadmap()`. If still invalid → return `feasible:false` with a deterministic `blocked_reason` + `relaxation_hint`. **Never render a roadmap that failed validation.**

**Minimum decisions that make it "agentic" (not a sorter):** which gap to prioritize, which eligible course fills which gap, sequencing by prerequisite/offering term, balancing term load, and what to do on conflict (mark infeasible + explain, or ask for a preference). If it merely bins courses into semesters, it is not agentic enough.

---

## 7. Risk grading (deterministic)

Inputs: `total_gap`, max single-area gap, missing-required-course count, unresolved/unconfirmed credits, remaining semesters, GPA-min status (yes/no/unknown), offering-availability risk (required course offered once/year).

| Grade | Label | Criteria (example) |
|---|---|---|
| A | 안전 | all hard reqs met or gap ≤ 3, no missing required |
| B | 주의 | gap ≤ 6, ≤1 missing required, solvable next regular semester |
| C | 위험 | gap 7–15, or ≥2 missing required, or annual-offering risk |
| D | 졸업불가 가능성 | gap > 15, GPA below min, or remaining semesters insufficient |

Return `{grade, label, score, reasons:[{factor, detail, severity}]}` — never a bare label.

---

## 8. API / response (JSON-first)

Backend returns structured JSON; the frontend renders the dashboard from it. `report_markdown` is **for display only, never the source of truth.**
```jsonc
{ "context": {...}, "verified_transcript": {...}, "audit": {...}, "risk": {...},
  "roadmap": {...}, "sources": [...], "node_trace": [...], "report_markdown": "..." }
```
`node_trace`: ordered step events `{node, status, summary}` for the Dify-style workflow visualization
(`요람 로딩 → 데이터 검증 → 갭 계산 → 로드맵 플래닝 → 검증/repair → 리스크 산정`).

---

## 9. Report / dashboard sections

1. Verdict header (risk grade + one-line conclusion + expected graduation term)
2. Context card (admission year, majors, applied 요람)
3. Verification table (editable; 폐강/F/retake toggles)
4. Per-area credit gauges
5. Key issues (gaps, missing required, page refs)
6. **Recommended roadmap timeline + "why this plan"** (the centerpiece)
7. Next-step checklist
8. Citations `G1/G2` — generated & validated, **collapsed by default**, "근거 보기" toggle

Cheap demo strengtheners: assumptions panel, citation toggle, risk badge, `node_trace` visualization, constraint-toggle re-plan (the demo "wow": toggle `remaining_semesters` / `max_courses_per_term` / `seasonal_semester_allowed` → roadmap re-plans, all grounded).

---

## 10. Privacy (minimal)

Input is a registration Excel with **no resident-registration number**. Show the student their own data (needed for verification). Mask only **student-ID trailing digits**. Do not persist; do not transmit to third parties. Demo with own/dummy data. → Strip the old heavy masking in `parser.py`/`service.py` and the reflexive "확인 필요 / 학과사무실 확인" hedging; adopt "assertive when grounded, 'unknown' only when genuinely uncertain."

---

## 11. Build order

1. **Data first** — hand-verified `course_catalog.json` + `requirements.json` (demo dept, 1–2 years). Blocks everything else. (needs 요람 source material)
2. v2 Pydantic schemas (§5)
3. `parser_excel.py` + `catalog.py` (match) + `verification.py` (HITL) → `VerifiedTranscript`
4. `audit.py` + `risk.py` (deterministic)
5. `planner.py` — LLM plan + deterministic validate + 1× repair + honest-failure (§6)
6. `report.py` (JSON-first) + frontend dashboard + `node_trace`

---

## 12. Guardrails / non-negotiables

- Facts are given as data; the LLM invents nothing. Validator re-checks everything.
- No roadmap rendered unless it passes deterministic validation; on hard failure, explain — don't fabricate.
- Deterministic for: matching, audit math, eligibility, prerequisites, offering terms, credits, risk. LLM for: roadmap planning (bounded), prose narrative.
- Citations (`G1/G2`) generated & validated internally even though display is collapsed.
- Stays an inward analysis/planning workflow — **no external actions** (that is the other team's career agent).
