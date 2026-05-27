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

const API_BASE =
  window.location.port === "5173"
    ? "http://127.0.0.1:8001"
    : window.location.origin;

const examples = [
  "이캠에 강의가 안 떠요",
  "등록금 냈는데 납부확인이 안 떠",
  "수변 기간 언제야?",
  "모바일 학생증 안 찍힘",
  "국장 들어왔는지 어디서 봐?",
  "복학생인데 이번 주 뭐 해야 해?",
];

const studentStatuses = [
  { value: "", label: "기본" },
  { value: "new_student", label: "신입생" },
  { value: "enrolled", label: "재학생" },
  { value: "returning", label: "복학생" },
  { value: "leave", label: "휴학생" },
  { value: "graduating", label: "졸업예정" },
];

const BUILDING_EXAMPLES = {
  admin: [
    "공결 신청 절차가 어떻게 돼?",
    "예비군 훈련 공결 인정 서류는?",
    "상해/질병 결석도 공결이 되나요?",
    "공결계 제출은 며칠 이내 해야 해?",
  ],
  union: [
    "일반휴학 신청 일정은?",
    "군휴학 신청 시 준비물은?",
    "질병휴학 연장하려면?",
    "복학 신청하고 나서 해야할 일?",
  ],
  library: [
    "모바일 학생증 안 찍힘",
    "실물 학생증 재발급 신청은?",
    "도서관 좌석 예약 오류나",
    "도서 연체 연체료 규정이 뭐야?",
  ],
  ecampus: [
    "이캠에 강의가 안 떠요",
    "이캠퍼스 아이디/비밀번호 변경",
    "이캠퍼스 모바일 앱 연동 오류",
    "비대면 줌 강의 연동 실패",
  ],
  bugak: [
    "수변 기간 언제야?",
    "성적 장학금 전액 기준은?",
    "졸업예정증명서 어디서 떼?",
    "학기 도중에 휴학할 수 있어?",
  ],
  engineering: [
    "소프트웨어학부 행정실 위치",
    "실습실 IT 장비 반납 규정",
    "졸업 요건 학점이 궁금해",
    "폐강 기준 인원이 몇 명이야?",
  ],
};

const DEFAULT_QUESTS = [
  {
    id: "quest_attendance",
    title: "공결 신청서 작성",
    desc: "본부관 학사지원팀 조교를 만나 출석인정신청서 작성 완료하기",
    status: "active",
    actionId: "draft_attendance_recognition_form",
    rewardXp: 40,
  },
  {
    id: "quest_leave_absence",
    title: "휴학/복학 신청 마스터",
    desc: "복지관 종합민원실 주임을 만나 휴학/복학 체크리스트 및 서류 준비하기",
    status: "active",
    actionId: "draft_leave_checklist",
    rewardXp: 40,
  },
  {
    id: "quest_library_id",
    title: "도서관 학생증 오류 해결",
    desc: "성곡도서관 사서를 방문하여 학생증 비활성화 에러 팁 확인하기",
    status: "active",
    triggerMsg: "모바일 학생증 안 찍힘",
    rewardXp: 20,
  },
  {
    id: "quest_ecampus_sync",
    title: "E-Campus 클래스룸 동기화",
    desc: "이캠퍼스 센터 헬프데스크를 방문해 수강 목록 누락 해결하기",
    status: "active",
    triggerMsg: "이캠에 강의가 안 떠요",
    rewardXp: 20,
  },
  {
    id: "quest_graduation_center",
    title: "졸업 센터 종합 진단",
    desc: "공학관 행정직원을 만나 성적증명서 기반 졸업/진로 분석 시작하기",
    status: "active",
    actionId: "graduation_audit",
    rewardXp: 60,
  },
];

const STATUS_LABELS = {
  "": "기본",
  new_student: "신입생",
  enrolled: "재학생",
  returning: "복학생",
  leave: "휴학생",
  graduating: "졸업예정",
};

