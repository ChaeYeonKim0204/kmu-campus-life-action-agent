import React from "react";

export default function RPGMessageConsole({
  messages,
  loading,
  onAsk,
  examples,
  setQuestion,
  question,
  activeBuilding,
  onCitationClick,
  showConsole,
  privacyWarnings
}) {
  const listEndRef = React.useRef(null);
  const inputRef = React.useRef(null);

  React.useEffect(() => {
    if (listEndRef.current) {
      listEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading]);

  React.useEffect(() => {
    if (showConsole && inputRef.current) {
      const timer = setTimeout(() => {
        inputRef.current.focus();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [showConsole]);

  // Parse text to find citations like [S1], [S2] and make them clickable
  const renderMessageText = (text) => {
    const citationRegex = /\[S(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      const matchIndex = match.index;
      // Add plain text before match
      if (matchIndex > lastIndex) {
        parts.push(text.substring(lastIndex, matchIndex));
      }
      const citationId = match[1];
      parts.push(
        <span
          key={`cite-${matchIndex}`}
          className="rpg-citation-pill"
          onClick={(e) => {
            e.stopPropagation();
            onCitationClick(citationId);
          }}
          title="공식 학사 근거 규정 보기"
        >
          📜 근거 S{citationId}
        </span>
      );
      lastIndex = citationRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  const getSpeakerAvatar = (role, text) => {
    if (role === "user") return "🏃";
    
    // Pick avatar based on active building or keywords
    if (activeBuilding === "admin") return "👨‍💼";
    if (activeBuilding === "union") return "👩‍💼";
    if (activeBuilding === "library") return "🕵️‍♂️";
    if (activeBuilding === "ecampus") return "👩‍💻";
    
    if (text && text.includes("도서관")) return "🕵️‍♂️";
    if (text && text.includes("이캠")) return "👩‍💻";
    
    return "🦆"; // Mascot '국민이'
  };

  const getSpeakerName = (role, text) => {
    if (role === "user") return "나 (학생)";
    
    if (activeBuilding === "admin") return "본부관 조교";
    if (activeBuilding === "union") return "종합민원실 주임";
    if (activeBuilding === "library") return "도서관 사서";
    if (activeBuilding === "ecampus") return "이캠퍼스 지원팀";
    
    if (text && text.includes("도서관")) return "도서관 사서";
    if (text && text.includes("이캠")) return "이캠퍼스 지원팀";
    
    return "국민이 (AI 도우미)";
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    onAsk(question);
    setQuestion("");
  };

  return (
    <div className="rpg-console-wrapper">
      {/* Dialogue scroll area */}
      <div className="rpg-dialogue-screen">
        {messages.length === 0 ? (
          <div className="rpg-welcome-bubble">
            <div className="avatar-anim">🦆</div>
            <div className="bubble-text">
              <h5>국민이와 함께하는 캠퍼스 라이프!</h5>
              <p>
                지도의 건물을 클릭해 해당 구역 조교에게 말을 걸거나 아래 추천 질문을 클릭해 대화를 시작해보세요.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === "user";
            const avatar = getSpeakerAvatar(msg.role, msg.text);
            const name = getSpeakerName(msg.role, msg.text);

            return (
              <div key={index} className={`rpg-speech-row ${isUser ? "user-row" : "npc-row"}`}>
                <div className="rpg-profile">
                  <div className="rpg-profile-img">{avatar}</div>
                  <span className="rpg-profile-name">{name}</span>
                </div>
                <div className="rpg-speech-bubble">
                  <div className="rpg-speech-text">
                    {renderMessageText(msg.text)}
                    {!isUser && index === messages.length - 1 && !loading && (
                      <span className="rpg-cursor">▮</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
        {loading && (
          <div className="rpg-speech-row npc-row">
            <div className="rpg-profile">
              <div className="rpg-profile-img loading-spin">🦆</div>
              <span className="rpg-profile-name">조회 중...</span>
            </div>
            <div className="rpg-speech-bubble loading-bubble">
              <div className="rpg-loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={listEndRef} />
      </div>

      {/* Suggested Fast Questions */}
      <div className="rpg-fast-questions">
        {examples.slice(0, 5).map((ex, idx) => (
          <button
            key={idx}
            className="rpg-fast-btn"
            onClick={() => {
              setQuestion(ex);
              onAsk(ex);
            }}
            disabled={loading}
          >
            🎯 {ex}
          </button>
        ))}
      </div>

      {/* RPG Dialog Composer input */}
      <form onSubmit={handleSubmit} className="rpg-dialog-composer">
        <input
          ref={inputRef}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="에이전트나 NPC에게 하고 싶은 질문을 입력하세요..."
          disabled={loading}
          className="rpg-input"
        />
        <button type="submit" disabled={loading || !question.trim()} className="primary rpg-send-btn">
          대화하기 💬
        </button>
      </form>
      {privacyWarnings && privacyWarnings.length > 0 && (
        <div className="privacy-warn-text" style={{ margin: "8px 12px 0 12px" }}>
          ⚠️ {privacyWarnings.join(", ")} 감지됨. 실제 개인정보 값은 빼고 상황만 요약해 주세요.
        </div>
      )}
    </div>
  );
}
