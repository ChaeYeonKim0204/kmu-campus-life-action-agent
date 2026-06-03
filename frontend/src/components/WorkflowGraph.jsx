import React from "react";

// Dify식 워크플로우 실행 그래프 — node_trace를 trace 순서대로 점등 + 실행 분기 표시.
// 라이브러리 없이 SVG. 색: 결정론 도구(초록)/사용자 확인(주황)/LLM 판단(파랑)/검증·수리(보라).
const KIND = {
  tool: { color: "#10B981", label: "결정론 도구", icon: "⚙" },
  hitl: { color: "#F59E0B", label: "사용자 확인", icon: "✋" },
  llm: { color: "#2563EB", label: "LLM 판단", icon: "✦" },
  validator: { color: "#7C3AED", label: "검증·수리", icon: "✔" },
  branch: { color: "#6B7280", label: "분기", icon: "⋔" },
};
const NODES = [
  { key: "요람 로딩", kind: "tool" },
  { key: "데이터 수집", kind: "tool" },
  { key: "코드 매칭", kind: "tool" },
  { key: "데이터 검증", kind: "hitl", shape: "diamond" },
  { key: "갭 계산", kind: "tool" },
  { key: "로드맵 플래닝", kind: "llm" },
  { key: "검증/repair", kind: "validator", shape: "diamond" },
  { key: "리스크 산정", kind: "tool" },
  { key: "리포트", kind: "tool", terminal: true },
];
const KNOWN = new Set(NODES.map((n) => n.key));
const STEP = 82, TOP = 20, NX = 70, NW = 230, NH = 54;
const idxOf = (key) => NODES.findIndex((n) => n.key === key);
const nodeY = (i) => TOP + i * STEP;
const STATUS_GLYPH = { fail: "✕", warn: "!", skip: "·" };

