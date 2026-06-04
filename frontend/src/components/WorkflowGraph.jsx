import React from "react";

// Dify식 워크플로우 실행 그래프 — node_trace를 순서대로 점등 + 분기 갈래·조건 엣지 라벨.
// 라이브러리 없이 SVG. 색: 결정론 도구(초록)/사용자 확인(주황)/LLM 판단(파랑)/검증·수리(보라).
const KIND = {
  tool: { color: "#10B981", label: "결정론 도구", icon: "⚙" },
  hitl: { color: "#F59E0B", label: "사용자 확인", icon: "✋" },
  llm: { color: "#2563EB", label: "LLM 판단", icon: "✦" },
  validator: { color: "#7C3AED", label: "검증·수리", icon: "✔" },
};
// lane:"side" = 분기 갈래 노드(우측 레인). branchFrom/branchTo: 갈래 엣지의 출발/합류 노드.
const NODES = [
  { key: "요람 로딩", kind: "tool" },
  { key: "데이터 수집", kind: "tool" },
  { key: "코드 매칭", kind: "tool" },
  { key: "데이터 검증", kind: "hitl", shape: "diamond" },
  { key: "갭 계산", kind: "tool" },
  { key: "로드맵 배치", kind: "tool" },
  { key: "로드맵 검증", kind: "validator", shape: "diamond" },
  { key: "초과학기 시나리오", kind: "tool", lane: "side",
    branchFrom: "로드맵 검증", branchTo: "리스크 산정", okLabel: "통과", failLabel: "미배치" },
  { key: "리스크 산정", kind: "tool" },
  { key: "요람 RAG 해설", kind: "llm" },
  { key: "해설 검증", kind: "validator", shape: "diamond" },
  { key: "리포트", kind: "tool", terminal: true },
];
const KNOWN = new Set(NODES.map((n) => n.key));
const STEP = 82, TOP = 20, NX = 178, NW = 230, NH = 54;
const SX = NX + NW + 26, SW = 168, SH = 46;        // 사이드 레인(분기 갈래)
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

  // 드래그(팬)
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
  const W = SX + SW + 12;
  const statusStroke = (evt, base) =>
    evt?.status === "fail" ? "#EF4444" : evt?.status === "warn" ? "#D97706" : base;

  if (!execKeys.length) {
    return <div style={{ fontSize: 13, color: "#9aa6b8", padding: 20, textAlign: "center" }}>아직 실행된 워크플로우가 없습니다. 졸업사정을 먼저 실행하세요.</div>;
  }

  const edge = (x1, y1, x2, y2, lit, key, label, labelLit) => (
    <g key={key}>
      <path d={`M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`}
        fill="none" stroke={lit ? "#475569" : "#dbe1ea"} strokeWidth={lit ? 2.5 : 1.5}
        markerEnd={`url(#${lit ? "ar" : "arDim"})`} />
      {label && (
        <text x={(x1 + x2) / 2 + (x1 === x2 ? 8 : 0)} y={(y1 + y2) / 2 - 4} fontSize="10.5"
          fontWeight="700" fill={labelLit ? "#334155" : "#b6c0cd"}
          textAnchor={x1 === x2 ? "start" : "middle"}>{label}</text>
      )}
    </g>
  );

  // 메인 레인 노드들 사이 엣지 + 분기 갈래 엣지
  const mains = NODES.filter((n) => n.lane !== "side");
  const edges = [];
  mains.slice(0, -1).forEach((n, mi) => {
    const next = mains[mi + 1];
    const side = NODES.find((s) => s.lane === "side" && s.branchFrom === n.key);
    const i = idxOf(n.key), j = idxOf(next.key);
    const yBot = nodeY(i) + NH + (n.shape === "diamond" ? 4 : 0);
    const yTop = nodeY(j) - (next.shape === "diamond" ? 4 : 0);
    if (side) {
      const evt = byNode[n.key];
      const sLit = litKeys.has(side.key);
      const okLit = litKeys.has(n.key) && litKeys.has(next.key) && !sLit;
      const si = idxOf(side.key);
      const sy = nodeY(si) + (STEP - SH) / 2;
      // 통과(직행) vs 미배치(사이드 경유) — 둘 다 항상 그려서 '갈 수 있는 길'을 보여줌
      edges.push(edge(cx, yBot, cx, yTop, okLit, `e-ok-${n.key}`, side.okLabel, okLit));
      edges.push(edge(cx + NW / 4, yBot, SX + SW / 2, sy, sLit, `e-f1-${n.key}`, side.failLabel, sLit));
      edges.push(edge(SX + SW / 2, sy + SH, cx + NW / 4, yTop, sLit, `e-f2-${n.key}`));
    } else {
      edges.push(edge(cx, yBot, cx, yTop, litKeys.has(n.key) && litKeys.has(next.key), `e-${n.key}`));
    }
  });

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
        {Object.values(KIND).map((k) => (
          <span key={k.label} style={{ color: "#475569" }}><span style={{ display: "inline-block", width: 11, height: 11, background: k.color, borderRadius: 3, marginRight: 4, verticalAlign: "-1px" }} />{k.label}</span>
        ))}
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${height}`}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}
        style={{ maxWidth: compact ? 540 : 640, display: "block", margin: "0 auto",
          cursor: drag.current ? "grabbing" : "grab", touchAction: "none", userSelect: "none" }}>
        <defs>
          <filter id="nshadow" x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="1.5" stdDeviation="2.5" floodColor="#1e293b" floodOpacity="0.16" />
          </filter>
          <marker id="ar" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6" fill="#475569" /></marker>
          <marker id="arDim" markerWidth="9" markerHeight="9" refX="6.5" refY="3" orient="auto"><path d="M0,0 L6.5,3 L0,6" fill="#cbd5e1" /></marker>
        </defs>
        <g transform={`translate(${pan.x},${pan.y})`}>
        {edges}
        {/* 노드 */}
        {NODES.map((n) => {
          const evt = byNode[n.key];
          const lit = litKeys.has(n.key);
          const base = KIND[n.kind].color;
          const stroke = lit ? statusStroke(evt, base) : "#dbe1ea";
          const i = idxOf(n.key);
          const isSide = n.lane === "side";
          const x = isSide ? SX : NX, w = isSide ? SW : NW, h = isSide ? SH : NH;
          const y = isSide ? nodeY(i) + (STEP - SH) / 2 : nodeY(i);
          const xc = x + w / 2;
          const fill = lit ? "#ffffff" : "#f6f8fb";
          const bt = evt?.branch_taken || "";
          const disp = bt.length > 17 ? bt.slice(0, 16) + "…" : bt;
          const glyph = lit && evt && STATUS_GLYPH[evt.status];
          return (
            <g key={n.key} opacity={lit ? 1 : 0.62}>
              {n.shape === "diamond" ? (
                <polygon points={`${xc},${y - 4} ${x + w + 4},${y + h / 2} ${xc},${y + h + 4} ${x - 4},${y + h / 2}`}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2.5 : 1.5} filter={lit ? "url(#nshadow)" : undefined} />
              ) : (
                <rect x={x} y={y} width={w} height={h} rx={n.terminal ? 26 : 12}
                  fill={fill} stroke={stroke} strokeWidth={lit ? 2.5 : 1.5} filter={lit ? "url(#nshadow)" : undefined}
                  strokeDasharray={isSide && !lit ? "5 4" : undefined} />
              )}
              <circle cx={x + 18} cy={y + h / 2} r={6} fill={lit ? base : "#cbd5e1"} />
              <text x={x + 18} y={y + h / 2 + 3.5} textAnchor="middle" fontSize="8" fill="#fff">{KIND[n.kind].icon}</text>
              <text x={x + 34} y={y + h / 2 - 2} fontSize={isSide ? 12 : 14} fontWeight="700" fill={lit ? "#0f172a" : "#94a3b8"}>{n.key}</text>
              <text x={x + 34} y={y + h / 2 + 13} fontSize="10.5" fill="#94a3b8">{KIND[n.kind].label}</text>
              {glyph && (
                <g>
                  <circle cx={x + w - 16} cy={y + 15} r={8} fill={statusStroke(evt, base)} />
                  <text x={x + w - 16} y={y + 18.5} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{glyph}</text>
                </g>
              )}
              {/* 분기 pill — 좌측 레인(겹침 없음·17자) */}
              {lit && bt && !isSide && (
                <g>
                  <title>{bt}</title>
                  <rect x={NX - 16 - (disp.length * 8.2 + 14)} y={y + NH / 2 - 11} width={disp.length * 8.2 + 14} height={22} rx={11}
                    fill={n.kind === "validator" ? "#f3effe" : n.kind === "llm" ? "#eff6ff" : "#eefcf3"} stroke={base} />
                  <text x={NX - 9 - (disp.length * 8.2 + 14) + 7} y={y + NH / 2 + 4} fontSize="11" fill={base} fontWeight="600">{disp}</text>
                </g>
              )}
              {lit && bt && isSide && <title>{bt}</title>}
            </g>
          );
        })}
        </g>
      </svg>
    </div>
  );
}
