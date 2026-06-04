"""데모 워밍업: 학생 4명 × 칩 질문을 사전 실행해 whatif_cache.json을 적재한다.

발표 전 1회 실행(OPENAI_API_KEY 필요). 적재 후에는 키 없이도(오프라인) 칩 질문이
캐시 히트로 동작한다 — demo_script의 fallback 전략과 짝.

실행:  python scripts/warm_whatif_cache.py
출력:  학생×질문별 status·category·headline 표 — **사람 검수용**.
       환각 delta(질문에 없는 융합 포기 등)가 보이면 캐시 삭제 후 재실행하거나
       whatif._prompt 규칙을 보강할 것(검증 e2e에서 실제 환각 사례 1건 발견 이력).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graduation_center.v2 import pipeline, whatif  # noqa: E402

MANIFEST = ROOT / "data/graduation/v2/demo_students/manifest.json"

# 프론트 whatifChips()와 동일 로직 — 칩 라벨이 바뀌면 여기도 함께 갱신
def chips(ctx: dict) -> list[str]:
    out = []
    if ctx.get("current_term"):
        out.append("다음 학기 휴학하면?")
    if ctx.get("convergence_program_ids"):
        out.append("다전공·부전공을 빼면?")
    out.append("계절학기를 못 듣게 되면?" if ctx.get("seasonal_semester_allowed")
               else "계절학기를 들으면?")
    out.append("한 학기에 15학점씩만 들으면?")
    return out[:4]


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = 0
    for sid, spec in manifest.items():
        sdir = MANIFEST.parent / sid
        files = [( (sdir / f).read_bytes(), f) for f in spec["files"]]
        v = pipeline.run_verify(files, dict(spec["context"]))
        payload = {"context": v["context"], "verification_table": v["verification_table"],
                   "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
        print(f"\n== {sid} ==")
        for q in chips(spec["context"]):
            resp = whatif.run_whatif({**payload, "question": q})
            head = resp.diff.headline if resp.diff else (resp.unsupported_reason or "")
            print(f"  [{resp.status}/{resp.category}] {q}")
            print(f"    → {head[:90]}")
            if resp.applied_changes:
                print(f"    적용: {'; '.join(resp.applied_changes)[:90]}")
            # 환각 검수: 질문에 융합 언급이 없는데 융합 변경이 적용되면 경고
            conv_q = any(w in q for w in ("전공", "다전공", "부전공"))
            conv_applied = any(("추가" in c or "포기" in c) and "전공" in c
                               for c in resp.applied_changes)
            if conv_applied and not conv_q:
                bad += 1
                print("    ⚠️ 환각 의심: 질문에 없는 융합전공 변경 — 캐시 검수 필요!")
    print(f"\n{'⚠️ 환각 의심 ' + str(bad) + '건 — whatif_cache.json 검수 후 해당 키 삭제 요망' if bad else '✅ 환각 의심 없음 — 캐시 적재 완료'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
