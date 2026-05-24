import React from "react";
import { createRoot } from "react-dom/client";
import ActionForm from "./components/ActionForm.jsx";
import AdminDashboard from "./components/AdminDashboard.jsx";
import ProcessingStatusPanel from "./components/ProcessingStatusPanel.jsx";
import SourcePanel from "./components/SourcePanel.jsx";
import ToolLogPanel from "./components/ToolLogPanel.jsx";
import CampusMap, { BUILDINGS } from "./components/CampusMap.jsx";
import GraduationCenter from "./components/GraduationCenter.jsx";
import QuestBoard from "./components/QuestBoard.jsx";
import RPGMessageConsole from "./components/RPGMessageConsole.jsx";
import "./styles.css";

const API_BASE = window.location.port === "5173" ? "http://127.0.0.1:8001" : window.location.origin;

const examples = [
  "이캠에 강의가 안 떠요",
  "등록금 냈는데 납부확인이 안 떠",
  "수변 기간 언제야?",
  "모바일 학생증 안 찍힘",
  "국장 들어왔는지 어디서 봐?",
  "복학생인데 이번 주 뭐 해야 해?",
  "내 학번이랑 성적으로 처리해줘."
];

const studentStatuses = [
  { value: "", label: "기본" },
  { value: "new_student", label: "신입생" },
  { value: "enrolled", label: "재학생" },
  { value: "returning", label: "복학생" },
  { value: "leave", label: "휴학생" },
  { value: "graduating", label: "졸업예정" }
];

const BUILDING_EXAMPLES = {
  admin: [
    "공결 신청 절차가 어떻게 돼?",
    "예비군 훈련 공결 인정 서류는?",
    "상해/질병 결석도 공결이 되나요?",
    "공결계 제출은 며칠 이내 해야 해?"
  ],
  union: [
    "일반휴학 신청 일정은?",
    "군휴학 신청 시 준비물은?",
    "질병휴학 연장하려면?",
    "복학 신청하고 나서 해야할 일?"
  ],
  library: [
    "모바일 학생증 안 찍힘",
    "실물 학생증 재발급 신청은?",
    "도서관 좌석 예약 오류나",
    "도서 연체 연체료 규정이 뭐야?"
  ],
  ecampus: [
    "이캠에 강의가 안 떠요",
    "이캠퍼스 아이디/비밀번호 변경",
    "이캠퍼스 모바일 앱 연동 오류",
    "비대면 줌 강의 연동 실패"
  ],
  bugak: [
    "수변 기간 언제야?",
    "성적 장학금 전액 기준은?",
    "졸업예정증명서 어디서 떼?",
    "학기 도중에 휴학할 수 있어?"
  ],
  engineering: [
    "소프트웨어학부 행정실 위치",
    "실습실 IT 장비 반납 규정",
    "졸업 요건 학점이 궁금해",
    "폐강 기준 인원이 몇 명이야?"
  ]
};

const DEFAULT_QUESTS = [
  {
    id: "quest_attendance",
    title: "공결 신청서 작성",
    desc: "본부관 학사지원팀 조교를 만나 출석인정신청서 작성 완료하기",
    status: "active",
    actionId: "draft_attendance_recognition_form",
    rewardXp: 40
  },
  {
    id: "quest_leave_absence",
    title: "휴학/복학 신청 마스터",
    desc: "복지관 종합민원실 주임을 만나 휴학/복학 체크리스트 및 서류 준비하기",
    status: "active",
    actionId: "draft_leave_checklist",
    rewardXp: 40
  },
  {
    id: "quest_library_id",
    title: "도서관 학생증 오류 해결",
    desc: "성곡도서관 사서를 방문하여 학생증 비활성화 에러 팁 확인하기",
    status: "active",
    triggerMsg: "모바일 학생증 안 찍힘",
    rewardXp: 20
  },
  {
    id: "quest_ecampus_sync",
    title: "E-Campus 클래스룸 동기화",
    desc: "이캠퍼스 센터 헬프데스크를 방문해 수강 목록 누락 해결하기",
    status: "active",
    triggerMsg: "이캠에 강의가 안 떠요",
    rewardXp: 20
  },
  {
    id: "quest_graduation_center",
    title: "졸업 센터 종합 진단",
    desc: "공학관 행정직원을 만나 성적증명서 기반 졸업/진로 분석 시작하기",
    status: "active",
    actionId: "graduation_audit",
    rewardXp: 60
  }
];

