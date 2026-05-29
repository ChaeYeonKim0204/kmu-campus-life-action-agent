export default function SourcePanel({ citations }) {
  if (citations.length === 0) {
    return (
      <div className="source-panel-container">
        <div className="source-empty">
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>📚</div>
          <p>답변의 <strong style={{ color: "var(--kmu-gold-light)" }}>[S1]</strong> 근거를 클릭하면<br />공식 출처가 여기에 표시됩니다.</p>
          <p style={{ marginTop: "8px", fontSize: "11px", color: "rgba(255,255,255,0.25)" }}>질문 후 citation이 있는 답변을 받아보세요.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="source-panel-container">
      {citations.map((source) => {
        const status = sourceStatus(source);
        return (
          <div className="source-card" key={source.id} id={`source-card-${source.id}`}>
            <div className="source-title-row">
              <div style={{ display: "flex", alignItems: "flex-start", gap: "6px", flex: 1, minWidth: 0 }}>
                <span className="source-id">[S{source.id}]</span>
                <span className="source-title-text">{source.title}</span>
              </div>
              <span className={`badge ${status.className}`}>{status.label}</span>
            </div>

            <div className="source-meta">
              Tier {source.source_tier} · {source.source_type} ·{" "}
              {source.department || "담당 부서 미확인"}
              {source.published_at ? ` · ${source.published_at}` : ""}
              {source.fetch_status ? ` · fetch: ${source.fetch_status}` : ""}
            </div>

            {source.text && (
              <p className="source-excerpt">{source.text}</p>
            )}

            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="source-link"
              >
                🔗 공식 문서 열기
              </a>
            )}
          </div>
        );
      })}
    </div>
  );
}

function sourceStatus(source) {
  if (source.fetched_from_network) return { label: "네트워크 확인", className: "ok" };
  if (source.used_fallback) return { label: "fallback", className: "warn" };
  return { label: "저장 근거", className: "" };
}
