import React from "react";

// Dify식 워크플로우 실행 그래프 — node_trace를 trace 순서대로 점등 + 실행 분기 표시.
// 라이브러리 없이 SVG. 색: 결정론 도구(초록)/사용자 확인(주황)/LLM 판단(파랑)/검증·수리(보라).
const KIND = {
  tool: { color: "#10B981", label: "결정론 도구" },
  hitl: { color: "#F59E0B", label: "사용자 확인" },
  llm: { color: "#2563EB", label: "LLM 판단" },
  validator: { color: "#7C3AED", label: "검증·수리" },
  branch: { color: "#6B7280", label: "분기" },
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
const STEP = 66, TOP = 14, NX = 24, NW = 188, NH = 42;
const idxOf = (key) => NODES.findIndex((n) => n.key === key);
const nodeY = (i) => TOP + i * STEP;

export default function WorkflowGraph({ trace }) {
  const byNode = React.useMemo(() => {
    const m = {};
    (trace || []).forEach((e) => { if (KNOWN.has(e.node)) m[e.node] = e; });
    return m;
  }, [trace]);
  // 실행 순서(trace에 실제 등장한 노드) + 종료 리포트
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
    }), 480);
    return () => clearInterval(id);
  }, [execKeys, replayKey]);

  const litKeys = new Set(execKeys.slice(0, active));
  const cx = NX + NW / 2;
  const height = TOP + NODES.length * STEP;
  const rf = idxOf("검증/repair"), rt = idxOf("로드맵 플래닝");
  const repairTaken = (byNode["검증/repair"]?.branch_taken || "").startsWith("repair");

  const statusStroke = (evt, base) =>
    evt?.status === "fail" ? "#EF4444" : evt?.status === "warn" ? "#D97706" : base;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: 13 }}>워크플로우 실행 그래프</strong>
        <button onClick={() => setReplayKey((k) => k + 1)} style={{ fontSize: 11 }}>▶ 다시 재생</button>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 11, margin: "4px 0 8px" }}>
        {Object.values(KIND).filter((k) => k.label !== "분기").map((k) => (
          <span key={k.label}><span style={{ display: "inline-block", width: 10, height: 10, background: k.color, borderRadius: 2, marginRight: 3 }} />{k.label}</span>
        ))}
      </div>
      <svg width="100%" viewBox={`0 0 440 ${height}`} style={{ maxWidth: 470 }}>
        <defs>
          <marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#374151" /></marker>
          <marker id="arDim" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#d1d5db" /></marker>
          <marker id="arP" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill={repairTaken ? "#7C3AED" : "#d1d5db"} /></marker>
        </defs>
        {/* 엣지 */}
        {NODES.slice(0, -1).map((n, i) => {
          const lit = litKeys.has(n.key) && litKeys.has(NODES[i + 1].key);
          return <line key={`e${i}`} x1={cx} y1={nodeY(i) + NH} x2={cx} y2={nodeY(i + 1)}
            stroke={lit ? "#374151" : "#d1d5db"} strokeWidth={lit ? 2 : 1.5} markerEnd={`url(#${lit ? "ar" : "arDim"})`} />;
        })}
        {/* repair 루프 (검증→로드맵) */}
        <path d={`M ${NX + NW} ${nodeY(rf) + NH / 2} C ${NX + NW + 38} ${nodeY(rf)}, ${NX + NW + 38} ${nodeY(rt) + NH}, ${NX + NW} ${nodeY(rt) + NH / 2}`}
          fill="none" stroke={repairTaken ? "#7C3AED" : "#e5e7eb"} strokeWidth={repairTaken ? 2.5 : 1.5}
          strokeDasharray="4 3" markerEnd="url(#arP)" />
        <text x={NX + NW + 42} y={(nodeY(rf) + nodeY(rt)) / 2 + NH / 2} fontSize="10" fill={repairTaken ? "#7C3AED" : "#9ca3af"}>repair</text>
        {/* 노드 */}
        {NODES.map((n, i) => {
          const evt = byNode[n.key];
          const lit = litKeys.has(n.key);
          const base = KIND[n.kind].color;
          const fill = lit ? base : "#f3f4f6";
          const stroke = lit ? statusStroke(evt, base) : "#d1d5db";
          const dash = lit && evt?.status === "warn" ? "5 3" : undefined;
          const y = nodeY(i);
          const bt = evt?.branch_taken || "";
          const disp = bt.length > 11 ? bt.slice(0, 10) + "…" : bt;
          return (
            <g key={n.key} opacity={lit ? 1 : 0.6}>
              {n.shape === "diamond" ? (
                <polygon points={`${cx},${y} ${NX + NW},${y + NH / 2} ${cx},${y + NH} ${NX},${y + NH / 2}`}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2 : 1} strokeDasharray={dash} />
              ) : (
                <rect x={NX} y={y} width={NW} height={NH} rx={n.terminal ? 20 : 8}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2 : 1} strokeDasharray={dash} />
              )}
              <text x={cx} y={y + NH / 2 + 4} textAnchor="middle" fontSize="12" fontWeight="600" fill={lit ? "#fff" : "#9ca3af"}>{n.key}</text>
              {lit && bt && (
                <g>
                  <title>{bt}</title>
                  <rect x={NX + NW + 6} y={y + NH / 2 - 9} width={disp.length * 8.5 + 12} height={18} rx={9}
                    fill={n.kind === "validator" ? "#ede9fe" : "#f0fdf4"} stroke={base} />
                  <text x={NX + NW + 12} y={y + NH / 2 + 4} fontSize="10" fill={base}>{disp}</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
