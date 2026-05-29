export default function ChatPanel({
  examples,
  question,
  setQuestion,
  studentStatuses,
  studentContext,
  setStudentContext,
  liveCheck,
  setLiveCheck,
  llmAssist,
  setLlmAssist,
  liveCheckStatus,
  messages,
  loading,
  onAsk,
  onCitationClick
}) {
  function updateContext(key, value) {
    setStudentContext((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="chat shell">
      <div className="student-context">
        <div className="context-row">
          <span className="context-label">학생 상태</span>
          <div className="segmented" role="group" aria-label="학생 상태">
            {studentStatuses.map((status) => (
              <button
                key={status.value || "default"}
                type="button"
                className={studentContext.status === status.value ? "selected" : ""}
                onClick={() => updateContext("status", status.value)}
              >
                {status.label}
              </button>
            ))}
          </div>
        </div>
        <div className="context-fields">
          <label>
            대상 학기
            <input
              value={studentContext.term}
              onChange={(event) => updateContext("term", event.target.value)}
              placeholder="예: 2026-2학기"
            />
          </label>
          <label>
            관심 항목
            <input
              value={studentContext.concern}
              onChange={(event) => updateContext("concern", event.target.value)}
              placeholder="예: 수강신청, 장학, 졸업"
            />
          </label>
        </div>
        <div className="context-row live-check-row">
          <div className="check-group">
            <label className="check-field">
              <input type="checkbox" checked={liveCheck} onChange={(event) => setLiveCheck(event.target.checked)} />
              <span>공식 사이트 최신 확인</span>
            </label>
            <label className="check-field">
              <input type="checkbox" checked={llmAssist} onChange={(event) => setLlmAssist(event.target.checked)} />
              <span>GPT 보조</span>
            </label>
          </div>
          {liveCheckStatus && (
            <span className={liveCheckStatus.network_success > 0 ? "live-status ok" : "live-status"}>
              {formatLiveCheckStatus(liveCheckStatus)}
            </span>
          )}
        </div>
      </div>
      <div className="examples">
        {examples.map((item) => (
          <button key={item} type="button" onClick={() => { setQuestion(item); onAsk(item); }}>
            {item}
          </button>
        ))}
      </div>
      <div className="messages">
        {messages.length === 0 && <div className="message agent muted">예시 질문을 누르거나 직접 질문을 입력하세요.</div>}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`message ${message.role}`}>
            {renderMessageText(message.text, onCitationClick)}
          </div>
        ))}
      </div>
      <div className="composer">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button className="primary" type="button" disabled={loading} onClick={() => onAsk()}>
          {loading ? "처리 중" : "질문"}
        </button>
      </div>
    </section>
  );
}

function formatLiveCheckStatus(status) {
  if (!status.requested && !status.attempted) return "";
  if (status.attempted) {
    if (status.network_success > 0) return `최신 확인 완료 · ${status.network_success}건 반영`;
    if (status.fallback_used > 0 || status.network_failed > 0) return "최신 확인 실패 · 기존 근거 사용";
    return "최신 확인 완료 · 변경 없음";
  }
  if (status.cooldown_remaining_seconds > 0) return `최근 확인됨 · ${status.cooldown_remaining_seconds}초 후 재확인`;
  return "기존 근거 사용";
}

function renderMessageText(text, onCitationClick) {
  if (!text) return "";
  const parts = text.split(/(\[S\d+\])/g);
  return parts.map((part, index) => {
    const match = part.match(/^\[S(\d+)\]$/);
    if (match) {
      const citationId = parseInt(match[1], 10);
      return (
        <span
          key={index}
          className="citation-link"
          style={{
            cursor: "pointer",
            textDecoration: "underline",
            color: "var(--blue-hover)",
            fontWeight: "bold",
            margin: "0 2px",
            padding: "1px 4px",
            borderRadius: "4px",
            background: "rgba(59, 130, 246, 0.15)"
          }}
          onClick={() => onCitationClick(citationId)}
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

