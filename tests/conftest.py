"""Pytest path + LLM usage-log isolation + live_llm opt-in skip."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_collection_modifyitems(config, items):
    """`live_llm` 마크 테스트는 명시 opt-in 없으면 skip.

    실행 방법:
    - 기본 (skip):  pytest
    - opt-in:        pytest -m live_llm   또는   RUN_LIVE_LLM=1 pytest
    """
    import os

    markexpr = config.getoption("-m", default="") or ""
    if "live_llm" in markexpr or os.getenv("RUN_LIVE_LLM"):
        return
    skip_live = pytest.mark.skip(reason="live_llm — opt-in via `pytest -m live_llm` 또는 RUN_LIVE_LLM=1")
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _isolate_llm_usage_log(tmp_path, monkeypatch):
    """Redirect llm_client.USAGE_LOG_PATH to a per-test tmp file.

    P1의 usage 로그는 항상 파일에 쓰는데, 테스트 중에 실제
    `data/state/llm_usage.jsonl`을 오염시키면 안 된다. 모든 테스트에 자동 적용,
    경로가 필요한 테스트는 `usage_log_path` 픽스처로 받는다.
    """
    log_path = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr("llm_client.USAGE_LOG_PATH", log_path, raising=False)
    yield log_path


@pytest.fixture
def usage_log_path(_isolate_llm_usage_log):
    """Expose the isolated log path for tests that want to read it."""
    return _isolate_llm_usage_log

