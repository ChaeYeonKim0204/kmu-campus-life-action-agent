"""졸업 시나리오 상담 Agent (What-if) — Tool Calling 패턴 (예제06 매개변수 추출기 동형).

질문 입력 → ① 매개변수 추출기(LLM 1회: category+delta) → ② 조건 가드(IF/ELSE)
→ ③ 졸업사정 재실행(기존 run_audit ×2, skip_explain) → ④ 시나리오 비교(결정론 diff)
→ ⑤ 다음 행동 제안(결정론 룰). LLM은 자연어→파라미터 변환만 — 판정·비교·제안은 전부 결정론.

가드레일: delta는 strict json_schema(전 필드 required+nullable, enum 동적)로만 받고,
적용은 StudentContext.model_validate 재검증(model_copy는 validator 미실행 — 검증 라운드1).
모든 실패는 500이 아니라 status="unsupported"로 degrade(데모 중 에러 화면 금지).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from graduation_center.v2.catalog import (
    PREV_GPA_BONUS, assemble_requirement_profile, load_catalog, load_programs,
    regular_term_cap,
)
from graduation_center.v2.models_v2 import (
    AuditPipelineResponse, NodeTraceEvent, StudentContext, WhatIfDelta, WhatIfDiff,
    WhatIfResponse,
)
from graduation_center.v2.pipeline import run_audit
from graduation_center.v2.planner import _nth_regular_term

CACHE_PATH = Path("data/graduation/v2/whatif_cache.json")
CATEGORIES = ["휴학", "수강학기변경", "계절학기", "학점상한", "다전공변경", "성적우수", "기타"]


def _term_ko(label: str | None) -> str:
    """학기 라벨 사람용 표기: 2027-1 → 2027-1학기, 2027-S → 2027 하계."""
    if not label:
        return "미상"
    y, _, s = label.partition("-")
    return {"1": f"{y}-1학기", "2": f"{y}-2학기", "S": f"{y} 하계", "W": f"{y} 동계"}.get(s, label)


# ---------- ① 매개변수 추출기 (LLM) ----------
def _candidates(ctx: StudentContext) -> tuple[list[str], list[str]]:
    """add/drop 후보 — add는 카탈로그가 실제 load되는 비-primary만(검증 라운드2 M3)."""
    progs = load_programs()
    add_ids = []
    for pid, p in progs.items():
        if p.get("track_type", "primary") == "primary":
            continue
        if pid == ctx.program_id or pid in ctx.convergence_program_ids:
            continue
        try:
            load_catalog(pid)
        except Exception:
            continue
        add_ids.append(pid)
    return sorted(add_ids), sorted(ctx.convergence_program_ids)


def _schema(add_ids: list[str], drop_ids: list[str]) -> dict:
    """strict 출력 schema — 전 필드 required, Optional=nullable union, 빈 enum 절대 금지.
    후보 0개인 array는 enum 없이 maxItems:0으로 닫는다(검증 라운드2·3)."""
    conv_item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "program_id": ({"type": "string", "enum": add_ids} if add_ids
                           else {"type": "string"}),
            "track": {"type": "string", "enum": ["다전공", "부전공"]},
        },
        "required": ["program_id", "track"],
    }
    add_schema = {"type": "array", "items": conv_item}
    if not add_ids:
        add_schema["maxItems"] = 0
    drop_schema = {"type": "array",
                   "items": ({"type": "string", "enum": drop_ids} if drop_ids
                             else {"type": "string"})}
    if not drop_ids:
        drop_schema["maxItems"] = 0
    delta = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "calendar_delay_terms": {"type": ["integer", "null"]},
            "remaining_semesters_change": {"type": ["integer", "null"]},
            "seasonal_semester_allowed": {"type": ["boolean", "null"]},
            "max_credits_per_term": {"type": ["number", "null"]},
            "prev_term_gpa_ge_375": {"type": ["boolean", "null"]},
            "add_convergence": add_schema,
            "drop_convergence": drop_schema,
        },
        "required": ["calendar_delay_terms", "remaining_semesters_change",
                     "seasonal_semester_allowed", "max_credits_per_term",
                     "prev_term_gpa_ge_375", "add_convergence", "drop_convergence"],
    }
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "category": {"type": "string", "enum": CATEGORIES},
            "interpretable": {"type": "boolean"},
            "question_summary": {"type": "string", "maxLength": 80},
            "delta": delta,
        },
        "required": ["category", "interpretable", "question_summary", "delta"],
    }


def _prompt(question: str, ctx: StudentContext, conv_names: list[str]) -> str:
    conv = ", ".join(conv_names) if conv_names else "없음"
    return f"""졸업사정 시뮬레이션의 매개변수 추출기다. 학생의 자연어 질문을 변경 파라미터(delta)로 변환한다.

