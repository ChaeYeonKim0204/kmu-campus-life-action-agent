import React from "react";
import WorkflowGraph from "./WorkflowGraph.jsx";

// 워크플로우 실행 그래프 전용 페이지(졸업센터 대시보드와 분리).
// 대시보드에서 졸업사정을 실행하면 trace를 localStorage에 저장하고, 이 페이지가 읽어 시각화한다.
const C = { navy: "#0F3D7A", bg: "#eef2f7", card: "#fff", border: "#e3e8ef", muted: "#6b7280" };

export default function WorkflowPage() {
  const [trace, setTrace] = React.useState([]);
  React.useEffect(() => {
    const load = () => {
      try { setTrace(JSON.parse(localStorage.getItem("v2_workflow_trace") || "[]")); }
      catch { setTrace([]); }
    };
    load();
    window.addEventListener("storage", load);   // 대시보드 창에서 갱신되면 자동 반영
    return () => window.removeEventListener("storage", load);
  }, []);

  return (
    <div style={{ background: C.bg, minHeight: "100vh", fontFamily: "'Pretendard',-apple-system,'Segoe UI',sans-serif", color: "#1f2937" }}>
      <div style={{ background: `linear-gradient(120deg,${C.navy},#143e8c 60%,#1d6fe0)`, color: "#fff", padding: "20px 26px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          <div style={{ fontSize: 12, letterSpacing: ".08em", opacity: .85, fontWeight: 600 }}>KOOKMIN UNIV · 졸업센터</div>
          <h1 style={{ margin: "4px 0 4px", fontSize: 21, fontWeight: 800 }}>워크플로우 실행 그래프</h1>
          <p style={{ margin: 0, fontSize: 13, opacity: .9 }}>
            업무를 결정론 도구 / 사용자 확인 / LLM 판단 / 검증·수리 노드로 분절하고, 실행 순서대로 점등 + 분기를 표시합니다.
          </p>
        </div>
      </div>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: 22 }}>
        <a href="#" style={{ fontSize: 13, color: C.navy, fontWeight: 600, textDecoration: "none" }}>← 졸업사정 대시보드로</a>
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 20, marginTop: 12, boxShadow: "0 1px 3px rgba(16,24,40,.06)" }}>
          <WorkflowGraph trace={trace} />
        </div>
      </div>
    </div>
  );
}