// 마스코트 SVG — 국민대 진청색 유니폼
function MascotSVG() {
  return (
    <svg viewBox="0 0 100 120" width="100%" height="100%">
      {/* 그림자 */}
      <ellipse cx="50" cy="112" rx="22" ry="5" fill="rgba(0,0,0,0.12)" />

      {/* 몸통 */}
      <rect x="35" y="65" width="30" height="35" rx="15" fill="#0F3D7A" />
      <rect x="42" y="66" width="16" height="28" rx="8" fill="rgba(255,255,255,0.85)" />

      {/* 팔 */}
      <path d="M 32,74 Q 20,80 28,89" fill="none" stroke="#0F3D7A" strokeWidth="6" strokeLinecap="round" />
      <path d="M 68,74 Q 80,80 72,89" fill="none" stroke="#0F3D7A" strokeWidth="6" strokeLinecap="round" />

      {/* 스카프 (골드) */}
      <rect x="37" y="60" width="26" height="7" rx="3.5" fill="#C8A951" />
      <path d="M 60,64 L 66,80" stroke="#C8A951" strokeWidth="5" strokeLinecap="round" />

      {/* 머리 */}
      <circle cx="50" cy="40" r="27" fill="#ffffff" stroke="#0F3D7A" strokeWidth="3" />

      {/* 눈 */}
      <circle cx="41" cy="38" r="4.5" fill="#0F1B2D" />
      <circle cx="59" cy="38" r="4.5" fill="#0F1B2D" />
      {/* 눈 반짝임 */}
      <circle cx="39" cy="36" r="1.5" fill="#ffffff" />
      <circle cx="57" cy="36" r="1.5" fill="#ffffff" />

      {/* 볼터치 */}
      <ellipse cx="34" cy="46" rx="3.5" ry="2" fill="#F87171" opacity="0.45" />
      <ellipse cx="66" cy="46" rx="3.5" ry="2" fill="#F87171" opacity="0.45" />

      {/* 입 */}
      <path d="M 46,47 Q 50,52 54,47" fill="none" stroke="#0F1B2D" strokeWidth="2" strokeLinecap="round" />

      {/* 학사모 */}
      <polygon points="50,10 78,19 50,28 22,19" fill="#0F2040" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" />
      <rect x="44" y="21" width="12" height="7" fill="#0F2040" />
      {/* 학사모 술 */}
      <path d="M 50,19 Q 30,24 30,33" fill="none" stroke="#C8A951" strokeWidth="2" />
      <circle cx="30" cy="34" r="3" fill="#C8A951" />
    </svg>
  );
}

// 레이더 미니맵 SVG
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
      <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(200,169,81,0.15)" strokeWidth="1" />
      <circle cx="50" cy="50" r="30" fill="none" stroke="rgba(200,169,81,0.12)" strokeWidth="1" />
      <circle cx="50" cy="50" r="15" fill="none" stroke="rgba(200,169,81,0.08)" strokeWidth="1" />
      <line x1="50" y1="5" x2="50" y2="95" stroke="rgba(200,169,81,0.1)" strokeWidth="0.5" />
      <line x1="5" y1="50" x2="95" y2="50" stroke="rgba(200,169,81,0.1)" strokeWidth="0.5" />

      {dots.map((d) => (
        <circle
          key={d.id}
          cx={d.cx}
          cy={d.cy}
          r={activeBuilding === d.id ? "3.5" : "2"}
          fill={activeBuilding === d.id ? "#C8A951" : "#3D5A80"}
          opacity={activeBuilding === d.id ? "1" : "0.6"}
        />
      ))}

      {/* 플레이어 위치 */}
      <circle cx={ax} cy={ay} r="3" fill="#EF4444" />
      <circle cx={ax} cy={ay} r="6" fill="none" stroke="#EF4444" strokeWidth="1">
        <animate attributeName="r" values="3;9;3" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="1;0;1" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

