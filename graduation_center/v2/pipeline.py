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
    trace = [
        NodeTraceEvent(node="요람 로딩", summary=f"{ctx.program_id} 카탈로그·요건 로드"),
        NodeTraceEvent(node="데이터 수집", summary=f"{len(files)}개 학기 파일 · {len(lines)}개 수강행"),
        NodeTraceEvent(node="코드 매칭",
                       summary=f"매칭 {sum(1 for t in table if t.course_id)} · 집계 {sum(1 for t in table if t.aggregate_only)} · 미해소 {len(unresolved)}"),
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
    risk = compute_risk(audit, ctx, roadmap_feasible=feasible)
    sources = [Source.model_validate(s) for s in pctx.get("sources", [])]

    trace = [
        NodeTraceEvent(node="데이터 검증", summary=f"확정 {len(verified.confirmed_courses)} · 제외 {len(verified.excluded)} · {verified.total_earned}학점"),
        NodeTraceEvent(node="갭 계산", summary=f"총 부족 {audit.total_gap} · 필수누락 {len(audit.missing_required_course_ids)}"),
        NodeTraceEvent(node="로드맵 플래닝",
                       status="ok" if plan.status == "generated" else ("warn" if plan.status == "not_generated" else "fail"),
                       summary=f"status={plan.status} feasible={plan.feasible}"),
        NodeTraceEvent(node="검증/repair", status="ok" if vrep.ok else "warn",
                       summary="통과" if vrep.ok else f"{len(vrep.errors)}건 → repair/blocked"),
        NodeTraceEvent(node="리스크 산정", summary=f"{risk.grade} {risk.label} ({risk.score})"),
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
        L.append(f"- 실현 가능한 계획 없음: {plan.blocked_reason}  · {plan.relaxation_hint or ''}")
    elif not plan.terms:
        L.append(f"- {plan.why_this_plan}")
    else:
        for t in plan.terms:
            courses = ", ".join(f"{c.name_ko}({c.credits:.0f})" for c in t.courses)
            L.append(f"- {t.term}: {courses}")
        if plan.why_this_plan:
            L.append(f"  - 왜 이 계획: {plan.why_this_plan}")
    return "\n".join(L)
