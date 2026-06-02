import React from "react";

const SLOT_LABELS = {
  event_date: "결석/훈련 일자",
  absence_reason: "결석 사유",
  course_name: "대상 교과목명",
  instructor_name_optional: "담당 교강사",
  evidence_document_type: "증빙 서류명",
  planned_submission_date: "제출 예정일",
  leave_type: "휴학 신청 유형",
  target_semester: "대상 학기",
  evidence_document_type_optional: "제출 증빙 서류",
  current_leave_type_optional: "현재 휴학 유형",
  concern: "관심 항목",
  certificate_type: "증명서 종류",
  purpose_optional: "사용 목적",
  card_type: "학생증 유형",
  student_status_optional: "학적 상태",
  scholarship_type: "장학 유형",
  target_semester_optional: "대상 학기",
  service_name: "대상 서비스",
  problem_summary: "문제 증상 요약",
  target_period: "대상 기간",
  concern_optional: "상세 관심사",
  correction_item: "학적 정정 항목",
  reason_optional: "정정 사유",
  incident_type: "사고/상해 유형",
  incident_date_optional: "사고 발생일",
  military_topic: "예비군/병무 주제",
  class_absence_optional: "공결 신청 여부",
  total_credits: "총 이수 학점",
  major_credits: "전공 이수 학점",
  target_total_credits_optional: "총 졸업 기준학점",
  target_major_credits_optional: "전공 졸업 기준학점",
  interests_optional: "관심 학문 분야",
  total_credit_gap: "부족 총 학점",
  major_credit_gap: "부족 전공 학점",
  topic: "문의 주제",
  destination_optional: "수신 부서",
  question_summary: "문의 요약 내용"
};

const PREVIEW_NAME = "이름 미기입";
const PREVIEW_STUDENT_ID = "학번 미기입";
const PREVIEW_APPLICANT = "본인 서명";