현재 컨텍스트(참고만 — 같은 값이어도 delta는 질문 그대로 채운다, no-op 판정은 시스템이 한다):
- 현재 학기: {ctx.current_term or "미입력"} · 잔여 수강 학기: {ctx.remaining_semesters}
- 계절학기 허용: {ctx.seasonal_semester_allowed} · 신청 융합전공: {conv}

필드 의미(혼동 금지):
- calendar_delay_terms: 휴학 — 수강 학기 수는 그대로, 시작(졸업) 시점만 N개 정규학기 뒤로. "다음 학기 휴학"=1, "1년 휴학"=2.
- remaining_semesters_change: 실제 남은 수강 학기 수 증감. "한 학기 더 다니면"=+1, "한 학기 줄이면"=-1.
- seasonal_semester_allowed: 계절학기 수강 가능 여부 변경.
- max_credits_per_term: 학기당 수강 학점 상한 변경. "15학점씩만 들으면"=15.
- prev_term_gpa_ge_375: 직전학기 평점 3.75 이상 여부(신청학점 +{PREV_GPA_BONUS:.0f} 보너스).
- add_convergence / drop_convergence: 융합·연계전공 추가/포기.

규칙:
- 위 필드로 표현 불가한 질문(조기졸업 요건, 전과, 성적포기, 특정 과목, "이번 학기 안에"류 절대 시점)은 interpretable=false.
- 변경이 없는 필드는 null(또는 빈 배열). 질문에 없는 변경을 만들지 마라.
- question_summary는 해석을 40자 내로 요약(한국어).

