"""Graduation requirement data loading and matching."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path("data/graduation")


@lru_cache(maxsize=1)
def load_graduation_data(data_dir: str = str(DATA_DIR)) -> dict[str, Any]:
    """Load structured graduation data files."""
    base = Path(data_dir)
    data: dict[str, Any] = {
        "requirements": None,
        "engineering": None,
        "codes": None,
        "search_index": None,
        "policies": None,
        "missing_files": [],
    }
    files = {
        "requirements": "graduation_requirements.json",
        "engineering": "engineering_cert_requirements.json",
        "codes": "grade_category_codes.json",
        "search_index": "department_search_index.json",
        "policies": "policies.json",
    }
    for key, filename in files.items():
        path = base / filename
        if not path.exists():
            data["missing_files"].append(str(path))
            continue
        with path.open("r", encoding="utf-8") as handle:
            data[key] = json.load(handle)
    return data


def policy_sources_for_task(data: dict[str, Any] | None, task: str) -> list[dict[str, Any]]:
    """Return curated policy sources from structured graduation policy data."""
    policies = (data or {}).get("policies")
    if not isinstance(policies, dict):
        return []
    entries = policies.get(task, [])
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    sources = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        sources.append(
            {
                "title": str(entry.get("title", "국민대학교 졸업센터 정책 자료")),
                "url": str(entry.get("url", "")),
                "page": str(entry.get("page", "정책자료")),
                "section": str(entry.get("section", "졸업센터 정책")),
                "text": text,
                "relevance": float(entry.get("relevance", 1.0)),
                "source_type": str(entry.get("source_type", "graduation_policy_json")),
            }
        )
    return sources


def find_department(query: str, requirements: dict | None, search_index: dict | None) -> list[dict]:
    """Find department graduation requirements by Korean department name."""
    if not query or not requirements or not search_index:
        return []
    departments = requirements.get("departments") or {}
    query_clean = re.sub(r"\s+", "", query)
    query_tokens = re.findall(r"[가-힣A-Za-z0-9]+", query)
    candidates: dict[str, int] = {}

    for token in query_tokens:
        if token in search_index:
            for key in search_index[token]:
                candidates[key] = candidates.get(key, 0) + 2

    if not candidates or len(candidates) < 3:
        for key, entry in departments.items():
            name_clean = re.sub(r"\s+", "", str(entry.get("학과_전공명", "")))
            if query_clean and (query_clean in name_clean or name_clean in query_clean):
                candidates[key] = candidates.get(key, 0) + 1
            for token in query_tokens:
                if len(token) >= 2 and token in name_clean:
                    candidates[key] = candidates.get(key, 0) + 1

    results = []
    for key, score in sorted(candidates.items(), key=lambda item: -item[1])[:5]:
        entry = dict(departments[key])
        entry["_match_score"] = score
        entry["_key"] = key
        results.append(entry)
    return results


def category_from_code(category: str, codes: dict | None) -> str:
    """Map transcript category codes to graduation categories."""
    raw = str(category or "").strip()
    if not raw:
        return "미분류"
    relevant = (codes or {}).get("graduation_relevant_map", {})
    for label, code_list in relevant.items():
        if raw in code_list or raw == label or label in raw:
            if label in {"부전공", "다전공"}:
                return "전공"
            return label
    if raw in {"C", "D", "M", "X"} or "전공" in raw:
        return "전공"
    if raw in {"A", "B", "K", "V"} or "기초" in raw:
        return "기초교양"
    if raw == "Y" or "핵심" in raw:
        return "핵심교양"
    if raw in {"E", "L", "Z"} or "자유" in raw or "교양" in raw:
        return "자유교양"
    if raw == "F" or "일반" in raw:
        return "일반선택"
    return raw


def compute_structured_check(transcript: dict, data: dict[str, Any]) -> dict[str, Any]:
    """Compute deterministic graduation gaps from structured 요람 data."""
    matches = find_department(transcript.get("department", ""), data.get("requirements"), data.get("search_index"))
    category_credits = transcript.get("category_credits") or {}
    if not matches:
        return {
            "matched": False,
            "department": transcript.get("department", "미확인"),
            "message": "학과별 졸업요건 구조화 데이터에서 일치 학과를 찾지 못했습니다.",
            "category_credits": category_credits,
        }

    req = matches[0]
    liberal = req.get("교양", {})
    requirements = {
        "기초교양": float(liberal.get("기초교양", 0)),
        "핵심교양": float(liberal.get("핵심교양", 0)),
        "자유교양": float(liberal.get("자유교양", 0)),
        "전공": float(req.get("전공_최저", 0)),
        "일반선택": float(req.get("일반선택", 0)),
        "총학점": float(req.get("졸업_최저합계", 0)),
    }
    completed = {
        "기초교양": float(category_credits.get("기초교양", 0)),
        "핵심교양": float(category_credits.get("핵심교양", 0)),
        "자유교양": float(category_credits.get("자유교양", 0)),
        "전공": float(category_credits.get("전공", 0)),
        "일반선택": float(category_credits.get("일반선택", 0)),
        "총학점": float(transcript.get("total_credits", 0)),
    }
    gaps = {key: max(0.0, requirements[key] - completed.get(key, 0.0)) for key in requirements}
    return {
        "matched": True,
        "department": req.get("학과_전공명"),
        "college": req.get("대학"),
        "source": "요람 별표5 졸업이수학점표",
        "requirements": requirements,
        "completed": completed,
        "gaps": gaps,
        "gpa_minimum_met": transcript.get("gpa_minimum_met", "unknown"),
        "note": req.get("비고", ""),
        "match_candidates": [
            {"department": item.get("학과_전공명"), "college": item.get("대학"), "score": item.get("_match_score")}
            for item in matches
        ],
    }
