import React from "react";

// 졸업센터 v2 — 수강내역 엑셀 → 검증(HITL) → 졸업사정 컨설팅 대시보드
const GRADE_COLOR = { A: "#10B981", B: "#F59E0B", C: "#EF4444", D: "#B91C1C" };
const C = {
  navy: "#0F3D7A", accent: "#1d6fe0", bg: "#eef2f7", card: "#ffffff",
  border: "#e3e8ef", text: "#1f2937", muted: "#6b7280", soft: "#f7f9fc",
  ok: "#10B981", warn: "#F59E0B", danger: "#EF4444",
};
const card = {
  background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
  padding: 18, marginBottom: 14, boxShadow: "0 1px 3px rgba(16,24,40,.06)",
};
const sectionTitle = { fontSize: 14, fontWeight: 700, margin: "0 0 12px", color: C.navy,
  display: "flex", alignItems: "center", gap: 7, letterSpacing: "-.01em" };
const inputStyle = { width: "100%", padding: "7px 9px", border: `1px solid ${C.border}`,
  borderRadius: 8, fontSize: 13, boxSizing: "border-box", marginTop: 4, background: "#fff" };
const labelStyle = { fontSize: 11.5, fontWeight: 600, color: C.muted };
const btnPrimary = (on = true) => ({ background: on ? C.navy : "#9aa6b8", color: "#fff",
  border: "none", borderRadius: 9, padding: "10px 20px", fontSize: 14, fontWeight: 600,
  cursor: on ? "pointer" : "default", boxShadow: on ? "0 1px 2px rgba(15,61,122,.3)" : "none" });
const btnGhost = { background: "#fff", color: C.navy, border: `1px solid ${C.border}`,
  borderRadius: 8, padding: "7px 14px", fontSize: 12.5, fontWeight: 600, cursor: "pointer" };

function Field({ label, children, hint }) {
  return (
    <label style={{ display: "block" }}>
      <span style={labelStyle}>{label}</span>
      {children}
      {hint && <span style={{ display: "block", fontSize: 10.5, color: "#94a3b8", marginTop: 3, lineHeight: 1.35 }}>{hint}</span>}
    </label>
  );
}

function Gauge({ label, earned, required, gap, sub }) {
  const pct = required > 0 ? Math.min(100, Math.round((earned / required) * 100)) : 100;
  const ok = gap <= 0;
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span style={{ fontWeight: 600, color: C.text }}>{label}{sub && <span style={{ color: C.muted, fontWeight: 400, marginLeft: 6, fontSize: 11.5 }}>{sub}</span>}</span>
        <span style={{ fontWeight: 600, color: ok ? C.ok : C.warn }}>
          {earned}/{required}
          <span style={{ marginLeft: 6, fontSize: 11.5 }}>{ok ? "충족" : `${gap} 부족`}</span>
        </span>
      </div>
      <div style={{ background: "#eef1f5", borderRadius: 6, height: 9, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: 9, borderRadius: 6, transition: "width .5s ease",
          background: ok ? "linear-gradient(90deg,#34d399,#10B981)" : "linear-gradient(90deg,#fbbf24,#f59e0b)" }} />
      </div>
    </div>
  );
}

const ASSIGN_STYLE = {
  "중복인정 추천": { bg: "#dbeafe", border: "#93c5fd", color: "#1d4ed8" },
  "중복인정 후보": { bg: "#f5f8ff", border: "#dbe7fb", color: "#7c93b8" },
  "융합전용": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
  "미이수": { bg: "#f3f4f6", border: "#e5e7eb", color: "#9aa6b8" },
};

