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



@pytest.fixture(autouse=True)
def _isolate_explain(request, tmp_path, monkeypatch):
    """규정 근거 해설(explain) 격리 — 테스트가 라이브 LLM을 부르거나 데모 캐시를 오염시키지 않게.

    test_graduation_real_e2e가 모듈 레벨에서 .env를 로드하면 프로세스 전체에 키가 주입돼,
    미이수 필수가 있는 모든 audit 테스트가 explain 라이브 호출을 하게 된다. live_llm 마크가
    아니면 클라이언트를 차단하고(명시 주입 fake client는 그대로 동작), 캐시는 tmp로 돌린다.
    """
    from graduation_center.v2 import explain as _ex
    monkeypatch.setattr(_ex, "CACHE_PATH", tmp_path / "explain_cache.json")
    if "live_llm" not in request.keywords:
        monkeypatch.setattr(_ex, "_get_client", lambda: None)
    yield
