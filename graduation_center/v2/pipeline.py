"""v2 오케스트레이션 — verify / audit 두 단계 + JSON-first 응답 조립.

run_verify: 엑셀(여러 학기) → 매칭 → 편집 가능한 검증 테이블 반환(HITL).
run_audit : 사용자 확정 테이블 → 진단 → 로드맵(LLM+검증) → 리스크 → AuditPipelineResponse.
"""
from __future__ import annotations

from graduation_center.v2.audit_v2 import compute_audit
from graduation_center.v2.catalog import assemble_requirement_profile
from graduation_center.v2.excel_parser import parse_many
from graduation_center.v2.models_v2 import (
    AuditPipelineResponse, CourseMatch, NodeTraceEvent, Source, StudentContext,
    VerifiedCourse,
)
from graduation_center.v2.planner import run_planner
from graduation_center.v2.risk import compute_risk
from graduation_center.v2.verification import build_verification_table, finalize_transcript


def run_verify(files: list[tuple[bytes, str]], context: dict) -> dict:
    ctx = StudentContext.model_validate(context)
    lines, retakes = parse_many(files)
    table, unresolved, retakes = build_verification_table(lines, ctx.program_id, retakes)
    matched_n = sum(1 for t in table if t.course_id and not t.aggregate_only)
    agg_n = sum(1 for t in table if t.aggregate_only)
    trace = [
        NodeTraceEvent(node="요람 로딩", kind="tool", summary=f"{ctx.program_id} 카탈로그·요건 로드"),
        NodeTraceEvent(node="데이터 수집", kind="tool",
                       summary=f"{len(files)}개 학기 파일 · {len(lines)}개 수강행", branch_taken=f"{len(files)}개 학기 병합"),
        NodeTraceEvent(node="코드 매칭", kind="tool",
                       summary=f"매칭 {matched_n} · 집계 {agg_n} · 미해소 {len(unresolved)}",
                       branch_taken=("미해소 있음" if unresolved else "전부 분류")),
    ]
    return {
        "context": ctx.model_dump(),
        "verification_table": [t.model_dump() for t in table],
        "unresolved": [u.model_dump() for u in unresolved],
        "possible_retakes": retakes,
        "node_trace": [e.model_dump() for e in trace],
    }


def run_audit(payload: dict, client=None) -> AuditPipelineResponse:
    ctx = StudentContext.model_validate(payload["context"])
    table = [VerifiedCourse.model_validate(x) for x in payload.get("verification_table", [])]
    unresolved = [CourseMatch.model_validate(x) for x in payload.get("unresolved", [])]
    retakes = payload.get("possible_retakes", [])

    verified = finalize_transcript(table, unresolved, retakes)
    profile = assemble_requirement_profile(ctx)
    audit = compute_audit(verified, profile, convergence_program_ids=ctx.convergence_program_ids,
                          convergence_tracks=ctx.convergence_tracks)
    plan, vrep, pctx = run_planner(audit, profile, ctx, verified, client=client)
    feasible = plan.feasible if plan.status != "not_generated" else None
    # 초과학기 1학기 완화(risk D→C)는 '실제 경로 검증' 후에만 — overflow의 extra는 학점 환산
    # 추정치라 개설학기·선수 제약으로 더 늘 수 있음(라운드5 codex). 잔여+1로 재배치가
    # 실제 feasible일 때만 overflow를 risk에 전달해 완화를 허용한다(결정론 재실행 1회).
    overflow_for_risk = plan.overflow
    if plan.status == "blocked" and plan.overflow and plan.overflow.extra_semesters <= 1:
        ctx_plus = ctx.model_copy(update={"remaining_semesters": ctx.remaining_semesters + 1})
        plan_plus, _, _ = run_planner(audit, profile, ctx_plus, verified, client=client)
        if plan_plus.feasible is not True:
            overflow_for_risk = None                  # 경로 미검증 → 완화 금지(D 유지)
    risk = compute_risk(audit, ctx, roadmap_feasible=feasible, overflow=overflow_for_risk)
    sources = [Source.model_validate(s) for s in pctx.get("sources", [])]

    conv_n = len(audit.convergence_checks)
    n_terms = len(plan.terms)
    n_courses = sum(len(t.courses) for t in plan.terms)
    if plan.status == "blocked":
        plan_branch = "실현불가(초과학기 필요)"
    elif not plan.terms:
        plan_branch = "갭 없음(이미 충족)" if plan.feasible else "학기 배치 보류"
    else:
        plan_branch = f"{n_terms}학기 {n_courses}과목 배치"
    # 결정론 통합 플래너(LLM 미사용) — 노드는 'tool', 검증은 미배치/학점상한 결정론 체크
    trace = [
        NodeTraceEvent(node="데이터 검증", kind="hitl",
                       summary=f"확정 {len(verified.confirmed_courses)} · 제외 {len(verified.excluded)} · {verified.total_earned}학점",
                       branch_taken="사용자 확정"),
        NodeTraceEvent(node="갭 계산", kind="tool",
                       summary=f"총 부족 {audit.total_gap} · 필수누락 {len(audit.missing_required_names)} · 연계융합 {conv_n}건",
                       # '충족'은 총학점·영역·필수·융합(그룹 포함) 전부 충족일 때만 — 리포트 ⚠️와 모순 방지
                       branch_taken=(("부족 있음" if (
                           audit.total_gap > 0 or any(g.gap > 0 for g in audit.area_gaps)
                           or bool(audit.missing_required_names)
                           or any(cc.get("gap", 0) > 0 or any(gc["gap"] > 0 for gc in cc.get("group_checks", []))
                                  for cc in audit.convergence_checks)) else "충족")
                           + (f" · 융합 {conv_n}건" if conv_n else ""))),
        NodeTraceEvent(node="로드맵 배치", kind="tool",
                       status="ok" if plan.status != "blocked" else "warn",
                       summary=plan.why_this_plan or plan.blocked_reason or "", branch_taken=plan_branch),
        NodeTraceEvent(node="로드맵 검증", kind="validator",
                       status="ok" if vrep.ok else "fail",
                       summary=("통과(선수·개설학기·학점상한)" if vrep.ok else f"{len(vrep.errors)}건 미충족"),
                       branch_taken=("통과" if vrep.ok else "미배치 → 초과학기")),
        NodeTraceEvent(node="리스크 산정", kind="tool",
                       summary=f"{risk.grade} {risk.label} ({risk.score})", branch_taken=f"{risk.grade} {risk.label}"),
    ]
    md = _markdown(ctx, profile, audit, risk, plan)
    return AuditPipelineResponse(
        context=ctx, verified_transcript=verified, audit=audit, risk=risk,
        roadmap=plan, sources=sources, node_trace=trace, report_markdown=md,
    )


