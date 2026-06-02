import React from "react";

// KMU Buildings configuration
export const BUILDINGS = {
  union: {
    id: "union",
    name: "복지관",
    desc: "종합민원실, 학생식당, 편의시설, 동아리방",
    npc: "종합민원실 주임님",
    questId: "quest_leave_absence",
    questDesc: "휴학/복학 신청 마스터 퀘스트",
    x: 310,
    y: 580,
    color: "#0891b2"
  },
  library: {
    id: "library",
    name: "성곡도서관",
    desc: "도서 대출, 열람실, 모바일 학생증 인증 데스크",
    npc: "성곡도서관 사서님",
    questId: "quest_library_id",
    questDesc: "모바일 학생증 오류 해결 퀘스트",
    x: 710,
    y: 350,
    color: "#eab308"
  },
  bugak: {
    id: "bugak",
    name: "북악관",
    desc: "인문대학, 사회과학대학, 조교실, 일반 강의실",
    npc: "북악관 조교님",
    questId: "quest_attendance",
    questDesc: "출석 인정 신청서 작성 퀘스트",
    x: 610,
    y: 580,
    color: "#10b981"
  },
  engineering: {
    id: "engineering",
    name: "공학관",
    desc: "창의공과대학, 소프트웨어학부, 행정실",
    npc: "공학관 행정직원",
    questId: "quest_graduation_center",
    questDesc: "성적증명서 기반 졸업 센터 진단",
    x: 770,
    y: 530,
    color: "#f97316"
  },
  gyeongsang: {
    id: "gyeongsang",
    name: "경상관",
    desc: "경상대학, 교학팀, 경제학과/경영학과 강의실",
    npc: "경상관 행정실장",
    questId: null,
    questDesc: "행정 규정 질의응답",
    x: 190,
    y: 450,
    color: "#f59e0b"
  },
  business: {
    id: "business",
    name: "경영관",
    desc: "경영대학, 경영전문대학원, 일체형 강의실 및 경상홀",
    npc: "경영대 교학팀 조교",
    questId: null,
    questDesc: "경영대학 학사 안내",
    x: 140,
    y: 380,
    color: "#f59e0b"
  },
  chohyung: {
    id: "chohyung",
    name: "조형관",
    desc: "조형대학, 디자인학부 실습실 및 전시실",
    npc: "조형관 조교님",
    questId: null,
    questDesc: "실습실 대여 규정 문의",
    x: 330,
    y: 380,
    color: "#a855f7"
  },
  art: {
    id: "art",
    name: "예술관",
    desc: "예술대학, 음악/미술/공연예술 전공 연습실 및 극장",
    npc: "예술관 관리인",
    questId: null,
    questDesc: "연습실 대관 절차 문의",
    x: 650,
    y: 220,
    color: "#ec4899"
  },
  science: {
    id: "science",
    name: "과학관",
    desc: "자연과학대학, 산림과학대학, 공동기기실, 실험실",
    npc: "과학관 연구원",
    questId: null,
    questDesc: "실험실 안전 수칙 확인",
    x: 850,
    y: 420,
    color: "#14b8a6"
  },
  international: {
    id: "international",
    name: "국제관",
    desc: "글로벌인문·지역대학, 어학원, 외국인 지원 센터",
    npc: "국제교류팀 직원",
    questId: "quest_ecampus_sync",
    questDesc: "온라인 대외 연동 퀘스트",
    x: 250,
    y: 300,
    color: "#6366f1"
  },
  gym: {
    id: "gym",
    name: "체육관",
    desc: "체육대학, 체력단련실, 대강당, 운동시설",
    npc: "체육관 관리 요원",
    questId: null,
    questDesc: "체육시설 이용 수칙 문의",
    x: 130,
    y: 580,
    color: "#3b82f6"
  },
  dormitory: {
    id: "dormitory",
    name: "생활관 (기숙사)",
    desc: "교내 생활관, 행정실, 체력단련실, 세탁실",
    npc: "생활관 사감님",
    questId: null,
    questDesc: "기숙사 통금 및 입사 규정 문의",
    x: 900,
    y: 600,
    color: "#06b6d4"
  }
};

