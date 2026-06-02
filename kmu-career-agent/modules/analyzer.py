"""modules/analyzer.py — Gemini/OpenAI 기반 맥락 분석 [뼈대].

설계 의도(스펙 3.3):
- 정제된 공지 + 첨부 평가기준 + user_context 를 비교 분석.
- 결과를 Pydantic BaseModel(AnalysisResult)로 **강제**해 정형 JSON 출력.
- 개인 역량 가중치: 공모 도메인이 user_context.high_proficiency에 속하면 0.7배(숙련),
  생소하면 1.5배(학습) 를 기본 소요시간에 곱해 estimated_hours_needed 를 동적 보정.

LLM 공급자: 스펙 헤더는 Gemini 3.5 Flash이나 구현 프롬프트는 OpenAI 기반 →
   팀 OpenAI 키(OPENAI_MODEL, 기본 gpt-4o-mini / 팀 권장 gpt-5-mini)로 구현.

⚠️ 현재는 뼈대 — analyze()는 단순 키워드 휴리스틱으로 placeholder 결과를 만든다.
   실제 LLM 구조화 출력은 아래 TODO + vibe-coding 프롬프트 참고해 채울 것.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from . import log_step

# 개인 역량 가중치 (스펙 3.3)
WEIGHT_SKILLED = 0.7   # 숙련 분야 → 시간 단축
WEIGHT_NOVEL = 1.5     # 생소 분야 → 학습 시간 가중
WEIGHT_NEUTRAL = 1.0


class AnalysisResult(BaseModel):
    """analyzer 최종 출력 스키마 (노드 간 데이터 계약)."""

    is_relevant: bool = Field(description="이 공지가 학생에게 관련 있는가")
    suitability_score: int = Field(description="적합도 0~100", ge=0, le=100)
    matching_reason: str = Field(description="매칭/비매칭 사유 (한국어)")
    estimated_hours_needed: int = Field(description="가중치 보정된 예상 소요 시간(h)", ge=0)
    # 부가(시연·디버깅·가중치 추적용)
    domain: str = Field(default="", description="공고 도메인: 'AI 기술 구현' | '서비스 기획' | '기타'")
    applied_weight: float = Field(default=1.0, description="적용된 역량 가중치")


def analyze(notice: dict, criteria: dict, user_context: dict) -> AnalysisResult:
    """공지 1건을 분석해 AnalysisResult 반환.

    뼈대: LLM 없이 키워드 휴리스틱으로 placeholder 결과 생성.
    """
    log_step("analyzer", f"맥락 분석 시작: {notice.get('title', '')[:30]}", status="run")

    # TODO(vibe-coding Prompt 3 / analyzer):
    #   1) OpenAI Structured Outputs(또는 pydantic 파싱)로 정형 JSON 강제 출력.
    #      from openai import OpenAI
    #      client = OpenAI()  # OPENAI_API_KEY 필요
    #      model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    #      프롬프트에 notice/criteria/user_context를 넣고 아래를 받게 한다:
    #        is_relevant(bool), suitability_score(int 0~100), matching_reason(str),
    #        base_hours(int), domain(str), required_skills(list[str])
    #      temperature=0  # 결정론적 출력(루브릭)
    #   2) 가중치는 파이썬에서 결정론적으로 계산(LLM에 맡기지 말 것):
    #        high = set(user_context.get("high_proficiency", []))
    #        weight = WEIGHT_SKILLED if (set(required_skills) & high) else \
    #                 (WEIGHT_NOVEL if is_relevant else WEIGHT_NEUTRAL)
    #        estimated = max(1, round(base_hours * weight))
    #      log_step("analyzer", f"개인 역량 가중치 {weight}배 적용 완료", status="ok")
    #   3) OPENAI_API_KEY 없으면 아래 휴리스틱으로 폴백.

    _ = os.getenv("OPENAI_API_KEY")  # (실제 구현 시 분기)

    # --- placeholder 휴리스틱 (뼈대) ---
    high = set(user_context.get("high_proficiency", []))
    text = (notice.get("title", "") + " " + notice.get("body", "")).lower()
    is_relevant = any(k in text for k in ["ai", "데이터", "공모", "경진"])
    skilled = any(s.lower() in text for s in high)
    weight = WEIGHT_SKILLED if skilled else (WEIGHT_NOVEL if is_relevant else WEIGHT_NEUTRAL)
    base_hours = 20
    estimated = max(1, round(base_hours * weight))
    domain = "AI 기술 구현" if skilled else ("서비스 기획" if is_relevant else "기타")

    log_step("analyzer", f"개인 역량 가중치 {weight}배 적용 완료(placeholder)", status="ok",
             weight=weight, estimated_hours=estimated)

    return AnalysisResult(
        is_relevant=is_relevant,
        suitability_score=80 if skilled else (60 if is_relevant else 20),
        matching_reason="[placeholder] 실제 LLM 분석으로 교체 필요",
        estimated_hours_needed=estimated,
        domain=domain,
        applied_weight=weight,
    )