function ConvergenceBlock({ cc, C, first }) {
  const groups = [...new Set((cc.courses || []).map((c) => c.group || "기타"))].sort();
  const taken = (cc.courses || []).filter((c) => c.taken).length;
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 14, background: C.soft, marginTop: first ? 0 : 12 }}>
      <Gauge label={cc.name} sub={`${cc.track}·${cc.conv_type}`} earned={cc.earned} required={cc.required} gap={cc.gap} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 11.5, color: C.muted, margin: "2px 0 8px" }}>
        <span>제1전공 겹침 {cc.overlap_credits} → 중복인정 {cc.double_recognizable}/{cc.double_cap}</span>
        {cc.group_checks?.map((gc, gi) => (
          <span key={gi} style={{ color: gc.gap > 0 ? "#b45309" : C.ok }}>{gc.group} {gc.earned}/{gc.required}{gc.gap > 0 ? ` (${gc.gap}↓)` : " ✓"}</span>
        ))}
        <span>이수 {taken}/{(cc.courses || []).length}과목</span>
      </div>
      {cc.recommend_double_count?.length > 0 && (
        <div style={{ fontSize: 11.5, color: C.accent, marginBottom: 8 }}>
          💡 중복인정 신청 권장(제1전공·다전공 전공필수 우선): <strong>{cc.recommend_double_count.join(", ")}</strong>
        </div>
      )}
      {/* 교육과정 전체 과목 — 그룹별, 이수 강조, 이수구분 배정 */}
      <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden", background: "#fff" }}>
        {groups.map((g) => (
          <div key={g}>
            <div style={{ background: C.soft, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, color: C.navy, borderTop: `1px solid ${C.border}` }}>{g}</div>
            {(cc.courses || []).filter((c) => (c.group || "기타") === g).map((c, ci) => {
              const a = ASSIGN_STYLE[c.assignment] || ASSIGN_STYLE["미이수"];
              return (
                <div key={ci} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", fontSize: 12,
                  borderTop: "1px solid #f1f4f8", opacity: c.taken ? 1 : 0.5, background: c.taken ? "#fafcff" : "#fff" }}>
                  <span style={{ width: 16 }}>{c.taken ? "✅" : "⬜"}</span>
                  <span style={{ flex: 1, fontWeight: c.taken ? 600 : 400 }}>
                    {c.name_ko}
                    {c.primary_required && <span style={{ marginLeft: 5, fontSize: 9.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 4, padding: "0 4px" }}>전공필수</span>}
                  </span>
                  <span style={{ width: 28, textAlign: "right", color: C.muted }}>{c.credits}</span>
                  <span style={{ width: 92, textAlign: "center", fontSize: 10.5, fontWeight: 600, color: a.color,
                    background: a.bg, border: `1px solid ${a.border}`, borderRadius: 5, padding: "2px 0", whiteSpace: "nowrap" }}>{c.assignment}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {cc.note && <div style={{ fontSize: 10.5, color: C.muted, marginTop: 6, lineHeight: 1.4 }}>※ {cc.note}</div>}
    </div>
  );
}

export default function GraduationV2({ apiBase }) {
  const [programs, setPrograms] = React.useState({});
  const [ctx, setCtx] = React.useState({
    program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
    seasonal_semester_allowed: false, gpa_min_met: "unknown",
    preferences: "", convergence_program_ids: [], convergence_tracks: {},
  });
  const [files, setFiles] = React.useState([]);
  const [verify, setVerify] = React.useState(null);
  const [table, setTable] = React.useState([]);
  const [audit, setAudit] = React.useState(null);
  const [busy, setBusy] = React.useState("");
  const [error, setError] = React.useState("");
  const [showSources, setShowSources] = React.useState(false);

  React.useEffect(() => {
    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
      .then((d) => {
        const progs = d.programs || {};
        setPrograms(progs);
        // 초기 주전공의 학사규정 상한을 기본값으로
        setCtx((c) => {
          const cap = progs[c.program_id]?.max_credits_per_term;
          return cap ? { ...c, max_credits_per_term: cap } : c;
        });
      }).catch(() => {});
  }, [apiBase]);

  const contextPayload = () => ({
    ...ctx,
    remaining_semesters: Number(ctx.remaining_semesters),
    max_credits_per_term: Number(ctx.max_credits_per_term),
    preferences: ctx.preferences ? ctx.preferences.split(",").map((s) => s.trim()).filter(Boolean) : [],
  });

  // 주전공 변경 시 학사규정 제32조 학기당 상한을 기본값으로 자동 채움
  const onProgramChange = (id) => {
    const cap = programs[id]?.max_credits_per_term;
    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
  };

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

  const toggleRow = (i) => setTable((t) => t.map((row, idx) => {
    if (idx !== i) return row;
    const included = !row.included;
    // 제외로 바꾸는데 사유가 없으면 기본값, 포함으로 되돌리면 사유 비움
    return { ...row, included, exclude_reason: included ? null : (row.exclude_reason || "F·재이수") };
  }));
  const setReason = (i, reason) => setTable((t) => t.map((row, idx) =>
    idx === i ? { ...row, exclude_reason: reason, included: false } : row));
  const EXCLUDE_REASONS = ["재수강(이전 이수)", "F·재이수", "드랍·철회", "폐강", "기타"];
  const retakeCount = table.filter((r) => (r.exclude_reason || "").includes("재수강")).length;

  const runAudit = async () => {
    setBusy("audit"); setError("");
    try {
      const payload = { context: verify.context, verification_table: table,
        unresolved: verify.unresolved, possible_retakes: verify.possible_retakes };
      const r = await fetch(`${apiBase}/graduation/v2/audit`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const result = await r.json();
      setAudit(result);
      // 워크플로우 전용 페이지(#workflow)가 읽도록 trace 저장
      try {
        localStorage.setItem("v2_workflow_trace",
          JSON.stringify([...(verify?.node_trace || []), ...(result.node_trace || [])]));
      } catch { /* storage 불가 무시 */ }
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  const stepActive = (n) => (n === 1 ? !!files.length : n === 2 ? !!verify : !!audit);

  return (
    <div style={{ background: C.bg, height: "100vh", overflowY: "auto", padding: "0 0 60px",
      fontFamily: "'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif", color: C.text }}>
      {/* 헤더 배너 */}
      <div style={{ background: `linear-gradient(120deg,${C.navy},#143e8c 60%,#1d6fe0)`, color: "#fff",
        padding: "22px 26px 20px" }}>
        <div style={{ maxWidth: 940, margin: "0 auto" }}>
          <div style={{ fontSize: 12, letterSpacing: ".08em", opacity: .85, fontWeight: 600 }}>KOOKMIN UNIV · 졸업센터</div>
          <h1 style={{ margin: "4px 0 6px", fontSize: 23, fontWeight: 800, letterSpacing: "-.02em" }}>졸업사정 컨설팅</h1>
          <p style={{ margin: 0, fontSize: 13, opacity: .9, lineHeight: 1.5 }}>
            내 수강내역 × 내 요람으로 졸업 가능 여부를 진단하고 남은 학기 로드맵을 설계합니다.
            결정론적 사실 위에서 LLM이 로드맵만 계획하고 검증기가 재확인합니다.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 940, margin: "0 auto", padding: "18px 20px 0" }}>
        {/* 스텝 인디케이터 */}
        <div style={{ display: "flex", gap: 8, marginBottom: 14, fontSize: 12.5 }}>
          {[[1, "수강내역 업로드"], [2, "검증 (HITL)"], [3, "졸업사정 리포트"]].map(([n, t]) => (
            <div key={n} style={{ flex: 1, padding: "8px 10px", borderRadius: 9, textAlign: "center", fontWeight: 600,
              background: stepActive(n) ? C.navy : "#fff", color: stepActive(n) ? "#fff" : C.muted,
              border: `1px solid ${stepActive(n) ? C.navy : C.border}` }}>
              <span style={{ opacity: .7, marginRight: 5 }}>{n}</span>{t}
            </div>
          ))}
        </div>

        {/* 1) 학생 정보 + 업로드 */}
        <div style={card}>
          <div style={sectionTitle}>🎓 학생 정보 & 수강내역</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
            <Field label="주전공">
              <select style={inputStyle} value={ctx.program_id} onChange={(e) => onProgramChange(e.target.value)}>
                {primaryPrograms.map(([id, p]) => <option key={id} value={id}>{p.name_ko}</option>)}
                {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
              </select>
            </Field>
            <Field label="현재 학기"><input style={inputStyle} value={ctx.current_term} onChange={(e) => setCtx({ ...ctx, current_term: e.target.value })} /></Field>
            <Field label="남은 학기" hint="현재 학기 다음부터 들을 정규학기 수 (현재 학기는 이미 수강내역에 포함 → 제외)">
              <input style={inputStyle} type="number" value={ctx.remaining_semesters} onChange={(e) => setCtx({ ...ctx, remaining_semesters: e.target.value })} /></Field>
            <Field label="한 학기 최대 수강 학점" hint="학사규정 제32조: 졸업학점 따라 17/18/19 자동 (수정 가능)">
              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
            <Field label="졸업 최소 평점 충족">
              <select style={inputStyle} value={ctx.gpa_min_met} onChange={(e) => setCtx({ ...ctx, gpa_min_met: e.target.value })}>
                <option value="unknown">모름</option><option value="yes">충족</option><option value="no">미달</option>
              </select>
            </Field>
            <label style={{ display: "flex", alignItems: "flex-end", gap: 7, fontSize: 12.5, paddingBottom: 8 }}>
              <input type="checkbox" checked={ctx.prev_term_gpa_ge_375} onChange={(e) => setCtx({ ...ctx, prev_term_gpa_ge_375: e.target.checked })} />
              직전학기 평점 3.75↑ (다음 학기 +3학점)
            </label>
            <label style={{ display: "flex", alignItems: "flex-end", gap: 7, fontSize: 13, paddingBottom: 8 }}>
              <input type="checkbox" checked={ctx.seasonal_semester_allowed} onChange={(e) => setCtx({ ...ctx, seasonal_semester_allowed: e.target.checked })} />
              계절학기 허용 (6학점)
            </label>
            <div style={{ gridColumn: "1 / 4" }}>
              <Field label="관심분야 (쉼표 구분)"><input style={inputStyle} value={ctx.preferences} placeholder="예: 데이터분석, 자율주행" onChange={(e) => setCtx({ ...ctx, preferences: e.target.value })} /></Field>
            </div>
          </div>

          {convergencePrograms.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <span style={labelStyle}>연계·융합전공 (다전공/부전공)</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>
                {convergencePrograms.map(([id, p]) => {
                  const on = ctx.convergence_program_ids.includes(id);
                  return (
                    <div key={id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
                      border: `1px solid ${on ? C.accent : C.border}`, background: on ? "#eef5ff" : "#fff", fontSize: 12.5 }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer", fontWeight: on ? 600 : 400 }}>
                        <input type="checkbox" checked={on} onChange={() => toggleConv(id)} />{p.name_ko}
                      </label>
                      {on && (
                        <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
                          style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px" }}>
                          <option value="다전공">다전공 · 36/중복12</option>
                          <option value="부전공">부전공 · 18/중복6</option>
                        </select>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <label style={{ ...btnGhost, display: "inline-flex", alignItems: "center", gap: 6 }}>
              📂 엑셀 선택
              <input type="file" multiple accept=".xls,.xlsx" style={{ display: "none" }} onChange={(e) => setFiles([...e.target.files])} />
            </label>
            <span style={{ fontSize: 12.5, color: C.muted }}>
              {files.length ? `${files.length}개 학기 파일 선택됨` : "ON국민 수강내역(.xls)을 학기별로 모두 선택"}
            </span>
            <button style={{ ...btnPrimary(busy !== "verify"), marginLeft: "auto" }} onClick={runVerify} disabled={busy === "verify"}>
              {busy === "verify" ? "검증 중…" : "① 검증 실행"}
            </button>
          </div>
          <p style={{ fontSize: 11.5, color: C.muted, margin: "10px 0 0" }}>※ 데모는 본인 또는 더미 수강내역을 사용하세요.</p>
        </div>

        {error && <div style={{ ...card, borderColor: "#fecaca", background: "#fef2f2", color: C.danger, fontSize: 13 }}>⚠️ {error}</div>}

        {/* 2) 검증 테이블 */}
        {verify && (
          <div style={card}>
            <div style={sectionTitle}>🔍 수강내역 검증 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>({table.length}행 · 학기 오름차순)</span></div>
            <p style={{ fontSize: 12, color: C.muted, margin: "0 0 10px", lineHeight: 1.5 }}>
              성적 정보가 없는 수강내역입니다. <strong style={{ color: C.text }}>F·드랍한 과목은 체크를 해제</strong>하고 비고에서 사유를 고르세요.
              재수강 의심 과목은 최신 이수만 자동 포함했습니다.
            </p>
            {retakeCount > 0 && (
              <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 9, padding: "9px 12px",
                fontSize: 12.5, color: "#b45309", marginBottom: 10 }}>
                ⚠️ <strong>재수강 의심 {retakeCount}건</strong> — 동일 교과목코드가 여러 학기에 있어 최신 이수만 포함했습니다.
                아래 강조된 행의 비고를 확인하세요. (사제동행세미나 등 반복수강 과목은 제외됨)
              </div>
            )}
            <div style={{ maxHeight: 260, overflow: "auto", border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                <thead><tr style={{ background: C.soft, position: "sticky", top: 0 }}>
                  {["포함", "과목명", "이수구분", "학점", "학기", "비고/제외사유"].map((h) => (
                    <th key={h} style={{ padding: "7px 8px", textAlign: "left", color: C.muted, fontWeight: 600, borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {table.map((row, i) => {
                    const isRetake = (row.exclude_reason || "").includes("재수강");
                    return (
                      <tr key={i} style={{ opacity: row.included ? 1 : 0.55, borderBottom: "1px solid #f1f4f8",
                        background: isRetake ? "#fffaf2" : undefined, borderLeft: isRetake ? "3px solid #f59e0b" : "3px solid transparent" }}>
                        <td style={{ textAlign: "center", padding: "5px 8px" }}><input type="checkbox" checked={row.included} onChange={() => toggleRow(i)} /></td>
                        <td style={{ padding: "5px 8px" }}>{row.name_ko}
                          {!row.course_id && <span style={{ marginLeft: 5, fontSize: 10.5, color: C.muted, background: "#eef1f5", borderRadius: 4, padding: "1px 5px" }}>집계</span>}</td>
                        <td style={{ padding: "5px 8px", color: C.muted }}>{row.requirement_area}{row.core_area ? `·${row.core_area}` : ""}</td>
                        <td style={{ textAlign: "center", padding: "5px 8px" }}>{row.credits}</td>
                        <td style={{ padding: "5px 8px", color: C.muted }}>{row.term_label}</td>
                        <td style={{ padding: "4px 8px" }}>
                          {row.included
                            ? <span style={{ color: "#9aa6b8" }}>정상 포함</span>
                            : (
                              <select value={EXCLUDE_REASONS.includes(row.exclude_reason) ? row.exclude_reason : "기타"}
                                onChange={(e) => setReason(i, e.target.value)}
                                style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px", color: "#b45309" }}>
                                {EXCLUDE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                              </select>
                            )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
              {verify.unresolved?.length > 0 && <span style={{ fontSize: 12, color: "#b45309" }}>미해소(확인 필요): {verify.unresolved.length}건</span>}
              <button style={{ ...btnPrimary(busy !== "audit"), marginLeft: "auto" }} onClick={runAudit} disabled={busy === "audit"}>
                {busy === "audit" ? "사정 중…" : "② 졸업사정 실행"}
              </button>
            </div>
          </div>
        )}

        {/* 3) 리포트 */}
        {audit && (
          <>
            {/* 종합 판정 히어로 */}
            <div style={{ ...card, padding: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "stretch" }}>
                <div style={{ width: 120, background: GRADE_COLOR[audit.risk.grade], color: "#fff",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "20px 0" }}>
                  <div style={{ fontSize: 46, fontWeight: 800, lineHeight: 1 }}>{audit.risk.grade}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{audit.risk.label}</div>
                </div>
                <div style={{ flex: 1, padding: "16px 18px" }}>
                  <div style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>종합 판정</div>
                  <div style={{ fontSize: 15, fontWeight: 700, margin: "3px 0 10px" }}>
                    총 {audit.audit.total_earned} / {audit.audit.total_required} 학점
                  </div>
                  <div style={{ background: "#eef1f5", borderRadius: 6, height: 9, overflow: "hidden", marginBottom: 10 }}>
                    <div style={{ width: `${Math.min(100, Math.round(audit.audit.total_earned / audit.audit.total_required * 100))}%`,
                      height: 9, background: GRADE_COLOR[audit.risk.grade] }} />
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {audit.risk.reasons.length === 0 && <span style={{ fontSize: 12, color: C.ok }}>리스크 요인 없음 — 졸업요건 충족</span>}
                    {audit.risk.reasons.map((r, i) => (
                      <span key={i} style={{ fontSize: 11.5, background: "#fff5ed", color: "#b45309",
                        border: "1px solid #fed7aa", borderRadius: 14, padding: "3px 9px" }}>{r.detail}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 영역별 현황 */}
            <div style={card}>
              <div style={sectionTitle}>📊 영역별 이수 현황</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {audit.audit.area_gaps.map((g, i) => <Gauge key={i} label={g.area} earned={g.earned} required={g.required} gap={g.gap} />)}
              </div>
              {audit.audit.core_area_gaps.some((g) => g.gap > 0) && (
                <p style={{ fontSize: 12, color: "#b45309", margin: "6px 0 0" }}>핵심교양 부족 영역: {audit.audit.core_area_gaps.filter((g) => g.gap > 0).map((g) => g.area).join(", ")}</p>
              )}
              {audit.audit.missing_required_names.length > 0 && (
                <p style={{ color: C.danger, fontSize: 13, margin: "8px 0 0" }}>미이수 필수지정: {audit.audit.missing_required_names.join(", ")}</p>
              )}
              {audit.audit.required_check_available === false && (
                <p style={{ fontSize: 11.5, color: C.muted, margin: "8px 0 0" }}>※ 이 학과는 요람 필수지정 과목 데이터가 아직 없어 필수과목 체크가 제외됐습니다(확인 필요).</p>
              )}
            </div>

            {/* 연계·융합전공 — 교육과정 전체 + 이수 강조 + 이수구분 배정 */}
            {audit.audit.convergence_checks?.length > 0 && (
              <div style={card}>
                <div style={sectionTitle}>🔗 연계·융합전공 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>(학점 중복인정 반영)</span></div>
                {audit.audit.convergence_checks.map((cc, i) => (
                  <ConvergenceBlock key={i} cc={cc} C={C} first={i === 0} />
                ))}
              </div>
            )}

            {/* 로드맵 */}
            <div style={card}>
              <div style={sectionTitle}>🗺️ 추천 학기별 로드맵</div>
              {audit.roadmap.status === "not_generated" && <p style={{ color: C.muted, fontSize: 13 }}>LLM 미설정 — 결정론 진단만 제공됩니다.</p>}
              {audit.roadmap.status === "blocked" && <p style={{ color: C.danger, fontSize: 13 }}>{audit.roadmap.blocked_reason} · {audit.roadmap.relaxation_hint}</p>}
              {audit.roadmap.status === "generated" && audit.roadmap.terms.length === 0 && (
                <div style={{ padding: "14px 16px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 10, color: "#047857", fontSize: 13.5, fontWeight: 600 }}>
                  ✅ {audit.roadmap.why_this_plan}
                </div>
              )}
              {audit.roadmap.terms.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {audit.roadmap.terms.map((t, i) => (
                    <div key={i} style={{ display: "flex", gap: 12 }}>
                      <div style={{ minWidth: 64, fontWeight: 700, color: C.navy, fontSize: 13.5, paddingTop: 2 }}>{t.term}</div>
                      <div style={{ flex: 1, borderLeft: `3px solid ${C.accent}`, paddingLeft: 12 }}>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {t.courses.map((c, ci) => (
                            <span key={ci} style={{ fontSize: 12.5, background: "#eef5ff", border: "1px solid #cfe1fb",
                              borderRadius: 7, padding: "4px 9px" }}>{c.name_ko} <span style={{ color: C.muted }}>{c.credits}</span></span>
                          ))}
                        </div>
                        <div style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>{t.term_credits}학점</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {audit.roadmap.why_this_plan && audit.roadmap.terms.length > 0 && (
                <p style={{ fontSize: 12.5, color: C.text, margin: "12px 0 0", padding: "10px 12px", background: C.soft, borderRadius: 8 }}>
                  <strong style={{ color: C.navy }}>왜 이 계획:</strong> {audit.roadmap.why_this_plan}</p>
              )}
              {audit.roadmap.assumptions?.length > 0 && <p style={{ fontSize: 11, color: C.muted, margin: "8px 0 0" }}>가정: {audit.roadmap.assumptions.join(" / ")}</p>}

              {audit.roadmap.overflow && (
                <div style={{ marginTop: 12, padding: 14, borderRadius: 10, background: "#fff7ed", border: "1px solid #fed7aa" }}>
                  <div style={{ fontWeight: 700, color: "#b45309", fontSize: 13.5, marginBottom: 8 }}>⏳ 초과학기 예상 시나리오</div>
                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 8 }}>
                    {[["부족 학점", `${audit.roadmap.overflow.shortfall_credits}학점`],
                      ["학기당 상한", `${audit.roadmap.overflow.per_term_credit_cap}학점`],
                      ["필요 총학기", `${audit.roadmap.overflow.total_semesters_needed}학기`],
                      ["초과학기", `${audit.roadmap.overflow.extra_semesters}학기`],
                      ["예상 졸업", audit.roadmap.overflow.projected_graduation_term || "—"]].map(([k, v]) => (
                      <div key={k}>
                        <div style={{ fontSize: 11, color: C.muted }}>{k}</div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: "#b45309" }}>{v}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{audit.roadmap.overflow.note}</div>
                </div>
              )}
            </div>

            {/* 워크플로우 그래프 — 별도 페이지로 분리 */}
            <div style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: C.navy }}>🔀 워크플로우 실행 그래프</div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>
                  업무 노드 분절·실행 순서·분기를 별도 화면에서 시각화합니다 (방금 실행 결과 반영).
                </div>
              </div>
              <button onClick={() => window.open(`${window.location.pathname}#workflow`, "_blank")}
                style={{ ...btnGhost, whiteSpace: "nowrap" }}>워크플로우 그래프 열기 ↗</button>
            </div>

            {/* 근거 */}
            <div style={{ ...card, marginBottom: 0 }}>
              <button style={btnGhost} onClick={() => setShowSources((s) => !s)}>
                {showSources ? "근거 숨기기 ▲" : "근거 보기 ▼"}
              </button>
              {showSources && (
                <ul style={{ fontSize: 12, color: C.muted, margin: "10px 0 0", paddingLeft: 18 }}>
                  {audit.sources.map((s) => <li key={s.id} style={{ marginBottom: 3 }}>[{s.id}] {s.doc} {s.page ? `p.${s.page}` : ""} <span style={{ opacity: .7 }}>({s.source_type})</span></li>)}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
