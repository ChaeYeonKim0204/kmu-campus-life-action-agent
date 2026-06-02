"""modules/validator.py — 일정 타당성 검증 알고리즘 [뼈대].

설계 의도(스펙 3.4):
- Google Calendar Free/Busy로 이번 주 고정 일정(Busy) 총 시간을 계산.
- 인간 생활 보호 버퍼: 순수 공강의 100%를 채우지 않고 항상 30% 여유를 남긴다
  (safe_ratio = 0.7). safe_free_hours >= estimated_hours_needed 일 때만 Pass.

⚠️ 현재는 뼈대 — _get_busy_hours_this_week()는 모의 Busy 값을 돌려준다.
   실제 Google Calendar 연동은 아래 TODO + vibe-coding 프롬프트 참고해 채울 것.
"""
from __future__ import annotations

import os

from . import log_step

SAFE_RATIO = 0.7  # 30% 안전 버퍼 (스펙 3.4)
WEEKLY_PRODUCTIVE_HOURS = float(os.getenv("WEEKLY_PRODUCTIVE_HOURS", "70"))

# 뼈대 단계에서 쓰는 모의 Busy(이번 주 고정 일정 합계, 시간)
MOCK_BUSY_HOURS = 28.0


def _get_busy_hours_this_week() -> float:
    """이번 주 Google Calendar Busy 총 시간(h). 뼈대: 모의 값 반환."""
    # TODO(vibe-coding Prompt 3 / validator):
    #   - google-api-python-client + token.json(OAuth)로 Calendar service 빌드.
    #   - service.freebusy().query(body={timeMin, timeMax(이번 주), items:[{id:'primary'}]})
    #   - 반환된 busy 구간들의 (end-start) 합을 시간 단위로 누적.
    #   - 자격증명 없으면 MOCK_BUSY_HOURS 폴백.
    log_step("validator", f"이번 주 Busy 시간 계산: {MOCK_BUSY_HOURS}h (모의)", status="warn")
    return MOCK_BUSY_HOURS


def validate_schedule(estimated_hours: int) -> bool:
    """예상 소요 시간이 30% 버퍼 적용 후 가용 시간에 들어오면 True."""
    log_step("validator", "일정 타당성 검증 시작", status="run")

    busy = _get_busy_hours_this_week()
    pure_free = max(0.0, WEEKLY_PRODUCTIVE_HOURS - busy)
    safe_free = round(pure_free * SAFE_RATIO, 1)

    log_step(
        "validator",
        f"30% 스케줄 안전 버퍼 계산 완료 (가용 {WEEKLY_PRODUCTIVE_HOURS}h - Busy {busy}h "
        f"→ 순수공강 {pure_free}h → 안전가용 {safe_free}h)",
        status="ok",
        safe_free=safe_free, estimated=estimated_hours,
    )

    ok = safe_free >= estimated_hours
    log_step(
        "validator",
        f"검증 결과: {'PASS' if ok else 'FAIL'} (필요 {estimated_hours}h vs 안전가용 {safe_free}h)",
        status="ok" if ok else "warn",
    )
    return ok
