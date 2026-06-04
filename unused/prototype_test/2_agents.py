"""
2_agents.py
4대 에이전트 로직 - RAG + GPT-4o 기반

졸업 진단 에이전트는 graduation_requirements.json(구조화 데이터)을 1차로 사용하고,
ChromaDB RAG를 2차 보완 자료로 활용합니다.
"""

import os
import re
import json
import importlib.util
import sys
from dataclasses import dataclass
from typing import Optional
import pdfplumber
import pypdf
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "kookmin_yoram"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"
TOP_K = 6  # RAG 검색 청크 수

# ─────────────────────────────────────────────
# 구조화 JSON 데이터 로더
# ─────────────────────────────────────────────

def _load_structured_data():
    """graduation_requirements.json과 grade_category_codes.json 로드."""
    data = {"requirements": None, "search_index": None, "codes": None}
    try:
        with open("graduation_requirements.json", encoding="utf-8") as f:
            data["requirements"] = json.load(f)
        with open("department_search_index.json", encoding="utf-8") as f:
            data["search_index"] = json.load(f)
        with open("grade_category_codes.json", encoding="utf-8") as f:
            data["codes"] = json.load(f)
    except FileNotFoundError:
        pass  # 인덱싱 전이면 RAG 단독 사용
    return data


def _find_dept_requirements(department: str, structured: dict) -> Optional[dict]:
    """학과명으로 졸업이수학점 구조 검색. 없으면 None."""
    if not structured["requirements"] or not structured["search_index"]:
        return None

    # 0_extract_structured_data의 find_department 함수 재사용
    spec = importlib.util.spec_from_file_location("extractor", "0_extract_structured_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    results = mod.find_department(
        department, structured["requirements"], structured["search_index"]
    )
    return results[0] if results else None


def _compute_credits_by_category(courses: list[dict], codes: Optional[dict]) -> dict:
    """
    이수 과목 목록에서 졸업 관련 이수구분별 학점을 계산.
    성적증명서 이수구분 코드(V=기초교양, Y=핵심교양, Z=자유교양, C/D/M/X=전공, F=일반선택)를 사용.
    """
    result = {
        "기초교양": 0, "핵심교양": 0, "자유교양": 0,
        "전공": 0, "일반선택": 0, "교직": 0, "미분류": 0,
    }
    FAILING = {"F", "NP", "N", "U", "W"}

    if codes:
        cat_map = codes.get("graduation_relevant_map", {})
        code_to_cat = {}
        for cat, code_list in cat_map.items():
            for code in code_list:
                code_to_cat[code] = cat
    else:
        # 코드 없을 때 카테고리 텍스트 직접 사용
        code_to_cat = {}

    for c in courses:
        if c.get("grade", "") in FAILING:
            continue
        credits = c.get("credits", 0)
        category = c.get("category", "미분류")

        # 이수구분 코드로 매핑 시도
        mapped = code_to_cat.get(category, None)
        if mapped and mapped in result:
            result[mapped] += credits
        elif category in result:
            result[category] += credits
        else:
            # 텍스트 기반 매핑 폴백
            if "기초교양" in category or category in ("A", "B", "K", "V"):
                result["기초교양"] += credits
            elif "핵심교양" in category or category == "Y":
                result["핵심교양"] += credits
            elif "자유교양" in category or category in ("E", "L", "Z"):
                result["자유교양"] += credits
            elif "전공" in category or category in ("C", "D", "M", "X"):
                result["전공"] += credits
            elif "일반선택" in category or category == "F":
                result["일반선택"] += credits
            else:
                result["미분류"] += credits

    result["교양소계"] = result["기초교양"] + result["핵심교양"] + result["자유교양"]
    return result


@dataclass
class TranscriptInfo:
    """파싱된 성적증명서 정보."""
    student_id: str
    name: str
    department: str
    admission_year: int
    completed_credits: int
    gpa: float
    courses: list[dict]  # [{name, credits, grade, category}]
    raw_text: str


@dataclass
class AgentResponse:
    answer: str
    sources: list[dict]  # [{text, page, section}]
    checklist: Optional[list[str]] = None


def get_clients():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수를 설정하세요")
    openai_client = OpenAI(api_key=api_key)
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_collection(COLLECTION_NAME)
    return openai_client, collection


