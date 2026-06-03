**Primary Recommendation**

For the graded live demo: build a **deterministic roadmap planner**, plus a **small bounded ReAct controller** that selects which deterministic tool node runs next. Do **not** let the LLM place courses or generate the final report wholesale.

That gives you the best grade-per-risk ratio: visible agent graph, official-rule grounding, personal transcript DB, deterministic report, and professor-approved “LLM chooses tool, tools do the work.”

**1. Semester Roadmap**

Choose **(a) deterministic greedy placement** as the primary implementation.

Reason:

- Near-graduation students have tiny gaps, so LLM placement adds little value.
- Candidate-pool generation and validation are required anyway.
- A deterministic planner gives stable live-demo output.
- The roadmap is a consulting artifact, not a creative task.
- If the LLM makes one odd semester choice on stage, the whole system looks unreliable.

Recommended structure:

```text
compute_gap
→ build_candidate_pool
→ deterministic_semester_placement
→ validate_roadmap
→ render_sectioned_report
```

Optional: use the LLM only for **short rationale text**, after deterministic facts are locked. Even then, treat it as cosmetic and removable.

I would not use LLM placement for the demo.

**2. LLM Feature Ranking**

| Rank | Feature | Rubric Fit | Demo Risk | Cost | Recommendation |
|---|---|---:|---:|---:|---|
| 1 | **Bounded ReAct controller: next_tool selection only** | 1, 4, 5 | Low-medium | Low-medium | **Build** |
| 2 | **요람·학사규정 RAG Q&A with citations** | 2, 3, 5 | Medium | Medium | **Build if time allows** |
| 3 | 대체경로/추천 | 2, 3, 5 | Medium-high | Medium-high | Only if scoped tightly |
| 4 | Report narrative | 4, 5 weakly | Medium | Low-medium | Avoid as main feature |

Best 1-2 to build:

1. **Bounded ReAct controller**
2. **요람·학사규정 RAG Q&A with citations**

The ReAct controller should choose from a fixed menu:

```json
{
  "next_tool": "compute_gap | retrieve_rule | find_substitute | recalc_convergence | build_roadmap | render_report",
  "reason_code": "missing_required | unclear_rule | convergence_conflict | ready_for_report"
}
```

No free-form tool names. No final answer generation. No hidden business logic.

The RAG Q&A should be used for questions like:

- “이 과목 대체돼?”
- “제가 졸업하려면 뭐가 부족해요?”
- “이 요건은 어느 규정에 근거해요?”

But the answer must cite official 요람/규정 chunks and should not override deterministic audit results.

**3. Is ReAct Worth It?**

Straight answer: **yes, but only as a constrained controller.**

A fixed deterministic graph is architecturally cleaner, but for this rubric it may look like ordinary workflow automation, not an “agent.” Since the professor explicitly emphasized ReAct, a lightweight controller is worth building as presentation leverage.

But it should be ReAct in this narrow sense:

```text
LLM: decides next_tool
Tool node: computes deterministically
Validator: checks result
Graph UI: lights up executed nodes
Report: deterministic renderer
```

Do not build a full open-ended ReAct agent. That would be demo-risky and unnecessary.

So: ReAct is partly “theater,” but it is useful theater because it maps directly to the grading language. Keep it bounded and observable.

**4. Highest-ROI LLM Feature**

Single highest-ROI LLM feature:

> **Bounded ReAct tool-selection controller visualized in the workflow graph.**

Build this because it directly hits the professor’s differentiator: “LLM이 next_tool만 고른다, 실행은 결정론 도구 노드.”

Explicitly do **not** build:

- LLM semester placement
- LLM-generated full consulting report
- Open-ended autonomous ReAct loops
- Broad recommendation generation without official-source citations
- Complex multi-semester optimization beyond deterministic greedy + validator

The winning demo story should be:

> “The LLM does not decide graduation eligibility. It only selects the next official grounded tool. The deterministic tools compute gaps, substitutions, convergence allocation, and semester roadmap using the student DB and 요람 rules. Every branch is visible in the graph, and every procedural claim is grounded or cited.”

That is the safest design and the best match to the rubric.