// Cute custom SVG mascot character
function MascotSVG() {
  return (
    <svg viewBox="0 0 100 120" width="100%" height="100%">
      {/* Shadow */}
      <ellipse cx="50" cy="110" rx="25" ry="6" fill="rgba(0,0,0,0.15)" />
      
      {/* Body */}
      <rect x="35" y="65" width="30" height="35" rx="15" fill="#0f3d7a" />
      <rect x="42" y="65" width="16" height="30" rx="8" fill="#ffffff" opacity="0.8" />
      
      {/* Arms */}
      <path d="M 32,75 Q 22,80 30,88" fill="none" stroke="#0f3d7a" strokeWidth="6" strokeLinecap="round" />
      <path d="M 68,75 Q 78,80 70,88" fill="none" stroke="#0f3d7a" strokeWidth="6" strokeLinecap="round" />

      {/* Scarf */}
      <rect x="38" y="60" width="24" height="6" rx="3" fill="#f59e0b" />
      <path d="M 58,63 L 64,80" stroke="#f59e0b" strokeWidth="5" strokeLinecap="round" />

      {/* Head */}
      <circle cx="50" cy="42" r="26" fill="#ffffff" stroke="#0f3d7a" strokeWidth="3.5" />
      
      {/* Eyes */}
      <circle cx="41" cy="40" r="4" fill="#0f172a" />
      <circle cx="59" cy="40" r="4" fill="#0f172a" />
      {/* Eye shines */}
      <circle cx="39.5" cy="38.5" r="1.2" fill="#ffffff" />
      <circle cx="57.5" cy="38.5" r="1.2" fill="#ffffff" />
      
      {/* Blush */}
      <ellipse cx="36" cy="47" rx="3" ry="1.5" fill="#f43f5e" opacity="0.5" />
      <ellipse cx="64" cy="47" rx="3" ry="1.5" fill="#f43f5e" opacity="0.5" />
      
      {/* Mouth */}
      <path d="M 47,46 Q 50,49 53,46" fill="none" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" />
      
      {/* Academic Cap */}
      <polygon points="50,12 76,20 50,28 24,20" fill="#1e293b" stroke="#ffffff" strokeWidth="1.5" />
      <rect x="44" y="22" width="12" height="6" fill="#1e293b" />
      {/* Tassel */}
      <path d="M 50,20 Q 32,25 32,32" fill="none" stroke="#f59e0b" strokeWidth="1.5" />
      <circle cx="32" cy="33" r="2.5" fill="#f59e0b" />
    </svg>
  );
}