def rag_search(
    openai_client: OpenAI,
    collection,
    query: str,
    top_k: int = TOP_K,
    section_filter: Optional[str] = None,
) -> list[dict]:
    """쿼리를 임베딩하여 ChromaDB에서 관련 청크 검색."""
    response = openai_client.embeddings.create(
        model=EMBED_MODEL, input=[query]
    )
    query_embedding = response.data[0].embedding

    where = {"section": section_filter} if section_filter else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    sources = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        sources.append({
            "text": doc,
            "page": meta.get("page", "?"),
            "section": meta.get("section", "일반"),
            "department": meta.get("department", "공통"),
            "relevance": round(1 - dist, 3),
        })
    return sources


def build_context(sources: list[dict]) -> str:
    """검색된 청크를 GPT 프롬프트용 컨텍스트로 조합."""
    lines = []
    for i, s in enumerate(sources, 1):
        lines.append(f"[출처 {i}: 요람 {s['page']}페이지, 섹션: {s['section']}]")
        lines.append(s["text"])
        lines.append("")
    return "\n".join(lines)


def parse_transcript_pdf(pdf_path: str, openai_api_key: Optional[str] = None) -> "TranscriptInfo":
    """
    성적증명서 PDF 파싱.
    1차: pdfplumber 텍스트 추출 (텍스트 기반 PDF)
    2차: GPT-4o Vision OCR (이미지 기반 PDF - 국민대 공식 성적증명서 형식)
    """
    import base64
    import numpy as np
    from PIL import Image

    # 텍스트 기반 파싱 시도
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # 텍스트가 충분히 추출됐으면 텍스트 파싱
    if len(full_text.strip()) > 200:
        return _parse_transcript_text(full_text)

    # 텍스트 없음 → 이미지 기반 PDF → GPT-4o Vision OCR
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("이미지 기반 성적증명서는 OpenAI API 키가 필요합니다.")

    # PDF에서 이미지 추출
    img_b64 = _extract_pdf_image_b64(pdf_path)
    if not img_b64:
        raise ValueError("PDF에서 이미지를 추출할 수 없습니다.")

    return _parse_transcript_vision(img_b64, api_key)


def _extract_pdf_image_b64(pdf_path: str) -> Optional[str]:
    """PDF 내 이미지를 Base64로 추출."""
    import base64
    import numpy as np
    from PIL import Image

    try:
        r = pypdf.PdfReader(pdf_path)
        for page in r.pages:
            resources = page.get("/Resources", {})
            xobjects = resources.get("/XObject", {})
            for _, obj in xobjects.items():
                xobj = obj.get_object()
                if xobj.get("/Subtype") == "/Image":
                    w = int(xobj["/Width"])
                    h = int(xobj["/Height"])
                    data = xobj.get_data()
                    cs = xobj.get("/ColorSpace", "/DeviceRGB")

                    if cs == "/DeviceRGB":
                        arr = np.frombuffer(data, dtype=np.uint8).reshape((h, w, 3))
                        img = Image.fromarray(arr, "RGB")
                    elif cs == "/DeviceGray":
                        arr = np.frombuffer(data, dtype=np.uint8).reshape((h, w))
                        img = Image.fromarray(arr, "L").convert("RGB")
                    else:
                        continue

                    # 이미지를 JPEG로 압축하여 Base64 인코딩
                    from io import BytesIO
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"이미지 추출 오류: {e}")
    return None


