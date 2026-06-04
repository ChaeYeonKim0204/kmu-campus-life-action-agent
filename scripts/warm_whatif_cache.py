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

# repo 기본 python은 3.8 — `str | None` 어노테이션으로 import 즉사하므로 선제 안내(코드R3)
if sys.version_info < (3, 10):
    sys.exit("Python >=3.10 필요 — conda kmu-agent로 실행하세요: "
             "/home/carol/exit/envs/kmu-agent/bin/python scripts/warm_whatif_cache.py")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(dotenv_path=ROOT / ".env", override=False)   # OPENAI_API_KEY — 서버와 동일 로드(실가동 발견)

from graduation_center.v2 import pipeline, report_summary, whatif  # noqa: E402

MANIFEST = ROOT / "data/graduation/v2/demo_students/manifest.json"
# cwd 무관 동작 — whatif.CACHE_PATH는 상대 경로 관례라 root 밖 실행 시 엉뚱한 위치에 생성됨(코드R3)
whatif.CACHE_PATH = ROOT / "data/graduation/v2/whatif_cache.json"
report_summary.CACHE_PATH = ROOT / "data/graduation/v2/summary_cache.json"
from graduation_center.v2 import explain  # noqa: E402
explain.CACHE_PATH = ROOT / "data/graduation/v2/explain_cache.json"  # 총평이 explain도 동반 실행(적대③)

# 프론트 whatifChips()와 동일 로직 — 칩 라벨이 바뀌면 여기도 함께 갱신
def chips(ctx: dict) -> list[str]:
    out = []
    if ctx.get("current_term"):
        out.append("다음 학기 휴학하면?")
    if ctx.get("convergence_program_ids"):
        # 신청 트랙 기반 문구 — "다전공·부전공" 병기는 LLM 추출 실패 빈발(실가동 검정)
        tracks = sorted(set((ctx.get("convergence_tracks") or {}).values()))
        out.append(f"{tracks[0] if len(tracks) == 1 else '다전공'}을 빼면?")
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
            # 환각 검수: 질문에 융합 언급이 없는데 융합 변경이 적용되면 경고 + 자동 evict
            # (런타임 _semantic_guard가 1차 차단하므로 여기 걸리면 가드 우회 신호 — 키 즉시 제거)
            conv_q = any(w in q for w in ("전공", "다전공", "부전공"))
            conv_applied = any(("추가" in c or "포기" in c) and "전공" in c
                               for c in resp.applied_changes)
            if conv_applied and not conv_q:
                bad += 1
                from graduation_center.v2.models_v2 import StudentContext
                sctx = StudentContext.model_validate(payload["context"])
                aid, _ = whatif._candidates(sctx)
                whatif._cache_evict(whatif._cache_key(
                    __import__("os").getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini"), q, sctx, aid))
                print("    ⚠️ 환각 의심: 질문에 없는 융합전공 변경 — 해당 캐시 키 자동 삭제(재실행 요망)")
            # 칩 질문은 전부 지원 범위 — unsupported가 나오면 추출 실패(자기모순 출력 등) 신호
            if resp.status != "ok":
                bad += 1
                from graduation_center.v2.models_v2 import StudentContext
                sctx = StudentContext.model_validate(payload["context"])
                aid, _ = whatif._candidates(sctx)
                whatif._cache_evict(whatif._cache_key(
                    __import__("os").getenv("OPENAI_GRADUATION_MODEL", "gpt-5-mini"), q, sctx, aid))
                print("    ⚠️ 칩 질문이 unsupported — 추출 실패 의심, 캐시 키 삭제(재실행 요망)")
    print(f"\n{'⚠️ 환각 의심 ' + str(bad) + '건 — whatif_cache.json 검수 후 해당 키 삭제 요망' if bad else '✅ 환각 의심 없음 — 캐시 적재 완료'}")

    # ---- 에이전트 총평(능동 시나리오 탐색) 워밍업 + 다양성 검수 (계획 §5) ----
    # run_summary=True opt-in — 허용 경로는 /audit 라우트와 이 스크립트뿐(계획 §1).
    print("\n==== 에이전트 총평 워밍업 ====")
    bad_chip, bad = bad, 0    # 섹션별 분리 집계 — exit code 오염 방지(적대③)
    rows, recs = [], set()
    for sid, spec in manifest.items():
        sdir = MANIFEST.parent / sid
        files = [((sdir / f).read_bytes(), f) for f in spec["files"]]
        v = pipeline.run_verify(files, dict(spec["context"]))
        payload = {"context": v["context"], "verification_table": v["verification_table"],
                   "unresolved": v["unresolved"], "possible_retakes": v["possible_retakes"]}
        r1 = pipeline.run_audit(payload, run_summary=True)        # 적재(미스 시 LLM 2콜)
        s = r1.agent_summary
        if s is None:
            bad += 1
            print(f"  ⚠️ {sid}: 총평 생성 실패 — {r1.summary_fallback}")
            continue
        r2 = pipeline.run_audit(payload, run_summary=True)        # 캐시 히트 확인(적대 H4)
        hit = (r2.agent_summary is not None
               and r2.agent_summary.model_dump() == s.model_dump())
        acc = sorted({sc.reason_code for sc in s.scenarios})
        rej = [f"{r.label[:18]}({r.rejected_by})" for r in s.candidates_review
               if r.verdict == "rejected"]
        recs.add((tuple(acc), s.recommendation))
        rows.append(sid)
        print(f"  {sid}: 후보 {len(s.candidates_review)} → 채택 {len(s.scenarios)} {acc}"
              f" · 권고 [{s.recommendation}] · 캐시 {'✅' if hit else '❌ 미스!'}")
        print(f"    headline: {s.headline[:80]}")
        if rej:
            print(f"    제외: {'; '.join(rej)[:100]}")
        if not hit:
            bad += 1
    # 다양성 지표(교수 처방③) — 전 학생이 같은 채택 조합+권고면 '라우터' 경고
    if len(rows) >= 3 and len(recs) == 1:
        bad += 1
        print("  ⚠️ 다양성 경고: 전 학생의 채택 reason_code 조합·권고가 동일 — "
              "에이전트가 아니라 라우터처럼 보임. selector 프롬프트 보강 후 캐시 삭제·재워밍업 요망.")
    print(f"검수 결과: 상담 {bad_chip}건 · 총평 {bad}건" if (bad_chip or bad) else "✅ 총평 워밍업 완료")
    return 1 if (bad_chip or bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
