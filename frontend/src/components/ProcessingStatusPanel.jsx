export default function ProcessingStatusPanel({ liveCheckStatus, llmStatus, answerValidation, outputPrivacy }) {
  const hasAny = Boolean(liveCheckStatus || llmStatus || answerValidation || outputPrivacy);

  if (!hasAny) {
    return (
      <div className="processing-status-panel">
        <p style={{ fontSize: "11.5px", color: "rgba(255,255,255,0.35)", textAlign: "center", padding: "12px 0" }}>
          질문 후 처리 상태가 여기에 표시됩니다.
        </p>
      </div>
    );
  }

  return (
    <div className="processing-status-panel">
      {answerValidation && (
        <div className="status-badge-row">
          <span className={`status-badge ${answerValidation.ok ? "ok" : "pending"}`}>
            {answerValidation.ok ? "✓" : "⚠"} 답변 검증 {answerValidation.ok ? "통과" : "확인 필요"}
          </span>
          {(answerValidation.markers?.length || 0) > 0 && (
            <span className="status-badge off">마커 {answerValidation.markers.length}개</span>
          )}
        </div>
      )}

      {outputPrivacy && (
        <div className="status-badge-row">
          <span className={`status-badge ${outputPrivacy.ok ? "ok" : "pending"}`}>
            {outputPrivacy.ok ? "🔒 민감정보 안전" : "⚠ 민감정보 확인 필요"}
          </span>
        </div>
      )}

      {liveCheckStatus && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div className="status-badge-row">
            <span className={`status-badge ${liveCheckStatus.network_success > 0 ? "ok" : liveCheckStatus.attempted ? "pending" : "off"}`}>
              🌐 최신 확인 {liveCheckStatus.attempted ? "실행" : "미실행"}
            </span>
            {liveCheckStatus.attempted && (
              <span className="status-badge off">
                성공 {liveCheckStatus.network_success || 0} / 실패 {liveCheckStatus.network_failed || 0}
              </span>
            )}
          </div>
          {liveCheckStatus.message && (
            <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.45)", marginLeft: "2px", lineHeight: "1.4" }}>
              {liveCheckStatus.message}
            </p>
          )}
        </div>
      )}

      {llmStatus && (
        <div className="status-badge-row">
          <span className={`status-badge ${llmStatus.enabled ? "ok" : "off"}`}>
            🤖 GPT 보조 {llmStatus.enabled ? "ON" : "OFF"}
          </span>
          {llmStatus.query_expansion?.used && (
            <span className="status-badge off">검색어 확장</span>
          )}
          {llmStatus.rerank?.used && (
            <span className="status-badge off">재정렬</span>
          )}
          {llmStatus.polish?.used && (
            <span className="status-badge off">Polish</span>
          )}
        </div>
      )}
    </div>
  );
}