def _parse_transcript_vision(img_b64: str, api_key: str) -> "TranscriptInfo":
    """GPT-4o Vision으로 성적증명서 OCR 파싱."""
    client = OpenAI(api_key=api_key)

    prompt = """이 국민대학교 성적증명서 이미지에서 정보를 정확히 추출하여 JSON으로 반환하세요.

【중요 구분】
- 학번: 증명서 상단 학생 정보란의 숫자 8자리 (예: 20192767). 입학일(날짜)과 혼동하지 마세요.
- 입학연도: 학번 앞 4자리 숫자 (예: 2019)
- 증명서번호(제G26-xxxxx)는 학번이 아닙니다.

반환 형식 (JSON만, 다른 텍스트 없이):
{
  "이름": "",
  "학번": "20192767",
  "대학": "",
  "학부_전공": "",
  "입학연도": 2019,
  "총_취득학점": 0.0,
  "총_평점평균": 0.0,
  "백분위": 0.0,
  "과목목록": [
    {
      "학년도": "2019",
      "학기": "1",
      "이수구분": "D",
      "교과목명": "과목명",
      "학점": 3.0,
      "성적": "A+"
    }
  ],
  "이수구분별_학점": {
    "기초교양(V)": 0.0,
    "핵심교양(Y)": 0.0,
    "자유교양(Z)": 0.0,
    "전공(C/D/M/X)": 0.0,
    "일반선택(F)": 0.0,
    "다전공(PN/PX/PM/PL)": 0.0,
    "기타": 0.0
  }
}

추출 규칙:
- 과목목록: 모든 학기의 모든 과목 포함 (중복 없이)
- 이수구분 코드: V(기초교양), Y(핵심교양), Z(자유교양), D(전공선택), C(전공필수), F(일반선택), PN/PX(다전공) 등 원본 그대로
- 동일 과목이 한글명+영문명으로 나뉘어 보이면 한 개만 포함
- 성적: A+, A0, B+, B0, C+, C0, D+, D0, F, P, N 형식으로 정확히"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "high",
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=4096,
        temperature=0.0,
    )

    raw = resp.choices[0].message.content.strip()
    # JSON 코드블록 제거
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"GPT 응답을 JSON으로 파싱 실패: {raw[:200]}")

    # 과목 목록 변환
    courses = []
    total_credits = 0
    FAILING = {"F", "NP", "N", "U", "W"}
    for c in data.get("과목목록", []):
        grade = str(c.get("성적", "")).strip()
        credits = float(c.get("학점", 0))
        if grade not in FAILING:
            total_credits += credits
        courses.append({
            "name": c.get("교과목명", ""),
            "credits": int(credits) if credits == int(credits) else credits,
            "grade": grade,
            "category": c.get("이수구분", "미분류"),
            "semester": f"{c.get('학년도', '')}년 {c.get('학기', '')}학기",
        })

    # 총취득학점은 증명서 표기값 우선
    final_credits = data.get("총_취득학점", total_credits)
    if isinstance(final_credits, str):
        final_credits = float(re.sub(r"[^\d.]", "", final_credits) or 0)

    학번 = str(data.get("학번", "미확인"))
    # 학번에서 연도 추출
    year_str = 학번[:4] if len(학번) >= 4 and 학번[:4].isdigit() else "2020"
    admission_year = int(year_str)

    return TranscriptInfo(
        student_id=학번,
        name=data.get("이름", "미확인"),
        department=data.get("학부_전공", data.get("대학", "미확인")),
        admission_year=admission_year,
        completed_credits=int(final_credits),
        gpa=float(data.get("총_평점평균", 0.0)),
        courses=courses,
        raw_text=json.dumps(data, ensure_ascii=False),
    )


def _parse_transcript_text(full_text: str) -> "TranscriptInfo":
    """텍스트 기반 성적증명서 파싱 (기존 로직)."""
    student_id = _extract(full_text, r"학\s*번[:\s]+(\d{7,10})", "미확인")
    name = _extract(full_text, r"성\s*명[:\s]+([가-힣]{2,5})", "미확인")
    department = _extract(full_text, r"학\s*과[:\s]+([가-힣\s]+?)(?:\n|학번)", "미확인")
    gpa_str = _extract(full_text, r"평점평균[:\s]+([\d.]+)", "0.0")
    gpa = float(gpa_str) if gpa_str != "0.0" else 0.0

    admission_year = (
        int("20" + student_id[:2])
        if student_id != "미확인" and student_id[:2].isdigit()
        else 2020
    )

    courses = []
    course_pattern = re.findall(
        r"([가-힣A-Za-z0-9\s\(\)]+?)\s+(\d)\s+([A-F][+\-]?|P|NP|S|U)\s*(전공|교양|일반선택|기초)?",
        full_text,
    )
    total_credits = 0
    for course_name, credits, grade, category in course_pattern:
        course_name = course_name.strip()
        if len(course_name) < 2:
            continue
        credit_int = int(credits)
        if grade not in ("F", "NP", "U"):
            total_credits += credit_int
        courses.append({
            "name": course_name,
            "credits": credit_int,
            "grade": grade,
            "category": category or "미분류",
            "semester": "",
        })

    credits_match = re.search(r"취득학점[:\s]+(\d+)", full_text)
    if credits_match:
        total_credits = int(credits_match.group(1))

    return TranscriptInfo(
        student_id=student_id,
        name=name,
        department=department.strip(),
        admission_year=admission_year,
        completed_credits=total_credits,
        gpa=gpa,
        courses=courses,
        raw_text=full_text,
    )


def _extract(text: str, pattern: str, default: str) -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else default


# ─────────────────────────────────────────────
# 에이전트 1: 대체 이수 대응
# ─────────────────────────────────────────────
def agent_substitute_courses(
    transcript: TranscriptInfo,
    failed_course: str,
    openai_client: OpenAI,
    collection,
) -> AgentResponse:
    """폐강/수강실패 과목의 대체 이수 가능 과목 탐색."""

    query = f"{transcript.department} {failed_course} 대체 인정 과목 교과목 이수 규정"
    sources = rag_search(openai_client, collection, query, top_k=8)
    context = build_context(sources)

    course_list = "\n".join(
        f"- {c['name']} ({c['credits']}학점, {c['grade']})" for c in transcript.courses
    )

    prompt = f"""당신은 국민대학교 학사 규정 전문가입니다.