// Radar Minimap SVG mapping
function RadarMinimapSVG({ activeBuilding, avatarPos }) {
  const dots = [
    { id: "admin", cx: 51, cy: 43 },
    { id: "union", cx: 31, cy: 58 },
    { id: "library", cx: 71, cy: 35 },
    { id: "ecampus", cx: 43, cy: 28 },
    { id: "bugak", cx: 61, cy: 58 },
    { id: "engineering", cx: 81, cy: 53 },
  ];
  
  const ax = avatarPos ? Math.round(avatarPos.x / 10) : 45;
  const ay = avatarPos ? Math.round(avatarPos.y / 10) : 65;

  return (
    <svg viewBox="0 0 100 100" className="minimap-svg-container">
      <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(96, 165, 250, 0.2)" strokeWidth="1" />
      <circle cx="50" cy="50" r="30" fill="none" stroke="rgba(96, 165, 250, 0.15)" strokeWidth="1" />
      <circle cx="50" cy="50" r="15" fill="none" stroke="rgba(96, 165, 250, 0.1)" strokeWidth="1" />
      <line x1="50" y1="5" x2="50" y2="95" stroke="rgba(96, 165, 250, 0.15)" strokeWidth="0.5" />
      <line x1="5" y1="50" x2="95" y2="50" stroke="rgba(96, 165, 250, 0.15)" strokeWidth="0.5" />
      
      {dots.map(d => (
        <circle 
          key={d.id} 
          cx={d.cx} 
          cy={d.cy} 
          r={activeBuilding === d.id ? "3.5" : "2"} 
          fill={activeBuilding === d.id ? "#3b82f6" : "#64748b"} 
          opacity={activeBuilding === d.id ? "1" : "0.5"}
        />
      ))}
      
      <circle cx={ax} cy={ay} r="3" fill="#ef4444" />
      <circle cx={ax} cy={ay} r="6" fill="none" stroke="#ef4444" strokeWidth="1">
        <animate attributeName="r" values="3;8;3" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="1;0;1" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

function App() {
  const [question, setQuestion] = React.useState("");

  const checkPrivacyIssues = (text) => {
    const warnings = [];
    if (/\b20\d{6,8}\b/.test(text) || /학번/.test(text)) {
      warnings.push("학번");
    }
    if (/\d{6}-\d{7}/.test(text) || /주민/.test(text)) {
      warnings.push("주민번호");
    }
    if (/비밀번호|패스워드|password|pw/i.test(text)) {
      warnings.push("비밀번호");
    }
    if (/성적표|평점|gpa|내\s*성적|제\s*성적|성적으로\s*처리/.test(text)) {
      warnings.push("성적");
    }
    if (/01[016789]-?\d{3,4}-?\d{4}|연락처|전화번호/.test(text)) {
      warnings.push("연락처");
    }
    return warnings;
  };

  const privacyWarnings = checkPrivacyIssues(question);
  const [studentContext, setStudentContext] = React.useState(() => {
    try {
      const saved = localStorage.getItem("studentContext");
      return saved ? JSON.parse(saved) : { status: "", term: "", concern: "" };
    } catch {
      return { status: "", term: "", concern: "" };
    }
  });
  const [messages, setMessages] = React.useState([]);
  const [toolLogs, setToolLogs] = React.useState([]);
  const [citations, setCitations] = React.useState([]);
  const [actions, setActions] = React.useState([]);
  const [actionState, setActionState] = React.useState(null);
  const [slots, setSlots] = React.useState({});
  const [loading, setLoading] = React.useState(false);
  const [liveCheck, setLiveCheck] = React.useState(false);
  const [llmAssist, setLlmAssist] = React.useState(true);
  const [liveCheckStatus, setLiveCheckStatus] = React.useState(null);
  const [llmStatus, setLlmStatus] = React.useState(null);
  const [answerValidation, setAnswerValidation] = React.useState(null);
  const [outputPrivacy, setOutputPrivacy] = React.useState(null);

  // Metaverse and Quest States
  const [level, setLevel] = React.useState(() => {
    try {
      const saved = localStorage.getItem("studentLevel");
      return saved ? parseInt(saved, 10) : 1;
    } catch {
      return 1;
    }
  });
  const [xp, setXp] = React.useState(() => {
    try {
      const saved = localStorage.getItem("studentXp");
      return saved ? parseInt(saved, 10) : 0;
    } catch {
      return 0;
    }
  });
  const [quests, setQuests] = React.useState(() => {
    try {
      const saved = localStorage.getItem("studentQuests");
      return saved ? JSON.parse(saved) : DEFAULT_QUESTS;
    } catch {
      return DEFAULT_QUESTS;
    }
  });
  const [activeBuilding, setActiveBuilding] = React.useState("admin");
  const [showLevelUpModal, setShowLevelUpModal] = React.useState(false);
  const [levelUpTitle, setLevelUpTitle] = React.useState("");

  // Modal overlay visibility states
  const [showActionModal, setShowActionModal] = React.useState(false);
  const [showEncyclopediaModal, setShowEncyclopediaModal] = React.useState(false);
  const [showSecretLabModal, setShowSecretLabModal] = React.useState(false);
  const [showProfileModal, setShowProfileModal] = React.useState(false);
  const [showQuests, setShowQuests] = React.useState(false);
  const [showConsole, setShowConsole] = React.useState(false);
  const [showGraduationCenter, setShowGraduationCenter] = React.useState(false);
  const [questAlert, setQuestAlert] = React.useState(null);

  const bubbleScrollRef = React.useRef(null);

  // LocalStorage persistence effects
  React.useEffect(() => {
    localStorage.setItem("studentContext", JSON.stringify(studentContext));
  }, [studentContext]);

  React.useEffect(() => {
    localStorage.setItem("studentLevel", level);
  }, [level]);

  React.useEffect(() => {
    localStorage.setItem("studentXp", xp);
  }, [xp]);

  React.useEffect(() => {
    localStorage.setItem("studentQuests", JSON.stringify(quests));
  }, [quests]);

  React.useEffect(() => {
    if (bubbleScrollRef.current) {
      bubbleScrollRef.current.scrollTop = bubbleScrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const currentExamples = activeBuilding && BUILDING_EXAMPLES[activeBuilding]
    ? BUILDING_EXAMPLES[activeBuilding]
    : examples;

  const STATUS_LABELS = {
    "": "기본",
    "new_student": "신입생",
    "enrolled": "재학생",
    "returning": "복학생",
    "leave": "휴학생",
    "graduating": "졸업예정"
  };

  // Handle Level Up & XP
  function completeQuest(questId) {
    setQuests((prevQuests) => {
      const targetQuest = prevQuests.find(q => q.id === questId && q.status === "active");
      if (targetQuest) {
        setQuestAlert({ title: targetQuest.title, xp: targetQuest.rewardXp });
        setTimeout(() => setQuestAlert(null), 3500);
      }
      return prevQuests.map((q) => {
        if (q.id === questId && q.status === "active") {
          const reward = q.rewardXp;
          setXp((prevXp) => {
            const nextXp = prevXp + reward;
            const nextLevel = Math.floor(nextXp / 100) + 1;
            if (nextLevel > level) {
              setLevel(nextLevel);
              setLevelUpTitle(
                nextLevel === 2
                  ? "🎓 배움에 눈뜬 재학생으로 전직했습니다!"
                  : nextLevel === 3
                  ? "⚡ 학사 행정 마스터가 되었습니다!"
                  : "👑 졸업 준비 왕선배가 되었습니다!"
              );
              setShowLevelUpModal(true);
            }
            return nextXp;
          });
          return { ...q, status: "completed" };
        }
        return q;
      });
    });
  }

  async function ask(text) {
    const queryText = text || question;
    if (!queryText.trim() || loading) return;
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: queryText }]);
    try {
      const response = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: queryText,
          student_context: studentContext,
          live_check: liveCheck,
          llm_assist: llmAssist
        })
      });
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "agent", text: data.answer || "응답을 생성하지 못했습니다." }]);
      setToolLogs(data.tool_logs || []);
      setCitations(data.citations || []);
      setActions(data.next_actions || []);
      setLiveCheckStatus(data.live_check || null);
      setLlmStatus(data.llm || null);
      setAnswerValidation(data.answer_validation || null);
      setOutputPrivacy(data.output_privacy || null);
      setActionState(null);
      setSlots({});

      // Check if this query triggers query-based quests
      const matchingQuest = quests.find(q => q.status === "active" && q.triggerMsg && queryText.includes(q.triggerMsg));
      if (matchingQuest) {
        completeQuest(matchingQuest.id);
      }

      // Keep the answer visible first; the user can open the document hub from the action button.
      if (data.next_actions && data.next_actions.length > 0) {
        setShowConsole(true);
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: "agent", text: `요청 실패: ${error.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function startAction(actionId) {
    if (["graduation_audit", "recommend_course_plan"].includes(actionId)) {
      setShowGraduationCenter(true);
      const matchingQuest = quests.find(q => q.actionId === actionId && q.status === "active");
      if (matchingQuest) {
        completeQuest(matchingQuest.id);
      }
      return;
    }
    const response = await fetch(`${API_BASE}/actions/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId })
    });
    const data = await response.json();
    setActionState(data);
    setSlots({});
    setShowActionModal(true);
  }

  async function continueAction() {
    if (!actionState) return;
    const response = await fetch(`${API_BASE}/actions/continue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionState.action_id, slots, live_check: liveCheck })
    });
    const data = await response.json();
    if (data.live_check) setLiveCheckStatus(data.live_check);
    if (data.output_privacy) setOutputPrivacy(data.output_privacy);
    if (data.status === "completed") {
      const checklist = (data.checklist || []).map((item, index) => `${index + 1}. ${item}`).join("\n");
      setMessages((prev) => [...prev, { role: "agent", text: `${data.document}\n\n[제출 전 체크리스트]\n${checklist}` }]);
      
      // Check if this completes an active action-based quest
      const completedActionId = actionState.action_id;
      const matchingQuest = quests.find(q => q.actionId === completedActionId && q.status === "active");
      if (matchingQuest) {
        completeQuest(matchingQuest.id);
      }

      setActionState(null);
      setSlots({});
      setShowActionModal(false);
    } else if (data.status === "blocked") {
      setMessages((prev) => [...prev, { role: "agent", text: data.message || "민감정보 보호를 위해 초안을 반환하지 않았습니다." }]);
      setActionState(null);
      setSlots({});
      setShowActionModal(false);
    } else {
      setActionState(data);
    }
  }

  function handleCitationClick(citationId) {
    setShowEncyclopediaModal(true);
    setTimeout(() => {
      const element = document.getElementById(`source-card-${citationId}`);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
        element.classList.add("highlighted-source");
        setTimeout(() => element.classList.remove("highlighted-source"), 2000);
      }
    }, 200);
  }

  // Parse text to find citations like [S1], [S2] and make them clickable
  const renderMessageText = (text) => {
    const citationRegex = /\[S(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      const matchIndex = match.index;
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
            handleCitationClick(citationId);
          }}
          title="공식 학사 근거 규정 보기"
          style={{ cursor: "pointer" }}
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

  const handleBubbleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    ask(question);
    setQuestion("");
  };

  // Render recent conversation flow inside the mascot speech bubble
  const renderBubbleMessages = () => {
    const lastTwo = messages.slice(-2);
    if (lastTwo.length === 0) {
      return (
        <p style={{ margin: 0 }}>
          안녕하세요! 학사지원 AI 국민이입니다. 지도의 건물을 클릭하여 각 구역의 조교를 만난 뒤 퀘스트를 수행해보세요! 무엇이든 물어보셔도 좋습니다.
        </p>
      );
    }
    return lastTwo.map((msg, index) => (
      <div key={index} style={{ marginBottom: index === 0 && lastTwo.length > 1 ? "8px" : "0", borderBottom: index === 0 && lastTwo.length > 1 ? "1px dashed rgba(15, 23, 42, 0.08)" : "none", paddingBottom: index === 0 && lastTwo.length > 1 ? "6px" : "0" }}>
        <strong style={{ color: msg.role === "user" ? "#2563eb" : "#f59e0b", fontSize: "10px", display: "block", marginBottom: "2px" }}>
          {msg.role === "user" ? "나 (학생)" : "국민이 (AI)"}
        </strong>
        <span style={{ fontSize: "11px", color: "#0f172a" }}>
          {renderMessageText(msg.text)}
        </span>
      </div>
    ));
  };

  return (
    <>
      {/* Moving sky backdrop */}
      <div className="sky-bg">
        <div className="sky-cloud" style={{ top: "10%", left: "10%", width: "120px", height: "40px" }}></div>
        <div className="sky-cloud" style={{ top: "25%", left: "45%", width: "180px", height: "60px", animationDelay: "-12s", animationDuration: "35s" }}></div>
        <div className="sky-cloud" style={{ top: "35%", left: "75%", width: "140px", height: "45px", animationDelay: "-24s", animationDuration: "50s" }}></div>
        <div className="sky-hill"></div>
        <div className="sky-hill-back"></div>
      </div>

      <div className="metaverse-game-container">
        <div className="metaverse-game-frame">
          {/* Main Title Banner */}
          <div className="metaverse-title-banner">
            <span className="metaverse-title-logo">🏫</span>
            <span>KMU 국문학사 메타버스 캠퍼스</span>
          </div>

          {/* Viewport content */}
          <div className="viewport-wrapper">
            {/* Campus map backdrop */}
            <CampusMap 
              activeBuilding={activeBuilding} 
              onBuildingSelect={(bId) => {
                setActiveBuilding(bId);
              }} 
              quests={quests} 
            />

            {/* Overlays */}
            {/* HUD Profile Card (Left Top) */}
            <div className="hud-card-left" onClick={() => setShowProfileModal(true)} title="내 학적 정보 설정">
              <div className="hud-avatar-img">🧑‍🎓</div>
              <div className="hud-details-left">
                <div className="name">{studentContext.status ? STATUS_LABELS[studentContext.status] : "학사"} 모험가</div>
                <div className="lvl-xp">
                  <span className="lvl">LV.{level}</span>
                  <div className="xp-mini-track">
                    <div className="xp-mini-fill" style={{ width: `${Math.min(xp % 100, 100)}%` }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* HUD Bot Profile Card (Right Top) */}
            <div className="hud-card-right">
              <div className="hud-avatar-img">🦆</div>
              <div className="hud-details-right">
                <div className="bot-name">국민이 AI</div>
                <span className="bot-tag">학사 가이드</span>
              </div>
            </div>

            {/* Left Vertical Menu */}
            <div className="menu-vertical-left">
              <button 
                type="button"
                className="menu-btn" 
                data-title="홈" 
                onClick={() => {
                  setActiveBuilding("admin");
                  setShowQuests(false);
                  setShowConsole(false);
                }}
              >
                🏠
              </button>
              <button 
                type="button"
                className={`menu-btn ${showQuests ? "active" : ""}`} 
                data-title="퀘스트" 
                onClick={() => setShowQuests(!showQuests)}
              >
                📋
              </button>
              <button 
                type="button"
                className="menu-btn" 
                data-title="학적카드" 
                onClick={() => setShowProfileModal(true)}
              >
                🎒
              </button>
              <button 
                type="button"
                className={`menu-btn ${showConsole ? "active" : ""}`} 
                data-title="대화기록" 
                onClick={() => setShowConsole(!showConsole)}
              >
                💬
              </button>
            </div>

            {/* Right Vertical Menu */}
            <div className="menu-vertical-right">
              <button 
                type="button"
                className="menu-btn" 
                data-title="서류함" 
                onClick={() => setShowActionModal(true)}
              >
                📂
              </button>
              <button 
                type="button"
                className="menu-btn" 
                data-title="대백과" 
                onClick={() => setShowEncyclopediaModal(true)}
              >
                📚
              </button>
              <button 
                type="button"
                className="menu-btn" 
                data-title="졸업센터" 
                onClick={() => setShowGraduationCenter(true)}
              >
                🎓
              </button>
              <button 
                type="button"
                className="menu-btn" 
                data-title="연구소" 
                onClick={() => setShowSecretLabModal(true)}
              >
                🧪
              </button>
            </div>

            {/* Radar Minimap (Bottom Left) */}
            <div className="minimap-radar">
              <div className="radar-sweep"></div>
              <RadarMinimapSVG 
                activeBuilding={activeBuilding} 
                avatarPos={activeBuilding && BUILDINGS[activeBuilding] ? BUILDINGS[activeBuilding] : { x: 450, y: 650 }} 
              />
            </div>

            {/* Mascot Container & Speech Bubble Chatbot (Bottom Right) */}
            <div className="mascot-container">
              <div className="mascot-speech-bubble">
                <div className="bubble-message-area" ref={bubbleScrollRef}>
                  {loading && messages.length > 0 && messages[messages.length - 1].role === "user" ? (
                    <div className="rpg-loading-dots" style={{ padding: "10px 0" }}>
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  ) : (
                    renderBubbleMessages()
                  )}
                </div>

                {/* Suggestions inside bubble if empty history */}
                {messages.length === 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", margin: "4px 0" }}>
                    {currentExamples.slice(0, 2).map((ex, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => ask(ex)}
                        style={{ 
                          padding: "3px 8px", 
                          fontSize: "9.5px", 
                          borderRadius: "10px", 
                          background: "#eff6ff", 
                          border: "1px solid #bfdbfe", 
                          color: "#1e3a8a",
                          cursor: "pointer",
                          fontWeight: "700"
                        }}
                      >
                        🎯 {ex}
                      </button>
                    ))}
                  </div>
                )}

                {/* Bubble Chat Input Bar */}
                <form onSubmit={handleBubbleSubmit} className="bubble-input-bar">
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="질문 입력..."
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleBubbleSubmit(e);
                      }
                    }}
                    disabled={loading}
                  />
                  <button 
                    type="submit" 
                    className="bubble-send-btn"
                    disabled={loading || !question.trim()}
                  >
                    ➤
                  </button>
                </form>
                {privacyWarnings.length > 0 && (
                  <div className="privacy-warn-text">
                    ⚠️ {privacyWarnings.join(", ")} 감지됨. 실제 정보를 제외하고 물어보세요.
                  </div>
                )}
                
                {/* Link to show sliding console */}
                <div style={{ textAlign: "right", marginTop: "2px" }}>
                  <span 
                    onClick={() => setShowConsole(true)} 
                    style={{ fontSize: "9px", color: "#3b82f6", cursor: "pointer", fontWeight: "700", textDecoration: "underline" }}
                  >
                    💬 상세 로그 및 답변기록 보기
                  </span>
                </div>
              </div>

              {/* Float Mascot character */}
              <div 
                className="mascot-character" 
                onClick={() => {
                  // Prompt suggestions in console or toggle showConsole
                  setShowConsole(true);
                }}
                title="국민이 AI 조우"
              >
                <MascotSVG />
              </div>
            </div>

            {/* Sliding console log panel */}
            {showConsole && (
              <div className="sliding-rpg-console open">
                <div className="console-header-bar">
                  <h4>📜 학사 행정 상세 대화 기록 & RAG 로그</h4>
                  <button type="button" className="console-close-btn" onClick={() => setShowConsole(false)}>✕</button>
                </div>
                <div className="console-scroll-body">
                  <RPGMessageConsole
                    messages={messages}
                    loading={loading}
                    onAsk={ask}
                    examples={currentExamples}
                    setQuestion={setQuestion}
                    question={question}
                    activeBuilding={activeBuilding}
                    onCitationClick={handleCitationClick}
                    showConsole={showConsole}
                    privacyWarnings={privacyWarnings}
                  />
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Floating lab button on bottom-right of the whole screen */}
      <button 
        type="button" 
        className="rpg-secret-lab-btn" 
        onClick={() => setShowSecretLabModal(true)}
        title="비밀 학사 정보 연구소"
      >
        🧪 ⚙️
      </button>

      {/* Action modal: Smart Document Hub */}
      {showActionModal && (
        <div className="rpg-modal-overlay" onClick={() => {
          const hasInputs = Object.values(slots).some(v => v !== "");
          if (hasInputs) {
            if (window.confirm("작성 중인 서류가 유실될 수 있습니다. 정말로 닫으시겠습니까? (서류 가방을 다시 열어 이어서 작성할 수 있습니다.)")) {
              setShowActionModal(false);
            }
          } else {
            setShowActionModal(false);
          }
        }}>
          <div className="rpg-scroll-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="rpg-modal-close" onClick={() => {
              const hasInputs = Object.values(slots).some(v => v !== "");
              if (hasInputs) {
                if (window.confirm("작성 중인 서류가 유실될 수 있습니다. 정말로 닫으시겠습니까?")) {
                  setShowActionModal(false);
                }
              } else {
                setShowActionModal(false);
              }
            }}>✕</button>
            <div className="rpg-scroll-content">
              <ActionForm
                actions={actions}
                actionState={actionState}
                slots={slots}
                setSlots={setSlots}
                onStart={startAction}
                onContinue={continueAction}
              />
            </div>
          </div>
        </div>
      )}

      {/* Graduation Center modal */}
      {showGraduationCenter && (
        <div className="rpg-modal-overlay" onClick={() => setShowGraduationCenter(false)}>
          <div className="graduation-center-modal" onClick={(e) => e.stopPropagation()}>
            <GraduationCenter apiBase={API_BASE} onClose={() => setShowGraduationCenter(false)} />
          </div>
        </div>
      )}

      {/* Quests board modal overlay */}
      {showQuests && (
        <div className="rpg-modal-overlay" onClick={() => setShowQuests(false)}>
          <div className="rpg-book-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "480px", height: "auto", maxHeight: "90vh" }}>
            <button type="button" className="rpg-modal-close" onClick={() => setShowQuests(false)}>✕</button>
            <div className="rpg-book-content" style={{ padding: "20px" }}>
              <QuestBoard
                level={level}
                xp={xp}
                quests={quests}
                activeBuilding={activeBuilding}
                onStartAction={(actionId) => {
                  setShowQuests(false);
                  startAction(actionId);
                }}
                onSelectBuilding={setActiveBuilding}
                onSendChatMessage={(msg) => {
                  setShowQuests(false);
                  ask(msg);
                }}
                onOpenEncyclopedia={() => {
                  setShowQuests(false);
                  setShowEncyclopediaModal(true);
                }}
                onOpenActionForm={() => {
                  setShowQuests(false);
                  setShowActionModal(true);
                }}
                studentContext={studentContext}
                onOpenProfile={() => {
                  setShowQuests(false);
                  setShowProfileModal(true);
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Quest Completed Banner Notification */}
      {questAlert && (
        <div className="quest-completed-banner">
          <div className="quest-completed-icon">🏆</div>
          <div className="quest-completed-details">
            <span className="quest-completed-title">QUEST COMPLETED!</span>
            <span className="quest-completed-name">{questAlert.title}</span>
            <span className="quest-completed-xp">+{questAlert.xp} XP 획득</span>
          </div>
        </div>
      )}

      {/* Student Profile Card Modal Overlay */}
      {showProfileModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowProfileModal(false)}>
          <div className="rpg-profile-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="rpg-modal-close" onClick={() => setShowProfileModal(false)}>✕</button>
            <div className="rpg-profile-modal-content">
              <h2 style={{ color: "#f59e0b", textShadow: "0 0 10px rgba(245, 158, 11, 0.4)", borderBottom: "1px solid rgba(245, 158, 11, 0.2)", paddingBottom: "10px", marginTop: 0 }}>🎒 캐릭터 학적 카드 발급</h2>
              <p style={{ fontSize: "13px", color: "#94a3b8", marginBottom: "20px" }}>학적 정보를 등록하면 본인에게 알맞은 맞춤형 퀘스트 및 공식 답변을 받을 수 있습니다.</p>
              
              <div className="rpg-settings-card" style={{ background: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "10px", padding: "16px", marginBottom: "16px" }}>
                <div className="student-context" style={{ display: "grid", gap: "16px", background: "none", border: "none", padding: 0 }}>
                  <div className="context-row" style={{ display: "grid", gap: "8px" }}>
                    <span className="context-label" style={{ fontSize: "12px", fontWeight: "700", color: "#f59e0b" }}>학생 학적 상태</span>
                    <div className="segmented" style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                      {studentStatuses.map((status) => (
                        <button
                          key={status.value || "default"}
                          type="button"
                          className={studentContext.status === status.value ? "selected" : ""}
                          onClick={() => setStudentContext(prev => ({ ...prev, status: status.value }))}
                          style={{
                            padding: "8px 14px",
                            fontSize: "12px",
                            borderRadius: "8px",
                            cursor: "pointer",
                            background: studentContext.status === status.value ? "#f59e0b" : "rgba(255, 255, 255, 0.05)",
                            borderColor: studentContext.status === status.value ? "#f59e0b" : "rgba(255,255,255,0.1)",
                            boxShadow: studentContext.status === status.value ? "0 0 10px rgba(245, 158, 11, 0.4)" : "none",
                            color: studentContext.status === status.value ? "#000" : "#94a3b8",
                            fontWeight: "700"
                          }}
                        >
                          {status.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="context-fields" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <label style={{ display: "grid", gap: "8px", fontSize: "12px", color: "#94a3b8", fontWeight: "700" }}>
                      대상 학기
                      <input
                        value={studentContext.term}
                        onChange={(event) => setStudentContext(prev => ({ ...prev, term: event.target.value }))}
                        placeholder="예: 2026-2학기"
                        style={{
                          background: "rgba(0,0,0,0.4)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                          padding: "10px",
                          color: "#fff"
                        }}
                      />
                    </label>
                    <label style={{ display: "grid", gap: "8px", fontSize: "12px", color: "#94a3b8", fontWeight: "700" }}>
                      관심 항목
                      <input
                        value={studentContext.concern}
                        onChange={(event) => setStudentContext(prev => ({ ...prev, concern: event.target.value }))}
                        placeholder="예: 수강신청, 장학"
                        style={{
                          background: "rgba(0,0,0,0.4)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                          padding: "10px",
                          color: "#fff"
                        }}
                      />
                    </label>
                  </div>
                </div>
              </div>
              
              <button 
                type="button" 
                className="primary wide" 
                onClick={() => setShowProfileModal(false)}
                style={{
                  background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                  borderColor: "#f59e0b",
                  color: "#000",
                  fontWeight: "700",
                  padding: "12px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  cursor: "pointer",
                  width: "100%",
                  boxShadow: "0 4px 12px rgba(245, 158, 11, 0.2)"
                }}
              >
                학적 카드 발급 완료 🎒
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Encyclopedia Book Modal Overlay */}
      {showEncyclopediaModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowEncyclopediaModal(false)}>
          <div className="rpg-book-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="rpg-modal-close" onClick={() => setShowEncyclopediaModal(false)}>✕</button>
            <div className="rpg-book-content">
              <SourcePanel citations={citations} />
            </div>
          </div>
        </div>
      )}

      {/* Secret Lab Settings Modal Overlay */}
      {showSecretLabModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowSecretLabModal(false)}>
          <div className="rpg-secret-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="rpg-modal-close" onClick={() => setShowSecretLabModal(false)}>✕</button>
            <div className="rpg-secret-content">
              <h2 style={{ color: "#10b981", textShadow: "0 0 10px rgba(16, 185, 129, 0.5)", borderBottom: "1px solid rgba(16, 185, 129, 0.3)", paddingBottom: "10px" }}>🧪 비밀 학사 정보 연구소</h2>
              
              <div className="rpg-settings-card" style={{ background: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "10px", padding: "16px", marginBottom: "16px" }}>
                <h3 style={{ margin: "0 0 12px 0", fontSize: "14px", color: "#10b981" }}>⚙️ 학생 상태 및 연동 설정</h3>
                
                <div className="student-context" style={{ display: "grid", gap: "12px", background: "none", border: "none", padding: 0 }}>
                  <div className="context-row" style={{ display: "grid", gap: "6px" }}>
                    <span className="context-label" style={{ fontSize: "11px", fontWeight: "700", color: "#94a3b8" }}>학생 학적 상태</span>
                    <div className="segmented" style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {studentStatuses.map((status) => (
                        <button
                          key={status.value || "default"}
                          type="button"
                          className={studentContext.status === status.value ? "selected" : ""}
                          onClick={() => setStudentContext(prev => ({ ...prev, status: status.value }))}
                          style={{
                            padding: "6px 12px",
                            fontSize: "12px",
                            background: studentContext.status === status.value ? "#10b981" : "rgba(255, 255, 255, 0.05)",
                            borderColor: studentContext.status === status.value ? "#10b981" : "rgba(255,255,255,0.1)",
                            boxShadow: studentContext.status === status.value ? "0 0 10px rgba(16, 185, 129, 0.4)" : "none",
                            color: studentContext.status === status.value ? "#000" : "#94a3b8"
                          }}
                        >
                          {status.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="context-fields" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <label style={{ display: "grid", gap: "6px", fontSize: "12px", color: "#94a3b8" }}>
                      대상 학기
                      <input
                        value={studentContext.term}
                        onChange={(event) => setStudentContext(prev => ({ ...prev, term: event.target.value }))}
                        placeholder="예: 2026-2학기"
                        style={{ background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" }}
                      />
                    </label>
                    <label style={{ display: "grid", gap: "6px", fontSize: "12px", color: "#94a3b8" }}>
                      관심 항목
                      <input
                        value={studentContext.concern}
                        onChange={(event) => setStudentContext(prev => ({ ...prev, concern: event.target.value }))}
                        placeholder="예: 수강신청, 장학, 졸업"
                        style={{ background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" }}
                      />
                    </label>
                  </div>

                  <div className="context-row live-check-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px dashed rgba(255,255,255,0.1)", paddingTop: "12px" }}>
                    <div className="check-group" style={{ display: "flex", gap: "16px" }}>
                      <label className="check-field" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", cursor: "pointer" }}>
                        <input type="checkbox" checked={liveCheck} onChange={(event) => setLiveCheck(event.target.checked)} style={{ width: "16px", height: "16px", accentColor: "#10b981" }} />
                        <span>공식 사이트 실시간 대조</span>
                      </label>
                      <label className="check-field" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", cursor: "pointer" }}>
                        <input type="checkbox" checked={llmAssist} onChange={(event) => setLlmAssist(event.target.checked)} style={{ width: "16px", height: "16px", accentColor: "#10b981" }} />
                        <span>GPT 보조</span>
                      </label>
                    </div>
                    {liveCheckStatus && (
                      <span className={liveCheckStatus.network_success > 0 ? "live-status ok" : "live-status"} style={{ fontSize: "11px" }}>
                        {formatLiveCheckStatus(liveCheckStatus)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="rpg-settings-card" style={{ background: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "10px", padding: "16px" }}>
                <h3 style={{ margin: "0 0 12px 0", fontSize: "14px", color: "#10b981" }}>🔍 실시간 에이전트 다이어그램</h3>
                <div className="debug-panels" style={{ display: "grid", gap: "16px", maxHeight: "400px", overflowY: "auto", paddingRight: "4px" }}>
                  <ProcessingStatusPanel
                    liveCheck={liveCheckStatus}
                    llm={llmStatus}
                    answerValidation={answerValidation}
                    outputPrivacy={outputPrivacy}
                  />
                  <ToolLogPanel logs={toolLogs} />
                  <AdminDashboard apiBase={API_BASE} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Level Up Congrats Modal */}
      {showLevelUpModal && (
        <div className="level-up-modal-overlay" onClick={() => setShowLevelUpModal(false)}>
          <div className="level-up-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="confetti-effect">🎉 ✨ 🎓 ✨ 🎉</div>
            <h3>LEVEL UP!</h3>
            <div className="level-up-badge">LV.{level}</div>
            <p className="level-up-congrats">축하합니다! 새로운 학사 레벨에 올랐습니다.</p>
            <p className="level-up-title-text">{levelUpTitle}</p>
            <button type="button" className="primary level-up-close-btn" onClick={() => setShowLevelUpModal(false)}>
              국민이와 계속 모험하기
            </button>
          </div>
        </div>
      )}
    </>
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

createRoot(document.getElementById("root")).render(<App />);
