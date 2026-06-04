"""
3_app.py
국민대학교 졸업 도우미 - Streamlit UI
실행: streamlit run 3_app.py
"""

import os
import json
import tempfile
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── 페이지 설정 ──────────────────────────────
st.set_page_config(
    page_title="국민대 졸업 도우미",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ─────────────────────────────────────
st.markdown("""
<style>
.agent-card {
    background: #f8f9fa;
    border-left: 4px solid #003087;
    padding: 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 1rem;
}
.source-badge {
    background: #e8f0fe;
    color: #1a73e8;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    margin-right: 4px;
}
.warning-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    padding: 0.75rem;
    border-radius: 8px;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ── 상태 초기화 ──────────────────────────────
def init_state():
    defaults = {
        "transcript": None,
        "clients_ready": False,
        "openai_client": None,
        "collection": None,
        "diagnosis_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ── 클라이언트 초기화 ────────────────────────
@st.cache_resource
def load_clients(api_key: str):
    import chromadb
    from openai import OpenAI
    from pathlib import Path

    if not Path("./chroma_db").exists():
        return None, None, "ChromaDB가 없습니다. 먼저 1_build_index.py를 실행하세요."

    try:
        client = OpenAI(api_key=api_key)
        chroma = chromadb.PersistentClient(path="./chroma_db")
        collection = chroma.get_collection("kookmin_yoram")
        return client, collection, None
    except Exception as e:
        return None, None, str(e)


# ── 사이드바 ─────────────────────────────────
with st.sidebar:
    st.image("https://www.kookmin.ac.kr/img/kookminLogoB.png", width=180)
    st.title("국민대 졸업 도우미")
    st.caption("RAG 기반 맞춤형 졸업 진단 서비스")
    st.divider()

    # API 키 입력
    api_key = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        placeholder="sk-...",
    )

    if api_key:
        with st.spinner("시스템 초기화 중..."):
            client, collection, err = load_clients(api_key)
        if err:
            st.error(f"초기화 실패: {err}")
        else:
            st.session_state.openai_client = client
            st.session_state.collection = collection
            st.session_state.clients_ready = True
            st.success("시스템 준비 완료")

            # 인덱스 통계
            if os.path.exists("index_stats.json"):
                with open("index_stats.json", encoding="utf-8") as f:
                    stats = json.load(f)
                st.metric("요람 청크 수", f"{stats['total_chunks']:,}개")
                st.metric("총 페이지", f"{stats['total_pages']:,}p")

    st.divider()
    st.markdown("""
    **사용 순서**
    1. API Key 입력
    2. 성적증명서 업로드 (또는 수동 입력)
    3. 원하는 에이전트 선택
    4. 결과 확인 및 다운로드

    ⚠️ 모든 결과는 **참고용**입니다.
    최종 확인은 교학팀에 문의하세요.
    """)


# ── 에이전트 실행 공통 함수 (탭보다 먼저 정의) ──────────────────
def _load_agents():
    import sys, importlib.util
    if "agents_module" not in sys.modules:
        spec = importlib.util.spec_from_file_location("agents_module", "2_agents.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules["agents_module"] = mod
    return sys.modules["agents_module"]


def show_sources(sources: list[dict]):
    with st.expander(f"📚 참고한 요람 출처 ({len(sources)}개)"):
        for i, s in enumerate(sources, 1):
            st.markdown(
                f'<span class="source-badge">요람 {s["page"]}p</span>'
                f'<span class="source-badge">{s["section"]}</span>'
                f'관련도: {s["relevance"]:.2f}',
                unsafe_allow_html=True,
            )
            st.caption(s["text"][:200] + "...")
            if i < len(sources):
                st.divider()


def check_transcript():
    if not st.session_state.transcript:
        st.warning("먼저 '성적증명서 입력' 탭에서 정보를 입력하세요.")
        return False
    return True


# ── 메인 ────────────────────────────────────
st.header("🎓 국민대학교 졸업 도우미")

if not st.session_state.clients_ready:
    st.info("사이드바에서 OpenAI API Key를 입력하고 1_build_index.py를 먼저 실행하세요.")
    st.stop()

# ── 탭 구성 ─────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 성적증명서 입력",
    "🔍 졸업 진단",
    "🔄 대체 이수",
    "🏅 마이크로 디그리",
    "💼 직무 역량 번역기",
])


# ══════════════════════════════════════════
# TAB 1: 성적증명서 입력
# ══════════════════════════════════════════
with tab1:
    st.subheader("성적증명서 입력")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**PDF 업로드 (자동 파싱)**")
        uploaded = st.file_uploader(
            "성적증명서 PDF", type=["pdf"], label_visibility="collapsed"
        )

        if uploaded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            agents = _load_agents()

            with st.spinner("성적증명서 파싱 중... (이미지 PDF는 GPT-4o Vision 사용, 10~20초 소요)"):
                try:
                    transcript = agents.parse_transcript_pdf(
                        tmp_path, openai_api_key=api_key
                    )
                    st.session_state.transcript = transcript
                    st.success(f"파싱 완료: {transcript.name} ({transcript.student_id})")
                except Exception as e:
                    st.error(f"파싱 실패: {e}")

    with col2:
        st.markdown("**수동 입력**")
        with st.form("manual_input"):
            name = st.text_input("이름", placeholder="홍길동")
            student_id = st.text_input("학번", placeholder="20210001")
            department = st.text_input("학과", placeholder="소프트웨어학부")
            admission_year = st.number_input("입학연도", min_value=2000, max_value=2030, value=2021)
            completed_credits = st.number_input("이수학점", min_value=0, max_value=200, value=120)
            gpa = st.number_input("GPA", min_value=0.0, max_value=4.5, value=3.5, step=0.01)
            courses_text = st.text_area(
                "이수 과목 (한 줄에 하나씩: 과목명,학점,성적,카테고리)",
                placeholder="데이터베이스설계,3,A+,전공\n알고리즘,3,B+,전공",
                height=150,
            )

            if st.form_submit_button("저장", type="primary"):
                import sys, importlib.util
                spec = importlib.util.spec_from_file_location("agents_module", "2_agents.py")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                sys.modules["agents_module"] = mod
                from agents_module import TranscriptInfo

                courses = []
                for line in courses_text.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        courses.append({
                            "name": parts[0],
                            "credits": int(parts[1]) if parts[1].isdigit() else 3,
                            "grade": parts[2],
                            "category": parts[3] if len(parts) > 3 else "미분류",
                        })

                st.session_state.transcript = TranscriptInfo(
                    student_id=student_id,
                    name=name,
                    department=department,
                    admission_year=int(admission_year),
                    completed_credits=int(completed_credits),
                    gpa=float(gpa),
                    courses=courses,
                    raw_text="",
                )
                st.success("저장 완료!")

    if st.session_state.transcript:
        t = st.session_state.transcript
        st.divider()
        st.subheader("입력된 정보 확인")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("이름/학번", f"{t.name} ({t.student_id})")
        c2.metric("학과", t.department)
        c3.metric("이수학점", f"{t.completed_credits}학점")
        c4.metric("GPA", f"{t.gpa:.2f}")

        if t.courses:
            import pandas as pd
            df = pd.DataFrame(t.courses)
            st.dataframe(df, use_container_width=True, height=300)


# ══════════════════════════════════════════
# TAB 2: 졸업 진단
# ══════════════════════════════════════════
with tab2:
    st.subheader("📊 종합 졸업 진단")
    st.markdown(
        '<div class="warning-box">⚠️ AI 진단 결과는 <strong>참고용</strong>입니다. '
        "최종 졸업 가능 여부는 반드시 교학팀에 확인하세요.</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    if check_transcript() and st.button("🔍 졸업 가능 여부 진단", type="primary", key="grad_check"):
        agents = _load_agents()
        t = st.session_state.transcript

        with st.spinner("요람 분석 중... (30초~1분 소요)"):
            result = agents.agent_graduation_check(
                t,
                st.session_state.openai_client,
                st.session_state.collection,
            )

        st.session_state.diagnosis_result = result
        st.markdown(result.answer)
        show_sources(result.sources)

        # 교학팀 제출용 문서 다운로드
        report = agents.generate_admin_report(t, result.answer, result.sources)
        st.download_button(
            "📄 교학팀 제출용 확인 요청서 다운로드",
            data=report,
            file_name=f"졸업진단_{t.student_id}.txt",
            mime="text/plain",
        )


# ══════════════════════════════════════════
# TAB 3: 대체 이수 대응
# ══════════════════════════════════════════
with tab3:
    st.subheader("🔄 대체 이수 과목 탐색")
    st.caption("폐강되거나 수강신청에 실패한 과목의 대체 이수 가능 과목을 찾아드립니다.")

    if check_transcript():
        failed_course = st.text_input(
            "문제가 된 과목명",
            placeholder="예: 캡스톤디자인, 전공종합설계, 사회봉사...",
        )

        if st.button("대체 과목 탐색", type="primary", key="sub_search") and failed_course:
            agents = _load_agents()
            t = st.session_state.transcript

            with st.spinner(f"'{failed_course}' 대체 과목 탐색 중..."):
                result = agents.agent_substitute_courses(
                    t,
                    failed_course,
                    st.session_state.openai_client,
                    st.session_state.collection,
                )

            st.markdown(result.answer)
            show_sources(result.sources)


# ══════════════════════════════════════════
# TAB 4: 마이크로 디그리
# ══════════════════════════════════════════
with tab4:
    st.subheader("🏅 마이크로 디그리 발굴")
    st.caption("이수 내역을 분석하여 추가로 취득 가능한 소학위/마이크로 디그리를 찾아드립니다.")

    if check_transcript():
        if st.button("마이크로 디그리 분석", type="primary", key="micro_deg"):
            agents = _load_agents()
            t = st.session_state.transcript

            with st.spinner("마이크로 디그리 달성도 분석 중..."):
                result = agents.agent_micro_degree(
                    t,
                    st.session_state.openai_client,
                    st.session_state.collection,
                )

            st.markdown(result.answer)
            show_sources(result.sources)

        st.divider()
        st.subheader("📋 졸업 후 체크리스트")
        st.caption("디지털 자산 백업, 증명서 발급 등 졸업 전후 할 일 목록을 생성합니다.")

        if st.button("체크리스트 생성", key="post_grad"):
            agents = _load_agents()
            t = st.session_state.transcript

            with st.spinner("졸업 체크리스트 생성 중..."):
                result = agents.agent_post_graduation(
                    t,
                    st.session_state.openai_client,
                    st.session_state.collection,
                )

            st.markdown(result.answer)
            if result.checklist:
                st.subheader("✅ 체크리스트")
                for item in result.checklist:
                    st.checkbox(item, key=f"chk_{item[:20]}")
            show_sources(result.sources)


# ══════════════════════════════════════════
# TAB 5: 직무 역량 번역기
# ══════════════════════════════════════════
with tab5:
    st.subheader("💼 직무 역량 번역기")
    st.caption("이수 과목을 취업 자기소개서에서 바로 쓸 수 있는 직무 역량으로 번역합니다.")

    if check_transcript():
        target_job = st.text_input(
            "희망 직무",
            placeholder="예: 백엔드 개발자, 데이터 분석가, UX 디자이너, 마케터...",
        )

        if st.button("역량 번역 시작", type="primary", key="career_trans") and target_job:
            agents = _load_agents()
            t = st.session_state.transcript

            with st.spinner(f"'{target_job}' 직무 역량 분석 중..."):
                result = agents.agent_career_translator(
                    t,
                    target_job,
                    st.session_state.openai_client,
                    st.session_state.collection,
                )

            st.markdown(result.answer)
            show_sources(result.sources)

            # 결과 다운로드
            st.download_button(
                "📥 역량 번역 결과 다운로드",
                data=result.answer,
                file_name=f"역량번역_{t.student_id}_{target_job}.txt",
                mime="text/plain",
            )