[학생 정보]
- 학과: {transcript.department}
- 입학연도: {transcript.admission_year}
- 이수학점: {transcript.completed_credits}학점
- 문제 과목: {failed_course} (폐강 또는 수강신청 실패)

[이수 완료 과목 목록]
{course_list}

[요람 관련 규정 (근거 자료)]
{context}

위 정보를 바탕으로:
1. {failed_course}를 대신할 수 있는 대체 이수 가능 과목을 구체적으로 제시하세요.
2. 각 대체 과목마다 근거가 되는 요람 내용을 인용하세요.
3. 주의사항과 교학팀 확인이 필요한 사항을 명시하세요.

※ 이 답변은 참고용이며 최종 졸업 승인은 교학팀 확인이 필요합니다."""

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return AgentResponse(answer=resp.choices[0].message.content, sources=sources)


# ─────────────────────────────────────────────
# 에이전트 2: 마이크로 디그리 발굴
# ─────────────────────────────────────────────
def agent_micro_degree(
    transcript: TranscriptInfo,
    openai_client: OpenAI,
    collection,
) -> AgentResponse:
    """이수 내역 기반 마이크로 디그리/소학위 달성도 분석."""

    query = "마이크로디그리 소학위 이수 요건 학점 조건"
    sources = rag_search(openai_client, collection, query, top_k=8)
    context = build_context(sources)

    course_list = "\n".join(
        f"- {c['name']} ({c['credits']}학점, {c['category']})" for c in transcript.courses
    )

    prompt = f"""당신은 국민대학교 마이크로디그리 및 소학위 제도 전문가입니다.

[학생 정보]
- 학과: {transcript.department}
- 입학연도: {transcript.admission_year}
- 총 이수학점: {transcript.completed_credits}학점

[이수 과목 목록]
{course_list}

[요람의 마이크로디그리/소학위 관련 규정]
{context}

위 정보를 바탕으로:
1. 학생이 이미 취득했거나, 1-3과목 추가 수강으로 달성 가능한 마이크로디그리/소학위 트랙을 분석하세요.
2. 각 트랙별로 달성률(%)과 부족한 과목을 표 형식으로 제시하세요.
3. 가장 달성 가능성이 높은 트랙 3가지를 우선순위 순으로 추천하세요.

※ 이 답변은 참고용이며 최종 확인은 교학팀에서 받으세요."""

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return AgentResponse(answer=resp.choices[0].message.content, sources=sources)


# ─────────────────────────────────────────────
# 에이전트 3: 포스트 국민 트랜지션
# ─────────────────────────────────────────────
def agent_post_graduation(
    transcript: TranscriptInfo,
    openai_client: OpenAI,
    collection,
) -> AgentResponse:
    """졸업 후 행정 절차 체크리스트 생성."""

    query = "졸업예정증명서 학위복 디지털 자산 메일 드라이브 졸업 절차"
    sources = rag_search(openai_client, collection, query, top_k=6)
    context = build_context(sources)

    prompt = f"""당신은 국민대학교 졸업 절차 안내 전문가입니다.

[학생 정보]
- 학과: {transcript.department}
- 입학연도: {transcript.admission_year}
- 이수학점: {transcript.completed_credits}학점

