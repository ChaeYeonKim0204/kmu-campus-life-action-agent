import React from "react";

// KMU Buildings configuration
export const BUILDINGS = {
  admin: {
    id: "admin",
    name: "본부관 (본관)",
    desc: "학사지원팀, 총무팀, 종합인재개발원",
    npc: "학사지원 조교님",
    questId: "quest_attendance",
    questDesc: "출석 인정 신청서 작성 퀘스트",
    x: 510,
    y: 430,
    color: "#4f46e5"
  },
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
  ecampus: {
    id: "ecampus",
    name: "이캠퍼스 센터 (정보통신처)",
    desc: "E-Campus 서버실, 스마트 강의실 장애 처리",
    npc: "이캠퍼스 헬프데스크",
    questId: "quest_ecampus_sync",
    questDesc: "온라인 대외 연동 퀘스트",
    x: 430,
    y: 280,
    color: "#ec4899"
  },
  bugak: {
    id: "bugak",
    name: "북악관",
    desc: "인문대학, 사회과학대학, 조교실, 일반 강의실",
    npc: "북악 조교",
    questId: null,
    questDesc: "행정 규정 질의응답",
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
  }
};

export default function CampusMap({ activeBuilding, onBuildingSelect, quests }) {
  const [avatarPos, setAvatarPos] = React.useState({ x: 450, y: 650 }); // Start at Main Field
  const [isMoving, setIsMoving] = React.useState(false);
  const [hoveredBuilding, setHoveredBuilding] = React.useState(null);

  React.useEffect(() => {
    if (activeBuilding && BUILDINGS[activeBuilding]) {
      const { x, y } = BUILDINGS[activeBuilding];
      setIsMoving(true);
      setAvatarPos({ x, y });
      const timer = setTimeout(() => setIsMoving(false), 800); // Match CSS transition duration
      return () => clearTimeout(timer);
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
        <svg viewBox="0 0 1000 800" className="kmu-isometric-svg" preserveAspectRatio="xMinYMid meet">
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

          {/* Main Campus Roads (Asphalt walkways connecting buildings) */}
          {/* Path from Field to Admin */}
          <path d="M 450,650 Q 500,580 510,480" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="12" strokeLinecap="round" />
          {/* Path from Admin to Library */}
          <path d="M 510,480 Q 620,430 710,380" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="10" strokeLinecap="round" />
          {/* Path from Admin to Union */}
          <path d="M 510,480 Q 400,510 310,580" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="10" strokeLinecap="round" />
          {/* Path from Admin to E-Campus */}
          <path d="M 510,480 Q 480,380 430,300" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="8" strokeLinecap="round" />
          {/* Path from Admin to Bugak */}
          <path d="M 510,480 L 610,580" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="8" strokeLinecap="round" />
          {/* Path from Bugak to Engineering */}
          <path d="M 610,580 L 810,530" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="8" strokeLinecap="round" />

          {/* Dashed Center lines for roads */}
          <path d="M 450,650 Q 500,580 510,480" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />
          <path d="M 510,480 Q 620,430 710,380" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />
          <path d="M 510,480 Q 400,510 310,580" fill="none" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="1.5" strokeDasharray="4,4" />

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
            className={`map-avatar ${isMoving ? "avatar-walking" : ""}`}
            style={{ transition: "transform 0.8s cubic-bezier(0.25, 1, 0.5, 1)" }}
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