function App() {
  const [question, setQuestion] = React.useState("");

  const checkPrivacyIssues = (text) => {
    const warnings = [];
    if (/\b20\d{6,8}\b/.test(text) || /학번/.test(text)) warnings.push("학번");
    if (/\d{6}-\d{7}/.test(text) || /주민/.test(text)) warnings.push("주민번호");
    if (/비밀번호|패스워드|password|pw/i.test(text)) warnings.push("비밀번호");
    if (/성적표|평점|gpa|내\s*성적|제\s*성적|성적으로\s*처리/.test(text)) warnings.push("성적");
    if (/01[016789]-?\d{3,4}-?\d{4}|연락처|전화번호/.test(text)) warnings.push("연락처");
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

  // 퀘스트/레벨
  const [level, setLevel] = React.useState(() => {
    try { return parseInt(localStorage.getItem("studentLevel") || "1", 10); }
    catch { return 1; }
  });
  const [xp, setXp] = React.useState(() => {
    try { return parseInt(localStorage.getItem("studentXp") || "0", 10); }
    catch { return 0; }
  });
  const [quests, setQuests] = React.useState(() => {
    try {
      const saved = localStorage.getItem("studentQuests");
      return saved ? JSON.parse(saved) : DEFAULT_QUESTS;
    } catch { return DEFAULT_QUESTS; }
  });

  const [activeBuilding, setActiveBuilding] = React.useState("admin");
  const [showLevelUpModal, setShowLevelUpModal] = React.useState(false);
  const [levelUpTitle, setLevelUpTitle] = React.useState("");

  // 모달 상태
  const [showActionModal, setShowActionModal] = React.useState(false);
  const [showEncyclopediaModal, setShowEncyclopediaModal] = React.useState(false);
  const [showSecretLabModal, setShowSecretLabModal] = React.useState(false);
  const [showProfileModal, setShowProfileModal] = React.useState(false);
  const [showQuests, setShowQuests] = React.useState(false);
  const [showConsole, setShowConsole] = React.useState(false);
  const [showGraduationCenter, setShowGraduationCenter] = React.useState(false);
  const [questAlert, setQuestAlert] = React.useState(null);

  // 임시 학적카드 편집 상태
  const [profileDraft, setProfileDraft] = React.useState(studentContext);

  const bubbleScrollRef = React.useRef(null);

  // localStorage 동기화
  React.useEffect(() => { localStorage.setItem("studentContext", JSON.stringify(studentContext)); }, [studentContext]);
  React.useEffect(() => { localStorage.setItem("studentLevel", level); }, [level]);
  React.useEffect(() => { localStorage.setItem("studentXp", xp); }, [xp]);
  React.useEffect(() => { localStorage.setItem("studentQuests", JSON.stringify(quests)); }, [quests]);

  React.useEffect(() => {
    if (bubbleScrollRef.current) {
      bubbleScrollRef.current.scrollTop = bubbleScrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const currentExamples =
    activeBuilding && BUILDING_EXAMPLES[activeBuilding]
      ? BUILDING_EXAMPLES[activeBuilding]
      : examples;

  // 퀘스트 완료 처리
  function completeQuest(questId) {
    setQuests((prev) => {
      const target = prev.find((q) => q.id === questId && q.status === "active");
      if (target) {
        setQuestAlert({ title: target.title, xp: target.rewardXp });
        setTimeout(() => setQuestAlert(null), 3500);
      }
      return prev.map((q) => {
        if (q.id === questId && q.status === "active") {
          const reward = q.rewardXp;
          setXp((prevXp) => {
            const nextXp = prevXp + reward;
            const nextLevel = Math.floor(nextXp / 100) + 1;
            if (nextLevel > level) {
              setLevel(nextLevel);
              setLevelUpTitle(
                nextLevel === 2
                  ? "📖 배움에 눈뜬 재학생으로 전직했습니다!"
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
    if (text) setQuestion("");

    try {
      const response = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: queryText,
          student_context: studentContext,
          live_check: liveCheck,
          llm_assist: llmAssist,
        }),
      });
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: data.answer || "응답을 생성하지 못했습니다." },
      ]);
      setToolLogs(data.tool_logs || []);
      setCitations(data.citations || []);
      setActions(data.next_actions || []);
      setLiveCheckStatus(data.live_check || null);
      setLlmStatus(data.llm || null);
      setAnswerValidation(data.answer_validation || null);
      setOutputPrivacy(data.output_privacy || null);
      setActionState(null);
      setSlots({});

      const matchingQuest = quests.find(
        (q) => q.status === "active" && q.triggerMsg && queryText.includes(q.triggerMsg)
      );
      if (matchingQuest) completeQuest(matchingQuest.id);

      if (data.next_actions && data.next_actions.length > 0) setShowConsole(true);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: `연결 오류: 백엔드 서버(8001)에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.\n(${error.message})` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function startAction(actionId) {
    if (["graduation_audit", "recommend_course_plan"].includes(actionId)) {
      setShowGraduationCenter(true);
      const mq = quests.find((q) => q.actionId === actionId && q.status === "active");
      if (mq) completeQuest(mq.id);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/actions/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: actionId }),
      });
      const data = await response.json();
      setActionState(data);
      setSlots({});
      setShowActionModal(true);
    } catch {
      setShowActionModal(true);
    }
  }

  async function continueAction() {
    if (!actionState) return;
    try {
      const response = await fetch(`${API_BASE}/actions/continue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: actionState.action_id, slots, live_check: liveCheck }),
      });
      const data = await response.json();
      if (data.live_check) setLiveCheckStatus(data.live_check);
      if (data.output_privacy) setOutputPrivacy(data.output_privacy);
      if (data.status === "completed") {
        const checklist = (data.checklist || []).map((item, i) => `${i + 1}. ${item}`).join("\n");
        setMessages((prev) => [
          ...prev,
          { role: "agent", text: `${data.document}\n\n[제출 전 체크리스트]\n${checklist}` },
        ]);
        const mq = quests.find((q) => q.actionId === actionState.action_id && q.status === "active");
        if (mq) completeQuest(mq.id);
        setActionState(null);
        setSlots({});
        setShowActionModal(false);
      } else if (data.status === "blocked") {
        setMessages((prev) => [
          ...prev,
          { role: "agent", text: data.message || "민감정보 보호를 위해 초안을 반환하지 않았습니다." },
        ]);
        setActionState(null);
        setSlots({});
        setShowActionModal(false);
      } else {
        setActionState(data);
      }
    } catch (error) {
      alert(`액션 오류: ${error.message}`);
    }
  }

  function handleCitationClick(citationId) {
    setShowEncyclopediaModal(true);
    setTimeout(() => {
      const el = document.getElementById(`source-card-${citationId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("highlighted-source");
        setTimeout(() => el.classList.remove("highlighted-source"), 2500);
      }
    }, 200);
  }

  const renderMessageText = (text) => {
    const citationRegex = /\[S(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    while ((match = citationRegex.exec(text)) !== null) {
      if (match.index > lastIndex) parts.push(text.substring(lastIndex, match.index));
      const citationId = match[1];
      parts.push(
        <span
          key={`cite-${match.index}`}
          className="rpg-citation-pill"
          onClick={(e) => { e.stopPropagation(); handleCitationClick(citationId); }}
          title="공식 학사 근거 규정 보기"
        >
          📜 근거 S{citationId}
        </span>
      );
      lastIndex = citationRegex.lastIndex;
    }
    if (lastIndex < text.length) parts.push(text.substring(lastIndex));
    return parts.length > 0 ? parts : text;
  };

  const handleBubbleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    ask(question);
    setQuestion("");
  };

  const renderBubbleMessages = () => {
    const lastTwo = messages.slice(-2);
    if (lastTwo.length === 0) {
      return (
        <p style={{ margin: 0, fontSize: "11.5px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
          안녕하세요! 학사지원 AI <strong style={{ color: "var(--kmu-primary)" }}>국민이</strong>입니다.
          지도의 건물을 클릭해 조교를 만난 뒤 퀘스트를 수행해보세요! 🎓
        </p>
      );
    }
    return lastTwo.map((msg, index) => (
      <div
        key={index}
        style={{
          marginBottom: index === 0 && lastTwo.length > 1 ? "6px" : "0",
          borderBottom: index === 0 && lastTwo.length > 1 ? "1px dashed rgba(15,61,122,0.1)" : "none",
          paddingBottom: index === 0 && lastTwo.length > 1 ? "6px" : "0",
        }}
      >
        <strong
          style={{
            color: msg.role === "user" ? "var(--kmu-primary)" : "var(--kmu-gold-dark)",
            fontSize: "10px",
            display: "block",
            marginBottom: "2px",
            fontWeight: 800,
          }}
        >
          {msg.role === "user" ? "나 (학생)" : "국민이 AI"}
        </strong>
        <span style={{ fontSize: "11.5px", color: "var(--text-primary)", lineHeight: "1.5" }}>
          {renderMessageText(msg.text)}
        </span>
      </div>
    ));
  };

  // ESC로 모달 닫기
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setShowActionModal(false);
        setShowEncyclopediaModal(false);
        setShowSecretLabModal(false);
        setShowProfileModal(false);
        setShowQuests(false);
        setShowGraduationCenter(false);
        setShowLevelUpModal(false);
        if (showConsole) setShowConsole(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showConsole]);

  return (
    <>
      {/* 배경 */}
      <div className="sky-bg">
        <div className="sky-cloud" style={{ top: "8%", left: "-5%", width: "140px", height: "48px", animationDuration: "28s" }} />
        <div className="sky-cloud" style={{ top: "22%", left: "30%", width: "200px", height: "65px", animationDelay: "-14s", animationDuration: "38s" }} />
        <div className="sky-cloud" style={{ top: "38%", left: "70%", width: "160px", height: "52px", animationDelay: "-26s", animationDuration: "48s" }} />
        <div className="sky-hill" />
        <div className="sky-hill-back" />
      </div>

      <div className="metaverse-game-container">
        <div className="metaverse-game-frame">
          {/* 타이틀 배너 */}
          <div className="metaverse-title-banner">
            <span className="metaverse-title-logo">🏫</span>
            <span>KMU 캠퍼스 생활 액션 에이전트</span>
            <span className="title-kmu-badge">AI</span>
          </div>

          <div className="viewport-wrapper">
            {/* 캠퍼스 맵 */}
            <CampusMap
              activeBuilding={activeBuilding}
              onBuildingSelect={(bId) => setActiveBuilding(bId)}
              quests={quests}
            />

            {/* 좌측 HUD 카드 (학생 프로필) */}
            <div
              className="hud-card-left"
              onClick={() => {
                setProfileDraft(studentContext);
                setShowProfileModal(true);
              }}
              title="내 학적 정보 설정"
              role="button"
              aria-label="학적 카드 열기"
            >
              <div className="hud-avatar-img">🧑‍🎓</div>
              <div className="hud-details-left">
                <div className="name">
                  {studentContext.status ? STATUS_LABELS[studentContext.status] : "학사"} 모험가
                </div>
                <div className="lvl-xp">
                  <span className="lvl">LV.{level}</span>
                  <div className="xp-mini-track">
                    <div className="xp-mini-fill" style={{ width: `${Math.min(xp % 100, 100)}%` }} />
                  </div>
                </div>
              </div>
            </div>

            {/* 우측 HUD 카드 (AI 봇) */}
            <div className="hud-card-right">
              <div className="hud-avatar-img">🦆</div>
              <div className="hud-details-right">
                <div className="bot-name">국민이 AI</div>
                <span className="bot-tag">학사 가이드</span>
              </div>
            </div>

            {/* 좌측 세로 메뉴 */}
            <div className="menu-vertical-left">
              <button
                type="button"
                className="menu-btn"
                data-title="홈"
                aria-label="홈"
                onClick={() => {
                  setActiveBuilding("admin");
                  setShowQuests(false);
                  setShowConsole(false);
                }}
              >🏠</button>
              <button
                type="button"
                className={`menu-btn ${showQuests ? "active" : ""}`}
                data-title="퀘스트"
                aria-label="퀘스트 보드"
                onClick={() => setShowQuests(!showQuests)}
              >📋</button>
              <button
                type="button"
                className="menu-btn"
                data-title="학적카드"
                aria-label="학적 카드"
                onClick={() => { setProfileDraft(studentContext); setShowProfileModal(true); }}
              >🎒</button>
              <button
                type="button"
                className={`menu-btn ${showConsole ? "active" : ""}`}
                data-title="대화기록"
                aria-label="대화 기록"
                onClick={() => setShowConsole(!showConsole)}
              >💬</button>
            </div>

            {/* 우측 세로 메뉴 — 패널 열리면 패널 너비만큼 안쪽으로 이동 */}
            <div
              className="menu-vertical-right"
              style={showConsole ? { right: "396px" } : {}}
            >
              <button
                type="button"
                className="menu-btn"
                data-title="서류함"
                aria-label="서류함"
                onClick={() => setShowActionModal(true)}
              >📂</button>
              <button
                type="button"
                className="menu-btn"
                data-title="대백과"
                aria-label="대백과"
                onClick={() => setShowEncyclopediaModal(true)}
              >📚</button>
              <button
                type="button"
                className="menu-btn"
                data-title="졸업센터"
                aria-label="졸업센터"
                onClick={() => setShowGraduationCenter(true)}
              >🎓</button>
              <button
                type="button"
                className="menu-btn"
                data-title="연구소"
                aria-label="연구소"
                onClick={() => setShowSecretLabModal(true)}
              >🧪</button>
            </div>

            {/* 레이더 미니맵 */}
            <div className="minimap-radar">
              <div className="radar-sweep" />
              <RadarMinimapSVG
                activeBuilding={activeBuilding}
                avatarPos={
                  activeBuilding && BUILDINGS[activeBuilding]
                    ? BUILDINGS[activeBuilding]
                    : { x: 450, y: 650 }
                }
              />
            </div>

            {/* 마스코트 + 말풍선 */}
            <div className="mascot-container">
              <div className="mascot-speech-bubble">
                <div className="bubble-message-area" ref={bubbleScrollRef}>
                  {loading && messages.length > 0 && messages[messages.length - 1].role === "user" ? (
                    <div className="rpg-loading-dots" style={{ padding: "8px 0" }}>
                      <span /><span /><span />
                    </div>
                  ) : (
                    renderBubbleMessages()
                  )}
                </div>

                {messages.length === 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "5px", margin: "6px 0 2px" }}>
                    {currentExamples.slice(0, 2).map((ex, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => ask(ex)}
                        disabled={loading}
                        style={{
                          padding: "3px 9px",
                          fontSize: "9.5px",
                          borderRadius: "var(--radius-full)",
                          background: "rgba(15,61,122,0.07)",
                          border: "1px solid rgba(15,61,122,0.18)",
                          color: "var(--kmu-primary)",
                          cursor: "pointer",
                          fontWeight: 700,
                          fontFamily: "var(--font-sans)",
                        }}
                      >
                        🎯 {ex}
                      </button>
                    ))}
                  </div>
                )}

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
                    aria-label="질문 입력"
                  />
                  <button
                    type="submit"
                    className="bubble-send-btn"
                    disabled={loading || !question.trim()}
                    aria-label="전송"
                  >
                    ➤
                  </button>
                </form>

                {privacyWarnings.length > 0 && (
                  <div className="privacy-warn-text">
                    ⚠️ {privacyWarnings.join(", ")} 감지됨. 실제 정보는 빼고 물어보세요.
                  </div>
                )}

                <div className="bubble-log-link">
                  <span onClick={() => setShowConsole(true)}>
                    💬 상세 답변 기록 보기
                  </span>
                </div>
              </div>

              <div
                className="mascot-character"
                onClick={() => setShowConsole(true)}
                title="국민이 AI 조우"
                role="button"
                aria-label="대화 기록 열기"
              >
                <MascotSVG />
              </div>
            </div>

            {/* 슬라이딩 대화 기록 패널 */}
            <div className={`sliding-rpg-console ${showConsole ? "open" : ""}`}>
              <div className="console-header-bar">
                <h4>📜 학사 행정 대화 기록</h4>
                <button
                  type="button"
                  className="console-close-btn"
                  style={{ position: "relative", zIndex: 100 }}
                  onClick={(e) => { e.stopPropagation(); setShowConsole(false); }}
                  aria-label="대화 기록 닫기"
                >✕</button>
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

            {/* 퀘스트 보드 슬라이딩 */}
            <div className={`sliding-rpg-console--left ${showQuests ? "open" : ""}`}>
              <div className="console-header-bar">
                <h4>📋 퀘스트 보드 & NPC</h4>
                <button
                  type="button"
                  className="console-close-btn"
                  style={{ position: "relative", zIndex: 100 }}
                  onClick={(e) => { e.stopPropagation(); setShowQuests(false); }}
                  aria-label="퀘스트 보드 닫기"
                >✕</button>
              </div>
              <div className="console-scroll-body">
                <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
                  <QuestBoard
                    level={level}
                    xp={xp}
                    quests={quests}
                    activeBuilding={activeBuilding}
                    onStartAction={startAction}
                    onSelectBuilding={setActiveBuilding}
                    onSendChatMessage={ask}
                    onOpenEncyclopedia={() => setShowEncyclopediaModal(true)}
                    onOpenActionForm={() => setShowActionModal(true)}
                    studentContext={studentContext}
                    onOpenProfile={() => { setProfileDraft(studentContext); setShowProfileModal(true); }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 퀘스트 완료 알림 ── */}
      {questAlert && (
        <div className="quest-alert-banner">
          🏆 퀘스트 완료! <strong>{questAlert.title}</strong> +{questAlert.xp} XP
        </div>
      )}

      {/* ── 학적 카드 모달 ── */}
      {showProfileModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowProfileModal(false)}>
          <div className="rpg-modal-box" style={{ maxWidth: "460px" }} onClick={(e) => e.stopPropagation()}>
            <div className="rpg-modal-header">
              <h2>🎒 학적 카드 설정</h2>
              <button type="button" className="rpg-modal-close" onClick={() => setShowProfileModal(false)} aria-label="닫기">✕</button>
            </div>
            <div className="rpg-modal-body">
              <div className="profile-modal-content">
                <div className="privacy-notice-card">
                  <strong>🔒 개인정보 보호 안내</strong>
                  학번, 주민번호, 연락처, 포털 ID/PW, 성적표 원본은 입력하지 마세요.
                  이 설정은 브라우저에만 저장되며 서버로 전송되지 않습니다.
                </div>

                <div className="profile-field">
                  <label>학적 상태</label>
                  <select
                    value={profileDraft.status}
                    onChange={(e) => setProfileDraft({ ...profileDraft, status: e.target.value })}
                  >
                    {studentStatuses.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>

                <div className="profile-field">
                  <label>대상 학기 (예: 2026-1학기)</label>
                  <input
                    type="text"
                    value={profileDraft.term}
                    onChange={(e) => setProfileDraft({ ...profileDraft, term: e.target.value })}
                    placeholder="예: 2026-1학기"
                  />
                </div>

                <div className="profile-field">
                  <label>주요 관심 항목 (예: 출석, 수강신청)</label>
                  <input
                    type="text"
                    value={profileDraft.concern}
                    onChange={(e) => setProfileDraft({ ...profileDraft, concern: e.target.value })}
                    placeholder="예: 출석, 장학금"
                  />
                </div>

                <button
                  type="button"
                  className="profile-save-btn"
                  onClick={() => {
                    setStudentContext(profileDraft);
                    setShowProfileModal(false);
                  }}
                >
                  ✅ 저장하기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 서류함 모달 ── */}
      {showActionModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowActionModal(false)}>
          <div className="rpg-modal-box wide" style={{ maxHeight: "90vh" }} onClick={(e) => e.stopPropagation()}>
            <div className="rpg-modal-header">
              <h2>📂 스마트 서류 센터</h2>
              <button type="button" className="rpg-modal-close" onClick={() => setShowActionModal(false)} aria-label="닫기">✕</button>
            </div>
            <div className="rpg-modal-body" style={{ padding: 0, overflow: "hidden" }}>
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

      {/* ── 대백과 모달 ── */}
      {showEncyclopediaModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowEncyclopediaModal(false)}>
          <div className="rpg-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="rpg-modal-header">
              <h2>📚 공식 근거 대백과</h2>
              <button type="button" className="rpg-modal-close" onClick={() => setShowEncyclopediaModal(false)} aria-label="닫기">✕</button>
            </div>
            <div className="rpg-modal-body">
              <SourcePanel citations={citations} />
            </div>
          </div>
        </div>
      )}

      {/* ── 연구소 모달 ── */}
      {showSecretLabModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowSecretLabModal(false)}>
          <div className="rpg-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="rpg-modal-header">
              <h2>🧪 연구소 — 처리 상태 & 관리자</h2>
              <button type="button" className="rpg-modal-close" onClick={() => setShowSecretLabModal(false)} aria-label="닫기">✕</button>
            </div>
            <div className="rpg-modal-body">
              <div className="secret-lab-content">
                {/* 설정 토글 */}
                <div className="lab-section">
                  <h4>⚙️ 연동 설정</h4>
                  <div className="lab-toggle-row">
                    <div>
                      <div className="lab-toggle-label">공식 사이트 실시간 대조</div>
                      <div className="lab-toggle-sub">답변 시 공식 URL에서 최신 내용 확인</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={liveCheck}
                        onChange={(e) => setLiveCheck(e.target.checked)}
                      />
                      <span className="toggle-slider" />
                    </label>
                  </div>
                  <div className="lab-toggle-row">
                    <div>
                      <div className="lab-toggle-label">GPT 보조</div>
                      <div className="lab-toggle-sub">LLM을 활용해 답변 품질 향상</div>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={llmAssist}
                        onChange={(e) => setLlmAssist(e.target.checked)}
                      />
                      <span className="toggle-slider" />
                    </label>
                  </div>
                </div>

                {/* 처리 상태 */}
                <div className="lab-section">
                  <h4>📊 처리 상태</h4>
                  <ProcessingStatusPanel
                    liveCheckStatus={liveCheckStatus}
                    llmStatus={llmStatus}
                    answerValidation={answerValidation}
                    outputPrivacy={outputPrivacy}
                  />
                </div>

                {/* 도구 로그 */}
                <div className="lab-section">
                  <h4>🔧 Tool Calling 로그</h4>
                  <ToolLogPanel toolLogs={toolLogs} />
                </div>

                {/* 관리자 */}
                <div className="lab-section">
                  <h4>🛡 관리자 대시보드</h4>
                  <AdminDashboard apiBase={API_BASE} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 졸업센터 모달 ── */}
      {showGraduationCenter && (
        <div className="rpg-modal-overlay" onClick={() => setShowGraduationCenter(false)}>
          <div className="rpg-modal-box wide" style={{ maxHeight: "90vh" }} onClick={(e) => e.stopPropagation()}>
            <div className="rpg-modal-header">
              <h2>🎓 졸업 센터</h2>
              <button type="button" className="rpg-modal-close" onClick={() => setShowGraduationCenter(false)} aria-label="닫기">✕</button>
            </div>
            <div className="rpg-modal-body" style={{ padding: "16px 20px" }}>
              <GraduationCenter
                apiBase={API_BASE}
                onClose={() => setShowGraduationCenter(false)}
                hideHeader
              />
            </div>
          </div>
        </div>
      )}

      {/* ── 레벨업 모달 ── */}
      {showLevelUpModal && (
        <div className="rpg-modal-overlay" onClick={() => setShowLevelUpModal(false)}>
          <div className="levelup-modal-box" onClick={(e) => e.stopPropagation()}>
            <span className="levelup-emoji">🎉</span>
            <div className="levelup-title">LEVEL UP! LV.{level}</div>
            <div className="levelup-desc">{levelUpTitle}</div>
            <button
              type="button"
              className="levelup-close-btn"
              onClick={() => setShowLevelUpModal(false)}
            >
              계속하기 →
            </button>
          </div>
        </div>
      )}
    </>
  );
}

const container = document.getElementById("root");
const root = createRoot(container);
root.render(<App />);
