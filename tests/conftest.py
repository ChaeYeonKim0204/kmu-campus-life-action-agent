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


# (티어1 정리: llm_client usage-log 격리 fixture 제거 — llm_client는 unused/ 보관,
#  문자열 monkeypatch 타깃이 모듈 import를 유발해 이동 후 전 테스트 ERROR를 내던 지점.
#  잔존 테스트 6종의 사용 0건 확인. 원본은 unused/tests_tier1/ 복구 시 함께 되돌릴 것.)


@pytest.fixture(autouse=True)
def _isolate_explain(request, tmp_path, monkeypatch):
    """규정 근거 해설(explain) 격리 — 테스트가 라이브 LLM을 부르거나 데모 캐시를 오염시키지 않게.

    test_graduation_real_e2e가 모듈 레벨에서 .env를 로드하면 프로세스 전체에 키가 주입돼,
    미이수 필수가 있는 모든 audit 테스트가 explain 라이브 호출을 하게 된다. live_llm 마크가
    아니면 클라이언트를 차단하고(명시 주입 fake client는 그대로 동작), 캐시는 tmp로 돌린다.
    """
    from graduation_center.v2 import explain as _ex
    from graduation_center.v2 import report_summary as _rs
    monkeypatch.setattr(_ex, "CACHE_PATH", tmp_path / "explain_cache.json")
    # 에이전트 총평도 동일 격리 — run_summary 게이트(기본 False)가 1차 방어지만,
    # 게이트를 명시적으로 켜는 테스트도 라이브 LLM·데모 캐시에 닿지 않게(적대 H1).
    monkeypatch.setattr(_rs, "CACHE_PATH", tmp_path / "summary_cache.json")
    if "live_llm" not in request.keywords:
        monkeypatch.setattr(_ex, "_get_client", lambda: None)
        monkeypatch.setattr(_rs, "_get_client", lambda: None)
    yield