export default function ActionForm({
  actions,
  actionState,
  slots,
  setSlots,
  onStart,
  onContinue,
  savedDocuments = [],
  setSavedDocuments
}) {
  const [errors, setErrors] = React.useState({});
  const [activeTab, setActiveTab] = React.useState("form");
  const [selectedSavedDocId, setSelectedSavedDocId] = React.useState(null);

  React.useEffect(() => {
    setErrors({});
    setActiveTab("form");
    if (actionState) {
      setSelectedSavedDocId(null);
    }
  }, [actionState]);

  const handleContinue = () => {
    const missing = actionState?.missing_slots || [];
    const newErrors = {};
    let hasError = false;
    missing.forEach((slot) => {
      if (!slots[slot] || !slots[slot].trim()) {
        newErrors[slot] = true;
        hasError = true;
      }
    });
    setErrors(newErrors);
    if (!hasError) {
      onContinue();
      if (window.innerWidth <= 1024) {
        setActiveTab("preview");
      }
    }
  };

  // Helper to render high-fidelity A4 document preview based on action type
  const renderA4Document = () => {
    let currentActionId = null;
    let currentLabel = "";
    let currentSlots = {};
    let isSaved = false;

    if (actionState) {
      currentActionId = actionState.action_id;
      currentLabel = actionState.label;
      currentSlots = slots;
    } else if (selectedSavedDocId) {
      const savedDoc = savedDocuments.find((d) => d.id === selectedSavedDocId);
      if (savedDoc) {
        currentActionId = savedDoc.action_id;
        currentLabel = savedDoc.label;
        currentSlots = savedDoc.slots;
        isSaved = true;
      }
    }

    if (!currentActionId) {
      return (
        <div className="a4-document-paper" style={{ justifyContent: "center", alignItems: "center", minHeight: "480px" }}>
          <div className="a4-logo" style={{ marginBottom: "20px" }}>
            <span className="a4-logo-icon">🏫</span>
            <span>KOOKMIN UNIVERSITY</span>
          </div>
          <p className="muted" style={{ textAlign: "center", fontSize: "12px", color: "#64748b" }}>
            선택된 학사 행정 문서가 없습니다.<br />
            왼쪽 패널에서 업무 시작 버튼을 누르거나<br />
            저장된 서류 보관함의 서류를 선택하세요.
          </p>
        </div>
      );
    }

    if (currentActionId === "draft_attendance_recognition_form") {
      return (
        <div className="a4-document-paper">
          <div className="a4-header">
            <div className="a4-logo">
              <span className="a4-logo-icon">🏫</span>
              <span>KOOKMIN UNIVERSITY</span>
            </div>
            <span className="a4-version">서식 제2호</span>
          </div>
          <div className="a4-title">출 석 인 정 신 신청 서</div>
          
          <table className="a4-table">
            <tbody>
              <tr>
                <th>성 명</th>
                <td>{PREVIEW_NAME}</td>
                <th>학 번</th>
                <td>{PREVIEW_STUDENT_ID}</td>
              </tr>
              <tr>
                <th>대상 교과목</th>
                <td className={currentSlots.course_name ? "filled-val" : ""}>{currentSlots.course_name || "(미입력)"}</td>
                <th>담당 교강사</th>
                <td className={currentSlots.instructor_name_optional ? "filled-val" : ""}>{currentSlots.instructor_name_optional || "(미입력)"}</td>
              </tr>
              <tr>
                <th>결석/훈련일</th>
                <td className={currentSlots.event_date ? "filled-val" : ""} colSpan="3">{currentSlots.event_date || "(미입력)"}</td>
              </tr>
              <tr>
                <th>결석 사유</th>
                <td className={currentSlots.absence_reason ? "filled-val" : ""} colSpan="3">{currentSlots.absence_reason || "(미입력)"}</td>
              </tr>
              <tr>
                <th>증빙 서류</th>
                <td className={currentSlots.evidence_document_type ? "filled-val" : ""} colSpan="3">{currentSlots.evidence_document_type || "(미입력)"}</td>
              </tr>
              <tr>
                <th>제출 예정일</th>
                <td className={currentSlots.planned_submission_date ? "filled-val" : ""} colSpan="3">{currentSlots.planned_submission_date || "(미입력)"}</td>
              </tr>
            </tbody>
          </table>

          <div className="a4-body-text">
            위 사유로 인하여 해당 교과목에 결석하였기에 증빙서류를 첨부하여 출석 인정을 신청하오니 승인하여 주시기 바랍니다.
          </div>

          <div className="a4-footer">
            <div className="a4-signature">
              <span>신청일: {currentSlots.planned_submission_date || "2026년   월   일"}</span>
              <span>신청인: {isSaved ? "홍길동 (서명완료 ✍️)" : PREVIEW_APPLICANT} <span className="sig-line"></span> (인)</span>
            </div>
            <div className={`a4-stamp-box ${isSaved ? "issued" : ""}`}>
              {isSaved ? "발급완료\n(직인)" : <>국민대학교<br />교무처인</>}
            </div>
          </div>
        </div>
      );
    }

    if (currentActionId === "draft_leave_checklist" || currentActionId === "draft_return_checklist") {
      const isLeave = currentActionId === "draft_leave_checklist";
      return (
        <div className="a4-document-paper">
          <div className="a4-header">
            <div className="a4-logo">
              <span className="a4-logo-icon">🏫</span>
              <span>KOOKMIN UNIVERSITY</span>
            </div>
            <span className="a4-version">행정 체크리스트</span>
          </div>
          <div className="a4-title">{isLeave ? "휴 학" : "복 학"} 신청 자가 체크리스트</div>
          
          <table className="a4-table">
            <tbody>
              <tr>
                <th>성 명</th>
                <td>{PREVIEW_NAME}</td>
                <th>학 번</th>
                <td>{PREVIEW_STUDENT_ID}</td>
              </tr>
              <tr>
                <th>대상 학기</th>
                <td className={currentSlots.target_semester ? "filled-val" : ""} colSpan="3">{currentSlots.target_semester || "(미입력)"}</td>
              </tr>
              {isLeave ? (
                <tr>
                  <th>휴학 유형</th>
                  <td className={currentSlots.leave_type ? "filled-val" : ""}>{currentSlots.leave_type || "(미입력)"}</td>
                  <th>증빙 서류</th>
                  <td className={currentSlots.evidence_document_type_optional ? "filled-val" : ""}>{currentSlots.evidence_document_type_optional || "(미입력)"}</td>
                </tr>
              ) : (
                <tr>
                  <th>현재 휴학구분</th>
                  <td className={currentSlots.current_leave_type_optional ? "filled-val" : ""} colSpan="3">{currentSlots.current_leave_type_optional || "(미입력)"}</td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="a4-body-text" style={{ background: "#fdfdfd" }}>
            <strong style={{ fontSize: "11px", display: "block", marginBottom: "6px" }}>[제출 및 점검 필요 사항]</strong>
            <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "10px", display: "flex", flexDirection: "column", gap: "4px" }}>
              <li>[✓] ON국민 포털 {isLeave ? "휴학" : "복학"} 신청 메뉴 기입 여부</li>
              <li>{currentSlots.target_semester ? `[✓] 대상 학기(${currentSlots.target_semester}) 신청 완료` : "[ ] 대상 학기 확인"}</li>
              <li>{isLeave && currentSlots.evidence_document_type_optional && currentSlots.evidence_document_type_optional !== "없음" ? `[✓] 증빙 서류(${currentSlots.evidence_document_type_optional}) 지참 및 접수` : "[ ] 증빙 서류 지참 (해당 시)"}</li>
              <li>[ ] 도서관 연체 도서 반납 및 체납 수수료 정산</li>
              <li>[ ] 장학금 수혜 예정자의 경우 등록금 선납 처리 후 휴학 권장</li>
            </ul>
          </div>

          <div className="a4-footer" style={{ marginTop: "auto" }}>
            <div className="a4-signature">
              <span>작성일: 2026년   월   일</span>
              <span>확인자: 종합민원실 조교 <span className="sig-line"></span> (인)</span>
            </div>
            <div className={`a4-stamp-box ${isSaved ? "issued" : ""}`} style={{ borderColor: isSaved ? "#10b981" : "#0f3d7a", color: isSaved ? "#10b981" : "#0f3d7a" }}>
              {isSaved ? "발급완료\n(직인)" : <>종합민원<br />영수인</>}
            </div>
          </div>
        </div>
      );
    }

    if (currentActionId === "graduation_audit") {
      const tc = parseInt(currentSlots.total_credits || "0", 10);
      const mc = parseInt(currentSlots.major_credits || "0", 10);
      const targetTc = parseInt(currentSlots.target_total_credits_optional || "130", 10);
      const targetMc = parseInt(currentSlots.target_major_credits_optional || "60", 10);
      
      const tcPct = Math.min(Math.round((tc / targetTc) * 100), 100);
      const mcPct = Math.min(Math.round((mc / targetMc) * 100), 100);

      return (
        <div className="a4-document-paper">
          <div className="a4-header">
            <div className="a4-logo">
              <span className="a4-logo-icon">🏫</span>
              <span>KOOKMIN UNIVERSITY</span>
            </div>
            <span className="a4-version">졸업 자가진단</span>
          </div>
          <div className="a4-title">졸업요건 간이 진단 점검표</div>

          <table className="a4-table">
            <tbody>
              <tr>
                <th>성 명</th>
                <td>{PREVIEW_NAME}</td>
                <th>학 번</th>
                <td>{PREVIEW_STUDENT_ID}</td>
              </tr>
              <tr>
                <th>이수 총학점</th>
                <td className="filled-val">{tc} / {targetTc} 학점 ({tcPct}%)</td>
                <th>이수 전공학점</th>
                <td className="filled-val">{mc} / {targetMc} 학점 ({mcPct}%)</td>
              </tr>
            </tbody>
          </table>

          <div className="a4-body-text">
            <strong>[요건 충족 진단 결과]</strong>
            <div style={{ display: "grid", gap: "10px", marginTop: "8px" }}>
              <div>
                <span style={{ fontSize: "10px", display: "block", color: "#64748b" }}>총 이수학점 기준 잔여:</span>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ flex: 1, height: "8px", background: "#e2e8f0", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ width: `${tcPct}%`, height: "100%", background: tcPct >= 100 ? "#10b981" : "#3b82f6" }}></div>
                  </div>
                  <strong style={{ fontSize: "10.5px" }}>{targetTc - tc > 0 ? `${targetTc - tc}학점 부족` : "충족"}</strong>
                </div>
              </div>
              
              <div>
                <span style={{ fontSize: "10px", display: "block", color: "#64748b" }}>전공 이수학점 기준 잔여:</span>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ flex: 1, height: "8px", background: "#e2e8f0", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ width: `${mcPct}%`, height: "100%", background: mcPct >= 100 ? "#10b981" : "#f59e0b" }}></div>
                  </div>
                  <strong style={{ fontSize: "10.5px" }}>{targetMc - mc > 0 ? `${targetMc - mc}학점 부족` : "충족"}</strong>
                </div>
              </div>
            </div>
          </div>

          <div className="a4-footer">
            <div className="a4-signature">
              <span>진단일: 2026년   월   일</span>
              <span>신청인: {isSaved ? "홍길동 (서명완료 ✍️)" : PREVIEW_APPLICANT} <span className="sig-line"></span> (인)</span>
            </div>
            <div className={`a4-stamp-box ${isSaved ? "issued" : ""}`}>
              {isSaved ? "발급완료\n(직인)" : <>국민대학교<br />자가진단</>}
            </div>
          </div>
        </div>
      );
    }

    // Generic Action Document Layout
    return (
      <div className="a4-document-paper">
        <div className="a4-header">
          <div className="a4-logo">
            <span className="a4-logo-icon">🏫</span>
            <span>KOOKMIN UNIVERSITY</span>
          </div>
          <span className="a4-version">행정 서식</span>
        </div>
        <div className="a4-title" style={{ fontSize: "15px" }}>{currentLabel || "학사 행정 신청서"}</div>

        <table className="a4-table">
          <tbody>
            <tr>
              <th>신청인</th>
              <td>{PREVIEW_NAME}</td>
              <th>학적 구분</th>
              <td>재학생</td>
            </tr>
            {Object.keys(currentSlots).map((key) => {
              const label = SLOT_LABELS[key] || key;
              return (
                <tr key={key}>
                  <th>{label}</th>
                  <td className="filled-val" colSpan="3">{currentSlots[key] || "(미입력)"}</td>
                </tr>
              );
            })}
            {/* If no slots yet, render missing ones as placeholders */}
            {Object.keys(currentSlots).length === 0 && (actionState?.missing_slots || []).map((key) => {
              const label = SLOT_LABELS[key] || key;
              return (
                <tr key={key}>
                  <th>{label}</th>
                  <td style={{ color: "#94a3b8" }} colSpan="3">(왼쪽 패널에 값을 입력해 주세요)</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="a4-body-text">
          국민대학교 학사 행정 규정에 의거하여 상기 내용과 같이 민원 신청 및 서류 초안 작성을 신청합니다.
        </div>

        <div className="a4-footer">
          <div className="a4-signature">
            <span>신청일: 2026년   월   일</span>
            <span>신청인: {isSaved ? "홍길동 (서명완료 ✍️)" : PREVIEW_APPLICANT} <span className="sig-line"></span> (서명)</span>
          </div>
          <div className={`a4-stamp-box ${isSaved ? "issued" : ""}`}>
            {isSaved ? "발급완료\n(직인)" : <>국민대학교<br />학사정보</>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`document-hub-layout active-tab-${activeTab}`}>
      {/* Mobile Tabs Header */}
      <div className="document-hub-mobile-tabs">
        <button 
          type="button" 
          className={`mobile-tab-btn ${activeTab === "form" ? "active" : ""}`}
          onClick={() => setActiveTab("form")}
        >
          ✍️ 입력 양식 기입
        </button>
        <button 
          type="button" 
          className={`mobile-tab-btn ${activeTab === "preview" ? "active" : ""}`}
          onClick={() => setActiveTab("preview")}
          disabled={!actionState && !selectedSavedDocId}
          title={!actionState && !selectedSavedDocId ? "활성화된 서류 양식이 없습니다." : ""}
        >
          📄 서류 실시간 미리보기
        </button>
      </div>

      {/* Left panel: form actions & inputs */}
      <div className="document-hub-left">
        <h2 style={{ fontSize: "16px", color: "#f1f5f9", margin: "0 0 10px 0", textTransform: "none" }}>스마트 서류 센터</h2>
        
        {/* Next Actions Options when no active action */}
        {!actionState && (
          <div>
            <p className="muted" style={{ fontSize: "12.5px", marginBottom: "16px" }}>아래에서 시작할 학사 서류 업무를 선택해 양식 입력을 진행해 보세요.</p>
            {actions.length === 0 && (
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.1)", borderRadius: "8px", padding: "16px", textAlign: "center" }}>
                <p className="muted" style={{ margin: 0, fontSize: "12px" }}>질문 후 에이전트가 추천한 액션들이 여기에 표시됩니다.</p>
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {actions.map((action) => (
                <div 
                  className="item" 
                  key={action.action_id}
                  style={{ 
                    background: "rgba(255,255,255,0.04)", 
                    border: "1px solid rgba(255,255,255,0.08)", 
                    borderRadius: "10px", 
                    padding: "14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px"
                  }}
                >
                  <strong style={{ color: "#60a5fa", fontSize: "13px" }}>{action.label}</strong>
                  <p className="muted" style={{ margin: 0, fontSize: "11.5px" }}>{action.description}</p>
                  <button 
                    className="action" 
                    type="button" 
                    onClick={() => onStart(action.action_id)}
                    style={{ padding: "6px 12px", fontSize: "12px", alignSelf: "flex-end" }}
                  >
                    시작하기 ⚡
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Saved Documents Briefcase */}
        {!actionState && (
          <div style={{ marginTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "20px" }}>
            <h3 style={{ fontSize: "14px", color: "#10b981", margin: "0 0 12px 0", display: "flex", alignItems: "center", gap: "6px" }}>
              📁 작성된 서류 보관함
              <span style={{ fontSize: "11px", fontWeight: "normal", color: "#64748b", marginLeft: "auto" }}>
                {savedDocuments.length}개 보관됨
              </span>
            </h3>
            
            {savedDocuments.length === 0 ? (
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.05)", borderRadius: "8px", padding: "20px", textAlign: "center" }}>
                <p className="muted" style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>보관된 완료 서류가 없습니다. 서류 신청 완료 시 여기에 자동 저장됩니다.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "280px", overflowY: "auto", paddingRight: "4px" }}>
                {savedDocuments.map((doc) => {
                  const isSelected = selectedSavedDocId === doc.id;
                  return (
                    <div
                      key={doc.id}
                      onClick={() => {
                        setSelectedSavedDocId(isSelected ? null : doc.id);
                        if (!isSelected && window.innerWidth <= 1024) {
                          setActiveTab("preview");
                        }
                      }}
                      style={{
                        background: isSelected ? "rgba(16, 185, 129, 0.08)" : "rgba(255,255,255,0.03)",
                        border: isSelected ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(255,255,255,0.06)",
                        borderRadius: "8px",
                        padding: "10px 12px",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "10px",
                        transition: "all 0.2s ease"
                      }}
                      className="saved-doc-item"
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: isSelected ? "#10b981" : "#e2e8f0", fontSize: "12.5px", fontWeight: "600", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {doc.label}
                        </div>
                        <div style={{ fontSize: "10.5px", color: "#64748b", marginTop: "2px" }}>
                          {doc.date}
                        </div>
                      </div>
                      
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }} onClick={(e) => e.stopPropagation()}>
                        {/* Delete Button */}
                        <button
                          type="button"
                          onClick={() => {
                            if (confirm("정말로 이 서류를 삭제하시겠습니까?")) {
                              setSavedDocuments((prev) => prev.filter((d) => d.id !== doc.id));
                              if (selectedSavedDocId === doc.id) {
                                setSelectedSavedDocId(null);
                              }
                            }
                          }}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "#ef4444",
                            cursor: "pointer",
                            fontSize: "14px",
                            padding: "4px",
                            borderRadius: "4px"
                          }}
                          title="삭제"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Current Active Action form */}
        {actionState && (
          <div className="action-box" style={{ background: "none", border: "none", padding: 0, margin: 0 }}>
            <h3 style={{ fontSize: "14px", color: "#f59e0b", borderBottom: "1px dashed rgba(245, 158, 11, 0.2)", paddingBottom: "8px", marginBottom: "12px" }}>
              📝 {actionState.label || "서류 정보 기입"}
            </h3>
            
            {actionState.message && <p className="status" style={{ fontSize: "11px", padding: "6px 10px" }}>{actionState.message}</p>}
            {actionState.privacy_notice && <p className="status" style={{ fontSize: "11px", padding: "6px 10px", borderColor: "#f59e0b" }}>{actionState.privacy_notice}</p>}
            
            <div className="action-form" style={{ marginTop: "12px", gap: "14px" }}>
              {(actionState.missing_slots || []).map((slot, index) => (
                <label key={slot} style={{ color: "#94a3b8" }}>
                  <span style={{ fontSize: "12px", color: "#e2e8f0", fontWeight: "600", marginBottom: "4px" }}>
                    {actionState.questions?.[index] || SLOT_LABELS[slot] || slot}
                  </span>
                  <input
                    className={errors[slot] ? "input-error" : ""}
                    value={slots[slot] || ""}
                    onChange={(event) => {
                      setSlots({ ...slots, [slot]: event.target.value });
                      if (errors[slot]) {
                        setErrors({ ...errors, [slot]: false });
                      }
                    }}
                    placeholder={`${SLOT_LABELS[slot] || slot} 기입...`}
                    style={{ fontSize: "12.5px" }}
                  />
                  {errors[slot] && <span className="error-text">필수 입력 항목입니다.</span>}
                </label>
              ))}
              
              {actionState.status !== "unsupported" && (
                <div style={{ marginTop: "16px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "14px" }}>
                  <div className="auto-save-notice" style={{ marginBottom: "12px" }}>
                    🎒 작성 중인 초안이 자동 보존됩니다.
                  </div>
                  <button 
                    className="primary" 
                    type="button" 
                    onClick={handleContinue}
                    style={{ width: "100%", padding: "12px" }}
                  >
                    초안 생성 완료 💾
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Right panel: Live A4 preview document */}
      <div className="document-hub-right">
        {renderA4Document()}
      </div>
    </div>
  );
}
