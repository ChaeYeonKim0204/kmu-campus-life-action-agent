export default function ToolLogPanel({ toolLogs }) {
  if (!toolLogs || toolLogs.length === 0) {
    return (
      <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.3)", textAlign: "center", padding: "8px 0" }}>
        Tool Calling 로그가 없습니다.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      {toolLogs.map((log, idx) => (
        <div key={idx} className="tool-log-entry">
          <span style={{ color: "var(--kmu-gold-light)", marginRight: "6px" }}>
            [{String(idx + 1).padStart(2, "0")}]
          </span>
          {typeof log === "string" ? log : JSON.stringify(log)}
        </div>
      ))}
    </div>
  );
}
