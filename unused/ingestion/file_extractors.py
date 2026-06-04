"""File extraction placeholders for attachments."""

from __future__ import annotations


def describe_attachment_support(file_name: str) -> dict:
    """Return MVP attachment support status by file extension."""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return {"supported": True, "method": "pdf_text_planned", "note": "PDF 텍스트 추출 확장 지점입니다."}
    if lower.endswith(".docx"):
        return {"supported": True, "method": "docx_text_planned", "note": "DOCX 텍스트 추출 확장 지점입니다."}
    if lower.endswith((".png", ".jpg", ".jpeg")):
        return {"supported": False, "method": "ocr_needed", "note": "이미지 OCR은 2차 확장 기능입니다."}
    if lower.endswith((".hwp", ".hwpx")):
        return {"supported": False, "method": "hwp_converter_needed", "note": "HWP/HWPX 처리는 장기 확장 기능입니다."}
    return {"supported": False, "method": "unknown", "note": "지원 여부 확인이 필요합니다."}

