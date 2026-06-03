"""졸업센터 v2 — Bounded Audit Agent.

기존 graduation_center/(8-task PDF 파이프라인)와 독립적으로 동작하는 재설계 파이프라인.
입력=ON국민 수강내역(엑셀) → 코드 매칭(카탈로그) → 사용자 검증 → 결정론 진단/리스크
→ LLM 로드맵(검증·repair) → JSON-first 응답.
"""
