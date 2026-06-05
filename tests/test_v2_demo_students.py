"""데모 학생 판정 회귀 + 반증 oracle (2026-06-05 사용자 발견 사후 추가).

기존 검증 캠페인의 맹점이었던 '최적성'을 핀한다: blocked/초과학기 판정은 같은 풀에
잔여 학기 배치 가능한 대안이 남아 있으면 안 된다. S1 김융합이 1학기-전용
텍스트데이터분석을 고집해 거짓 초과학기(C)로 떨어졌던 사례 — 인공지능(2학기) 선택
시 2026-2 졸업 가능(A+). 데모 4명의 '검증된 진짜 판정'을 고정해 동류 회귀를 차단.
(설계 의도와 실행 결과의 일치만 보면 '기대값에 박힌 버그'를 영원히 통과시킨다 —
 이 파일은 손으로 반증 검증한 ground truth를 핀한다.)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from graduation_center.v2.pipeline import run_audit, run_verify

BASE = Path("data/graduation/v2/demo_students")

pytestmark = pytest.mark.skipif(not (BASE / "manifest.json").exists(),
                                reason="데모 학생 데이터 없음")


def _run(key: str) -> dict:
    man = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    s = man[key]
    files = [((BASE / key / f).read_bytes(), f) for f in s["files"]]
    v = run_verify(files, s["context"])
    return run_audit({"context": v["context"], "verification_table": v["verification_table"],
                      "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]},
                     skip_explain=True, run_summary=False).model_dump()


def test_s1_no_false_overflow():
    """S1: 융합 9학점 부족은 잔여 학기(2026-2) 개설 과목 3개로 닫힌다 — 거짓 초과학기 금지."""
    r = _run("S1_졸업반_김융합")
    plan, risk = r["roadmap"], r["risk"]
    assert plan["status"] == "generated" and plan["feasible"] is True
    assert plan.get("overflow") is None
    assert risk["grade"] == "A+"
    # ground truth 핀: 2026-2 단일 학기에 2학기-개설 융합 3과목 — 과목명까지 고정하고
    # 전부 catalog_verified·offered_terms 보유를 요구(codex 지적: offered_terms 빈 값
    # name_only로 새면 아래 개설학기 oracle이 무력화되는 구멍 차단)
    assert [t["term"] for t in plan["terms"]] == ["2026-2"]
    placed = {c["name_ko"] for t in plan["terms"] for c in t["courses"]}
    assert placed == {"다변량통계분석", "비즈니스통계응용", "인공지능"}
    # oracle 핵심: 배치된 모든 과목이 그 학기에 실제 개설되는가
    for t in plan["terms"]:
        sem = t["term"].split("-")[1]
        for c in t["courses"]:
            assert c["confidence"] == "catalog_verified" and c["offered_terms"], \
                f"{c['name_ko']} 개설학기 미상으로 oracle 우회"
            assert sem in c["offered_terms"], f"{c['name_ko']}를 {t['term']} 미개설인데 배치"


def test_s2_overflow_is_arithmetic_floor():
    """S2: 초과 +1은 산술 실재(잔여 55학점 > 18캡×3=54) — 선택 버그로 부풀린 값 아님을 고정."""
    r = _run("S2_3학년_박분석")
    assert r["roadmap"]["status"] == "blocked"
    assert r["roadmap"]["overflow"]["extra_semesters"] == 1
    assert r["risk"]["grade"] == "B"


def test_s3_true_overflow_unchanged():
    """S3: +4는 92학점/18캡=6학기의 진짜 floor (반증 리뷰로 확인) — ⑦′ 분기 데모 케이스."""
    r = _run("S3_2학년_이지연")
    assert r["roadmap"]["status"] == "blocked"
    assert r["roadmap"]["overflow"]["extra_semesters"] == 4
    assert r["risk"]["grade"] == "D"


def test_s4_feasible_unchanged():
    """S4: 계절 없이 정규 2학기 feasible·A+ (데모 메인)."""
    r = _run("S4_4학년_최계절")
    assert r["roadmap"]["feasible"] is True
    assert r["risk"]["grade"] == "A+"
