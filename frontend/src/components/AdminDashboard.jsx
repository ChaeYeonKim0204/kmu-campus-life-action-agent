import React from "react";

export default function AdminDashboard({ apiBase }) {
  const [health, setHealth] = React.useState(null);
  const [ingest, setIngest] = React.useState(null);
  const [running, setRunning] = React.useState(false);
  const [liveIssue, setLiveIssue] = React.useState("course_registration");
  const [liveRefresh, setLiveRefresh] = React.useState(null);
  const [liveRunning, setLiveRunning] = React.useState(false);

  async function loadHealth() {
    try {
      const response = await fetch(`${apiBase}/health`);
      setHealth(await response.json());
    } catch {
      setHealth({ error: "서버 연결 실패" });
    }
  }

  async function runIngest() {
    setRunning(true);
    try {
      const response = await fetch(`${apiBase}/ingest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "all", limit: 20, force_rebuild: false }),
      });
      const data = await response.json();
      setIngest(data);
      await loadHealth();
    } finally {
      setRunning(false);
    }
  }

  async function runLiveRefresh() {
    setLiveRunning(true);
    try {
      const response = await fetch(`${apiBase}/ingest/live-refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue_type: liveIssue, query: liveIssue, max_pages: 3 }),
      });
      const data = await response.json();
      setLiveRefresh(data);
      await loadHealth();
    } finally {
      setLiveRunning(false);
    }
  }

  React.useEffect(() => { loadHealth(); }, []);

  return (
    <div className="admin-dashboard">
      {/* 헬스 체크 */}
      <div className="admin-section">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
          <h4 style={{ margin: 0 }}>🩺 서버 상태</h4>
          <button type="button" className="secondary" style={{ padding: "4px 12px", fontSize: "11px" }} onClick={loadHealth}>
            새로고침
          </button>
        </div>

        {!health && (
          <p style={{ fontSize: "11.5px", color: "rgba(255,255,255,0.35)" }}>상태를 불러오는 중...</p>
        )}

        {health?.error && (
          <div className="status-badge-row">
            <span className="status-badge pending">⚠ {health.error}</span>
          </div>
        )}

        {health && !health.error && (
          <div className="health-grid">
            <div className="health-item">
              <span className="health-key">JSONL 청크</span>
              <span className="health-value">{health.keyword_chunks ?? "—"}</span>
            </div>
            <div className="health-item">
              <span className="health-key">Chroma</span>
              <span className="health-value" style={{ color: health.vector_retriever_available ? "#6EE7B7" : "#FCA5A5" }}>
                {health.vector_retriever_available ? "ON" : "OFF"}
              </span>
            </div>
            <div className="health-item">
              <span className="health-key">Vector 문서</span>
              <span className="health-value">{health.vector_indexed_count ?? "—"}</span>
            </div>
            <div className="health-item">
              <span className="health-key">GPT Assist</span>
              <span className="health-value" style={{ color: health.llm?.enabled ? "#6EE7B7" : "#94A3B8" }}>
                {health.llm?.enabled ? "ON" : "OFF"}
              </span>
            </div>
            <div className="health-item">
              <span className="health-key">API Key</span>
              <span className="health-value" style={{ color: health.llm?.api_key_configured ? "#6EE7B7" : "#FCA5A5" }}>
                {health.llm?.api_key_configured ? "OK" : "NO"}
              </span>
            </div>
            <div className="health-item">
              <span className="health-key">Polish</span>
              <span className="health-value" style={{ color: health.llm?.polish_enabled ? "#6EE7B7" : "#94A3B8" }}>
                {health.llm?.polish_enabled ? "ON" : "OFF"}
              </span>
            </div>
          </div>
        )}

        {health?.vector_error && (
          <p style={{ fontSize: "10.5px", color: "#FCA5A5", marginTop: "8px" }}>Vector: {health.vector_error}</p>
        )}
        {health?.llm?.error && (
          <p style={{ fontSize: "10.5px", color: "#FCA5A5", marginTop: "4px" }}>GPT: {health.llm.error}</p>
        )}
      </div>

      {/* 데이터 수집 */}
      <div className="admin-section">
        <h4>📥 공식자료 수집 / 인덱싱</h4>
        <button
          type="button"
          className="primary wide"
          disabled={running}
          onClick={runIngest}
          style={{ width: "100%", padding: "10px" }}
        >
          {running ? "⏳ 수집 중..." : "공식자료 수집 / 인덱싱 실행"}
        </button>
        {ingest && (
          <div style={{ marginTop: "10px", fontSize: "11.5px", color: "rgba(255,255,255,0.65)", lineHeight: "1.7" }}>
            <strong style={{ color: "var(--kmu-gold-light)" }}>{ingest.status}</strong>
            <br />{ingest.message}
            <br />문서 {ingest.documents_seen} · 신규 {ingest.new_documents} · 변경 {ingest.changed_documents}
            <br />청크 {ingest.chunks_written} · Vector {ingest.vector_indexed}
            {(ingest.failures || []).map((f) => (
              <p key={`${f.source}-${f.error}`} style={{ color: "#FCA5A5", fontSize: "10.5px", marginTop: "4px" }}>
                ⚠ {f.source}: {f.error}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* 이슈별 최신 확인 */}
      <div className="admin-section">
        <h4>🌐 이슈별 최신 확인</h4>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <select
            value={liveIssue}
            onChange={(e) => setLiveIssue(e.target.value)}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: "var(--radius-md)",
              padding: "8px 10px",
              color: "#fff",
              fontSize: "12px",
              width: "100%",
            }}
          >
            <option value="attendance">출석</option>
            <option value="leave_return">휴학 / 복학</option>
            <option value="course_registration">수강신청</option>
            <option value="registration_tuition">등록금</option>
            <option value="certificate">증명서</option>
            <option value="scholarship">장학</option>
            <option value="portal_access">포털 / eCampus</option>
            <option value="schedule">학사일정</option>
            <option value="graduation">졸업</option>
          </select>
          <button
            type="button"
            className="secondary"
            style={{ width: "100%", padding: "9px" }}
            disabled={liveRunning}
            onClick={runLiveRefresh}
          >
            {liveRunning ? "⏳ 확인 중..." : "선택 이슈 최신 확인"}
          </button>
          {liveRefresh && (
            <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)", lineHeight: "1.7" }}>
              <strong style={{ color: "var(--kmu-gold-light)" }}>{liveRefresh.status}</strong>
              <br />{liveRefresh.message}
              <br />이슈: {liveRefresh.issue_type} · 문서 {liveRefresh.documents_seen} ·
              갱신 {liveRefresh.updated_documents} · 성공 {liveRefresh.network_success} · 실패 {liveRefresh.network_failed}
            </div>
          )}
        </div>
      </div>

      {/* 최근 실시간 확인 */}
      {health?.live_refresh?.latest && (
        <div className="admin-section">
          <h4>📌 최근 실시간 확인</h4>
          <div style={{ fontSize: "11.5px", color: "rgba(255,255,255,0.7)", lineHeight: "1.6" }}>
            <strong style={{ color: "var(--kmu-gold-light)" }}>{health.live_refresh.latest.issue_type}</strong>
            <br />{health.live_refresh.latest.completed_at}
            <br />성공 {health.live_refresh.latest.network_success || 0} ·
            fallback {health.live_refresh.latest.fallback_used || 0} ·
            실패 {health.live_refresh.latest.network_failed || 0}
          </div>
        </div>
      )}
    </div>
  );
}
