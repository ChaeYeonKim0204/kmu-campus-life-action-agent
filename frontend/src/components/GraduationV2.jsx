import React from "react";
import WorkflowGraph from "./WorkflowGraph.jsx";

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
  "중복인정": { bg: "#dbeafe", border: "#93c5fd", color: "#1d4ed8" },
  "융합 유지": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
  "융합전용": { bg: "#ecfdf5", border: "#a7f3d0", color: "#047857" },
  "미이수": { bg: "#f3f4f6", border: "#e5e7eb", color: "#9aa6b8" },
};

function StatBox({ label, earned, required, C }) {
  const ok = earned >= required;
  return (
    <div style={{ flex: 1, minWidth: 140, border: `1px solid ${ok ? "#a7f3d0" : "#fecaca"}`, borderRadius: 10,
      padding: "10px 12px", background: ok ? "#f0fdf4" : "#fef2f2" }}>
      <div style={{ fontSize: 11.5, color: C.muted, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: ok ? "#047857" : "#dc2626" }}>
        {earned}<span style={{ fontSize: 12, color: C.muted, fontWeight: 500 }}> / {required}</span>
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: ok ? "#047857" : "#dc2626" }}>{ok ? "충족" : `${(required - earned).toFixed(0)}학점 부족`}</div>
    </div>
  );
}

const SEL3 = [["dup", "중복인정", "#1d4ed8", "#dbeafe", "#93c5fd"],
  ["primary", "제1전공", "#6d28d9", "#ede9fe", "#c4b5fd"],
  ["fusion", "융합전공", "#047857", "#ecfdf5", "#a7f3d0"]];

