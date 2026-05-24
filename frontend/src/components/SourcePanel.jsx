export default function SourcePanel({ citations }) {
  return (
    <section className="panel shell">
      <h2>출처</h2>
      {citations.length === 0 && <p className="muted">답변의 [S1] 출처가 여기에 표시됩니다.</p>}
      {citations.map((source) => {
        const status = sourceStatus(source);
        return (
          <div className="item" key={source.id} id={`source-card-${source.id}`}>
            <div className="source-title-row">
              <div><span className="source-id">[{source.id}]</span> {source.title}</div>
              <span className={status.className}>{status.label}</span>
            </div>
            <div className="muted">
              Tier {source.source_tier} · {source.source_type} · {source.department || "담당 부서 미확인"}
              {source.published_at ? ` · ${source.published_at}` : ""}
            </div>
            {source.fetch_status && (
              <div className="muted compact">
                fetch: {source.fetch_status}{source.http_status ? ` · HTTP ${source.http_status}` : ""}
              </div>
            )}
            <p>{source.text}</p>
            <a href={source.url} target="_blank" rel="noreferrer">공식 문서 열기</a>
          </div>
        );
      })}
    </section>
  );
}

function sourceStatus(source) {
  if (source.fetched_from_network) return { label: "네트워크 확인", className: "badge ok" };
  if (source.used_fallback) return { label: "fallback", className: "badge warn" };
  return { label: "저장 근거", className: "badge" };
}
