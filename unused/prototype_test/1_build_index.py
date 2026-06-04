"""
1_build_index.py
요람 PDF를 파싱하여 ChromaDB에 인덱싱합니다.
실행: python3 1_build_index.py
"""

import os
import re
import json
import pdfplumber
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

PDF_PATH = "2025국민대학교요람_20250910.pdf"
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "kookmin_yoram"

# 목차 기반 주요 섹션 키워드 (청킹 분리 기준)
SECTION_MARKERS = [
    "졸업이수학점", "졸업 이수 학점", "졸업요건", "졸업 요건",
    "교과과정", "교과 과정", "교육과정",
    "교과목 개요", "교과목개요",
    "이수규정", "이수 규정",
    "마이크로디그리", "마이크로 디그리", "소학위",
    "복수전공", "부전공", "융합전공",
    "졸업예정증명서", "학위수여",
]


def chunk_text(text: str, page_num: int, max_chars: int = 800) -> list[dict]:
    """텍스트를 의미 단위(문단 + 길이 제한)로 청킹."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > max_chars and current:
            chunks.append({"text": current.strip(), "page": page_num})
            current = para
        else:
            current = current + "\n" + para if current else para

    if current.strip():
        chunks.append({"text": current.strip(), "page": page_num})

    return chunks


def detect_section(text: str) -> str:
    """텍스트에서 섹션 유형 감지."""
    text_lower = text
    for marker in SECTION_MARKERS:
        if marker in text_lower:
            return marker
    return "일반"


def extract_department(text: str) -> str:
    """학과명 추출 시도."""
    patterns = [
        r"([가-힣]+학과)\s",
        r"([가-힣]+전공)\s",
        r"([가-힣]+학부)\s",
        r"([가-힣]+대학)\s",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "공통"


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """OpenAI 임베딩 배치 처리 (최대 100개씩)."""
    embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # 빈 텍스트 방지
        batch = [t if t.strip() else " " for t in batch]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        embeddings.extend([r.embedding for r in response.data])
        print(f"  임베딩 {i + len(batch)}/{len(texts)} 완료")
    return embeddings


def build_index():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수를 설정하세요 (.env 파일 또는 export)")

    openai_client = OpenAI(api_key=api_key)
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 기존 컬렉션 삭제 후 재생성
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print("기존 컬렉션 삭제 완료")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"PDF 파싱 시작: {PDF_PATH}")
    all_chunks = []

    with pdfplumber.open(PDF_PATH) as pdf:
        total = len(pdf.pages)
        print(f"총 {total}페이지")

        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num % 100 == 0:
                print(f"  페이지 {page_num}/{total} 처리 중...")

            text = page.extract_text()
            if not text or len(text.strip()) < 30:
                continue

            chunks = chunk_text(text, page_num)
            for chunk in chunks:
                chunk["section"] = detect_section(chunk["text"])
                chunk["department"] = extract_department(chunk["text"])
                all_chunks.append(chunk)

    print(f"\n총 {len(all_chunks)}개 청크 생성 완료")

    # 임베딩 생성 및 ChromaDB 저장
    texts = [c["text"] for c in all_chunks]
    print("임베딩 생성 중 (OpenAI text-embedding-3-small)...")
    embeddings = embed_batch(openai_client, texts)

    print("ChromaDB에 저장 중...")
    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        collection.add(
            ids=[f"chunk_{i + j}" for j in range(len(batch))],
            embeddings=embeddings[i : i + len(batch)],
            documents=[c["text"] for c in batch],
            metadatas=[
                {
                    "page": c["page"],
                    "section": c["section"],
                    "department": c["department"],
                }
                for c in batch
            ],
        )
        print(f"  저장 {i + len(batch)}/{len(all_chunks)} 완료")

    # 인덱스 통계 저장
    stats = {
        "total_chunks": len(all_chunks),
        "total_pages": total,
        "pdf_path": PDF_PATH,
        "embedding_model": "text-embedding-3-small",
        "sections": {},
    }
    for c in all_chunks:
        stats["sections"][c["section"]] = stats["sections"].get(c["section"], 0) + 1

    with open("index_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n인덱싱 완료! ChromaDB: {CHROMA_DIR}")
    print(f"섹션별 청크 수: {stats['sections']}")


if __name__ == "__main__":
    build_index()
