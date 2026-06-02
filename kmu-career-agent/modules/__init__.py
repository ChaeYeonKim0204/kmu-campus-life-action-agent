"""kmu-career-agent — 공통 유틸리티 (구조화된 단계 로깅 + 경량 트레이스 버스).

각 노드(scraper → document_ai → analyzer → validator → executor)가 실행 단계를
구조화된 형태로 콘솔에 출력하고 트레이스에 기록하도록 돕는다. 이 트레이스는
데모에서 "지금 어떤 워크플로우 노드가 흐르고 있는지"를 시각적으로 보여주는
토대가 된다(향후 별도 시각화 프론트가 trace.json / NDJSON 을 소비).
"""
from __future__ import annotations

import json
import os
import sys
import time

__all__ = ["log_step", "trace_events", "dump_trace", "NODE_LABELS"]

NODE_LABELS = {
    "main": "0·파이프라인",
    "scraper": "1·데이터수집",
    "document_ai": "2·문서지능",
    "analyzer": "3·맥락분석",
    "validator": "4·일정검증",
    "executor": "5·HITL액션",
}

_STATUS_ICON = {"run": "▶", "ok": "✓", "warn": "!", "fail": "✗", "wait": "⏳", "info": "·"}

# 누적 트레이스(실행 1회분). 시각화 프론트가 dump_trace 결과를 로드할 수 있다.
trace_events: list[dict] = []

_EMIT_JSON = os.getenv("TRACE_JSON", "").lower() in ("1", "true", "yes")


def log_step(node: str, message: str, status: str = "info", **data) -> dict:
    """노드 실행 한 단계를 콘솔에 출력하고 트레이스에 기록한다."""
    event = {
        "ts": time.strftime("%H:%M:%S"),
        "node": node,
        "label": NODE_LABELS.get(node, node),
        "status": status,
        "message": message,
        "data": data or {},
    }
    trace_events.append(event)
    icon = _STATUS_ICON.get(status, "·")
    label = NODE_LABELS.get(node, node)
    print(f"[{event['ts']}] {icon} {label:<12} | {message}", flush=True)
    if _EMIT_JSON:
        print("TRACE " + json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)
    return event


def dump_trace(path: str = "trace.json") -> None:
    """누적된 워크플로우 트레이스를 JSON으로 저장."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(trace_events, fh, ensure_ascii=False, indent=2)
    log_step("main", f"워크플로우 트레이스 저장 완료 → {path}", status="ok")