export default function CampusMap({ activeBuilding, onBuildingSelect, quests }) {
  const [avatarPos, setAvatarPos] = React.useState({ x: 450, y: 650 }); // Start at Main Field
  const [hoveredBuilding, setHoveredBuilding] = React.useState(null);

  React.useEffect(() => {
    if (activeBuilding && BUILDINGS[activeBuilding]) {
      const { x, y } = BUILDINGS[activeBuilding];
      setAvatarPos({ x, y });
    }
  }, [activeBuilding]);

  const handleMapClick = (e) => {
    // Click on empty space could clear selection or do nothing
  };

  const getQuestStatus = (buildingId) => {
    const b = BUILDINGS[buildingId];
    if (!b || !b.questId) return null;
    const q = quests.find(item => item.id === b.questId);
    return q ? q.status : null;
  };

  return (
    <div className="campus-map-wrapper" style={{ border: "none", background: "transparent", padding: 0, boxShadow: "none", width: "100%", height: "100%", borderRadius: 0 }}>
      <div className="map-viewport" style={{ marginTop: 0 }} onClick={handleMapClick}>
        <svg viewBox="0 0 1000 800" className="kmu-isometric-svg" preserveAspectRatio="xMidYMid meet">
          {/* Defs for gradients/shadows */}
          <defs>
            <radialGradient id="field-grad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#047857" stopOpacity="0.4" />
            </radialGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="building-shadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="5" dy="15" stdDeviation="5" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Base Grid / Grass land */}
          <polygon points="500,50 950,350 950,700 500,780 50,700 50,350" fill="rgba(16, 185, 129, 0.08)" stroke="rgba(16, 185, 129, 0.2)" strokeWidth="2" />
          
          {/* Main Field (대운동장) */}
          <ellipse cx="450" cy="650" rx="140" ry="60" fill="url(#field-grad)" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
          <ellipse cx="450" cy="650" rx="100" ry="40" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1" strokeDasharray="5,5" />
          <line x1="450" y1="590" x2="450" y2="710" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />

          {/* Main Campus Roads (Asphalt walkways connecting active buildings) */}
          {/* Left side connections */}
          <path d="M 450,650 Q 380,620 310,580" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="12" strokeLinecap="round" />
          <path d="M 310,580 L 130,580" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="10" strokeLinecap="round" />
          <path d="M 310,580 L 330,380" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="10" strokeLinecap="round" />
          <path d="M 330,380 L 250,300" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 310,580 Q 250,515 190,450" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 190,450 L 140,380" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 140,380 L 250,300" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 130,580 L 190,450" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />

          {/* Right side connections */}
          <path d="M 450,650 Q 530,620 610,580" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="12" strokeLinecap="round" />
          <path d="M 610,580 L 770,530" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="10" strokeLinecap="round" />
          <path d="M 610,580 Q 660,465 710,350" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="10" strokeLinecap="round" />
          <path d="M 770,530 L 850,420" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 850,420 L 710,350" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 710,350 L 650,220" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />
          <path d="M 770,530 Q 835,565 900,600" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeLinecap="round" />

          {/* Dashed Center lines for roads */}
          <path d="M 450,650 Q 380,620 310,580" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />
          <path d="M 450,650 Q 530,620 610,580" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />
          <path d="M 310,580 Q 250,515 190,450" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />
          <path d="M 610,580 Q 660,465 710,350" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />

          {/* Campus Decorative Trees */}
          {[[200, 480], [250, 420], [380, 450], [580, 360], [640, 400], [530, 530], [670, 480], [750, 450], [880, 580]].map(([tx, ty], idx) => (
            <g key={`tree-${idx}`} opacity="0.8">
              <ellipse cx={tx} cy={ty + 8} rx="10" ry="4" fill="rgba(0,0,0,0.2)" />
              <polygon points={`${tx},${ty - 15} ${tx - 8},${ty + 5} ${tx + 8},${ty + 5}`} fill="#065f46" />
              <polygon points={`${tx},${ty - 25} ${tx - 6},${ty - 5} ${tx + 6},${ty - 5}`} fill="#047857" />
              <rect x={tx - 1.5} y={ty + 5} width="3" height="5" fill="#78350f" />
            </g>
          ))}

          {/* Render Buildings */}
          {Object.values(BUILDINGS).map((b) => {
            const bx = b.x;
            const by = b.y;
            const isSelected = activeBuilding === b.id;
            const isHovered = hoveredBuilding === b.id;
            const qStatus = getQuestStatus(b.id);

            return (
              <g
                key={b.id}
                className="map-building-group"
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredBuilding(b.id)}
                onMouseLeave={() => setHoveredBuilding(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  onBuildingSelect(b.id);
                }}
                filter={isSelected || isHovered ? "url(#glow)" : "url(#building-shadow)"}
              >
                {/* Building Floor/Base shadow */}
                <polygon
                  points={`${bx - 60},${by} ${bx},${by + 30} ${bx + 60},${by} ${bx},${by - 30}`}
                  fill="rgba(0,0,0,0.15)"
                />

                {/* 3D Isometric building box */}
                {/* Left side face */}
                <polygon
                  points={`${bx - 40},${by - 40} ${bx - 40},${by + 10} ${bx},${by + 30} ${bx},${by - 20}`}
                  fill={isSelected ? "#1e40af" : isHovered ? "#2b3b5c" : "#1e293b"}
                  stroke="rgba(255,255,255,0.08)"
                />
                {/* Right side face */}
                <polygon
                  points={`${bx},${by - 20} ${bx},${by + 30} ${bx + 40},${by + 10} ${bx + 40},${by - 40}`}
                  fill={isSelected ? "#3b82f6" : isHovered ? "#3d5480" : "#2d3748"}
                  stroke="rgba(255,255,255,0.08)"
                />
                {/* Top roof face */}
                <polygon
                  points={`${bx - 40},${by - 40} ${bx},${by - 20} ${bx + 40},${by - 40} ${bx},${by - 60}`}
                  fill={isSelected ? "#60a5fa" : isHovered ? b.color : "#4a5568"}
                  stroke="rgba(255,255,255,0.15)"
                />

                {/* Accent Stripes / Windows on Right Wall */}
                {[-10, 0, 10].map((dy) => (
                  <g key={`win-${b.id}-${dy}`}>
                    <polygon
                      points={`${bx + 12},${by + dy - 18} ${bx + 12},${by + dy - 10} ${bx + 22},${by + dy - 15} ${bx + 22},${by + dy - 23}`}
                      fill={isSelected ? "#93c5fd" : "rgba(255,255,255,0.2)"}
                    />
                    <polygon
                      points={`${bx + 26},${by + dy - 25} ${bx + 26},${by + dy - 17} ${bx + 36},${by + dy - 22} ${bx + 36},${by + dy - 30}`}
                      fill={isSelected ? "#93c5fd" : "rgba(255,255,255,0.2)"}
                    />
                  </g>
                ))}

                {/* Accent Stripes / Windows on Left Wall */}
                {[-10, 0, 10].map((dy) => (
                  <g key={`win-l-${b.id}-${dy}`}>
                    <polygon
                      points={`${bx - 22},${by + dy - 23} ${bx - 22},${by + dy - 15} ${bx - 12},${by + dy - 10} ${bx - 12},${by + dy - 18}`}
                      fill={isSelected ? "#93c5fd" : "rgba(255,255,255,0.15)"}
                    />
                    <polygon
                      points={`${bx - 36},${by + dy - 30} ${bx - 36},${by + dy - 22} ${bx - 26},${by + dy - 17} ${bx - 26},${by + dy - 25}`}
                      fill={isSelected ? "#93c5fd" : "rgba(255,255,255,0.15)"}
                    />
                  </g>
                ))}

                {/* Building Entrance Door (front center) */}
                <polygon
                  points={`${bx - 10},${by + 13} ${bx - 10},${by + 25} ${bx + 10},${by + 25} ${bx + 10},${by + 13}`}
                  fill={isSelected ? "#60a5fa" : "#0f172a"}
                  stroke="rgba(255,255,255,0.3)"
                />

                {/* Bouncing Quest Pointer/Pin above the building if it's the active building or quest target */}
                {qStatus === "active" && (
                  <g className="bouncing-quest-pin" transform={`translate(${bx}, ${by - 100})`}>
                    {/* Golden pin */}
                    <path
                      d="M-8,-16 C-8,-26 8,-26 8,-16 C8,-8 0,0 0,0 C0,0 -8,-8 -8,-16 Z"
                      fill="#f59e0b"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                    <circle cx="0" cy="-16" r="3.5" fill="#ffffff" />
                  </g>
                )}

                {/* Label Tag (Floating above building) */}
                <g transform={`translate(${bx}, ${by - 80})`}>
                  {/* Backdrop flag */}
                  <rect
                    x="-65"
                    y="-12"
                    width="130"
                    height="24"
                    rx="6"
                    fill={isSelected ? "rgba(37, 99, 235, 0.9)" : "rgba(15, 23, 42, 0.8)"}
                    stroke={isSelected ? "#60a5fa" : "rgba(255,255,255,0.2)"}
                    strokeWidth="1.5"
                  />
                  <text
                    textAnchor="middle"
                    y="4"
                    fill="#ffffff"
                    fontSize="11"
                    fontWeight="700"
                  >
                    {b.name}
                  </text>

                  {/* Quest status badge inside the label if available */}
                  {qStatus && (
                    <g transform="translate(55, -8)">
                      <circle
                        r="9"
                        fill={
                          qStatus === "completed"
                            ? "#10b981"
                            : qStatus === "active"
                            ? "#f59e0b"
                            : "#94a3b8"
                        }
                        stroke="#ffffff"
                        strokeWidth="1"
                      />
                      <text
                        textAnchor="middle"
                        y="3"
                        fill="#ffffff"
                        fontSize="9"
                        fontWeight="900"
                      >
                        {qStatus === "completed" ? "✓" : qStatus === "active" ? "!" : "?"}
                      </text>
                    </g>
                  )}
                </g>
              </g>
            );
          })}

          {/* Student Avatar (🏃) */}
          <g
            transform={`translate(${avatarPos.x}, ${avatarPos.y})`}
            className="map-avatar"
          >
            {/* Avatar Shadow */}
            <ellipse cx="0" cy="18" rx="14" ry="6" fill="rgba(0,0,0,0.4)" />
            
            {/* Glowing circle ring */}
            <circle
              r="22"
              fill="none"
              stroke="#60a5fa"
              strokeWidth="2.5"
              strokeDasharray="6,4"
              className="avatar-ring"
            />
            
            {/* Avatar Body representation (clean capsule / character style) */}
            <rect
              x="-8"
              y="-18"
              width="16"
              height="28"
              rx="8"
              fill="#2563eb"
              stroke="#ffffff"
              strokeWidth="2"
            />
            
            {/* Academic Cap on top */}
            <path
              d="M -13,-18 L 0,-24 L 13,-18 L 0,-12 Z"
              fill="#1e293b"
              stroke="#ffffff"
              strokeWidth="1"
            />
            <rect x="-3" y="-17" width="6" height="5" fill="#1e293b" />
            <line x1="8" y1="-18" x2="11" y2="-10" stroke="#f59e0b" strokeWidth="1" />
            <circle cx="11" cy="-9" r="1.5" fill="#f59e0b" />

            {/* Glowing inner core */}
            <circle cx="0" cy="-2" r="5" fill="#60a5fa" />
            
            {/* Tag label */}
            <g transform="translate(0, 32)">
              <rect x="-24" y="-8" width="48" height="15" rx="4" fill="#ef4444" stroke="#ffffff" strokeWidth="1" />
              <text textAnchor="middle" y="3" fill="#ffffff" fontSize="9" fontWeight="800">나</text>
            </g>
          </g>
        </svg>
      </div>

      {hoveredBuilding && BUILDINGS[hoveredBuilding] && (
        <div className="map-tooltip">
          <h4>{BUILDINGS[hoveredBuilding].name}</h4>
          <p className="tooltip-desc">{BUILDINGS[hoveredBuilding].desc}</p>
          {BUILDINGS[hoveredBuilding].questId && (
            <div className="tooltip-quest">
              <span className="quest-label">Quest</span>
              <span className="quest-name">{BUILDINGS[hoveredBuilding].questDesc}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
