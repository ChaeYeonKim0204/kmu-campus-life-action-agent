import React from "react";

// Dify식 워크플로우 실행 그래프 — node_trace를 순서대로 점등 + 분기 갈래·조건 엣지 라벨.
// 라이브러리 없이 SVG. 색: 결정론 도구(초록)/사용자 확인(주황)/LLM 판단(파랑)/검증·수리(보라).
const KIND = {
  tool: { color: "#10B981", label: "결정론 도구", icon: "⚙" },
  hitl: { color: "#F59E0B", label: "사용자 확인", icon: "✋" },
  llm: { color: "#2563EB", label: "LLM 판단", icon: "✦" },
  validator: { color: "#7C3AED", label: "검증·수리", icon: "✔" },
};
const kindOf = (k) => KIND[k] || KIND.tool;   // 미정의 kind 방어(검증 라운드3 — branch 등)
// lane:"side" = 분기 갈래 노드(우측 레인). branchFrom/branchTo: 갈래 엣지의 출발/합류 노드.
const BASE_NODES = [
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
  // 에이전트 총평(bounded ReAct 단일 턴) — LLM이 갈림길 후보·delta 값을 고르고(Thought),
  // 결정론 시뮬레이터가 재실행(Action)·diff 관찰(Observation) 후 비교 총평(Answer).
  { key: "갈림길 선정", kind: "llm" },
  { key: "갈림길 시뮬레이션", kind: "tool" },
  { key: "총평 생성", kind: "llm" },
  { key: "총평 검증", kind: "validator", shape: "diamond" },
  { key: "리포트", kind: "tool", terminal: true },
];
// 졸업 시나리오 상담 Agent(what-if) 클러스터 — trace에 상담 이벤트가 있을 때만 그린다.
// 안내 종료는 합류 없는 종단 분기(noRejoin) — 예제06의 실패메시지 노드 대응.
const CONSULT_NODES = [
  { key: "질문 분류", kind: "llm" },
  { key: "매개변수 추출", kind: "llm" },
  { key: "조건 가드", kind: "validator", shape: "diamond" },
  { key: "안내 종료", kind: "tool", lane: "side", noRejoin: true,
    branchFrom: "조건 가드", okLabel: "통과", failLabel: "지원 범위 밖" },
  { key: "졸업사정 재실행", kind: "tool" },
  { key: "시나리오 비교", kind: "tool" },
  { key: "다음 행동 제안", kind: "tool", terminal: true },
];
const BASE_KNOWN = new Set(BASE_NODES.map((n) => n.key));
const CONSULT_KNOWN = new Set(CONSULT_NODES.map((n) => n.key));
const STEP = 82, TOP = 20, NX = 178, NW = 230, NH = 54;
const SX = NX + NW + 26, SW = 168, SH = 46;        // 사이드 레인(분기 갈래)
const STATUS_GLYPH = { fail: "✕", warn: "!", skip: "·" };
// SVG <text>는 width 자동 계산이 없어 글자폭을 추정 — 한글(전각) ≈ fontSize, 그 외 ≈ 절반.
// 평균치(8.2) 방식은 한글 비중 높은 라벨이 pill 밖으로 삐져나갔다(정렬 수정 2026-06-05).
const charW = (ch) => (ch.charCodeAt(0) > 0x2e7f ? 11 : 6.2);
const textW = (s) => [...s].reduce((w, c) => w + charW(c), 0);
const PILL_PAD_X = 10, PILL_PAD_Y = 4, PILL_MAX_TEXT = 140;   // padding 4px 10px, 레인 침범 방지 상한
const pillDisp = (s) => {
  if (textW(s) <= PILL_MAX_TEXT) return s;
  let out = s;
  while (out.length > 1 && textW(out) + 11 > PILL_MAX_TEXT) out = out.slice(0, -1);
  return out.trimEnd() + "…";
};