[요람의 졸업 관련 안내 사항]
{context}

위 정보를 바탕으로 졸업 전/후 체크리스트를 작성하세요:

1. **졸업 전 (D-90~D-30)**
   - 서류/증명서 발급 사항
   - 수강/이수 확인 사항

2. **졸업 직전 (D-30~D-0)**
   - 학위복 대여/구매
   - 졸업식 관련

3. **졸업 후 즉시 (D+1~D+30)**
   - 학교 이메일/드라이브 백업
   - 포털 접근 권한 변경

4. **졸업 후 장기 (D+30 이후)**
   - 동문 서비스 전환
   - 각종 증명서 발급 방법

각 항목에 마감일 또는 유의사항을 포함하세요."""

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    checklist = _extract_checklist(resp.choices[0].message.content)
    return AgentResponse(
        answer=resp.choices[0].message.content,
        sources=sources,
        checklist=checklist,
    )


# ─────────────────────────────────────────────
# 에이전트 4: 직무 역량 번역기
# ─────────────────────────────────────────────
def agent_career_translator(
    transcript: TranscriptInfo,
    target_job: str,
    openai_client: OpenAI,
    collection,
) -> AgentResponse:
    """이수 과목을 직무 역량 키워드로 변환."""

    query = f"{transcript.department} 교과목 개요 {target_job}"
    sources = rag_search(openai_client, collection, query, top_k=8)
    context = build_context(sources)

    course_names = ", ".join(c["name"] for c in transcript.courses[:30])

    prompt = f"""당신은 대학 교과목을 취업 역량으로 번역하는 커리어 코치입니다.

[학생 정보]
- 학과: {transcript.department}
- 희망 직무: {target_job}
- 이수 과목 (주요): {course_names}

[요람의 교과목 개요]
{context}

위 정보를 바탕으로:

1. **직무 관련 핵심 역량 키워드** (상위 10개)
   - 각 역량 키워드와 근거 과목 1-2개를 매핑하세요
   - 예: "데이터 분석 (SQL, Python)" → 데이터베이스설계, 프로그래밍기초

2. **자기소개서 활용 문장 예시** (3개)
   - 이수 과목 내용을 직무 경험처럼 서술하는 예시

3. **보완이 필요한 역량**
   - {target_job} 직무에서 요구하지만 이수 내역에 부족한 역량

형식은 명확하고 구체적으로 작성하세요."""

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return AgentResponse(answer=resp.choices[0].message.content, sources=sources)


# ─────────────────────────────────────────────
# 종합 졸업 진단 (구조화 JSON + RAG 하이브리드)
# ─────────────────────────────────────────────
def agent_graduation_check(
    transcript: TranscriptInfo,
    openai_client: OpenAI,
    collection,
) -> AgentResponse:
    """
    성적증명서 기반 졸업 가능 여부 종합 진단.
    1단계: graduation_requirements.json에서 학과별 정확한 기준 학점을 가져옴
    2단계: RAG로 세부 규정 보완
    3단계: GPT-4o가 최종 판정
    """
    # 1단계: 구조화 데이터에서 졸업 기준 로드
    structured = _load_structured_data()
    dept_req = _find_dept_requirements(transcript.department, structured)
    credits_by_cat = _compute_credits_by_category(transcript.courses, structured.get("codes"))

    # 구조화 데이터로 계산된 충족 여부 (사전 계산)
    pre_check = {}
    source_label = "요람 별표5 (p.195-196) - 구조화 데이터"
    if dept_req:
        req = dept_req
        pre_check = {
            "학과": req["학과_전공명"],
            "졸업_최저합계": req["졸업_최저합계"],
            "기초교양_필요": req["교양"]["기초교양"],
            "핵심교양_필요": req["교양"]["핵심교양"],
            "자유교양_필요": req["교양"]["자유교양"],
            "전공_필요": req["전공_최저"],
            "일반선택_필요": req["일반선택"],
            "기초교양_이수": credits_by_cat.get("기초교양", 0),
            "핵심교양_이수": credits_by_cat.get("핵심교양", 0),
            "자유교양_이수": credits_by_cat.get("자유교양", 0),
            "전공_이수": credits_by_cat.get("전공", 0),
            "일반선택_이수": credits_by_cat.get("일반선택", 0),
            "총_이수": transcript.completed_credits,
        }
        # 충족 여부
        pre_check["기초교양_충족"] = pre_check["기초교양_이수"] >= pre_check["기초교양_필요"]
        pre_check["핵심교양_충족"] = pre_check["핵심교양_이수"] >= pre_check["핵심교양_필요"]
        pre_check["전공_충족"] = pre_check["전공_이수"] >= pre_check["전공_필요"]
        pre_check["총학점_충족"] = pre_check["총_이수"] >= pre_check["졸업_최저합계"]
        pre_check["gpa_충족"] = transcript.gpa >= 2.0

    # 2단계: RAG로 세부 규정 보완
    query = f"{transcript.department} 졸업요건 필수과목 이수규정"
    sources = rag_search(openai_client, collection, query, top_k=8)
    context = build_context(sources)

    # 3단계: GPT 프롬프트 (구조화 데이터 + RAG 컨텍스트 결합)
    pre_check_str = json.dumps(pre_check, ensure_ascii=False, indent=2) if pre_check else "구조화 데이터 없음 (인덱싱 필요)"

    prompt = f"""당신은 국민대학교 졸업 요건 심사 전문가입니다.

