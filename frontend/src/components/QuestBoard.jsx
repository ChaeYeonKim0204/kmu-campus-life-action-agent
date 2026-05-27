import React from "react";
import { BUILDINGS } from "./CampusMap.jsx";

const STATUS_LABELS = {
  "": "기본",
  "new_student": "신입생",
  "enrolled": "재학생",
  "returning": "복학생",
  "leave": "휴학생",
  "graduating": "졸업예정"
};

export default function QuestBoard({
  level,
  xp,
  quests,
  activeBuilding,
  onStartAction,
  onSelectBuilding,
  onSendChatMessage,
  onOpenEncyclopedia,
  onOpenActionForm,
  studentContext,
  onOpenProfile
}) {
  const selectedBuildingData = activeBuilding ? BUILDINGS[activeBuilding] : null;

  // Calculate XP percentage (assuming 100 XP per level)
  const xpPercentage = Math.min((xp % 100), 100);

  const getQuestForBuilding = (buildingId) => {
    const b = BUILDINGS[buildingId];
    if (!b || !b.questId) return null;
    return quests.find(q => q.id === b.questId);
  };

  const handleQuestAction = (quest) => {
    if (quest.actionId) {
      onStartAction(quest.actionId);
    } else if (quest.triggerMsg) {
      onSendChatMessage(quest.triggerMsg);
    }
  };

  return (
    <div className="quest-board-container">
      {/* Level & XP HUD */}
      <div className="quest-hud">
        <div className="hud-level">
          <div className="level-badge">LV.{level}</div>
          <div className="level-name">
            {level === 1 && "🎓 아기오리 신입생"}
            {level === 2 && "📖 배움에 눈뜬 재학생"}
            {level === 3 && "⚡ 학사 행정 마스터"}
            {level > 3 && "👑 졸업 준비 왕선배"}
          </div>
        </div>
        <div className="hud-xp-bar">
          <div className="xp-label">XP: {xp % 100} / 100</div>
          <div className="xp-track">
            <div className="xp-fill" style={{ width: `${xpPercentage}%` }}></div>
          </div>
        </div>

        {/* HUD Student Profile Card */}
        {studentContext && (
          <div className="hud-profile-card" onClick={onOpenProfile} title="학적 카드 수정하기">
            <div className="hud-profile-avatar">🎒</div>
            <div className="hud-profile-info">
              <div className="hud-profile-status">
                학적: <span className="highlight-text">{STATUS_LABELS[studentContext.status] || "미설정"}</span>
              </div>
              <div className="hud-profile-term">
                학기: <span className="highlight-text">{studentContext.term || "미설정"}</span>
              </div>
              {studentContext.concern && (
                <div className="hud-profile-concern">
                  관심: <span className="highlight-text">{studentContext.concern}</span>
                </div>
              )}
            </div>
            <div className="hud-profile-edit-indicator">⚙️</div>
          </div>
        )}

        <div style={{ marginTop: "12px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          <button
            type="button"
            className="action"
            onClick={onOpenEncyclopedia}
            style={{ padding: "9px 6px", fontSize: "11.5px", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}
          >
            📚 규정 대백과
          </button>
          <button
            type="button"
            className="primary"
            onClick={onOpenActionForm}
            style={{ padding: "9px 6px", fontSize: "11.5px", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}
          >
            📂 서류 가방
          </button>
        </div>
      </div>

      {/* Quest Checklist */}
      <div className="quest-checklist-section">
        <h4>📋 나의 학사 퀘스트 보드</h4>
        <div className="quest-list">
          {quests.map((q) => (
            <div
              key={q.id}
              className={`quest-item-card ${q.status} ${
                selectedBuildingData && selectedBuildingData.questId === q.id ? "focused" : ""
              }`}
              onClick={() => {
                // Find building associated with quest and select it
                const bId = Object.keys(BUILDINGS).find(k => BUILDINGS[k].questId === q.id);
                if (bId) onSelectBuilding(bId);
              }}
            >
              <div className="quest-icon">
                {q.status === "completed" && "✅"}
                {q.status === "active" && "🔥"}
                {q.status === "locked" && "🔒"}
              </div>
              <div className="quest-details">
                <span className="quest-title">{q.title}</span>
                <span className="quest-subtext">{q.desc}</span>
              </div>
              <div className="quest-reward">
                {q.status === "completed" ? (
                  <span className="reward-done">완료됨</span>
                ) : (
                  <span className="reward-xp">+{q.rewardXp} XP</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* NPC Interactive Dialog Box */}
      <div className="npc-dialog-box">
        {selectedBuildingData ? (
          <>
            <div className="npc-header">
              <div className="npc-avatar">
                {activeBuilding === "admin" && "👨‍💼"}
                {activeBuilding === "union" && "👩‍💼"}
                {activeBuilding === "library" && "🕵️‍♂️"}
                {activeBuilding === "ecampus" && "👩‍💻"}
                {activeBuilding === "bugak" && "👨‍🏫"}
                {activeBuilding === "engineering" && "🧑‍🔬"}
              </div>
              <div className="npc-info">
                <h5>{selectedBuildingData.npc}</h5>
                <span className="npc-location">소속: {selectedBuildingData.name}</span>
              </div>
            </div>

            <div className="npc-speech">
              {activeBuilding === "admin" && (
                <p>
                  "안녕하세요! 본부관 학사지원팀에 오신 것을 환영해요. 공결이나 질병으로 결석 시 필요한 <b>출석인정신청서</b> 작성을 도와드릴게요. 아래 버튼을 눌러 양식을 기입해 보세요."
                </p>
              )}
              {activeBuilding === "union" && (
                <p>
                  "안녕하세요! 종합민원실입니다. 휴학 신청이나 복학 일정 때문에 고민이 많으시죠? 복잡한 서류 절차와 체크리스트를 한번에 정리해 드릴게요. 퀘스트를 진행해 보세요!"
                </p>
              )}
              {activeBuilding === "library" && (
                <p>
                  "반갑습니다. 성곡도서관 사서입니다. 모바일 학생증 태그 인식이 실패해서 오셨군요? 에이전트에게 <b>'모바일 학생증 안 찍힘'</b>을 물어보시면 해결 가이드를 알려드릴게요!"
                </p>
              )}
              {activeBuilding === "ecampus" && (
                <p>
                  "환영합니다! E-Campus 정보기술처 지원팀입니다. 강의실 목록이 누락되었나요? <b>'이캠에 강의가 안 떠요'</b>를 질의하시면 실시간 DB를 확인해 연동 퀘스트를 처리해 드려요."
                </p>
              )}
              {activeBuilding === "bugak" && (
                <p>
                  "안녕! 교양 강의실이 모여있는 북악관이야. 학기 일정이나 학기 중 휴학 제한 등에 관한 행정 규정집 검색을 도와줄게. 무엇이든 채팅창에 질문해봐!"
                </p>
              )}
              {activeBuilding === "engineering" && (
                <p>
                  "안녕하세요! 졸업 준비 중이라면 성적증명서 기반 졸업 센터에서 부족 학점, 대체 이수, 마이크로디그리, 직무 역량까지 한 번에 점검해 보세요."
                </p>
              )}
            </div>

            <div className="npc-actions">
              {(() => {
                const q = getQuestForBuilding(activeBuilding);
                if (q && q.status === "active") {
                  return (
                    <button
                      className="primary wide quest-accept-btn"
                      onClick={() => handleQuestAction(q)}
                    >
                      ⚡ 퀘스트 수락 및 서류 작성 시작
                    </button>
                  );
                } else if (q && q.status === "completed") {
                  return (
                    <div className="quest-completed-badge">
                      🏆 이 건물에서의 퀘스트를 완료했습니다!
                    </div>
                  );
                } else {
                  return (
                    <button
                      className="quest-accept-btn wide"
                      onClick={() => {
                        // Send simple greeting or trigger dialogue
                        onSendChatMessage(`${selectedBuildingData.name} ${selectedBuildingData.npc}에 대해 안내해줘.`);
                      }}
                    >
                      💬 상담원에게 기본 규정 질문하기
                    </button>
                  );
                }
              })()}
            </div>
          </>
        ) : (
          <div className="npc-placeholder">
            <div className="companion-avatar-large">🦆</div>
            <h5>AI 마스코트 '국민이'</h5>
            <p>
              "반가워요! 국민대학교 캠퍼스 맵의 건물을 눌러 다른 NPC를 만나보세요. 퀘스트 보드에 등록된 미션을 완료하면 경험치를 획득해 레벨업을 할 수 있답니다!"
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