export default function WorkflowGraph({ trace, compact = false }) {
  // 상담 이벤트가 있을 때만 상담 클러스터를 노출(레이아웃·높이·엣지 전부 동적 — 검증 라운드2 H3)
  const hasConsult = React.useMemo(
    () => (trace || []).some((e) => CONSULT_KNOWN.has(e.node)), [trace]);
  const nodes = React.useMemo(
    () => (hasConsult ? [...BASE_NODES, ...CONSULT_NODES] : BASE_NODES), [hasConsult]);
  const known = React.useMemo(() => new Set(nodes.map((n) => n.key)), [nodes]);
  const idxOf = React.useCallback((key) => nodes.findIndex((n) => n.key === key), [nodes]);
  const nodeY = (i) => TOP + i * STEP;

  const byNode = React.useMemo(() => {
    const m = {};
    (trace || []).forEach((e) => { if (known.has(e.node)) m[e.node] = e; });
    return m;
  }, [trace, known]);
  const execKeys = React.useMemo(() => {
    // '리포트'는 audit trace 직후에 삽입 — 상담 노드가 리포트보다 먼저 점등되는 순서 왜곡 방지.
    // 단 audit 완료 신호('리스크 산정')가 있을 때만 — verify-only 단계에서 리포트가
    // 실행된 것처럼 거짓 점등되는 문제 방지(검증 코드R2).
    const all = (trace || []).map((e) => e.node);
    const audit = all.filter((k) => BASE_KNOWN.has(k));
    const consult = all.filter((k) => CONSULT_KNOWN.has(k));
    const ks = [...audit];
    if (audit.includes("리스크 산정")) ks.push("리포트");
    ks.push(...consult);
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
  const height = TOP + nodes.length * STEP;
  const W = SX + SW + 12;
  const statusStroke = (evt, base) =>
    evt?.status === "fail" ? "#EF4444" : evt?.status === "warn" ? "#D97706"
    : evt?.status === "skip" ? "#94a3b8" : base;   // skip은 회색 — '실행됨'과 시각 구분(적대②)

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

  // 메인 레인 노드들 사이 엣지 + 분기 갈래 엣지 (branchFrom 키별 매핑 — 사이드 2개 공존 지원)
  const mains = nodes.filter((n) => n.lane !== "side");
  const sideByFrom = {};
  nodes.forEach((s) => { if (s.lane === "side" && s.branchFrom) sideByFrom[s.branchFrom] = s; });
  const edges = [];
  mains.slice(0, -1).forEach((n, mi) => {
    const next = mains[mi + 1];
    const side = sideByFrom[n.key];
    const i = idxOf(n.key), j = idxOf(next.key);
    const yBot = nodeY(i) + NH + (n.shape === "diamond" ? 4 : 0);
    const yTop = nodeY(j) - (next.shape === "diamond" ? 4 : 0);
    if (side) {
      const sLit = litKeys.has(side.key);
      const okLit = litKeys.has(n.key) && litKeys.has(next.key) && !sLit;
      const si = idxOf(side.key);
      const sy = nodeY(si) + (STEP - SH) / 2;
      // 통과(직행) vs 실패(사이드 경유) — 둘 다 항상 그려서 '갈 수 있는 길'을 보여줌
      edges.push(edge(cx, yBot, cx, yTop, okLit, `e-ok-${n.key}`, side.okLabel, okLit));
      edges.push(edge(cx + NW / 4, yBot, SX + SW / 2, sy, sLit, `e-f1-${n.key}`, side.failLabel, sLit));
      // noRejoin(안내 종료): 합류 엣지 없음 — 흐름이 거기서 끝남(거짓 합류 표시 금지)
      if (!side.noRejoin) {
        edges.push(edge(SX + SW / 2, sy + SH, cx + NW / 4, yTop, sLit, `e-f2-${n.key}`));
      }
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
        {nodes.map((n) => {
          const evt = byNode[n.key];
          const lit = litKeys.has(n.key);
          const base = kindOf(n.kind).color;
          const stroke = lit ? statusStroke(evt, base) : "#dbe1ea";
          const i = idxOf(n.key);
          const isSide = n.lane === "side";
          const x = isSide ? SX : NX, w = isSide ? SW : NW, h = isSide ? SH : NH;
          const y = isSide ? nodeY(i) + (STEP - SH) / 2 : nodeY(i);
          const xc = x + w / 2;
          const fill = lit ? "#ffffff" : "#f6f8fb";
          const bt = evt?.branch_taken || "";
          const disp = pillDisp(bt);
          const pillW = textW(disp) + PILL_PAD_X * 2;   // fit-content: 텍스트 실측폭 + 좌우 padding
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
              {/* padding-left 22, 아이콘→텍스트 간격 16 유지; 제목+보조 2줄 블록을 노드 세로 중심에 정렬 */}
              <circle cx={x + 22} cy={y + h / 2} r={6} fill={lit ? base : "#cbd5e1"} />
              <text x={x + 22} y={y + h / 2 + 3.5} textAnchor="middle" fontSize="8" fill="#fff">{kindOf(n.kind).icon}</text>
              <text x={x + 38} y={y + h / 2 - 3} fontSize={isSide ? 12 : 14} fontWeight="700" fill={lit ? "#0f172a" : "#94a3b8"}>{n.key}</text>
              <text x={x + 38} y={y + h / 2 + 12} fontSize="10.5" fill="#94a3b8">{kindOf(n.kind).label}</text>
              {glyph && (
                <g>
                  <circle cx={x + w - 16} cy={y + 15} r={8} fill={statusStroke(evt, base)} />
                  <text x={x + w - 16} y={y + 18.5} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{glyph}</text>
                </g>
              )}
              {/* 분기 pill — 좌측 레인(겹침 없음). 글자폭 실측 + 좌우 padding, 텍스트는 pill 중앙 정렬 */}
              {lit && bt && !isSide && (
                <g>
                  <title>{bt}</title>
                  <rect x={NX - 16 - pillW} y={y + NH / 2 - 11 - PILL_PAD_Y / 2} width={pillW} height={22 + PILL_PAD_Y} rx={11 + PILL_PAD_Y / 2}
                    fill={n.kind === "validator" ? "#f3effe" : n.kind === "llm" ? "#eff6ff" : "#eefcf3"} stroke={base} />
                  <text x={NX - 16 - pillW / 2} y={y + NH / 2 + 4} textAnchor="middle" fontSize="11" fill={base} fontWeight="600">{disp}</text>
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
