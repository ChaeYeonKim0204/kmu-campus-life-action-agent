"""modules/document_ai.py — 첨부파일(PDF) 문서 지능 [뼈대].

설계 의도(스펙 3.2):
- 첨부 URL을 io.BytesIO 스트림으로 받아(디스크 저장 X) pdfplumber로 본문 텍스트와
  '평가 기준 표(Table)'를 한 번에 추출해 정형화한다.
- 데모는 PDF 기준. 향후 한글(HWP) 확장 레이어 고려.
- PDF 미확보 시: 데모 안정성을 위해 샘플 평가기준 표로 폴백.

⚠️ 현재는 뼈대 — parse_attachment()는 SAMPLE_CRITERIA(플레이스홀더)를 돌려준다.
"""
from __future__ import annotations

import io  # noqa: F401  (TODO에서 사용)

from . import log_step

# 첨부 PDF가 없을 때(또는 뼈대 단계) 쓰는 샘플 평가기준.
SAMPLE_CRITERIA: dict = {
    "text": "본 공모전은 기술 구현 완성도와 서비스 기획의 균형을 평가한다. ...",
    "tables": [
        [
            ["평가 항목", "배점"],
            ["기술 구현 완성도", "40"],
            ["서비스 기획·문제정의", "30"],
            ["발표·데모", "30"],
        ]
    ],
    "source": "(sample)",
}


def parse_attachment(url: str | None, timeout: int = 10) -> dict:
    """첨부 PDF에서 {text, tables, source} 를 추출해 반환.

    뼈대: 지금은 SAMPLE_CRITERIA를 반환한다.
    """
    if not url:
        log_step("document_ai", "첨부파일 없음 → 샘플 평가기준 사용(폴백)", status="warn")
        return dict(SAMPLE_CRITERIA)

    log_step("document_ai", f"첨부파일 분석 시작: {url}", status="run")

    # TODO(vibe-coding Prompt 2 / document_ai):
    #   - resp = requests.get(url, headers={"User-Agent": ...}, timeout=timeout)
    #   - stream = io.BytesIO(resp.content)            # 디스크 저장 없이 메모리 스트림
    #   - import pdfplumber
    #   - with pdfplumber.open(stream) as pdf:
    #         text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    #         tables = [t for p in pdf.pages for t in p.extract_tables()]
    #   - return {"text": text, "tables": tables, "source": url}
    #   - 실패 시 SAMPLE_CRITERIA 폴백
    #   - (확장) HWP 처리 레이어는 별도 분기로

    log_step("document_ai", "PDF 파싱 미구현 → 샘플 평가기준 사용(폴백)", status="warn")
    return dict(SAMPLE_CRITERIA)
