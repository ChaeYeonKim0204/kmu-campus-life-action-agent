"""Build the graduation-center Chroma index from the KMU yearbook PDF."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

# 루트의 .env 자동 로드 (OPENAI_API_KEY 등)
load_dotenv()


PDF_PATH = Path("test/2025국민대학교요람_20250910.pdf")
CHROMA_DIR = Path("data/graduation/chroma")
COLLECTION_NAME = "kmu_graduation_yoram"
EMBED_MODEL = "text-embedding-3-small"

SECTION_MARKERS = [
    "졸업이수학점",
    "졸업 이수 학점",
    "졸업요건",
    "졸업 요건",
    "교과과정",
    "교육과정",
    "교과목 개요",
    "이수규정",
    "마이크로디그리",
    "마이크로 디그리",
    "소학위",
    "복수전공",
    "부전공",
    "융합전공",
    "졸업예정증명서",
    "학위수여",
]


def chunk_text(text: str, page_num: int, max_chars: int = 800) -> list[dict]:
    """Split text into paragraph-aware chunks."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) > max_chars and current:
            chunks.append({"text": current.strip(), "page": page_num})
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current.strip():
        chunks.append({"text": current.strip(), "page": page_num})
    return chunks


def detect_section(text: str) -> str:
    """Detect a broad yearbook section."""
    for marker in SECTION_MARKERS:
        if marker in text:
            return marker
    return "일반"


def extract_department(text: str) -> str:
    """Best-effort department extraction for index metadata."""
    for pattern in [r"([가-힣]+학과)\s", r"([가-힣]+전공)\s", r"([가-힣]+학부)\s", r"([가-힣]+대학)\s"]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "공통"


def embed_batch(client, texts: list[str]) -> list[list[float]]:
    """Create OpenAI embeddings in batches."""
    embeddings = []
    batch_size = 100
    for index in range(0, len(texts), batch_size):
        batch = [text if text.strip() else " " for text in texts[index : index + batch_size]]
        response = client.embeddings.create(model=EMBED_MODEL, input=batch)
        embeddings.extend([item.embedding for item in response.data])
        print(f"임베딩 {index + len(batch)}/{len(texts)} 완료")
    return embeddings


def _resolve_pdf_path(default: Path) -> Path:
    """Match NFC/NFD-normalized filenames so 한글 PDF가 정규화 차이로 안 깨지게."""
    if default.exists():
        return default
    parent = default.parent if default.parent.exists() else Path(".")
    target_nfc = unicodedata.normalize("NFC", default.name)
    for candidate in parent.glob("*.pdf"):
        if unicodedata.normalize("NFC", candidate.name) == target_nfc:
            return candidate
    return default


def build_index(pdf_path: Path = PDF_PATH, chroma_dir: Path = CHROMA_DIR) -> None:
    """Build a persistent Chroma index for graduation-center RAG."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 환경변수가 필요합니다.")
    pdf_path = _resolve_pdf_path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"요람 PDF를 찾을 수 없습니다: {pdf_path}")

    import chromadb
    import pdfplumber
    from openai import OpenAI

    chroma_dir.mkdir(parents=True, exist_ok=True)
    openai_client = OpenAI()
    chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma_client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    all_chunks = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text or len(text.strip()) < 30:
                continue
            for chunk in chunk_text(text, page_num):
                chunk["section"] = detect_section(chunk["text"])
                chunk["department"] = extract_department(chunk["text"])
                all_chunks.append(chunk)

    print(f"총 {len(all_chunks)}개 청크 생성")
    embeddings = embed_batch(openai_client, [chunk["text"] for chunk in all_chunks])
    for index in range(0, len(all_chunks), 500):
        batch = all_chunks[index : index + 500]
        collection.add(
            ids=[f"grad_chunk_{index + offset}" for offset in range(len(batch))],
            embeddings=embeddings[index : index + len(batch)],
            documents=[chunk["text"] for chunk in batch],
            metadatas=[
                {"page": chunk["page"], "section": chunk["section"], "department": chunk["department"]}
                for chunk in batch
            ],
        )
        print(f"저장 {index + len(batch)}/{len(all_chunks)} 완료")

    stats = {
        "total_chunks": len(all_chunks),
        "total_pages": total_pages,
        "pdf_path": str(pdf_path),
        "embedding_model": EMBED_MODEL,
        "collection_name": COLLECTION_NAME,
    }
    with (chroma_dir.parent / "index_stats.json").open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)
    print(f"졸업 센터 인덱싱 완료: {chroma_dir}")


if __name__ == "__main__":
    build_index()
