"""modules/executor.py — Human-in-the-Loop 의사결정 및 액션 [뼈대].

설계 의도(스펙 3.5):
- 안전한 자율성: 에이전트가 독단으로 캘린더/이메일을 건드리지 않는다.
- 마이크로 인터랙션: 분석 리포트 + 신청서 초안 링크를 Telegram 인라인 버튼
  ([승인]/[거절])으로 발송. 사용자가 [승인]을 누르는 순간 콜백이 Google Calendar /
  Notion API를 깨워 최종 액션을 완료한다.

모드:
- TELEGRAM_BOT_TOKEN+CHAT_ID 있으면 → 실제 텔레그램 승인.
- 없으면 → 콘솔 승인(AUTO_APPROVE=1 이면 자동 승인). "모의" = 실제 API 대신 로그만.

⚠️ 현재는 뼈대 — 텔레그램/캘린더/노션 실연동은 TODO. 콘솔 승인 + 모의 로그로 흐름만.
"""
from __future__ import annotations

import os

from . import log_step

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "").lower() in ("1", "true", "yes")


def _format_report(notice: dict, result, schedule_ok: bool) -> str:
    """승인 요청에 띄울 컨설팅 리포트 텍스트."""
    return (
        f"📩 [공모전 추천] {notice.get('title', '')}\n"
        f"   적합도 {result.suitability_score}점 · 예상 {result.estimated_hours_needed}h "
        f"· 일정 {'여유 있음' if schedule_ok else '빠듯함'}\n"
        f"   사유: {result.matching_reason}"
    )


def request_approval(notice: dict, result, schedule_ok: bool = True) -> str:
    """승인 요청을 보내고 'approve' / 'reject' 를 반환."""
    report = _format_report(notice, result, schedule_ok)
    log_step("executor", "승인 요청 준비", status="run")

    # TODO(vibe-coding Prompt 4 / executor — Telegram):
    #   - requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
    #         "chat_id": CHAT_ID, "text": report,
    #         "reply_markup": {"inline_keyboard": [[
    #             {"text": "승인", "callback_data": "approve"},
    #             {"text": "거절", "callback_data": "reject"}]]}})
    #   - getUpdates 롱폴링으로 callback_query 대기 → answerCallbackQuery → 결과 반환
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        raise NotImplementedError("텔레그램 실연동 미구현 — 위 TODO 참고")

    # --- 콘솔 폴백 (뼈대) ---
    log_step("executor", "텔레그램 미설정 → 콘솔 승인으로 대체(모의)", status="warn")
    print("\n" + report + "\n")
    if AUTO_APPROVE:
        log_step("executor", "AUTO_APPROVE=1 → 자동 승인", status="ok")
        return "approve"
    try:
        answer = input("승인하시겠습니까? [y/n]: ").strip().lower()
    except EOFError:
        log_step("executor", "비대화형 환경 → 자동 승인(데모)", status="warn")
        return "approve"
    return "approve" if answer in ("y", "yes", "ㅛ") else "reject"


def execute_actions(notice: dict, result) -> None:
    """승인된 건에 대해 캘린더 일정 등록 + 노션 티켓 생성."""
    log_step("executor", "승인 확인 — 자율 실행 시작", status="ok")
    _create_calendar_event(notice, result)
    _create_notion_ticket(notice, result)


def _create_calendar_event(notice: dict, result) -> None:
    # TODO(vibe-coding Prompt 4 / executor — Google Calendar):
    #   - Calendar service.events().insert(...) 로 비어있는 시간대에
    #     '공모전 준비'(estimated_hours_needed 만큼) 일정 등록.
    if os.getenv("GOOGLE_TOKEN_PATH") and os.path.exists(os.getenv("GOOGLE_TOKEN_PATH", "")):
        raise NotImplementedError("구글 캘린더 실연동 미구현 — 위 TODO 참고")
    log_step("executor",
             f"(모의) 구글캘린더에 '공모전 준비' {result.estimated_hours_needed}h 일정 가등록 완료",
             status="ok")


def _create_notion_ticket(notice: dict, result) -> None:
    # TODO(vibe-coding Prompt 4 / executor — Notion):
    #   - requests.post("https://api.notion.com/v1/pages", headers={Authorization, Notion-Version},
    #         json={parent:{database_id: NOTION_DATABASE_ID}, properties:{...}})
    #   - 칸반 작업 티켓 + 서류 초안 뼈대 생성.
    if os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID"):
        raise NotImplementedError("노션 실연동 미구현 — 위 TODO 참고")
    log_step("executor",
             f"(모의) 노션 칸반에 '{notice.get('title', '')[:20]}' 작업 티켓 + 서류 초안 뼈대 생성 완료",
             status="ok")
