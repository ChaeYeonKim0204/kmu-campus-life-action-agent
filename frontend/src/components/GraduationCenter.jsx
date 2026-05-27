import React from "react";

const TABS = [
  { id: "upload", label: "성적증명서 업로드" },
  { id: "audit", label: "졸업 진단" },
  { id: "early", label: "조기졸업" },
  { id: "customized", label: "커스터마이징" },
  { id: "creditDrop", label: "학점 드랍" },
  { id: "substitute", label: "대체 이수" },
  { id: "micro", label: "마이크로디그리" },
  { id: "post", label: "졸업 체크리스트" },
  { id: "career", label: "직무 역량" }
];

const CATEGORY_ORDER = ["기초교양", "핵심교양", "자유교양", "전공", "일반선택", "교직", "미분류"];

export default function GraduationCenter({ apiBase, onClose, hideHeader }) {
  const [status, setStatus] = React.useState(null);
  const [activeTab, setActiveTab] = React.useState("upload");
  const [file, setFile] = React.useState(null);
  const [visionConsent, setVisionConsent] = React.useState(false);
  const [transcript, setTranscript] = React.useState(null);
  const [uploadMessage, setUploadMessage] = React.useState("");
  const [needsVisionConsent, setNeedsVisionConsent] = React.useState(false);
  const [loadingUpload, setLoadingUpload] = React.useState(false);
  const [loadingTask, setLoadingTask] = React.useState("");
  const [results, setResults] = React.useState({});
  const [courseName, setCourseName] = React.useState("");
  const [targetJob, setTargetJob] = React.useState("");
  const [earlyOptions, setEarlyOptions] = React.useState({
    registered_semesters: "",
    is_five_year_architecture: false,
    has_transfer_or_readmission: false,
    has_academic_warning: false,
    has_repeated_semester: false,
    has_grade_waiver_history: false,
    has_disciplinary_record: false
  });
  const [customizedOptions, setCustomizedOptions] = React.useState({
    desired_field: "",
    target_recognition: "전공선택"
  });
  const [creditDropConcern, setCreditDropConcern] = React.useState("성적포기 가능 여부와 졸업/조기졸업 영향");

  React.useEffect(() => {
    fetch(`${apiBase}/graduation/status`)
      .then((response) => response.json())
      .then(setStatus)
      .catch((error) => setStatus({ ready: false, error: error.message }));
  }, [apiBase]);

  const parseTranscript = async () => {
    if (!file || loadingUpload) return;
    setLoadingUpload(true);
    setUploadMessage("");
    setNeedsVisionConsent(false);
    const form = new FormData();
    form.append("file", file);
    form.append("vision_ocr_consent", visionConsent ? "true" : "false");
    form.append("store_result", "false");
    try {
      const response = await fetch(`${apiBase}/graduation/transcript/parse`, {
        method: "POST",
        body: form
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "성적증명서 파싱에 실패했습니다.");
      }
      setUploadMessage(data.message || "");
      if (data.status === "needs_vision_consent") {
        setNeedsVisionConsent(true);
      }
      if (data.status === "parsed") {
        setTranscript(data.transcript);
        setResults({});
        setNeedsVisionConsent(false);
        setActiveTab("audit");
      }
    } catch (error) {
      setUploadMessage(error.message);
    } finally {
      setLoadingUpload(false);
    }
  };

  const runAnalysis = async (task) => {
    if (!transcript || loadingTask) return;
    const endpointByTask = {
      audit: "/graduation/audit",
      early: "/graduation/early-graduation",
      customized: "/graduation/customized-major",
      creditDrop: "/graduation/credit-drop",
      substitute: "/graduation/substitute-courses",
      micro: "/graduation/micro-degree",
      post: "/graduation/post-graduation-checklist",
      career: "/graduation/career-translator"
    };
    const body = { transcript };
    if (task === "substitute") body.course_name = courseName;
    if (task === "career") body.target_job = targetJob;
    if (task === "early") {
      body.registered_semesters = earlyOptions.registered_semesters ? Number(earlyOptions.registered_semesters) : null;
      body.is_five_year_architecture = earlyOptions.is_five_year_architecture;
      body.has_transfer_or_readmission = earlyOptions.has_transfer_or_readmission;
      body.has_academic_warning = earlyOptions.has_academic_warning;
      body.has_repeated_semester = earlyOptions.has_repeated_semester;
      body.has_grade_waiver_history = earlyOptions.has_grade_waiver_history;
      body.has_disciplinary_record = earlyOptions.has_disciplinary_record;
    }
    if (task === "customized") {
      body.desired_field = customizedOptions.desired_field;
      body.target_recognition = customizedOptions.target_recognition;
    }
    if (task === "creditDrop") body.concern = creditDropConcern;
    setLoadingTask(task);
    try {
      const response = await fetch(`${apiBase}${endpointByTask[task]}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "분석을 실행하지 못했습니다.");
      }
      setResults((prev) => ({ ...prev, [task]: data }));
    } catch (error) {
      setResults((prev) => ({
        ...prev,
        [task]: { status: "blocked", answer: `요청 실패: ${error.message}`, sources: [], warnings: [] }
      }));
    } finally {
      setLoadingTask("");
    }
  };

  const downloadResult = (task) => {
    const result = results[task];
    if (!result?.answer) return;
    const blob = new Blob([result.answer], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `graduation_${task}_result.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const disabledReason = !transcript ? "먼저 성적증명서 PDF를 업로드하고 파싱해야 합니다." : "";

  return (
    <div className="graduation-center">
      {!hideHeader && (
        <div className="graduation-header">
          <div>
            <h2>졸업 센터</h2>
            <p>성적증명서를 임시 파싱해 졸업요건, 조기졸업, Customized전공, 성적포기, 직무 역량을 분석합니다.</p>
          </div>
          <button type="button" className="rpg-modal-close inline" onClick={onClose}>✕</button>
        </div>
      )}

      {status && !status.ready && (
        <div className="graduation-alert">
          졸업 센터 준비가 필요합니다. OpenAI API 키, 요람 구조화 데이터, 졸업용 Chroma 인덱스를 확인해 주세요.
        </div>
      )}

      <div className="graduation-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="graduation-body">
        {activeTab === "upload" && (
          <section className="graduation-panel">
            <h3>성적증명서 PDF 업로드</h3>
            <p className="graduation-muted">
              성적증명서는 졸업 진단에만 임시 사용되며 저장하지 않습니다. 이름, 학번, GPA, 과목별 성적은 결과에 표시하지 않습니다.
            </p>
            <label className="graduation-file">
              <span>PDF 파일</span>
              <input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </label>
            <label className="graduation-check">
              <input type="checkbox" checked={visionConsent} onChange={(event) => setVisionConsent(event.target.checked)} />
              <span>이미지 기반 PDF인 경우 OpenAI Vision으로 전송될 수 있음에 동의합니다.</span>
            </label>
            {needsVisionConsent && (
              <div className="graduation-message inline">
                이 PDF는 이미지 기반일 가능성이 높습니다. Vision OCR 동의 체크 후 다시 파싱해 주세요.
              </div>
            )}
            <button type="button" className="primary" disabled={!file || loadingUpload} onClick={parseTranscript}>
              {loadingUpload ? "파싱 중..." : needsVisionConsent ? "Vision OCR로 다시 파싱" : "성적증명서 파싱"}
            </button>
            {uploadMessage && <div className="graduation-message">{uploadMessage}</div>}
            {transcript && <TranscriptSummaryCard transcript={transcript} />}
          </section>
        )}

        {activeTab === "audit" && (
          <AnalysisPanel
            title="졸업 가능 여부 진단"
            description="요람 별표 기준과 성적증명서의 비식별 이수 요약을 비교합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "audit"}
            result={results.audit}
            onRun={() => runAnalysis("audit")}
            onDownload={() => downloadResult("audit")}
          />
        )}

        {activeTab === "substitute" && (
          <AnalysisPanel
            title="대체 이수 과목 탐색"
            description="폐강 또는 수강 실패 과목의 대체 가능 후보를 요람 근거로 찾습니다."
            disabledReason={disabledReason || (!courseName.trim() ? "문제가 된 과목명을 입력해 주세요." : "")}
            loading={loadingTask === "substitute"}
            result={results.substitute}
            onRun={() => runAnalysis("substitute")}
            onDownload={() => downloadResult("substitute")}
          >
            <input
              value={courseName}
              onChange={(event) => setCourseName(event.target.value)}
              placeholder="예: 캡스톤디자인"
            />
          </AnalysisPanel>
        )}

        {activeTab === "early" && (
          <AnalysisPanel
            title="조기졸업 가능 여부 및 조심할 점"
            description="등록학기, 성적포기 이력, 성적경고 등 조기졸업 제한 조건을 함께 점검합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "early"}
            result={results.early}
            onRun={() => runAnalysis("early")}
            onDownload={() => downloadResult("early")}
          >
            <div className="graduation-option-grid">
              <label>
                등록 학기 수
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={earlyOptions.registered_semesters}
                  onChange={(event) => setEarlyOptions(prev => ({ ...prev, registered_semesters: event.target.value }))}
                  placeholder="예: 6"
                />
              </label>
              <CheckOption label="5년제 건축대학" checked={earlyOptions.is_five_year_architecture} onChange={(value) => setEarlyOptions(prev => ({ ...prev, is_five_year_architecture: value }))} />
              <CheckOption label="편입/재입학 이력 있음" checked={earlyOptions.has_transfer_or_readmission} onChange={(value) => setEarlyOptions(prev => ({ ...prev, has_transfer_or_readmission: value }))} />
              <CheckOption label="성적경고 이력 있음" checked={earlyOptions.has_academic_warning} onChange={(value) => setEarlyOptions(prev => ({ ...prev, has_academic_warning: value }))} />
              <CheckOption label="유급학기 있음" checked={earlyOptions.has_repeated_semester} onChange={(value) => setEarlyOptions(prev => ({ ...prev, has_repeated_semester: value }))} />
              <CheckOption label="성적포기 이력 있음" checked={earlyOptions.has_grade_waiver_history} onChange={(value) => setEarlyOptions(prev => ({ ...prev, has_grade_waiver_history: value }))} />
              <CheckOption label="징계처분 이력 있음" checked={earlyOptions.has_disciplinary_record} onChange={(value) => setEarlyOptions(prev => ({ ...prev, has_disciplinary_record: value }))} />
            </div>
          </AnalysisPanel>
        )}

        {activeTab === "customized" && (
          <AnalysisPanel
            title="커스터마이징 전공 제도"
            description="타 학과 전공과목을 1전공/2전공/3전공 학점 또는 필수과목 대체로 인정받을 수 있는지 확인합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "customized"}
            result={results.customized}
            onRun={() => runAnalysis("customized")}
            onDownload={() => downloadResult("customized")}
          >
            <div className="graduation-option-grid">
              <label>
                희망 진로/직무 분야
                <input
                  value={customizedOptions.desired_field}
                  onChange={(event) => setCustomizedOptions(prev => ({ ...prev, desired_field: event.target.value }))}
                  placeholder="예: 보험계리사, 보안, 재활치료"
                />
              </label>
              <label>
                인정 희망 유형
                <select
                  value={customizedOptions.target_recognition}
                  onChange={(event) => setCustomizedOptions(prev => ({ ...prev, target_recognition: event.target.value }))}
                >
                  <option value="전공선택">전공선택 인정</option>
                  <option value="2전공">2전공 인정</option>
                  <option value="3전공">3전공 인정</option>
                  <option value="필수과목 대체">필수과목 대체</option>
                </select>
              </label>
            </div>
          </AnalysisPanel>
        )}

        {activeTab === "creditDrop" && (
          <AnalysisPanel
            title="학점 드랍/성적포기 제도"
            description="국민대 공식 표현인 성적포기 기준으로 졸업요건과 조기졸업 영향까지 확인합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "creditDrop"}
            result={results.creditDrop}
            onRun={() => runAnalysis("creditDrop")}
            onDownload={() => downloadResult("creditDrop")}
          >
            <input
              value={creditDropConcern}
              onChange={(event) => setCreditDropConcern(event.target.value)}
              placeholder="예: 성적포기 가능 여부와 조기졸업 영향"
            />
          </AnalysisPanel>
        )}

        {activeTab === "micro" && (
          <AnalysisPanel
            title="마이크로디그리/소학위 발굴"
            description="이수 과목 기반으로 달성 가능성이 높은 트랙을 추천합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "micro"}
            result={results.micro}
            onRun={() => runAnalysis("micro")}
            onDownload={() => downloadResult("micro")}
          />
        )}

        {activeTab === "post" && (
          <AnalysisPanel
            title="졸업 전후 체크리스트"
            description="졸업 전, 직전, 졸업 후 행정 확인 항목을 정리합니다."
            disabledReason={disabledReason}
            loading={loadingTask === "post"}
            result={results.post}
            onRun={() => runAnalysis("post")}
            onDownload={() => downloadResult("post")}
          />
        )}

        {activeTab === "career" && (
          <AnalysisPanel
            title="직무 역량 번역기"
            description="이수 과목을 희망 직무의 역량 언어와 자기소개서 문장으로 변환합니다."
            disabledReason={disabledReason || (!targetJob.trim() ? "희망 직무를 입력해 주세요." : "")}
            loading={loadingTask === "career"}
            result={results.career}
            onRun={() => runAnalysis("career")}
            onDownload={() => downloadResult("career")}
          >
            <input
              value={targetJob}
              onChange={(event) => setTargetJob(event.target.value)}
              placeholder="예: 백엔드 개발자, 데이터 분석가"
            />
          </AnalysisPanel>
        )}
      </div>
    </div>
  );
}

function TranscriptSummaryCard({ transcript }) {
  const categories = CATEGORY_ORDER
    .filter((key) => transcript.category_credits?.[key])
    .map((key) => [key, transcript.category_credits[key]]);
  return (
    <div className="transcript-summary-card">
      <h4>파싱 요약</h4>
      <div className="summary-grid">
        <span>이름</span><strong>{transcript.masked_name || "마스킹됨"}</strong>
        <span>학번</span><strong>{transcript.masked_student_id || "마스킹됨"}</strong>
        <span>학과</span><strong>{transcript.department}</strong>
        <span>입학연도</span><strong>{transcript.admission_year || "미확인"}</strong>
        <span>총 이수학점</span><strong>{transcript.total_credits}학점</strong>
        <span>평점 기준</span><strong>{gpaStatusLabel(transcript.gpa_minimum_met)}</strong>
      </div>
      <div className="category-credit-list">
        {categories.map(([label, value]) => (
          <span key={label}>{label}: {value}학점</span>
        ))}
      </div>
      <div className="course-preview">
        {(transcript.courses || []).slice(0, 20).map((course, index) => (
          <div key={`${course.name}-${index}`}>
            <span>{course.name}</span>
            <strong>{course.credits}학점 · {course.category}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function AnalysisPanel({ title, description, disabledReason, loading, result, onRun, onDownload, children }) {
  const disabled = Boolean(disabledReason) || loading;
  return (
    <section className="graduation-panel">
      <h3>{title}</h3>
      <p className="graduation-muted">{description}</p>
      {children && <div className="graduation-input-row">{children}</div>}
      {disabledReason && <div className="graduation-message">{disabledReason}</div>}
      <button type="button" className="primary" disabled={disabled} onClick={onRun}>
        {loading ? "분석 중..." : "분석 실행"}
      </button>
      {result && (
        <div className="graduation-result">
          <pre>{result.answer}</pre>
          {result.sources?.length > 0 && (
            <div className="graduation-sources">
              {result.sources.map((source) => (
                <div key={source.id || source.title}>
                  <strong>[{source.id}] {source.title}</strong>
                  <span>{source.page}p · {source.section}</span>
                </div>
              ))}
            </div>
          )}
          <button type="button" className="secondary" onClick={onDownload}>TXT 다운로드</button>
        </div>
      )}
    </section>
  );
}

function CheckOption({ label, checked, onChange }) {
  return (
    <label className="graduation-small-check">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function gpaStatusLabel(value) {
  if (value === "yes") return "기준 충족";
  if (value === "no") return "기준 미충족";
  return "미확인";
}
