import React from "react";
import WorkflowGraph from "./WorkflowGraph.jsx";

// 졸업센터 v2 — 수강내역 엑셀 → 검증(HITL) → 졸업사정 컨설팅 대시보드
const GRADE_COLOR = { A: "#10B981", B: "#F59E0B", C: "#EF4444", D: "#B91C1C" };

function Gauge({ label, earned, required, gap }) {
  const pct = required > 0 ? Math.min(100, Math.round((earned / required) * 100)) : 100;
  const ok = gap <= 0;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
        <span>{label}</span>
        <span>{earned}/{required} {ok ? "✅" : `⚠️ ${gap} 부족`}</span>
      </div>
      <div style={{ background: "#e5e7eb", borderRadius: 6, height: 10 }}>
        <div style={{ width: `${pct}%`, height: 10, borderRadius: 6,
          background: ok ? "#10B981" : "#F59E0B" }} />
      </div>
    </div>
  );
}

export default function GraduationV2({ apiBase }) {
  const [programs, setPrograms] = React.useState({});
  const [ctx, setCtx] = React.useState({
    program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
    max_courses_per_term: 6, seasonal_semester_allowed: false, gpa_min_met: "unknown",
    preferences: "", convergence_program_ids: [], convergence_tracks: {},
  });
  const [files, setFiles] = React.useState([]);
  const [verify, setVerify] = React.useState(null);
  const [table, setTable] = React.useState([]);
  const [audit, setAudit] = React.useState(null);
  const [busy, setBusy] = React.useState("");
  const [error, setError] = React.useState("");
  const [showSources, setShowSources] = React.useState(false);

  // 워크플로우 그래프용 trace — verify/audit가 바뀔 때만 새 배열(재생 애니메이션 불필요 재시작 방지)
  const workflowTrace = React.useMemo(
    () => [...(verify?.node_trace || []), ...(audit?.node_trace || [])],
    [verify, audit],
  );

  React.useEffect(() => {
    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
      .then((d) => setPrograms(d.programs || {})).catch(() => {});
  }, [apiBase]);

  const contextPayload = () => ({
    ...ctx,
    remaining_semesters: Number(ctx.remaining_semesters),
    max_courses_per_term: Number(ctx.max_courses_per_term),
    preferences: ctx.preferences ? ctx.preferences.split(",").map((s) => s.trim()).filter(Boolean) : [],
  });

  const primaryPrograms = Object.entries(programs).filter(([, p]) => (p.track_type || "primary") === "primary");
  const convergencePrograms = Object.entries(programs).filter(([, p]) => p.track_type === "convergence");
  const toggleConv = (id) => setCtx((c) => {
    const on = c.convergence_program_ids.includes(id);
    const ids = on ? c.convergence_program_ids.filter((x) => x !== id) : [...c.convergence_program_ids, id];
    const tracks = { ...c.convergence_tracks };
    if (on) delete tracks[id]; else tracks[id] = tracks[id] || "다전공";
    return { ...c, convergence_program_ids: ids, convergence_tracks: tracks };
  });
  const setConvTrack = (id, track) => setCtx((c) => ({ ...c, convergence_tracks: { ...c.convergence_tracks, [id]: track } }));

  const runVerify = async () => {
    if (!files.length) { setError("수강내역 엑셀(.xls/.xlsx)을 업로드하세요."); return; }
    setBusy("verify"); setError(""); setAudit(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      form.append("context", JSON.stringify(contextPayload()));
      const r = await fetch(`${apiBase}/graduation/v2/verify`, { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const d = await r.json();
      setVerify(d); setTable(d.verification_table);
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  const toggleRow = (i) => setTable((t) => t.map((row, idx) =>
    idx === i ? { ...row, included: !row.included } : row));

  const runAudit = async () => {
    setBusy("audit"); setError("");
    try {
      const payload = { context: verify.context, verification_table: table,
        unresolved: verify.unresolved, possible_retakes: verify.possible_retakes };
      const r = await fetch(`${apiBase}/graduation/v2/audit`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      setAudit(await r.json());
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  return (
    <div style={{ padding: 12 }}>
      <h3>졸업사정 v2 — 수강내역 기반 컨설팅</h3>
      <p style={{ fontSize: 12, color: "#6b7280" }}>
        ON국민 수강신청내역 엑셀(.xls)을 학기별로 모두 업로드 → 검증 → 졸업사정.
        ※ 데모: 본인/더미 데이터 사용. (실서비스는 ON국민에서 내려받은 파일 업로드)
      </p>

      {/* 1) 컨텍스트 + 업로드 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, margin: "8px 0" }}>
        <label>주전공
          <select value={ctx.program_id} onChange={(e) => setCtx({ ...ctx, program_id: e.target.value })}>
            {primaryPrograms.map(([id, p]) => <option key={id} value={id}>{p.name_ko}</option>)}
            {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
          </select>
        </label>
        <label>현재 학기 <input value={ctx.current_term} onChange={(e) => setCtx({ ...ctx, current_term: e.target.value })} /></label>
        <label>남은 학기 <input type="number" value={ctx.remaining_semesters} onChange={(e) => setCtx({ ...ctx, remaining_semesters: e.target.value })} /></label>
        <label>학기당 최대 과목 <input type="number" value={ctx.max_courses_per_term} onChange={(e) => setCtx({ ...ctx, max_courses_per_term: e.target.value })} /></label>
        <label>계절학기 <input type="checkbox" checked={ctx.seasonal_semester_allowed} onChange={(e) => setCtx({ ...ctx, seasonal_semester_allowed: e.target.checked })} /></label>
        <label>평점 기준 충족
          <select value={ctx.gpa_min_met} onChange={(e) => setCtx({ ...ctx, gpa_min_met: e.target.value })}>
            <option value="unknown">모름</option><option value="yes">충족</option><option value="no">미달</option>
          </select>
        </label>
        <label style={{ gridColumn: "1 / 3" }}>관심분야(쉼표) <input value={ctx.preferences} onChange={(e) => setCtx({ ...ctx, preferences: e.target.value })} /></label>
        {convergencePrograms.length > 0 && (
          <div style={{ gridColumn: "1 / 3" }}>
            <div style={{ fontSize: 13 }}>연계·융합전공(다전공) 선택:</div>
            {convergencePrograms.map(([id, p]) => (
              <span key={id} style={{ marginRight: 14, fontSize: 13, whiteSpace: "nowrap" }}>
                <input type="checkbox" checked={ctx.convergence_program_ids.includes(id)} onChange={() => toggleConv(id)} /> {p.name_ko}
                {ctx.convergence_program_ids.includes(id) && (
                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)} style={{ marginLeft: 4 }}>
                    <option value="다전공">다전공(36·중복12)</option>
                    <option value="부전공">부전공(18·중복6)</option>
                  </select>
                )}
              </span>
            ))}
          </div>
        )}
      </div>
      <input type="file" multiple accept=".xls,.xlsx" onChange={(e) => setFiles([...e.target.files])} />
      <button onClick={runVerify} disabled={busy === "verify"}>{busy === "verify" ? "검증 중…" : "① 검증"}</button>

      {error && <p style={{ color: "#EF4444" }}>{error}</p>}

      {/* 2) 검증 테이블 */}
      {verify && (
        <div style={{ marginTop: 12 }}>
          <h4>검증 테이블 ({table.length}행) — F/재수강/미이수 과목은 체크 해제</h4>
          <div style={{ maxHeight: 220, overflow: "auto", border: "1px solid #e5e7eb", fontSize: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th>포함</th><th>과목명</th><th>이수구분</th><th>학점</th><th>학기</th><th>비고</th></tr></thead>
              <tbody>
                {table.map((row, i) => (
                  <tr key={i} style={{ opacity: row.included ? 1 : 0.45 }}>
                    <td style={{ textAlign: "center" }}><input type="checkbox" checked={row.included} onChange={() => toggleRow(i)} /></td>
                    <td>{row.name_ko}{row.course_id ? "" : " (집계)"}</td>
                    <td>{row.requirement_area}{row.core_area ? `·${row.core_area}` : ""}</td>
                    <td style={{ textAlign: "center" }}>{row.credits}</td>
                    <td>{row.term_label}</td>
                    <td style={{ color: "#b45309" }}>{row.exclude_reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {verify.unresolved?.length > 0 && <p style={{ fontSize: 12 }}>미해소(확인 필요): {verify.unresolved.length}건</p>}
          <button onClick={runAudit} disabled={busy === "audit"}>{busy === "audit" ? "사정 중…" : "② 졸업사정 실행"}</button>
        </div>
      )}

      {/* 3) 대시보드 */}
      {audit && (
        <div style={{ marginTop: 16 }}>
          <div style={{ padding: 12, borderRadius: 10, background: "#f9fafb", borderLeft: `6px solid ${GRADE_COLOR[audit.risk.grade]}` }}>
            <strong style={{ color: GRADE_COLOR[audit.risk.grade] }}>종합 판정: {audit.risk.grade} {audit.risk.label}</strong>
            <span style={{ marginLeft: 12 }}>총 {audit.audit.total_earned}/{audit.audit.total_required}학점</span>
            <div style={{ fontSize: 12, marginTop: 4 }}>{audit.risk.reasons.map((r, i) => <span key={i}>· {r.detail} </span>)}</div>
          </div>

          <h4 style={{ marginTop: 12 }}>영역별 이수 현황</h4>
          {audit.audit.area_gaps.map((g, i) => <Gauge key={i} label={g.area} earned={g.earned} required={g.required} gap={g.gap} />)}
          {audit.audit.core_area_gaps.some((g) => g.gap > 0) && (
            <p style={{ fontSize: 12, color: "#b45309" }}>핵심교양 부족 영역: {audit.audit.core_area_gaps.filter((g) => g.gap > 0).map((g) => g.area).join(", ")}</p>
          )}

          {audit.audit.convergence_checks?.length > 0 && (
            <>
              <h4>연계·융합전공 (학점 중복인정 반영)</h4>
              {audit.audit.convergence_checks.map((cc, i) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <Gauge label={`${cc.name} (${cc.track})`} earned={cc.earned} required={cc.required} gap={cc.gap} />
                  <div style={{ fontSize: 11, color: "#6b7280" }}>
                    {cc.conv_type} · 제1전공과 겹침 {cc.overlap_credits} 중 중복(동시)인정 가능 {cc.double_recognizable}/{cc.double_cap}
                  </div>
                  {cc.group_checks?.map((gc, gi) => (
                    <div key={gi} style={{ fontSize: 11, marginLeft: 10, color: gc.gap > 0 ? "#b45309" : "#10B981" }}>
                      {gc.group}: {gc.earned}/{gc.required} {gc.gap > 0 ? `(${gc.gap} 부족)` : "✅"}
                    </div>
                  ))}
                  {cc.recommend_double_count?.length > 0 && <div style={{ fontSize: 11, color: "#0F3D7A" }}>중복인정 신청 권장: {cc.recommend_double_count.join(", ")}</div>}
                  {cc.note && <div style={{ fontSize: 11, color: "#b45309" }}>※ {cc.note}</div>}
                </div>
              ))}
            </>
          )}

          {audit.audit.missing_required_names.length > 0 && (
            <p style={{ color: "#EF4444" }}>미이수 필수지정: {audit.audit.missing_required_names.join(", ")}</p>
          )}
          {audit.audit.required_check_available === false && (
            <p style={{ fontSize: 12, color: "#b45309" }}>※ 이 학과는 요람 필수지정 과목 데이터가 아직 없어 필수과목 체크가 제외됐습니다(확인 필요).</p>
          )}

          <h4>추천 학기별 로드맵</h4>
          {audit.roadmap.status === "not_generated" && <p style={{ color: "#6b7280" }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
          {audit.roadmap.status === "blocked" && <p style={{ color: "#EF4444" }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
          {audit.roadmap.status === "generated" && audit.roadmap.terms.length === 0 && <p>{audit.roadmap.why_this_plan}</p>}
          {audit.roadmap.terms.map((t, i) => (
            <div key={i} style={{ borderLeft: "3px solid #0F3D7A", padding: "2px 10px", margin: "6px 0" }}>
              <strong>{t.term}</strong> ({t.term_credits}학점)
              <div style={{ fontSize: 13 }}>{t.courses.map((c) => `${c.name_ko}(${c.credits})`).join(" · ")}</div>
            </div>
          ))}
          {audit.roadmap.why_this_plan && audit.roadmap.terms.length > 0 && <p style={{ fontSize: 12 }}>왜 이 계획: {audit.roadmap.why_this_plan}</p>}
          {audit.roadmap.assumptions?.length > 0 && <p style={{ fontSize: 11, color: "#6b7280" }}>가정: {audit.roadmap.assumptions.join(" / ")}</p>}

          {/* Dify식 워크플로우 실행 그래프 (verify+audit trace 합산) */}
          <div style={{ margin: "12px 0", padding: 10, border: "1px solid #e5e7eb", borderRadius: 10 }}>
            <WorkflowGraph trace={workflowTrace} />
          </div>

          <button onClick={() => setShowSources((s) => !s)} style={{ fontSize: 12 }}>
            {showSources ? "근거 숨기기" : "근거 보기"}
          </button>
          {showSources && (
            <ul style={{ fontSize: 12 }}>
              {audit.sources.map((s) => <li key={s.id}>[{s.id}] {s.doc} {s.page ? `p.${s.page}` : ""} ({s.source_type})</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
