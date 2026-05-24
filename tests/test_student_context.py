from agent.answer_builder import build_final_answer
from agent.student_context import normalize_student_context, student_context_guidance


def test_normalizes_student_status_aliases():
    context = normalize_student_context({"status": "복학생", "term": "2026-2학기"})
    assert context["status"] == "returning"
    assert context["status_label"] == "복학생"
    assert context["term"] == "2026-2학기"


def test_student_context_guidance_for_returning_schedule():
    guidance = student_context_guidance("schedule", {"status": "returning", "concern": "수강신청"})
    assert guidance["label"] == "복학생"
    assert any("복학 신청" in task for task in guidance["tasks"])
    assert any("수강신청" in task for task in guidance["tasks"])


def test_answer_includes_student_context_section():
    chunks = [
        {
            "chunk_id": "schedule_1",
            "doc_id": "schedule_2026",
            "title": "국민대학교 학사일정",
            "url": "https://www.kookmin.ac.kr/user/scGuid/scSchedule/index.do",
            "text": "2026학년도 주요 학사일정 안내",
            "source_type": "schedule",
            "source_tier": 4,
            "issue_types": ["schedule"],
        }
    ]
    result = build_final_answer(
        "복학생인데 이번 주 뭐 해야 해?",
        "schedule",
        chunks,
        [],
        {"status": "returning", "term": "2026-2학기", "concern": "수강신청"},
    )
    assert "[학생 맞춤 확인]" in result["answer"]
    assert "선택한 학생 상태: 복학생" in result["answer"]
    assert "2026-2학기" in result["answer"]