function ConvergenceBlock({ cc, C, first }) {
  const ov = cc.overlap_courses || [];
  const cap = cc.double_cap || 0;
  // 기본 선택: 전공필수 우선 중복인정(한도까지) → 제1전공 부족분 채움(제1전공) → 나머지 융합
  const defaultSel = React.useMemo(() => {
    const order = [...ov.keys()].sort((i, j) =>
      (ov[j].primary_required - ov[i].primary_required) || (ov[j].credits - ov[i].credits));
    const s = {}; let dup = 0;
    for (const i of order) { if (dup + ov[i].credits <= cap) { s[i] = "dup"; dup += ov[i].credits; } }
    // 전공필수 겹침은 융합 전용 이동 불가 → dup 아니면 제1전공 고정 (백엔드 기본배정과 동일)
    let reqP = 0;
    for (const i of order) { if (!s[i] && ov[i].primary_required) { s[i] = "primary"; reqP += ov[i].credits; } }
    let pneed = Math.max(0, (cc.primary_required || 0) - (cc.primary_base || 0) - dup - reqP);
    for (const i of order) {
      if (s[i]) continue;
      if (pneed > 0) { s[i] = "primary"; pneed -= ov[i].credits; } else s[i] = "fusion";
    }
    return s;
  }, [cc]);
  const [sel, setSel] = React.useState(defaultSel);
  React.useEffect(() => { setSel(defaultSel); }, [defaultSel]);

  const sum = (pred) => ov.reduce((s, f, i) => s + (pred(sel[i]) ? f.credits : 0), 0);
  const dupCr = sum((x) => x === "dup");
  const primaryCr = (cc.primary_base || 0) + sum((x) => x === "dup" || x === "primary");
  const fusionCr = (cc.fusion_base || 0) + sum((x) => x === "dup" || x === "fusion");
  const overCap = dupCr > cap;
  // 그룹별 최저(다전공12/부전공6)도 충족해야 '둘 다 충족' (백엔드 배정 반영 group_checks 기준)
  const groupsOk = (cc.group_checks || []).every((g) => g.gap <= 0);
  const fits = !overCap && primaryCr >= (cc.primary_required || 0) && fusionCr >= cc.required && groupsOk;

  // 미이수 시나리오: 융합 부족 시 안 들은 융합 과목 추천(부족 그룹 우선)
  const untaken = (cc.courses || []).filter((c) => !c.taken);
  const fusionGap = Math.max(0, cc.required - fusionCr);
  const shortGroups = new Set((cc.group_checks || []).filter((g) => g.gap > 0).map((g) => g.group));
  const suggest = [];
  if (fusionGap > 0) {
    const pool = [...untaken].sort((a, b) => (shortGroups.has(b.group) - shortGroups.has(a.group)));
    let acc = 0;
    for (const c of pool) { if (acc >= fusionGap) break; suggest.push(c); acc += c.credits; }
  }

  const groups = [...new Set((cc.courses || []).map((c) => c.group || "기타"))].sort();
  const taken = (cc.courses || []).filter((c) => c.taken).length;
  const selByName = {}; ov.forEach((f, i) => { selByName[f.name_ko] = sel[i]; });

  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 14, background: C.soft, marginTop: first ? 0 : 14 }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: C.navy, marginBottom: 8 }}>{cc.name} <span style={{ fontSize: 11.5, color: C.muted, fontWeight: 400 }}>{cc.track}·{cc.conv_type} · 이수 {taken}/{(cc.courses || []).length}과목 · 중복인정 한도 {cap}학점</span></div>

      <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
        <StatBox label="제1전공 전공 (배정 반영)" earned={primaryCr} required={cc.primary_required || 0} C={C} />
        <StatBox label={`${cc.conv_type} 이수 (배정 반영)`} earned={fusionCr} required={cc.required} C={C} />
      </div>
      <div style={{ fontSize: 10.5, color: C.muted, marginBottom: 8 }}>
        융합 과목 총 이수 {cc.designated_total ?? "-"}학점 · 중복인정 한도 {cap}학점 — 한도 초과분은 제1전공/융합 한쪽에만 인정(아래 3-way로 조정)
      </div>
      {overCap && <div style={{ fontSize: 11.5, color: "#dc2626", marginBottom: 6 }}>⚠️ 중복인정 {dupCr}학점 &gt; 한도 {cap}학점 — 일부를 제1전공/융합으로 바꾸세요.</div>}
      <div style={{ fontSize: 11.5, color: fits ? "#047857" : "#b45309", marginBottom: 8 }}>
        {fits
          ? "✅ 현재 배정으로 제1전공·융합 둘 다 졸업요건 충족 (그룹별 최저 포함)"
          : (primaryCr < (cc.primary_required || 0)
            ? `⚠️ 제1전공 ${((cc.primary_required || 0) - primaryCr).toFixed(0)}학점 부족 — 겹침과목을 제1전공으로 더 돌리거나 제1전공 과목 추가 이수`
            : (!groupsOk
              ? `⚠️ 그룹별 최저 미충족: ${(cc.group_checks || []).filter((g) => g.gap > 0).map((g) => `${g.group} ${g.gap}학점`).join(", ")} — 해당 그룹 과목 추가 이수 필요`
              : `⚠️ ${cc.conv_type} ${fusionGap.toFixed(0)}학점 부족 — 아래 미이수 과목 추가 이수 필요`))}
      </div>

      {/* 미이수 시나리오 — 무엇을 더 들어 어떤 이수구분으로 빼면 졸업 가능 */}
      {suggest.length > 0 && (
        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: 10, marginBottom: 8 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "#b45309", marginBottom: 4 }}>📋 졸업 가능 시나리오 (미이수 과목 추가 이수)</div>
          <div style={{ fontSize: 11.5, color: "#7c4a12" }}>
            다음 {cc.conv_type} 과목을 추가 이수하면 충족: {suggest.map((c) => `${c.name_ko}(${c.credits}${c.group ? "·" + c.group : ""})`).join(", ")}
          </div>
        </div>
      )}

      {cc.recommend_double_count?.length > 0 && (
        <div style={{ fontSize: 11.5, color: C.accent, marginBottom: 8 }}>
          💡 중복인정(양쪽 동시) 권장 — 제1전공·다전공 전공필수 우선: <strong>{cc.recommend_double_count.join(", ")}</strong>
        </div>
      )}

      {/* 교육과정 전체 — 그룹별. 겹침(이수) 과목은 옆에서 3-way 이수구분 선택 */}
      <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden", background: "#fff" }}>
        {groups.map((g) => (
          <div key={g}>
            <div style={{ background: C.soft, padding: "4px 10px", fontSize: 11.5, fontWeight: 700, color: C.navy, borderTop: `1px solid ${C.border}` }}>{g}</div>
            {(cc.courses || []).filter((c) => (c.group || "기타") === g).map((c, ci) => {
              const ovIdx = ov.findIndex((f) => f.name_ko === c.name_ko);
              const selectable = c.taken && c.overlap && ovIdx >= 0;
              return (
                <div key={ci} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", fontSize: 12,
                  borderTop: "1px solid #f1f4f8", opacity: c.taken ? 1 : 0.5, background: c.taken ? "#fafcff" : "#fff" }}>
                  <span style={{ width: 16 }}>{c.taken ? "✅" : "⬜"}</span>
                  <span style={{ flex: 1, fontWeight: c.taken ? 600 : 400 }}>
                    {c.name_ko}
                    {c.primary_required && <span style={{ marginLeft: 5, fontSize: 9.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 4, padding: "0 4px" }}>전공필수</span>}
                  </span>
                  <span style={{ width: 24, textAlign: "right", color: C.muted }}>{c.credits}</span>
                  {selectable ? (
                    <span style={{ display: "inline-flex", border: `1px solid ${C.border}`, borderRadius: 6, overflow: "hidden" }}>
                      {SEL3.map(([key, lbl, col, bg, bd]) => {
                        const on = sel[ovIdx] === key;
                        // 중복인정은 한도(cap) 초과 시, 융합전공은 전공필수 과목이면 선택 불가
                        const wouldExceed = (key === "dup" && !on && (dupCr + ov[ovIdx].credits > cap))
                          || (key === "fusion" && ov[ovIdx].primary_required);
                        return (
                          <button key={key} disabled={wouldExceed}
                            onClick={() => !wouldExceed && setSel((s) => ({ ...s, [ovIdx]: key }))}
                            title={wouldExceed ? (key === "fusion" ? "전공필수 과목은 융합 전용으로 이동 불가" : `중복인정 한도 ${cap}학점 초과`) : ""}
                            style={{ fontSize: 10, fontWeight: 700, padding: "3px 6px",
                              cursor: wouldExceed ? "not-allowed" : "pointer", border: "none",
                              borderLeft: key !== "dup" ? `1px solid ${C.border}` : "none",
                              background: on ? bg : "#fff", color: on ? col : (wouldExceed ? "#d1d5db" : "#9aa6b8") }}>{lbl}</button>
                        );
                      })}
                    </span>
                  ) : (
                    <span style={{ width: 70, textAlign: "center", fontSize: 10.5, fontWeight: 600,
                      color: c.taken ? "#047857" : "#9aa6b8", background: c.taken ? "#ecfdf5" : "#f3f4f6",
                      border: `1px solid ${c.taken ? "#a7f3d0" : "#e5e7eb"}`, borderRadius: 5, padding: "2px 0" }}>{c.taken ? "융합전용" : "미이수"}</span>
                  )}
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
    student_id: "", program_id: "ai_bigdata", current_term: "2026-1", remaining_semesters: 2,
    max_credits_per_term: 18, prev_term_gpa_ge_375: false,
    seasonal_semester_allowed: true, gpa_min_met: "unknown",
    preferences: "", convergence_program_ids: [], convergence_tracks: {},
  });
  const [departments, setDepartments] = React.useState([]);   // 전체 학과(검색용)
  const [otherMajors, setOtherMajors] = React.useState([]);   // 데모 미지원 다전공/부전공(표시만)
  const [majorQuery, setMajorQuery] = React.useState("");
  const [files, setFiles] = React.useState([]);
  const [verify, setVerify] = React.useState(null);
  const [table, setTable] = React.useState([]);
  const [audit, setAudit] = React.useState(null);
  const [busy, setBusy] = React.useState("");
  const [error, setError] = React.useState("");
  const [showSources, setShowSources] = React.useState(false);
  // 졸업 시나리오 상담(what-if) — audit 시점 payload를 동결해 사용(편집된 table과 분리, 검증 라운드2)
  const [auditPayload, setAuditPayload] = React.useState(null);
  const [whatif, setWhatif] = React.useState(null);
  const [question, setQuestion] = React.useState("");
  const [showAfterPlan, setShowAfterPlan] = React.useState(false);
  const [whatifError, setWhatifError] = React.useState("");   // 상담 카드 인라인 표시(상단 error와 분리)

  // #workflow 전용 페이지용 trace를 단일 effect로 동기화 — 이벤트 핸들러의 stale closure로
  // 옛 audit trace가 섞여 저장되는 경로 차단(검증 코드R3). 계약: whatif.node_trace만,
  // whatif.after.node_trace는 audit 노드명과 겹쳐 덮어쓰기를 유발하므로 절대 미포함.
  React.useEffect(() => {
    if (!verify && !audit) return;
    try {
      localStorage.setItem("v2_workflow_trace",
        JSON.stringify([...(verify?.node_trace || []), ...(audit?.node_trace || []),
                        ...(whatif?.node_trace || [])]));
    } catch { /* storage 불가 무시 */ }
  }, [verify, audit, whatif]);

  React.useEffect(() => {
    fetch(`${apiBase}/graduation/v2/status`).then((r) => r.json())
      .then((d) => {
        const progs = d.programs || {};
        setPrograms(progs);
        setDepartments(d.departments || []);
        // 초기 주전공의 학사규정 상한을 기본값으로
        setCtx((c) => {
          const cap = progs[c.program_id]?.max_credits_per_term;
          return cap ? { ...c, max_credits_per_term: cap } : c;
        });
      }).catch(() => {});
  }, [apiBase]);

  const admissionYear = () => {
    const m = String(ctx.student_id || "").match(/(20\d{2})/);
    return m ? Number(m[1]) : null;
  };
  const contextPayload = () => {
    // 프라이버시: 입력칸은 입학연도(4자리)지만, 원본 student_id는 서버로 보내지 않는다.
    // 연도만 추출해 admission_year로, 표시는 'YYYYXXXX' 마스킹으로 전송.
    const { student_id, ...rest } = ctx;
    const yr = admissionYear();
    return {
      ...rest,
      remaining_semesters: Number(ctx.remaining_semesters),
      max_credits_per_term: Number(ctx.max_credits_per_term),
      admission_year: yr,
      masked_student_id: yr ? `${yr}XXXX` : null,
      preferences: ctx.preferences ? ctx.preferences.split(",").map((s) => s.trim()).filter(Boolean) : [],
    };
  };

  // 주전공 변경 시 학사규정 제32조 학기당 상한을 기본값으로 자동 채움
  const onProgramChange = (id) => {
    const cap = programs[id]?.max_credits_per_term;
    setCtx((c) => ({ ...c, program_id: id, ...(cap ? { max_credits_per_term: cap } : {}) }));
  };

  // 다전공·부전공 검색 옵션: 연계융합(분석지원) + 전체 학과(데모 미지원)
  const majorOptions = () => {
    const convNames = new Set(convergencePrograms.map(([, p]) => p.name_ko));
    const conv = convergencePrograms.map(([id, p]) => ({ key: "c:" + id, id, label: p.name_ko, supported: true }));
    const depts = departments.filter((d) => !convNames.has(d.name))
      .map((d) => ({ key: "d:" + d.name, label: d.name, supported: false }));
    return [...conv, ...depts];
  };
  const pickMajor = (o) => {
    setMajorQuery("");
    if (o.supported) { if (!ctx.convergence_program_ids.includes(o.id)) toggleConv(o.id); }
    else { setOtherMajors((m) => (m.includes(o.label) ? m : [...m, o.label])); }
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
    setAuditPayload(null); setWhatif(null); setQuestion(""); setWhatifError("");  // stale 상담 상태 정리
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
      setAuditPayload(payload);            // what-if 동결 payload — 이후 테이블 편집과 분리
      setWhatif(null); setQuestion(""); setShowAfterPlan(false); setWhatifError("");
      // (#workflow trace 저장은 useEffect([verify, audit, whatif])가 단일 책임)
    } catch (e) { setError(String(e.message || e)); }
    setBusy("");
  };

  // ---------- 졸업 시나리오 상담 Agent (what-if) ----------
  // 테이블이 audit 이후 편집되면 시뮬레이션 비활성(화면 보고서와 before 불일치 방지)
  const tableDirty = auditPayload
    ? JSON.stringify(table) !== JSON.stringify(auditPayload.verification_table) : false;
  // 칩은 동결 payload의 context 기준(라이브 ctx 금지 — 칩 라벨·실제 요청 불일치 방지)
  const whatifChips = () => {
    const c = auditPayload?.context || {};
    const chips = [];
    if (c.current_term) chips.push("다음 학기 휴학하면?");
    if ((c.convergence_program_ids || []).length) {
      // 신청 트랙 기반 문구 — "다전공·부전공" 병기는 LLM이 모호해해 추출 실패(실가동 검정)
      const tracks = [...new Set(Object.values(c.convergence_tracks || {}))];
      chips.push(`${tracks.length === 1 ? tracks[0] : "다전공"}을 빼면?`);
    }
    chips.push(c.seasonal_semester_allowed ? "계절학기를 못 듣게 되면?" : "계절학기를 들으면?");
    chips.push("한 학기에 15학점씩만 들으면?");
    return chips.slice(0, 4);   // slice(0,3)은 '15학점' 칩(임팩트 큰 질문)을 잘라먹음(검증 코드R3)
  };
  const runWhatIf = async (q) => {
    const text = String(q ?? question).trim();
    if (!text || !auditPayload || tableDirty) return;
    setBusy("whatif"); setWhatifError(""); setShowAfterPlan(false);
    try {
      const r = await fetch(`${apiBase}/graduation/v2/whatif`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...auditPayload, question: text }) });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const d = await r.json();
      setWhatif(d); setQuestion(text);
      // (#workflow trace 저장은 useEffect가 단일 책임 — stale closure 방지)
    } catch (e) { setWhatifError(String(e.message || e)); }   // 상담 카드 안에 표시(상단까지 안 가도 보임)
    setBusy("");
  };
  const fmtNum = (x) => (Number.isInteger(x) ? x : Number(x).toFixed(1));
  const termKo = (lab) => {
    if (!lab) return "산출 불가";
    const [y, s] = String(lab).split("-");
    return s === "1" ? `${y}-1학기` : s === "2" ? `${y}-2학기` : s === "S" ? `${y} 하계` : s === "W" ? `${y} 동계` : lab;
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
            진단·로드맵은 결정론 노드가 계산·검증해 매번 같은 결과를 보장합니다.
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

          {/* ① 학적 정보 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "2px 0 8px" }}>① 학적 정보</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="입학연도 (학번 앞 4자리)" hint={admissionYear() ? `→ ${admissionYear()} 요람 적용` : "입학연도 기준 요람 적용"}>
              <input style={inputStyle} placeholder="예: 2025" value={ctx.student_id} onChange={(e) => setCtx({ ...ctx, student_id: e.target.value })} /></Field>
            <Field label="주전공">
              <select style={inputStyle} value={ctx.program_id} onChange={(e) => onProgramChange(e.target.value)}>
                {primaryPrograms.map(([id, p]) => <option key={id} value={id}>{p.name_ko}</option>)}
                {!primaryPrograms.length && <option value="ai_bigdata">AI빅데이터융합경영학과</option>}
              </select>
            </Field>
          </div>

          {/* 다전공·부전공 (연계융합 포함, 검색) */}
          <div style={{ marginTop: 12 }}>
            <span style={labelStyle}>다전공 · 부전공 (연계·융합전공 포함, 검색)</span>
            <div style={{ position: "relative", marginTop: 4 }}>
              <input style={inputStyle} placeholder="학과/전공 검색 후 선택 (데모 분석: 데이터사이언스융합·모빌리티데이터분석)"
                value={majorQuery} onChange={(e) => setMajorQuery(e.target.value)} />
              {majorQuery.trim() && (
                <div style={{ position: "absolute", zIndex: 5, left: 0, right: 0, top: "100%", maxHeight: 190, overflow: "auto",
                  background: "#fff", border: `1px solid ${C.border}`, borderRadius: 8, marginTop: 2, boxShadow: "0 4px 12px rgba(16,24,40,.1)" }}>
                  {majorOptions().filter((o) => o.label.includes(majorQuery.trim())).slice(0, 30).map((o) => (
                    <div key={o.key} onClick={() => pickMajor(o)}
                      style={{ padding: "6px 10px", fontSize: 12.5, cursor: "pointer", borderBottom: "1px solid #f1f4f8",
                        color: o.supported ? C.text : "#9aa6b8" }}>
                      {o.label}{o.supported ? <span style={{ color: C.accent, fontSize: 10.5, marginLeft: 6 }}>분석지원</span>
                        : <span style={{ fontSize: 10.5, marginLeft: 6 }}>(데모 미지원)</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* 선택된 추가전공 칩 */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {convergencePrograms.filter(([id]) => ctx.convergence_program_ids.includes(id)).map(([id, p]) => (
                <div key={id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
                  border: `1px solid ${C.accent}`, background: "#eef5ff", fontSize: 12.5 }}>
                  <span style={{ fontWeight: 600 }}>{p.name_ko}</span>
                  <select value={ctx.convergence_tracks[id] || "다전공"} onChange={(e) => setConvTrack(id, e.target.value)}
                    style={{ border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11.5, padding: "2px 4px" }}>
                    <option value="다전공">다전공 · 36/중복12</option>
                    <option value="부전공">부전공 · 18/중복6</option>
                  </select>
                  <span onClick={() => toggleConv(id)} style={{ cursor: "pointer", color: C.muted }}>✕</span>
                </div>
              ))}
              {otherMajors.map((nm, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 20,
                  border: `1px solid ${C.border}`, background: "#f3f4f6", fontSize: 12.5, color: "#9aa6b8" }}>
                  {nm} (데모 미지원)
                  <span onClick={() => setOtherMajors((o) => o.filter((x) => x !== nm))} style={{ cursor: "pointer" }}>✕</span>
                </div>
              ))}
            </div>
            {ctx.convergence_program_ids.length === 0 && otherMajors.length === 0 && (
              <div style={{ fontSize: 11.5, color: "#b45309", marginTop: 8, background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, padding: "7px 10px" }}>
                ※ 다전공·부전공을 모두 이수하지 않는 경우 <strong>심화전공(심화과정)</strong>을 이수해야 합니다 (학사규정 제33조).
              </div>
            )}
          </div>

          {/* ② 학기 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "16px 0 8px" }}>② 학기</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="현재 학기"
              hint={ctx.current_term && !/^20\d{2}-(1|2|S|W)$/.test(ctx.current_term)
                ? "⚠️ 형식이 올바르지 않습니다 — 연도 4자리-학기 (예: 2026-1)"
                : "형식: 연도-학기 (1=1학기, 2=2학기). 예: 2026-1"}>
              <input style={inputStyle} placeholder="예: 2026-1" value={ctx.current_term} onChange={(e) => setCtx({ ...ctx, current_term: e.target.value })} /></Field>
            <Field label="남은 학기" hint="현재 학기 다음부터 들을 정규학기 수 (현재 학기는 수강내역에 포함 → 제외)">
              <input style={inputStyle} type="number" value={ctx.remaining_semesters} onChange={(e) => setCtx({ ...ctx, remaining_semesters: e.target.value })} /></Field>
          </div>

          {/* ③ 수강 제약 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, margin: "16px 0 8px" }}>③ 수강 제약</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="한 학기 최대 수강 학점" hint="학사규정 제32조: 졸업학점 따라 17/18/19 자동 (수정 가능)">
              <input style={inputStyle} type="number" value={ctx.max_credits_per_term} onChange={(e) => setCtx({ ...ctx, max_credits_per_term: e.target.value })} /></Field>
            <Field label="졸업 최소 평점 충족" hint="졸업 요건: 전학년 평점평균 2.0/4.5 이상 (학사규정 제95조)">
              <select style={inputStyle} value={ctx.gpa_min_met} onChange={(e) => setCtx({ ...ctx, gpa_min_met: e.target.value })}>
                <option value="unknown">모름</option><option value="yes">충족 (2.0↑)</option><option value="no">미달 (2.0 미만)</option>
              </select>
            </Field>
            <label style={{ gridColumn: "1 / 3", display: "flex", alignItems: "center", gap: 7, fontSize: 12.5 }}>
              <input type="checkbox" checked={ctx.prev_term_gpa_ge_375} onChange={(e) => setCtx({ ...ctx, prev_term_gpa_ge_375: e.target.checked })} />
              직전학기 성적우수 (평점평균 3.75↑) — 다음 학기 +3학점 추가 수강 (학사규정 제32조)
            </label>
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 8 }}>※ 계절학기(6학점)는 기본 포함해 시나리오를 짭니다. 리포트 후 계절학기 불가 시 알려주시면 다시 계산합니다.</div>

          <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <label style={{ ...btnGhost, display: "inline-flex", alignItems: "center", gap: 6 }}>
              📂 엑셀 선택
              <input type="file" multiple accept=".xls,.xlsx" style={{ display: "none" }} onChange={(e) => setFiles([...e.target.files])} />
            </label>
            <span style={{ fontSize: 12.5, color: C.muted }}>
              {files.length ? `${files.length}개 학기 파일 선택됨` : "ON국민 수강내역(.xls)을 학기별로 모두 선택"}
            </span>
            <button style={{ ...btnPrimary(!busy), marginLeft: "auto" }} onClick={runVerify} disabled={!!busy}>
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
              <button style={{ ...btnPrimary(!busy), marginLeft: "auto" }} onClick={runAudit} disabled={!!busy}>
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
                    <div style={{ width: `${audit.audit.total_required > 0 ? Math.min(100, Math.round(audit.audit.total_earned / audit.audit.total_required * 100)) : 0}%`,
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

            {/* 졸업 최소 평점 주의 (충족이 아닐 때) */}
            {audit.context?.gpa_min_met !== "yes" && (
              <div style={{ ...card, background: audit.context?.gpa_min_met === "no" ? "#fef2f2" : "#fff7ed",
                border: `1px solid ${audit.context?.gpa_min_met === "no" ? "#fecaca" : "#fed7aa"}`,
                color: audit.context?.gpa_min_met === "no" ? C.danger : "#b45309", fontSize: 13 }}>
                ⚠️ {audit.context?.gpa_min_met === "no"
                  ? "졸업 최소 평점(전학년 평점평균 2.0/4.5) 미달 — 졸업요건을 충족하지 못합니다. 평점 관리가 필요합니다."
                  : "졸업 최소 평점(2.0/4.5) 충족 여부가 확인되지 않았습니다 — 성적표로 직접 확인하세요. (미달 시 졸업 불가)"}
              </div>
            )}

            {/* 영역별 현황 */}
            <div style={card}>
              <div style={sectionTitle}>📊 영역별 이수 현황</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
                {audit.audit.area_gaps.map((g, i) => <Gauge key={i} label={g.area} earned={g.earned} required={g.required} gap={g.gap} />)}
              </div>
              {(() => {
                const tf = audit.audit.to_fusion_total || 0;   // 백엔드 dedup값(다중 융합 합산 오류 방지)
                return tf > 0 ? (
                  <p style={{ fontSize: 11, color: C.muted, margin: "4px 0 0" }}>
                    ※ 전공 이수 학점 중 {tf}학점은 연계·융합전공 인정으로 배정되어 전공 게이지에서 제외됨 (중복인정 한도 초과분 — 총학점에는 포함)
                  </p>
                ) : null;
              })()}
              {audit.audit.core_area_gaps?.length > 0 && (
                <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.navy, marginBottom: 8 }}>핵심교양 영역별 (각 최저 학점 · 소통은 단과대 규정 반영)</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {audit.audit.core_area_gaps.map((g, i) => {
                      const ok = g.gap <= 0;
                      const pct = g.required > 0 ? Math.min(100, Math.round((g.earned / g.required) * 100)) : 100;
                      return (
                        <div key={i} style={{ flex: "1 1 90px", minWidth: 90, border: `1px solid ${ok ? "#a7f3d0" : "#fed7aa"}`,
                          borderRadius: 9, padding: "7px 9px", background: ok ? "#f0fdf4" : "#fff7ed" }}>
                          <div style={{ fontSize: 11.5, fontWeight: 600, color: "#334155" }}>{g.area}</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: ok ? C.ok : "#b45309" }}>{g.earned}<span style={{ fontSize: 11, color: C.muted, fontWeight: 400 }}>/{g.required}</span></div>
                          <div style={{ background: "#eef1f5", borderRadius: 5, height: 6, overflow: "hidden", marginTop: 3 }}>
                            <div style={{ width: `${pct}%`, height: 6, background: ok ? "#10B981" : "#f59e0b" }} />
                          </div>
                          <div style={{ fontSize: 10, color: ok ? C.ok : "#b45309", marginTop: 2 }}>{ok ? "충족" : `${g.gap} 부족`}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {audit.audit.gen_basic_courses?.length > 0 && (
                <div style={{ marginTop: 10, borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.navy, marginBottom: 6 }}>기초교양 필수 과목</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {audit.audit.gen_basic_courses.map((c, i) => (
                      <span key={i} style={{ fontSize: 12, padding: "3px 9px", borderRadius: 14,
                        background: c.taken ? "#f0fdf4" : "#fff7ed", border: `1px solid ${c.taken ? "#a7f3d0" : "#fed7aa"}`,
                        color: c.taken ? "#047857" : "#b45309" }}>{c.taken ? "✅" : "⬜"} {c.name_ko}</span>
                    ))}
                  </div>
                </div>
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
              {/* blocked 상세는 아래 feasible=false 박스·초과학기 카드에서 1회만 표시(3중 중복 방지) */}
              {/* 진짜 충족: feasible===true & 빈 계획 → 초록 / 현재학기 미입력(feasible null) → 중립 안내 */}
              {audit.roadmap.terms.length === 0 && audit.roadmap.feasible === true && (
                <div style={{ padding: "14px 16px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 10, color: "#047857", fontSize: 13.5, fontWeight: 600 }}>
                  ✅ {audit.roadmap.why_this_plan}
                </div>
              )}
              {audit.roadmap.terms.length === 0 && audit.roadmap.feasible === null && (
                <div style={{ padding: "14px 16px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 10, color: "#b45309", fontSize: 13 }}>
                  ⚠️ {audit.roadmap.why_this_plan}
                </div>
              )}
              {/* 남은 요건 요약 */}
              {(() => {
                const rem = [];
                const mg = audit.audit.area_gaps.find((g) => g.area === "전공");
                if (audit.audit.missing_required_names?.length) rem.push(`필수지정 ${audit.audit.missing_required_names.length}과목`);
                if (mg && mg.gap > 0) rem.push(`전공 ${mg.gap}학점`);
                (audit.audit.convergence_checks || []).forEach((cc) => { if (cc.gap > 0) rem.push(`${cc.name} ${cc.gap}학점`); });
                (audit.audit.core_area_gaps || []).filter((g) => g.gap > 0).forEach((g) => rem.push(`핵심교양 ${g.area} ${g.gap}학점`));
                ["기초교양", "자유교양"].forEach((a) => { const g = audit.audit.area_gaps.find((x) => x.area === a); if (g && g.gap > 0) rem.push(`${a} ${g.gap}학점`); });
                return rem.length > 0 && audit.roadmap.terms.length > 0 ? (
                  <div style={{ fontSize: 12, marginBottom: 10 }}>
                    <span style={{ color: C.muted, fontWeight: 600 }}>남은 요건: </span>
                    {rem.map((r, i) => <span key={i} style={{ display: "inline-block", background: "#fff7ed", border: "1px solid #fed7aa", color: "#b45309", borderRadius: 12, padding: "2px 8px", marginRight: 5, marginBottom: 4 }}>{r}</span>)}
                  </div>
                ) : null;
              })()}
              {audit.roadmap.terms.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {audit.roadmap.terms.map((t, i) => (
                    <div key={i} style={{ display: "flex", gap: 12 }}>
                      <div style={{ minWidth: 64, fontWeight: 700, color: C.navy, fontSize: 13.5, paddingTop: 2 }}>{t.term}<div style={{ fontSize: 10.5, color: C.muted, fontWeight: 400 }}>{t.term_credits}학점</div></div>
                      <div style={{ flex: 1, borderLeft: `3px solid ${C.accent}`, paddingLeft: 12, display: "flex", flexDirection: "column", gap: 5 }}>
                        {t.courses.map((c, ci) => {
                          const offered = (c.offered_terms || []).length ? `${c.offered_terms.map((x) => (x === "1" ? "1학기" : x === "2" ? "2학기" : x)).join("·")} 개설` : null;
                          return (
                            <div key={ci} style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", fontSize: 12.5 }}>
                              <span style={{ fontWeight: 600 }}>{c.name_ko}</span>
                              <span style={{ color: C.muted }}>{c.credits}학점</span>
                              {c.satisfies && <span style={{ fontSize: 10.5, background: "#eef5ff", color: C.accent, border: "1px solid #cfe1fb", borderRadius: 5, padding: "1px 6px" }}>{c.satisfies}</span>}
                              {c.assignment && <span style={{ fontSize: 10.5, background: "#ede9fe", color: "#6d28d9", border: "1px solid #c4b5fd", borderRadius: 5, padding: "1px 6px" }}>{c.assignment}</span>}
                              {offered && <span style={{ fontSize: 10.5, color: "#047857" }}>· {offered}</span>}
                              {c.manual_check && <span style={{ fontSize: 10.5, color: "#b45309", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 5, padding: "1px 6px" }}>확인 필요</span>}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {audit.roadmap.feasible === false && audit.roadmap.blocked_reason && (
                <div style={{ fontSize: 12.5, color: "#b45309", margin: "10px 0 0", padding: "10px 12px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8 }}>
                  ⚠️ {audit.roadmap.blocked_reason}
                  {/* hint는 초과학기 카드가 있으면 거기서만(문장 중복 방지) */}
                  {audit.roadmap.relaxation_hint && !audit.roadmap.overflow ? ` · ${audit.roadmap.relaxation_hint}` : ""}
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

            {/* 규정 근거 해설 — 보고서 내장 RAG (요람 chunk 인용, LLM은 해설만·판정은 결정론) */}
            {(audit.explanations?.length > 0 || audit.explain_fallback) && (
              <div style={card}>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: C.navy, marginBottom: 4 }}>
                  📖 규정 근거 해설 <span style={{ fontSize: 11, color: C.muted, fontWeight: 500 }}>요람 원문 기반 · 판정은 결정론 엔진</span>
                </div>
                {audit.explain_fallback && (
                  <div style={{ fontSize: 12, color: "#b45309", padding: "8px 10px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8 }}>
                    해설 생성 불가({audit.explain_fallback}) — 결정론 진단과 G 근거는 유효합니다.
                  </div>
                )}
                {(audit.explanations || []).map((sec) => (
                  <div key={sec.key} style={{ marginTop: 10 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: C.text }}>{sec.title}</div>
                    <ul style={{ margin: "5px 0 0", paddingLeft: 18 }}>
                      {sec.lines.map((ln, i) => (
                        <li key={i} style={{ fontSize: 12.5, color: ln.grounded ? C.text : "#b45309", lineHeight: 1.55, marginBottom: 3 }}>
                          {ln.text}
                          {ln.source_ids.map((s) => (
                            <span key={s} style={{ fontSize: 10, color: "#2563EB", marginLeft: 4, background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 4, padding: "0 4px" }}>{s}</span>
                          ))}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}

            {/* 졸업 시나리오 상담 Agent (what-if) — 자연어 → 매개변수 추출(LLM) → 결정론 재실행 */}
            <div style={card}>
              <div style={sectionTitle}>🔮 졸업 시나리오 상담 <span style={{ color: C.muted, fontWeight: 400, fontSize: 12 }}>
                질문을 LLM이 시뮬레이션 조건으로 변환하고, 판정은 결정론 엔진이 다시 계산합니다</span></div>
              {tableDirty && (
                <div style={{ fontSize: 12, color: "#b45309", padding: "8px 10px", background: "#fff7ed",
                  border: "1px solid #fed7aa", borderRadius: 8, marginBottom: 10 }}>
                  ⚠️ 검증 테이블이 수정되었습니다 — 시뮬레이션에 반영하려면 졸업사정을 다시 실행하세요.
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input value={question} onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") runWhatIf(); }}
                  placeholder='예: "다음 학기 휴학하면 졸업이 늦어지나요?"'
                  disabled={tableDirty || busy === "whatif"} maxLength={200}
                  style={{ flex: 1, padding: "9px 12px", border: `1px solid ${C.border}`, borderRadius: 9,
                    fontSize: 13, outline: "none", background: tableDirty ? "#f6f8fb" : "#fff" }} />
                <button onClick={() => runWhatIf()} disabled={tableDirty || busy === "whatif" || !question.trim()}
                  style={{ padding: "9px 16px", borderRadius: 9, border: "none", fontWeight: 700, fontSize: 13,
                    background: tableDirty || !question.trim() ? "#cbd5e1" : C.navy, color: "#fff",
                    cursor: tableDirty || !question.trim() ? "default" : "pointer" }}>
                  {busy === "whatif" ? "분석 중…" : "시뮬레이션"}
                </button>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                {whatifChips().map((c) => (
                  <button key={c} onClick={() => { setQuestion(c); runWhatIf(c); }}
                    disabled={tableDirty || busy === "whatif"}
                    style={{ fontSize: 12, padding: "5px 11px", borderRadius: 14, cursor: "pointer",
                      border: `1px solid ${C.border}`, background: "#fff", color: C.navy, fontWeight: 600 }}>{c}</button>
                ))}
              </div>
              <p style={{ fontSize: 10.5, color: C.muted, margin: "2px 0 0" }}>
                ※ 시뮬레이션은 서버 기본 겹침 배정 기준이며, 지원 범위: 휴학 · 잔여 학기 · 계절학기 · 학점 상한 · 다전공/부전공 변경
              </p>
              {whatifError && (
                <div style={{ marginTop: 10, padding: "9px 12px", background: "#fef2f2",
                  border: "1px solid #fecaca", borderRadius: 8, fontSize: 12.5, color: C.danger }}>
                  시뮬레이션 요청 실패: {whatifError}
                </div>
              )}

              {whatif && whatif.status === "unsupported" && (
                <div style={{ marginTop: 12, padding: "12px 14px", background: "#f6f8fb",
                  border: `1px solid ${C.border}`, borderRadius: 10, fontSize: 13, color: "#475569" }}>
                  💬 {whatif.unsupported_reason}
                </div>
              )}
              {whatif && whatif.status === "ok" && whatif.diff && (
                <div style={{ marginTop: 12, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
                  <div style={{ padding: "12px 16px", background: C.soft, fontSize: 13.5, fontWeight: 700, color: C.navy }}>
                    {whatif.diff.headline}
                  </div>
                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap", padding: "12px 16px" }}>
                    <div>
                      <div style={{ fontSize: 11, color: C.muted }}>리스크 등급</div>
                      <div style={{ fontSize: 16, fontWeight: 800 }}>
                        <span style={{ color: GRADE_COLOR[whatif.diff.risk_before] }}>{whatif.diff.risk_before}</span>
                        <span style={{ color: C.muted, fontWeight: 400 }}> → </span>
                        <span style={{ color: GRADE_COLOR[whatif.diff.risk_after] }}>{whatif.diff.risk_after}</span>
                        <span style={{ fontSize: 11.5, color: C.muted, fontWeight: 500, marginLeft: 5 }}>{whatif.diff.risk_label_after}</span>
                      </div>
                    </div>
                    {/* 양쪽 다 산출 불가면 블록 자체를 숨김 — "산출 불가 → 산출 불가" 무의미 표시 방지(코드R3) */}
                    {(whatif.diff.already_met_after || whatif.diff.graduation_term_before || whatif.diff.graduation_term_after) && (
                      <div>
                        <div style={{ fontSize: 11, color: C.muted }}>예상 졸업</div>
                        <div style={{ fontSize: 15, fontWeight: 700 }}>
                          {whatif.diff.already_met_after && !whatif.diff.graduation_term_after
                            ? "추가 수강 불요(충족 유지)"
                            : <>{termKo(whatif.diff.graduation_term_before)} <span style={{ color: C.muted, fontWeight: 400 }}>→</span> {termKo(whatif.diff.graduation_term_after)}</>}
                        </div>
                      </div>
                    )}
                    <div>
                      <div style={{ fontSize: 11, color: C.muted }}>총 부족 학점</div>
                      <div style={{ fontSize: 15, fontWeight: 700 }}>
                        {fmtNum(whatif.diff.total_gap_before)} <span style={{ color: C.muted, fontWeight: 400 }}>→</span> {fmtNum(whatif.diff.total_gap_after)}
                      </div>
                    </div>
                  </div>
                  {(whatif.applied_changes?.length > 0 || whatif.diff.convergence_changes?.length > 0 || whatif.diff.changed_areas?.length > 0) && (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", padding: "0 16px 10px" }}>
                      {(whatif.applied_changes || []).map((c, i) => (
                        <span key={"a" + i} style={{ fontSize: 11.5, background: "#eff6ff", color: "#1d4ed8",
                          border: "1px solid #bfdbfe", borderRadius: 13, padding: "3px 9px" }}>{c}</span>
                      ))}
                      {(whatif.diff.convergence_changes || []).map((c, i) => (
                        <span key={"c" + i} style={{ fontSize: 11.5, background: "#ede9fe", color: "#6d28d9",
                          border: "1px solid #c4b5fd", borderRadius: 13, padding: "3px 9px" }}>{c}</span>
                      ))}
                      {(whatif.diff.changed_areas || []).map((a, i) => (
                        <span key={"r" + i} style={{ fontSize: 11.5, background: "#fff7ed", color: "#b45309",
                          border: "1px solid #fed7aa", borderRadius: 13, padding: "3px 9px" }}>{a} 변동</span>
                      ))}
                    </div>
                  )}
                  {whatif.next_actions?.length > 0 && (
                    <div style={{ padding: "10px 16px", borderTop: `1px solid ${C.border}` }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: C.navy, marginBottom: 5 }}>다음 행동</div>
                      {whatif.next_actions.map((a, i) => (
                        <div key={i} style={{ fontSize: 12.5, color: C.text, lineHeight: 1.6 }}>☑️ {a}</div>
                      ))}
                    </div>
                  )}
                  {whatif.assumptions?.length > 0 && (
                    <p style={{ fontSize: 10.5, color: C.muted, margin: 0, padding: "6px 16px 10px" }}>가정: {whatif.assumptions.join(" / ")}</p>
                  )}
                  {whatif.after?.roadmap?.terms?.length > 0 && (
                    <div style={{ padding: "0 16px 12px" }}>
                      <button style={btnGhost} onClick={() => setShowAfterPlan((s) => !s)}>
                        {showAfterPlan ? "변경 후 로드맵 접기 ▲" : "변경 후 로드맵 보기 ▼"}
                      </button>
                      {showAfterPlan && (
                        <div style={{ marginTop: 8 }}>
                          {whatif.applied_changes?.some((c) => c.includes("휴학")) && (
                            <p style={{ fontSize: 11, color: C.muted, margin: "0 0 6px" }}>
                              ※ 휴학 반영 — 휴학 중 학기는 건너뛰고 복학 학기부터 배치됩니다.
                            </p>
                          )}
                          {whatif.after.roadmap.terms.map((t, i) => (
                            <div key={i} style={{ display: "flex", gap: 10, fontSize: 12.5, marginBottom: 4 }}>
                              <span style={{ minWidth: 78, fontWeight: 700, color: C.navy }}>{termKo(t.term)}</span>
                              <span style={{ color: C.text }}>{t.courses.map((c) => `${c.name_ko}(${c.credits})`).join(", ")}
                                <span style={{ color: C.muted }}> · {t.term_credits}학점</span></span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 워크플로우 그래프 — 보고서와 같은 화면에 인라인(노드 점등이 결과 옆에서 보임) */}
            <div style={card}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
                <div style={{ fontSize: 12, color: C.muted }}>
                  🔀 업무 노드 분절·실행 순서·분기 갈래 (방금 실행 결과 반영)
                </div>
                <button onClick={() => window.open(`${window.location.pathname}#workflow`, "_blank")}
                  style={{ ...btnGhost, whiteSpace: "nowrap" }}>크게 보기 ↗</button>
              </div>
              {/* 계약: whatif.node_trace만 합성 — whatif.after.node_trace는 audit 노드명과 겹쳐 덮어쓰기 유발(금지) */}
              <WorkflowGraph compact trace={[...(verify?.node_trace || []), ...(audit?.node_trace || []), ...(whatif?.node_trace || [])]} />
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