export default function WorkflowGraph({ trace, compact = false }) {
  const byNode = React.useMemo(() => {
    const m = {};
    (trace || []).forEach((e) => { if (KNOWN.has(e.node)) m[e.node] = e; });
    return m;
  }, [trace]);
  const execKeys = React.useMemo(() => {
    const ks = (trace || []).map((e) => e.node).filter((k) => KNOWN.has(k));
    if (ks.length) ks.push("리포트");
    return ks;
  }, [trace]);

  const [active, setActive] = React.useState(0);
  const [replayKey, setReplayKey] = React.useState(0);
  React.useEffect(() => {
    setActive(0);
    if (!execKeys.length) return;
    const id = setInterval(() => setActive((a) => {
      if (a >= execKeys.length) { clearInterval(id); return a; }
      return a + 1;
    }), 520);
    return () => clearInterval(id);
  }, [execKeys, replayKey]);

  // 드래그(팬) — 그래프가 길어 화면 밖으로 나가면 끌어서 이동
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const drag = React.useRef(null);
  const onDown = (e) => { drag.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y }; };
  const onMove = (e) => {
    if (!drag.current) return;
    setPan({ x: drag.current.px + (e.clientX - drag.current.sx), y: drag.current.py + (e.clientY - drag.current.sy) });
  };
  const onUp = () => { drag.current = null; };

  const litKeys = new Set(execKeys.slice(0, active));
  const cx = NX + NW / 2;
  const height = TOP + NODES.length * STEP;
  const W = 460;
  const rf = idxOf("검증/repair"), rt = idxOf("로드맵 플래닝");
  const repairTaken = (byNode["검증/repair"]?.branch_taken || "").startsWith("repair");
  const statusStroke = (evt, base) =>
    evt?.status === "fail" ? "#EF4444" : evt?.status === "warn" ? "#D97706" : base;

  if (!execKeys.length) {
    return <div style={{ fontSize: 13, color: "#9aa6b8", padding: 20, textAlign: "center" }}>아직 실행된 워크플로우가 없습니다. 졸업사정을 먼저 실행하세요.</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <strong style={{ fontSize: compact ? 13 : 15, color: "#0F3D7A" }}>워크플로우 실행 그래프</strong>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setPan({ x: 0, y: 0 })}
            style={{ fontSize: 12, border: "1px solid #e3e8ef", borderRadius: 7, background: "#fff", padding: "5px 11px", cursor: "pointer", fontWeight: 600, color: "#475569" }}>⊕ 위치 초기화</button>
          <button onClick={() => setReplayKey((k) => k + 1)}
            style={{ fontSize: 12, border: "1px solid #e3e8ef", borderRadius: 7, background: "#fff", padding: "5px 11px", cursor: "pointer", fontWeight: 600, color: "#0F3D7A" }}>▶ 다시 재생</button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 12, margin: "0 0 10px" }}>
        {Object.values(KIND).filter((k) => k.label !== "분기").map((k) => (
          <span key={k.label} style={{ color: "#475569" }}><span style={{ display: "inline-block", width: 11, height: 11, background: k.color, borderRadius: 3, marginRight: 4, verticalAlign: "-1px" }} />{k.label}</span>
        ))}
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${height}`}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}
        style={{ maxWidth: compact ? 480 : 560, display: "block", margin: "0 auto",
          cursor: drag.current ? "grabbing" : "grab", touchAction: "none", userSelect: "none" }}>
        <defs>
          <filter id="nshadow" x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="1.5" stdDeviation="2.5" floodColor="#1e293b" floodOpacity="0.16" />
          </filter>
          <marker id="ar" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6" fill="#475569" /></marker>
          <marker id="arDim" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6" fill="#cbd5e1" /></marker>
          <marker id="arP" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6" fill={repairTaken ? "#7C3AED" : "#cbd5e1"} /></marker>
        </defs>
        <g transform={`translate(${pan.x},${pan.y})`}>
        {/* 엣지 */}
        {NODES.slice(0, -1).map((n, i) => {
          const lit = litKeys.has(n.key) && litKeys.has(NODES[i + 1].key);
          return <line key={`e${i}`} x1={cx} y1={nodeY(i) + NH} x2={cx} y2={nodeY(i + 1)}
            stroke={lit ? "#475569" : "#dbe1ea"} strokeWidth={lit ? 2.5 : 1.5} markerEnd={`url(#${lit ? "ar" : "arDim"})`} />;
        })}
        {/* repair 루프 */}
        <path d={`M ${NX + NW} ${nodeY(rf) + NH / 2} C ${NX + NW + 48} ${nodeY(rf)}, ${NX + NW + 48} ${nodeY(rt) + NH}, ${NX + NW} ${nodeY(rt) + NH / 2}`}
          fill="none" stroke={repairTaken ? "#7C3AED" : "#e5e7eb"} strokeWidth={repairTaken ? 2.5 : 1.5}
          strokeDasharray="5 4" markerEnd="url(#arP)" />
        <text x={NX + NW + 53} y={(nodeY(rf) + nodeY(rt)) / 2 + NH / 2} fontSize="11" fill={repairTaken ? "#7C3AED" : "#9ca3af"}>repair</text>
        {/* 노드 */}
        {NODES.map((n, i) => {
          const evt = byNode[n.key];
          const lit = litKeys.has(n.key);
          const base = KIND[n.kind].color;
          const fill = lit ? "#ffffff" : "#f6f8fb";
          const stroke = lit ? statusStroke(evt, base) : "#dbe1ea";
          const y = nodeY(i);
          const bt = evt?.branch_taken || "";
          const disp = bt.length > 12 ? bt.slice(0, 11) + "…" : bt;
          const glyph = lit && evt && STATUS_GLYPH[evt.status];
          return (
            <g key={n.key} opacity={lit ? 1 : 0.65}>
              {n.shape === "diamond" ? (
                <polygon points={`${cx},${y - 4} ${NX + NW + 4},${y + NH / 2} ${cx},${y + NH + 4} ${NX - 4},${y + NH / 2}`}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2.5 : 1.5} filter={lit ? "url(#nshadow)" : undefined} />
              ) : (
                <rect x={NX} y={y} width={NW} height={NH} rx={n.terminal ? 26 : 12}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2.5 : 1.5} filter={lit ? "url(#nshadow)" : undefined} />
              )}
              {/* kind 좌측 액센트 점 */}
              <circle cx={NX + 18} cy={y + NH / 2} r={6} fill={lit ? base : "#cbd5e1"} />
              <text x={NX + 18} y={y + NH / 2 + 3.5} textAnchor="middle" fontSize="8" fill="#fff">{KIND[n.kind].icon}</text>
              <text x={NX + 34} y={y + NH / 2 - 2} fontSize="14" fontWeight="700" fill={lit ? "#0f172a" : "#94a3b8"}>{n.key}</text>
              <text x={NX + 34} y={y + NH / 2 + 13} fontSize="10.5" fill="#94a3b8">{KIND[n.kind].label}</text>
              {glyph && (
                <g>
                  <circle cx={NX + NW - 16} cy={y + 15} r={8} fill={statusStroke(evt, base)} />
                  <text x={NX + NW - 16} y={y + 18.5} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{glyph}</text>
                </g>
              )}
              {lit && bt && (
                <g>
                  <title>{bt}</title>
                  <rect x={NX + NW + 8} y={y + NH / 2 - 11} width={disp.length * 8.2 + 14} height={22} rx={11}
                    fill={n.kind === "validator" ? "#f3effe" : "#eefcf3"} stroke={base} />
                  <text x={NX + NW + 15} y={y + NH / 2 + 4} fontSize="11" fill={base} fontWeight="600">{disp}</text>
                </g>
              )}
            </g>
          );
        })}
        </g>
      </svg>
    </div>
  );
}