질문: {question}"""


def interpret_question(question: str, ctx: StudentContext, client,
                       model: str, add_ids: list[str], drop_ids: list[str]) -> dict:
    progs = load_programs()
    conv_names = [progs.get(p, {}).get("name_ko", p) + f"({p})"
                  for p in ctx.convergence_program_ids]
    kwargs = {
        "model": model,
        "input": [
            {"role": "system",
             "content": "You convert Korean student questions into structured graduation-simulation parameters."},
            {"role": "user", "content": _prompt(question, ctx, conv_names)},
        ],
        "text": {"format": {"type": "json_schema", "name": "whatif_delta",
                            "schema": _schema(add_ids, drop_ids), "strict": True}},
    }
    if model.startswith(("gpt-5", "o")):
        kwargs["reasoning"] = {"effort": "minimal"}
    try:
        resp = client.responses.create(**kwargs, temperature=0.1)
    except Exception as exc:
        if "temperature" in str(exc).lower():
            resp = client.responses.create(**kwargs)
        else:
            raise
    return json.loads(getattr(resp, "output_text", "") or "")


# ---------- ② 조건 가드 (validator, 결정론) ----------
def apply_delta(ctx: StudentContext, delta: WhatIfDelta, profile,
                ) -> tuple[StudentContext | None, list[str], list[str], str | None]:
    """반환: (new_ctx | None, applied_changes, assumptions, unsupported_reason)."""
    updates: dict = {}
    changes: list[str] = []
    assumptions: list[str] = []

    # 휴학 — current_term을 복학 정규학기 직전 계절 슬롯으로 전진시킨 ctx 전체를
    # run_audit에 흘린다(_ordered_terms·overflow가 ctx에서 읽으므로 일관 적용).
    # 휴학 중 학기(정규·계절)는 배치에서 제외됨(검증 라운드2·3 수치 확인).
    d = delta.calendar_delay_terms or 0
    if d > 0:
        if not ctx.current_term:
            return None, [], [], "현재 학기가 미입력이라 휴학 시뮬레이션이 불가합니다 — 학생 정보에서 현재 학기를 입력해 주세요."
        ret = _nth_regular_term(ctx.current_term, d + 1)   # 복학 정규학기
        if not ret:
            return None, [], [], "현재 학기 형식 오류 — 휴학 시뮬레이션이 불가합니다."
        y, _, s = ret.partition("-")
        updates["current_term"] = f"{int(y) - 1}-W" if s == "1" else f"{y}-S"
        # 복학 첫 학기 보너스 의미 불명 → 보수적으로 미적용(질문의 명시 변경보다 우선)
        updates["prev_term_gpa_ge_375"] = False
        changes.append(f"휴학 {d}학기 — 복학 후 {_term_ko(ret)}부터 수강 배치")
        assumptions.append("휴학 중 학기(계절 포함)는 수강 불가로 가정, 복학 첫 학기 신청학점 보너스(직전학기 3.75↑) 미적용 가정")

    n = delta.remaining_semesters_change or 0
    if n != 0:
        new_rem = max(0, ctx.remaining_semesters + n)
        updates["remaining_semesters"] = new_rem
        changes.append(f"잔여 수강 학기 {ctx.remaining_semesters}→{new_rem}")

    if delta.seasonal_semester_allowed is not None:
        if delta.seasonal_semester_allowed == ctx.seasonal_semester_allowed:
            changes.append(f"계절학기 {'허용' if ctx.seasonal_semester_allowed else '불가'} — 현재 설정과 동일")
        else:
            updates["seasonal_semester_allowed"] = delta.seasonal_semester_allowed
            changes.append(f"계절학기 {'허용' if delta.seasonal_semester_allowed else '불가'}로 변경")

    if delta.max_credits_per_term is not None:
        legal = regular_term_cap(profile.total_credits_min)
        if delta.max_credits_per_term > legal:
            return None, [], [], (f"학기당 {delta.max_credits_per_term:.0f}학점은 설정할 수 없습니다 — "
                                  f"학사규정 제32조 상한 {legal:.0f}학점"
                                  f"(직전학기 3.75 이상 시 +{PREV_GPA_BONUS:.0f}학점까지) 초과.")
        updates["max_credits_per_term"] = delta.max_credits_per_term
        changes.append(f"학기당 학점 상한 {delta.max_credits_per_term:.0f}학점으로 제한")

    if delta.prev_term_gpa_ge_375 is not None and d == 0:   # 휴학 시 리셋이 우선
        updates["prev_term_gpa_ge_375"] = delta.prev_term_gpa_ge_375
        changes.append("직전학기 3.75 이상 가정" if delta.prev_term_gpa_ge_375
                       else "직전학기 3.75 미만 가정")

    progs = load_programs()
    conv_ids = list(ctx.convergence_program_ids)
    conv_tracks = dict(ctx.convergence_tracks)
    for ch in delta.add_convergence:
        p = progs.get(ch.program_id)
        if p is None or p.get("track_type", "primary") == "primary" \
                or ch.program_id == ctx.program_id or ch.program_id in conv_ids:
            return None, [], [], f"'{ch.program_id}'는 추가할 수 없는 융합·연계전공입니다."
        try:
            load_catalog(ch.program_id)
        except Exception:
            return None, [], [], f"'{ch.program_id}' 교육과정 데이터가 없어 시뮬레이션이 불가합니다."
        conv_ids.append(ch.program_id)
        conv_tracks[ch.program_id] = ch.track
        changes.append(f"{p.get('name_ko', ch.program_id)}({ch.track}) 추가")
    for pid in delta.drop_convergence:
        if pid not in conv_ids:
            return None, [], [], f"'{pid}'는 현재 신청하지 않은 융합·연계전공입니다."
        conv_ids.remove(pid)
        conv_tracks.pop(pid, None)                    # stale track 동반 제거(검증 라운드1)
        changes.append(f"{progs.get(pid, {}).get('name_ko', pid)} 포기(시뮬레이션)")
    if delta.add_convergence or delta.drop_convergence:
        updates["convergence_program_ids"] = conv_ids
        updates["convergence_tracks"] = conv_tracks

    if not updates:
        return None, changes, [], "요청하신 변경이 현재 설정과 동일합니다 — 변경할 내용이 없습니다."
    # model_copy는 validator를 재실행하지 않음(검증 라운드1 실측) → model_validate로 입구 가드 재통과
    new_ctx = StudentContext.model_validate({**ctx.model_dump(), **updates})
    return new_ctx, changes, assumptions, None


# ---------- ④ 시나리오 비교 (tool, 결정론) ----------
def _graduation_term(resp: AuditPipelineResponse) -> tuple[str | None, bool]:
    """(졸업 예상 정규학기 라벨 | None, already_met). 단일 산식 — before/after 동일 기준."""
    plan = resp.roadmap
    if plan.feasible and plan.terms:
        regs = [t.term for t in plan.terms if t.term.endswith(("-1", "-2"))]
        return (regs[-1], False) if regs else (None, False)   # 전부 계절 → 산출 불가(라운드3)
    if plan.feasible and not plan.terms:
        return None, True                                     # 이미 충족
    if plan.overflow and plan.overflow.projected_graduation_term:
        return plan.overflow.projected_graduation_term, False
    return None, False


def build_diff(before: AuditPipelineResponse, after: AuditPipelineResponse,
               delta: WhatIfDelta) -> WhatIfDiff:
    gt_b, met_b = _graduation_term(before)
    gt_a, met_a = _graduation_term(after)
    gaps_b = {g.area: g.gap for g in before.audit.area_gaps}
    changed = [a for a, g in ((g.area, g.gap) for g in after.audit.area_gaps)
               if abs(gaps_b.get(a, 0.0) - g) > 0.01]
    conv_b = {c["program_id"]: c for c in before.audit.convergence_checks}
    conv_a = {c["program_id"]: c for c in after.audit.convergence_checks}
    conv_changes: list[str] = []
    for pid, c in conv_b.items():
        if pid not in conv_a:
            conv_changes.append(f"{c['name']}({c['track']}) 제외 — 시뮬레이션 반영")
    for pid, c in conv_a.items():
        if pid not in conv_b:
            conv_changes.append(f"{c['name']}({c['track']}) 추가 — 부족 {c['gap']:.0f}학점")
        elif abs(c["gap"] - conv_b[pid]["gap"]) > 0.01:
            conv_changes.append(f"{c['name']}: 부족 {conv_b[pid]['gap']:.0f}→{c['gap']:.0f}학점")
    if abs(before.audit.to_fusion_total - after.audit.to_fusion_total) > 0.01:
        conv_changes.append(f"전공→융합 배정 {before.audit.to_fusion_total:.0f}→"
                            f"{after.audit.to_fusion_total:.0f}학점")

    d = delta.calendar_delay_terms or 0
    risk_changed = before.risk.grade != after.risk.grade
    if d > 0 and met_a:
        headline = f"졸업요건은 충족 상태가 유지되지만, 휴학 {d}학기만큼 졸업 시점이 늦어집니다."
    elif gt_b and gt_a and gt_b != gt_a:
        headline = f"예상 졸업이 {_term_ko(gt_b)} → {_term_ko(gt_a)}로 변동합니다" + \
                   (f" (리스크 {before.risk.grade}→{after.risk.grade})." if risk_changed else ".")
    elif met_a and not met_b:
        headline = "변경 후에도 추가 수강 없이 졸업요건을 충족합니다."
    elif risk_changed:
        headline = f"리스크 등급이 {before.risk.grade}({before.risk.label}) → {after.risk.grade}({after.risk.label})로 변동합니다."
    elif conv_changes:
        headline = conv_changes[0]
    elif abs(before.audit.total_gap - after.audit.total_gap) > 0.01:
        headline = f"총 부족 학점이 {before.audit.total_gap:.0f} → {after.audit.total_gap:.0f}학점으로 변동합니다."
    else:
        headline = "이 변경으로는 졸업사정 결과에 유의미한 변화가 없습니다."

    return WhatIfDiff(
        risk_before=before.risk.grade, risk_after=after.risk.grade,
        risk_label_before=before.risk.label, risk_label_after=after.risk.label,
        total_gap_before=before.audit.total_gap, total_gap_after=after.audit.total_gap,
        feasible_before=before.roadmap.feasible, feasible_after=after.roadmap.feasible,
        graduation_term_before=gt_b, graduation_term_after=gt_a,
        already_met_after=met_a,
        overflow_before=before.roadmap.overflow is not None,
        overflow_after=after.roadmap.overflow is not None,
        changed_areas=changed, convergence_changes=conv_changes, headline=headline,
    )


# ---------- ⑤ 다음 행동 제안 (tool, 결정론 룰 테이블) ----------
def suggest_next_actions(diff: WhatIfDiff, delta: WhatIfDelta,
                         ctx: StudentContext) -> list[str]:
    acts: list[str] = []
    if diff.overflow_after and not diff.overflow_before:
        acts.append("초과학기 위험이 생겼습니다 — " +
                    ("학기당 학점 배분을 조정한 시나리오를 추가로 확인해 보세요."
                     if ctx.seasonal_semester_allowed
                     else "계절학기 허용 시나리오를 추가로 확인해 보세요."))
    if diff.overflow_before and not diff.overflow_after:
        acts.append("이 변경으로 초과학기가 해소됩니다 — 수강신청 시 개설학기를 꼭 확인하세요.")
    if delta.drop_convergence:
        acts.append("융합·연계전공 포기 시 학위 표기가 달라집니다 — 포기 절차·시점을 학과사무실에 확인하세요.")
    if delta.add_convergence:
        acts.append("다전공·부전공은 신청 기간과 승인 요건이 있습니다 — 모집 공지를 확인하세요.")
    if (delta.calendar_delay_terms or 0) > 0:
        acts.append("휴학은 신청 기한·복학 절차가 있습니다 — 학과사무실 또는 원스톱서비스센터에 확인하세요.")
    if diff.graduation_term_before and diff.graduation_term_after \
            and diff.graduation_term_after > diff.graduation_term_before:
        acts.append("초과 등록 학기의 등록금·국가장학 신청 요건을 확인하세요.")
    if delta.seasonal_semester_allowed is True:
        acts.append("계절학기 개설 과목은 학기마다 다릅니다 — 개설 공지를 확인하세요.")
    if diff.risk_after > diff.risk_before:                      # A<B<C<D 문자 비교
        acts.append("변경 전 계획이 더 안전합니다 — 변경이 꼭 필요하면 학과 상담을 권장합니다.")
    if diff.already_met_after and not acts:
        acts.append("졸업사정 결과가 충족으로 유지됩니다 — 졸업신청 일정만 확인하세요.")
    return acts[:3]


# ---------- 캐시 (LLM 해석 결과만 — ②~⑤는 매번 결정론 재계산) ----------
def _cache_key(model: str, question: str, ctx: StudentContext, add_ids: list[str]) -> str:
    # 융합 선언·enum 모집단·컨텍스트 요약 입력값 포함 — 학생 간 delta 오반환·schema 드리프트 차단(라운드2)
    payload = {"m": model, "q": " ".join(question.split()), "p": ctx.program_id,
               "y": ctx.admission_year, "c": sorted(ctx.convergence_program_ids),
               "t": sorted(ctx.convergence_tracks.items()), "a": add_ids,
               "s": ctx.seasonal_semester_allowed, "r": ctx.remaining_semesters,
               "x": ctx.max_credits_per_term, "ct": ctx.current_term}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                     sort_keys=True).encode()).hexdigest()[:24]


def _cache_get(key: str):
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8")).get(key)
    except Exception:
        return None


def _cache_put(key: str, value: dict) -> None:
    try:
        data = {}
        if CACHE_PATH.exists():
            try:
                data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[key] = value
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


def _get_client():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None
    try:
        from openai import OpenAI
        return OpenAI(timeout=20)
    except Exception:
        return None


# ---------- 오케스트레이션 ----------
def _unsupported(question_summary: str, category, reason: str,
                 trace: list[NodeTraceEvent]) -> WhatIfResponse:
    trace = trace + [
        NodeTraceEvent(node="조건 가드", kind="validator", status="warn",
                       summary=reason[:120], branch_taken="지원 범위 밖"),
        NodeTraceEvent(node="안내 종료", kind="tool", status="skip",
                       summary="시뮬레이션 미실행 — 안내만 반환", branch_taken=reason[:40]),
    ]
    return WhatIfResponse(status="unsupported", category=category,
                          question_summary=question_summary,
                          unsupported_reason=reason, node_trace=trace)


def run_whatif(payload: dict, client=None) -> WhatIfResponse:
    ctx = StudentContext.model_validate(payload["context"])
    question = " ".join(str(payload.get("question", "")).split())
    if not question:
        raise ValueError("question이 비어 있습니다.")
    profile = assemble_requirement_profile(ctx)
    model = os.getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini")
    add_ids, drop_ids = _candidates(ctx)

    # ① 매개변수 추출기 (LLM 1회, 캐시 우선 — 데모 일관성·오프라인 폴백)
    key = _cache_key(model, question, ctx, add_ids)
    raw = _cache_get(key)
    cached = raw is not None
    if raw is None:
        client = client or _get_client()
        if client is None:
            return _unsupported(question[:40], None,
                                "LLM 미설정 — 예시 질문 버튼을 이용해 주세요.", [
                NodeTraceEvent(node="질문 분류", kind="llm", status="skip",
                               summary="LLM 미설정", branch_taken="해석 불가")])
        try:
            raw = interpret_question(question, ctx, client, model, add_ids, drop_ids)
            _cache_put(key, raw)
        except Exception as exc:
            return _unsupported(question[:40], None,
                                f"질문 해석 실패({type(exc).__name__}) — 잠시 후 다시 시도해 주세요.", [
                NodeTraceEvent(node="질문 분류", kind="llm", status="fail",
                               summary=f"LLM 호출 실패({type(exc).__name__})",
                               branch_taken="해석 실패")])

    category = raw.get("category") if raw.get("category") in CATEGORIES else "기타"
    qsum = str(raw.get("question_summary", ""))[:80]
    try:
        delta = WhatIfDelta.model_validate(raw.get("delta") or {})
    except Exception:
        # 범위 밖 값(예: delay=99) — strict schema가 막지만 캐시 오염 등 방어
        delta = WhatIfDelta()
    cache_note = " (캐시 — 동일 입력 동일 해석)" if cached else ""
    trace = [
        NodeTraceEvent(node="질문 분류", kind="llm",
                       summary=f"\"{question[:40]}\"{cache_note}", branch_taken=category),
        NodeTraceEvent(node="매개변수 추출", kind="llm",
                       summary=qsum or "해석 결과 없음",
                       branch_taken=("delta 추출" if not delta.is_empty() else "변경 없음")),
    ]

    # ② 조건 가드 (IF/ELSE)
    if not raw.get("interpretable", False) or delta.is_empty():
        return _unsupported(qsum or question[:40], category,
                            "이 질문은 시뮬레이션 범위 밖입니다 — 지원: 휴학, 잔여 학기 변경, "
                            "계절학기, 학기당 학점 상한, 다전공·부전공 추가/포기.", trace)
    new_ctx, changes, assumptions, err = apply_delta(ctx, delta, profile)
    if err:
        return _unsupported(qsum, category, err, trace)
    trace.append(NodeTraceEvent(node="조건 가드", kind="validator",
                                summary="; ".join(changes)[:120] or "변경값 검증 통과",
                                branch_taken="통과"))

    # ③ 졸업사정 재실행 (before/after 모두 서버 재계산 — 클라이언트 diff 불신뢰)
    try:
        before = run_audit(payload, skip_explain=True)
        after = run_audit({**payload, "context": new_ctx.model_dump()}, skip_explain=True)
    except (ValueError, KeyError) as exc:
        return _unsupported(qsum, category,
                            f"해당 변경은 시뮬레이션할 수 없습니다({exc}).", trace)

    # ④ 비교 / ⑤ 제안 (결정론)
    diff = build_diff(before, after, delta)
    acts = suggest_next_actions(diff, delta, ctx)
    trace += [
        NodeTraceEvent(node="졸업사정 재실행", kind="tool",
                       summary=f"부족 {diff.total_gap_before:.0f}→{diff.total_gap_after:.0f} · "
                               f"리스크 {diff.risk_before}→{diff.risk_after}",
                       branch_taken="before/after 2회 실행"),
        NodeTraceEvent(node="시나리오 비교", kind="tool", summary=diff.headline[:120],
                       branch_taken=f"리스크 {diff.risk_before}→{diff.risk_after}"),
        NodeTraceEvent(node="다음 행동 제안", kind="tool",
                       summary=(acts[0][:80] if acts else "제안 없음"),
                       branch_taken=f"{len(acts)}건"),
    ]
    return WhatIfResponse(status="ok", category=category, question_summary=qsum,
                          applied_changes=changes, assumptions=assumptions,
                          diff=diff, next_actions=acts, after=after, node_trace=trace)
