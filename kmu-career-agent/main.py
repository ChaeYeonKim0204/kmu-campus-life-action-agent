"""main.py — 학업·커리어 매니지먼트 에이전트 메인 파이프라인 [뼈대].

데이터 수집 → 문서 지능 → 맥락 분석 → 일정 검증 → (Human-in-the-Loop) 승인 → 액션
순으로 노드를 순차 실행하며 각 단계를 시각적 로그로 출력한다.
(데모 가독성을 위해 스케줄러 대신 즉시 1회 실행되는 형태)

실행:
    cd kmu-career-agent
    python main.py

키가 하나도 없어도 끝까지 동작한다(각 노드가 모의/콘솔로 폴백). 실제 동작은
각 modules/*.py의 TODO + vibe-coding 프롬프트를 채우면 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from modules import analyzer, document_ai, executor, scraper, validator
from modules import dump_trace, log_step

try:  # .env 가 있으면 로드 (없어도 무방)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv 미설치 등
    pass

CONFIG_PATH = Path(__file__).parent / "config" / "user_context.json"


def load_user_context() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        ctx = json.load(fh)
    log_step("main", f"학생 프로필 로드: {ctx.get('department', '')} / {ctx.get('desired_role', '')}",
             status="ok")
    return ctx


def run_pipeline() -> None:
    log_step("main", "===== 파이프라인 시작 =====", status="run")
    user_ctx = load_user_context()

    # 1) 수집
    notices = scraper.fetch_notices()

    # 2~4) 각 공지: 문서지능 → 맥락분석 → 일정검증
    candidates = []
    for notice in notices:
        criteria = document_ai.parse_attachment(notice.get("attachment_url"))
        result = analyzer.analyze(notice, criteria, user_ctx)
        if not result.is_relevant:
            log_step("main", f"관련 없음 → 스킵: {notice.get('title', '')[:24]}", status="info")
            continue
        schedule_ok = validator.validate_schedule(result.estimated_hours_needed)
        candidates.append((notice, result, schedule_ok))

    if not candidates:
        log_step("main", "추천할 관련 공지 없음 — 종료", status="warn")
        dump_trace()
        return

    # 5) 최적 후보 선정: 일정 통과 우선, 그중 적합도 최고
    passable = [c for c in candidates if c[2]] or candidates
    best_notice, best_result, schedule_ok = max(
        passable, key=lambda c: c[1].suitability_score
    )
    log_step("main", f"최적 후보 선정: {best_notice.get('title', '')[:24]} "
                     f"(적합도 {best_result.suitability_score})", status="ok")

    # 6) Human-in-the-Loop 승인 → 액션
    decision = executor.request_approval(best_notice, best_result, schedule_ok=schedule_ok)
    if decision == "approve":
        executor.execute_actions(best_notice, best_result)
        log_step("main", "===== 완료 (승인·실행) =====", status="ok")
    else:
        log_step("main", "===== 종료 (사용자 거절) =====", status="info")

    dump_trace()


if __name__ == "__main__":
    run_pipeline()