def _markdown(ctx, profile, audit, risk, plan) -> str:
    L = [f"# 졸업사정 컨설팅 리포트 — {profile.department_name_ko}",
         f"**종합 판정: {risk.grade} {risk.label}**  ·  총 {audit.total_earned:.0f}/{audit.total_required:.0f}학점"
         f"  ·  적용 요람 {profile.applied_yoram}", "", "## 영역별 현황"]
    for g in audit.area_gaps:
        mark = "✅" if g.gap <= 0 else f"⚠️ {g.gap:.0f} 부족"
        # 전공 '학점'은 충족이어도 필수지정 미이수가 있으면 ✅만 띄우지 않음(모순 방지)
        if g.area == "전공" and g.gap <= 0 and audit.missing_required_names:
            mark = f"⚠️ 학점 충족 · 필수지정 {len(audit.missing_required_names)}과목 미이수"
        L.append(f"- {g.area}: {g.earned:.0f}/{g.required:.0f} {mark}")
    if audit.convergence_checks:
        L += ["", "## 연계·융합전공 (학점 중복인정 반영)"]
        for cc in audit.convergence_checks:
            mark = "✅" if cc["gap"] <= 0 else f"⚠️ {cc['gap']:.0f} 부족"
            L.append(f"- {cc['name']}({cc['track']}·{cc['conv_type']}): {cc['earned']:.0f}/{cc['required']:.0f} {mark}"
                     f"  [제1전공과 겹침 {cc['overlap_credits']:.0f} 중 중복인정 가능 {cc['double_recognizable']:.0f}/{cc['double_cap']:.0f}]")
            for gc in cc.get("group_checks", []):
                gm = "✅" if gc["gap"] <= 0 else f"⚠️ {gc['gap']:.0f} 부족"
                L.append(f"    · {gc['group']}: {gc['earned']:.0f}/{gc['required']:.0f} {gm}")
            if cc["recommend_double_count"]:
                L.append(f"  · 중복인정 신청 권장: {', '.join(cc['recommend_double_count'])}")
            if cc.get("note"):
                L.append(f"  · {cc['note']}")
    if not profile.required_course_ids:
        L += ["", f"※ {profile.department_name_ko} 요람 필수지정 과목 데이터 미구축 — 필수과목 체크 제외(확인 필요)"]
    if audit.missing_required_names:
        L += ["", "## 미이수 필수지정"] + [f"- {n}" for n in audit.missing_required_names]
    core_short = [g for g in audit.core_area_gaps if g.gap > 0]
    if core_short:
        L += ["", "## 핵심교양 영역 부족"] + [f"- {g.area}: {g.earned:.0f}/{g.required:.0f}" for g in core_short]
    L += ["", "## 추천 로드맵"]
    if plan.status == "not_generated":
        L.append("- (LLM 미설정 — 결정론 진단만 제공)")
    elif plan.status == "blocked":
        # 부분 배치가 있으면 숨기지 않고 보여준다(JSON 로드맵과 markdown 표면 일치).
        for t in plan.terms:
            courses = ", ".join(f"{c.name_ko}({c.credits:.0f})" for c in t.courses)
            L.append(f"- {t.term}: {courses}")
        L.append(("- ⚠️ 일부만 배치 가능: " if plan.terms else "- 실현 가능한 계획 없음: ")
                 + (plan.blocked_reason or ""))
        # overflow 섹션이 같은 사유를 다시 출력하므로 hint는 overflow 없을 때만(중복 방지)
        if plan.relaxation_hint and not plan.overflow:
            L.append(f"  - {plan.relaxation_hint}")
    elif not plan.terms:
        L.append(f"- {plan.why_this_plan}")
    else:
        for t in plan.terms:
            courses = ", ".join(f"{c.name_ko}({c.credits:.0f})" for c in t.courses)
            L.append(f"- {t.term}: {courses}")
        if plan.why_this_plan:
            L.append(f"  - 왜 이 계획: {plan.why_this_plan}")
    if plan.overflow:
        o = plan.overflow
        # note에 사유(용량/개설학기 제약)가 담겨 있으므로 그대로 사용 — '12<19인데 왜 못 채움'
        # 같은 단독 문장 어색함 방지(개설학기 제약 캐비엣 포함)
        L += ["", "## ⚠️ 초과학기 예상 시나리오",
              f"- {o.note}",
              f"- 졸업까지 최소 **{o.total_semesters_needed}학기**(초과학기 **{o.extra_semesters}학기**) 필요"
              + (f" · 예상 졸업: **{o.projected_graduation_term}**" if o.projected_graduation_term else "")]
    return "\n".join(L)
