"""Detect out-of-scope (casual / non-academic) intent before retrieval.

Inserted between classify_issue and retrieval. Without this node, casual queries
either coincidentally match an issue keyword (e.g. "오늘 점심 뭐먹을까?" hits the
schedule "오늘" keyword and returns 학사일정 chunks — 동문서답) or fall through
to ``other`` and surface as a cold "공식 근거 없음" block. Either path damages
the demo. This node yields a single deterministic friendly redirect that lists
sample 학사·캠퍼스 questions instead.
"""

from __future__ import annotations


CASUAL_PATTERNS: dict[str, list[str]] = {
    "greeting": ["안녕", "ㅎㅇ", "hello", "hi ", "반가워", "잘 지내", "잘지내"],
    "food": [
        "점심", "저녁", "아침", "야식", "간식",
        "뭐 먹", "뭐먹", "뭘 먹", "뭘먹", "먹을까",
        "맛집", "맛있는", "배고프", "배고파",
    ],
    "weather": ["날씨", "비 와", "비와", "더워", "추워", "눈 와", "눈와", "흐려"],
    "smalltalk": [
        "심심", "재밌어", "재밌는", "지루",
        "할 거 없", "할거없", "뭐 하지", "뭐하지", "심심해",
    ],
    "personal": [
        "내 mbti", "운세", "사주", "타로", "연애",
        "여자친구", "남자친구", "썸",
    ],
}


# Academic / campus-procedure terms that veto the out-of-scope verdict.
# If any of these are present we trust the classifier and run normal retrieval.
# Keep this list synced with classifier.ISSUE_KEYWORDS roots — anything that
# names a 학사 절차, 캠퍼스 시설 (학식 포함), 또는 행정 키워드 should be here.
ACADEMIC_OVERRIDE_TERMS: list[str] = [
    "학식", "기숙사", "셔틀", "도서관", "열람", "주차",
    "출석", "결석", "공결", "휴학", "복학", "수강", "수강신청",
    "등록금", "납부", "장학", "장학금", "증명서", "학생증",
    "포털", "이캠", "ecampus", "졸업", "학적", "학적부",
    "보험", "상해", "예비군", "병무", "훈련", "공가",
    "신청", "발급", "정정", "환불",
]


def detect_out_of_scope(query: str) -> dict:
    """Classify whether a query is casual / out-of-scope.

    Returns ``{"out_of_scope": bool, "category": str | None, "matched_terms": [...]}``.
    """
    normalized = (query or "").lower().strip()
    if not normalized:
        return {"out_of_scope": False, "category": None, "matched_terms": []}

    if any(term in normalized for term in ACADEMIC_OVERRIDE_TERMS):
        return {"out_of_scope": False, "category": None, "matched_terms": []}

    matched: list[str] = []
    category: str | None = None
    for cat, patterns in CASUAL_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                matched.append(pattern)
                if category is None:
                    category = cat

    if matched:
        return {"out_of_scope": True, "category": category, "matched_terms": matched}
    return {"out_of_scope": False, "category": None, "matched_terms": []}


SUGGESTED_QUESTIONS: list[str] = [
    "오늘 학식 메뉴는 어디서 확인해?",
    "이번 주 학사일정 알려줘",
    "출석인정신청서 어떻게 써?",
    "장학금 신청 기간 언제야?",
    "졸업요건 확인하고 싶어",
]


_CATEGORY_INTRO: dict[str, str] = {
    "greeting": "안녕하세요! 저는 국민대학교 학사·캠퍼스 절차 안내를 도와드리는 도우미예요.",
    "food": "맛있는 식사 고민이시군요. 다만 저는 국민대 학사·캠퍼스 절차 안내 전용이라 식사 추천은 어려워요.",
    "weather": "날씨 정보는 제 영역이 아니에요. 저는 국민대 학사·캠퍼스 절차 안내 전용이에요.",
    "smalltalk": "잠시 한숨 돌리는 시간이시죠? 저는 학사·캠퍼스 절차 전용이라 잡담은 잘 못 도와드려요.",
    "personal": "개인 상담은 제 영역이 아니에요. 저는 국민대 학사·캠퍼스 절차 안내 전용이에요.",
}

_DEFAULT_INTRO = "저는 국민대학교 학사·캠퍼스 절차 안내 전용이에요."


def build_out_of_scope_answer(category: str | None, suggestions: list[str] | None = None) -> str:
    """Compose the deterministic friendly redirect text."""
    intro = _CATEGORY_INTRO.get(category or "", _DEFAULT_INTRO)
    picks = (suggestions or SUGGESTED_QUESTIONS)[:3]
    sample_block = "\n".join(f"• {q}" for q in picks)
    return (
        f"{intro}\n\n"
        f"대신 이런 질문에 답해 드릴 수 있어요:\n{sample_block}\n\n"
        f"[주의] 본 안내는 국민대학교 학사·캠퍼스 절차 범위 안에서만 동작합니다. "
        f"공식 자료가 닿지 않는 질문은 정확한 답을 보장하기 어렵습니다."
    )


def suggested_questions(limit: int = 3) -> list[str]:
    """Expose suggestion list so callers (e.g. response payload) can surface chips."""
    return SUGGESTED_QUESTIONS[:limit]