[학생 정보]
- 학과: {transcript.department}
- 입학연도: {transcript.admission_year}년
- GPA: {transcript.gpa}
- 이수구분별 취득학점: {json.dumps(credits_by_cat, ensure_ascii=False)}

[구조화된 졸업 기준 (요람 별표5 직접 추출 - 신뢰도 높음)]
출처: {source_label}
{pre_check_str}

[RAG로 검색한 세부 규정 (보완 자료)]
{context}

위 데이터를 바탕으로 다음 형식으로 졸업 가능 여부를 분석하세요:

## 📊 졸업 진단 결과

### 1. 최종 판정
**[졸업 가능 / 졸업 불가 / 조건부 가능]** - 한 줄 이유 포함

### 2. 이수현황 체크리스트
| 구분 | 필요 학점 | 이수 학점 | 충족 여부 |
|------|-----------|-----------|-----------|
(구조화 데이터의 수치를 정확히 사용하세요)

### 3. 미충족 항목 및 해결 방안
(구체적인 부족 학점 수와 해결책)

### 4. 주의 사항
- GPA 2.0 미만 여부
- 핵심교양 영역별 3학점 이상 이수 여부 (인문Ⅰ·Ⅱ·소통·글로벌·창의)
- 졸업논문/졸업인증제 해당 여부

### 5. 근거 자료
- 구조화 출처: {source_label}
- RAG 보완 출처: (아래 요람 페이지 인용)

⚠️ 이 진단은 참고용입니다. 최종 확인은 반드시 교학팀에서 받으세요."""

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    # 구조화 데이터 출처를 sources 앞에 추가
    structured_source = {
        "text": json.dumps(pre_check, ensure_ascii=False) if pre_check else "구조화 데이터 없음",
        "page": "195-196",
        "section": "별표5 졸업이수학점표",
        "department": transcript.department,
        "relevance": 1.0,
        "source_type": "structured_json",
    }
    all_sources = [structured_source] + sources

    return AgentResponse(answer=resp.choices[0].message.content, sources=all_sources)


def generate_admin_report(
    transcript: TranscriptInfo,
    diagnosis: str,
    sources: list[dict],
) -> str:
    """교학팀 제출용 확인 요청서 생성."""
    source_list = "\n".join(
        f"- 요람 {s['page']}p ({s['section']}): {s['text'][:80]}..."
        for s in sources[:5]
    )
    return f"""============================
교학팀 제출용 AI 진단 확인 요청서
============================
학생명: {transcript.name}
학번: {transcript.student_id}
학과: {transcript.department}
입학연도: {transcript.admission_year}
이수학점: {transcript.completed_credits}학점
GPA: {transcript.gpa}

[AI 진단 결과 요약]
{diagnosis[:500]}...

[참고한 요람 근거 자료]
{source_list}

---
※ 본 문서는 AI가 생성한 참고 자료이며 법적 효력이 없습니다.
※ 최종 졸업 승인은 교학팀 검토 후 확정됩니다.
============================"""


def _extract_checklist(text: str) -> list[str]:
    """텍스트에서 체크리스트 항목 추출."""
    items = re.findall(r"[-•*]\s+(.+)", text)
    return items[:20] if items else []
