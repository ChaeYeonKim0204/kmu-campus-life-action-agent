export default function ProcessingStatusPanel({ liveCheck, llm, answerValidation, outputPrivacy }) {
  const hasLiveCheck = Boolean(liveCheck);
  const hasLlm = Boolean(llm);
  const hasValidation = Boolean(answerValidation);
  const hasOutputPrivacy = Boolean(outputPrivacy);

  return (
    <section className="panel shell">
      <h2>처리 상태</h2>
      {!hasLiveCheck && !hasLlm && !hasValidation && !hasOutputPrivacy && <p className="muted">질문 후 최신 확인과 GPT 보조 상태가 표시됩니다.</p>}
      {hasValidation && (
        <div className="item">
          <div className="status-heading">
            <strong>답변 검증</strong>
            <span className={answerValidation.ok ? "badge ok" : "badge warn"}>
              {answerValidation.ok ? "통과" : "확인 필요"}
            </span>
          </div>
          <div className="mini-metrics">
            <span>markers {answerValidation.markers?.length || 0}</span>
            <span>citations {answerValidation.citation_ids?.length || 0}</span>
          </div>
          {(answerValidation.flags || []).map((flag) => (
            <p className="status compact" key={flag}>{flag}</p>
          ))}
        </div>
      )}
      {hasOutputPrivacy && (
        <div className="item">
          <div className="status-heading">
            <strong>민감정보 검사</strong>
            <span className={outputPrivacy.ok ? "badge ok" : "badge warn"}>
              {outputPrivacy.ok ? "통과" : "확인 필요"}
            </span>
          </div>
          {(outputPrivacy.flags || []).map((flag) => (
            <p className="status compact" key={flag}>{flag}</p>
          ))}
        </div>
      )}
      {hasLiveCheck && (
        <div className="item">
          <div className="status-heading">
            <strong>공식 사이트 최신 확인</strong>
            <span className={liveCheck.network_success > 0 ? "badge ok" : liveCheck.attempted ? "badge warn" : "badge"}>
              {liveCheck.attempted ? "실행" : "미실행"}
            </span>
          </div>
          <p className="muted">{liveCheck.message || liveCheck.reason || "요청된 경우 관련 공식 공개 소스만 확인합니다."}</p>
          <div className="mini-metrics">
            <span>성공 {liveCheck.network_success || 0}</span>
            <span>fallback {liveCheck.fallback_used || 0}</span>
            <span>실패 {liveCheck.network_failed || 0}</span>
          </div>
          {(liveCheck.selected_pages || []).slice(0, 3).map((page) => (
            <p className="muted compact" key={`${page.source}-${page.doc_id}`}>{page.title}</p>
          ))}
          {(liveCheck.failed_urls || []).slice(0, 2).map((failure) => (
            <p className="status compact" key={`${failure.doc_id}-${failure.status}`}>{failure.doc_id}: {failure.status}</p>
          ))}
        </div>
      )}
      {hasLlm && (
        <div className="item">
          <div className="status-heading">
            <strong>GPT 보조</strong>
            <span className={llm.enabled ? "badge ok" : "badge"}>{llm.enabled ? "ON" : "OFF"}</span>
          </div>
          <div className="mini-metrics">
            <span>검색어 {llm.query_expansion?.used ? "사용" : "기본"}</span>
            <span>재정렬 {llm.rerank?.used ? "사용" : "기본"}</span>
            <span>문장 polish {llm.polish?.used ? "사용" : "기본"}</span>
          </div>
          {llm.query_expansion?.keywords?.length > 0 && (
            <p className="muted compact">확장어: {llm.query_expansion.keywords.join(", ")}</p>
          )}
          {llm.rerank?.selected_chunk_ids?.length > 0 && (
            <p className="muted compact">선택 chunk: {llm.rerank.selected_chunk_ids.join(", ")}</p>
          )}
          {llm.polish?.rejected_reason && (
            <p className="status compact">polish fallback: {llm.polish.rejected_reason}</p>
          )}
        </div>
      )}
    </section>
  );
}
