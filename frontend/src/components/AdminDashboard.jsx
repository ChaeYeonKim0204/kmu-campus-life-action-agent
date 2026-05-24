import React from "react";

export default function AdminDashboard({ apiBase }) {
  const [health, setHealth] = React.useState(null);
  const [ingest, setIngest] = React.useState(null);
  const [running, setRunning] = React.useState(false);
  const [liveIssue, setLiveIssue] = React.useState("course_registration");
  const [liveRefresh, setLiveRefresh] = React.useState(null);
  const [liveRunning, setLiveRunning] = React.useState(false);

  async function loadHealth() {
    const response = await fetch(`${apiBase}/health`);
    setHealth(await response.json());
  }

  async function runIngest() {
    setRunning(true);
    try {
      const response = await fetch(`${apiBase}/ingest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "all", limit: 20, force_rebuild: false })
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
        body: JSON.stringify({ issue_type: liveIssue, query: liveIssue, max_pages: 3 })
      });
      const data = await response.json();
      setLiveRefresh(data);
      await loadHealth();
    } finally {
      setLiveRunning(false);
    }
  }

  React.useEffect(() => {
    loadHealth();
  }, []);

  return (
    <section className="panel shell">
      <div className="panel-title">
        <h2>관리자</h2>
        <button type="button" onClick={loadHealth}>새로고침</button>
      </div>
      {!health && <p className="muted">상태를 불러오는 중입니다.</p>}
      {health && (
        <div className="metrics">
          <div><strong>{health.keyword_chunks}</strong><span>JSONL chunks</span></div>
          <div><strong>{health.vector_retriever_available ? "ON" : "OFF"}</strong><span>Chroma</span></div>
          <div><strong>{health.vector_indexed_count}</strong><span>Vector docs</span></div>
          <div><strong>{health.llm?.enabled ? "ON" : "OFF"}</strong><span>GPT assist</span></div>
          <div><strong>{health.llm?.api_key_configured ? "OK" : "NO"}</strong><span>API key</span></div>
          <div><strong>{health.llm?.polish_enabled ? "ON" : "OFF"}</strong><span>Polish</span></div>
        </div>
      )}
      {health?.vector_error && <p className="status">Vector 상태: {health.vector_error}</p>}
      {health?.llm?.error && <p className="status">GPT 상태: {health.llm.error}</p>}
      {health?.live_refresh?.latest && (
        <div className="item">
          <strong>최근 실시간 확인: {health.live_refresh.latest.issue_type}</strong>
          <p className="muted compact">{health.live_refresh.latest.completed_at}</p>
          <div className="mini-metrics">
            <span>성공 {health.live_refresh.latest.network_success || 0}</span>
            <span>fallback {health.live_refresh.latest.fallback_used || 0}</span>
            <span>실패 {health.live_refresh.latest.network_failed || 0}</span>
          </div>
        </div>
      )}
      <button className="primary wide" type="button" disabled={running} onClick={runIngest}>
        {running ? "수집 중" : "공식자료 수집/인덱싱 실행"}
      </button>
      <div className="admin-live-refresh">
        <label>
          이슈별 최신 확인
          <select value={liveIssue} onChange={(event) => setLiveIssue(event.target.value)}>
            <option value="attendance">출석</option>
            <option value="leave_return">휴학/복학</option>
            <option value="course_registration">수강신청</option>
            <option value="registration_tuition">등록금</option>
            <option value="certificate">증명서</option>
            <option value="scholarship">장학</option>
            <option value="portal_access">포털/eCampus</option>
            <option value="schedule">학사일정</option>
            <option value="graduation">졸업</option>
          </select>
        </label>
        <button className="wide" type="button" disabled={liveRunning} onClick={runLiveRefresh}>
          {liveRunning ? "확인 중" : "선택 이슈 최신 확인"}
        </button>
      </div>
      {liveRefresh && (
        <div className="item">
          <strong>{liveRefresh.status}</strong>
          <p>{liveRefresh.message}</p>
          <p className="muted">
            이슈 {liveRefresh.issue_type} · 문서 {liveRefresh.documents_seen} · 갱신 {liveRefresh.updated_documents} ·
            성공 {liveRefresh.network_success} · fallback {liveRefresh.fallback_used} · 실패 {liveRefresh.network_failed}
          </p>
        </div>
      )}
      {ingest && (
        <div className="item">
          <strong>{ingest.status}</strong>
          <p>{ingest.message}</p>
          <p className="muted">
            문서 {ingest.documents_seen} · 신규 {ingest.new_documents} · 변경 {ingest.changed_documents} ·
            chunks {ingest.chunks_written} · vector {ingest.vector_indexed}
          </p>
          {(ingest.failures || []).map((failure) => (
            <p className="status" key={`${failure.source}-${failure.error}`}>{failure.source}: {failure.error}</p>
          ))}
        </div>
      )}
    </section>
  );
}
