"""Rule-based issue classifier for the MVP agent."""

from __future__ import annotations


ISSUE_KEYWORDS: dict[str, list[str]] = {
    "attendance": ["출석", "출석인정", "결석", "예비군", "훈련", "공결", "공가", "훈련필증", "소집통지서"],
    "leave_return": ["휴학", "복학", "질병휴학", "가사휴학", "군휴학", "휴복학"],
    "course_registration": ["수강신청", "수강 신청", "수강정정", "수강 정정", "수변", "폐강", "시간표", "장바구니", "담아두기", "매크로", "교과목 거래", "분반"],
    "registration_tuition": ["등록금", "등록", "분납", "납부", "납부확인", "납부 확인", "고지서", "등록기간", "입금", "납입"],
    "certificate": ["증명서", "졸업예정증명서", "성적증명서", "재학증명서", "발급"],
    "student_id": ["학생증", "모바일학생증", "모바일 학생증", "k-card", "kcard", "케이카드", "국제학생증", "재발급", "카드 인식", "안 찍"],
    "scholarship": ["장학", "장학금", "국가장학금", "국장", "근로장학", "근장", "학자금", "대출", "등록금지원", "선발", "지급"],
    "portal_access": ["포털", "on국민", "온국민", "종정시", "종합정보", "ecampus", "e-campus", "이캠", "이캠퍼스", "가상대학", "가대", "로그인", "비밀번호", "아이디"],
    "campus_facility": ["통학버스", "셔틀", "셔틀버스", "주차", "기숙사", "생활관", "도서관", "열람석", "오늘의 메뉴", "식단", "밥", "학식"],
    "academic_record": ["학적부", "학적부 정정", "개명", "이름 변경", "영문명", "학적 정정", "주소 변경"],
    "student_insurance": ["학생보험", "보험", "상해", "사고", "치료비"],
    "graduation": ["졸업요건", "졸업", "이수학점", "요람", "전공필수", "전공선택"],
    "schedule": ["언제", "기간", "일정", "마감", "신청기간", "오늘", "이번 주", "이번주", "이번 달", "이번달", "지금", "다가오는", "할 일"],
    "contact": ["문의", "어디에", "어디로", "부서", "전화", "연락", "과사", "학과사무실", "메일", "문자"],
    "military": ["예비군", "병무", "군", "훈련"],
    "student_support": ["학생증", "보험", "상담", "IT", "기숙사", "도서관"],
}


def classify_issue(query: str) -> dict:
    """Classify a user query into a campus-life issue type."""
    normalized = (query or "").lower()
    scores: dict[str, int] = {}
    for issue, keywords in ISSUE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if score:
            scores[issue] = score

    if not scores:
        return {"issue_type": "other", "confidence": 0.0, "scores": {}}

    attendance_specific = ["출석", "출석인정", "결석", "공결"]
    if scores.get("military") and not any(keyword in normalized for keyword in attendance_specific):
        return {
            "issue_type": "military",
            "confidence": min(1.0, 0.35 + scores["military"] * 0.2),
            "scores": scores,
        }

    strong_schedule_intent = ["이번 주", "이번주", "이번 달", "이번달", "오늘", "다가오는", "할 일", "뭐 해야"]
    specific_scores_for_schedule = {issue: score for issue, score in scores.items() if issue not in {"schedule", "contact", "student_support"}}
    if scores.get("schedule") and any(keyword in normalized for keyword in strong_schedule_intent):
        if not specific_scores_for_schedule or set(specific_scores_for_schedule) <= {"leave_return"}:
            return {
                "issue_type": "schedule",
                "confidence": min(1.0, 0.35 + scores["schedule"] * 0.2),
                "scores": scores,
            }

    meta_issues = {"schedule", "contact", "student_support"}
    specific_scores = {issue: score for issue, score in scores.items() if issue not in meta_issues}
    rankable_scores = specific_scores or scores
    ranked = sorted(rankable_scores.items(), key=lambda item: (-item[1], item[0]))
    issue_type, score = ranked[0]
    return {
        "issue_type": issue_type,
        "confidence": min(1.0, 0.35 + score * 0.2),
        "scores": scores,
    }
