"""Grounded answer assembly for the campus-life action agent."""

from __future__ import annotations

from datetime import date

from agent.citation import build_citations, cite
from agent.student_context import student_context_guidance
from agent.student_playbook import get_student_playbook
from tools.checklist import generate_checklist
from tools.contact_router import route_contact
from tools.deadline import calculate_deadline, extract_event_date


def _first_chunk(chunks: list[dict], predicate) -> dict | None:
    for chunk in chunks:
        if predicate(chunk):
            return chunk
    return chunks[0] if chunks else None


def build_final_answer(
    query: str,
    issue_type: str,
    chunks: list[dict],
    next_actions: list[dict],
    student_context: dict | None = None,
) -> dict:
    """Build the final grounded answer with citations, tool results, and source metadata."""
    labels, citations = build_citations(chunks)
    checklist = generate_checklist(issue_type, chunks)
    contacts = route_contact(issue_type, chunks)
    playbook = get_student_playbook(query, issue_type)
    context_guidance = student_context_guidance(issue_type, student_context)
    deadline = None

    deadline_chunk = _first_chunk(chunks, lambda c: bool(c.get("deadline_rule")))
    event_date = extract_event_date(query)
    if deadline_chunk and event_date:
        days = int(deadline_chunk["deadline_rule"].get("days", 0))
        if days:
            deadline = calculate_deadline(event_date, days)

    summary = _build_summary(query, issue_type, chunks, labels, deadline)
    lines = [
        "[답변 요약]",
        summary,
        "",
        "[해야 할 일]",
    ]
    lines.extend([f"{idx}. {task}" for idx, task in enumerate(checklist["tasks"], 1)])

    lines.extend(["", "[학생 경험 팁]"])
    lines.append(f"- 상황 판단: {playbook['scenario']}")
    if playbook.get("student_terms"):
        lines.append("- 알아들은 국민대식 표현: " + ", ".join(playbook["student_terms"]))
    for item in playbook.get("prechecks", [])[:3]:
        lines.append(f"- 문의 전 확인: {item}")
    if playbook.get("common_mistakes"):
        lines.append(f"- 자주 헷갈리는 점: {playbook['common_mistakes'][0]}")

    if context_guidance:
        lines.extend(["", "[학생 맞춤 확인]"])
        lines.append(f"- 선택한 학생 상태: {context_guidance['label']}")
        for item in context_guidance["tasks"]:
            lines.append(f"- {item}")

    lines.extend(["", "[문의 전 준비]"])
    for item in playbook.get("evidence", [])[:5]:
        lines.append(f"- {item}")

    lines.extend(["", "[필요 서류]"])
    if checklist["required_documents"]:
        lines.extend([f"- {document}" for document in checklist["required_documents"]])
    else:
        lines.append("- 공식 근거에서 별도 제출서류가 확인되지 않았습니다. 담당 부서 확인이 필요합니다.")

    lines.extend(["", "[신청 경로]"])
    if checklist["application_paths"]:
        lines.extend([f"- {path}" for path in checklist["application_paths"]])
    else:
        lines.append("- 공식 근거에 명시된 신청 경로가 부족합니다. 관련 공식 페이지 또는 담당 부서를 확인하세요.")

    lines.extend(["", "[기한]"])
    schedule_chunks = _unique_schedule_chunks([chunk for chunk in chunks if chunk.get("schedule")])
    if deadline:
        lines.append(f"- {deadline['description']}")
    if schedule_chunks:
        for chunk in schedule_chunks[:6]:
            marker = cite(chunk, labels)
            schedule = chunk["schedule"]
            status = _schedule_status(schedule)
            status_text = f" ({status})" if status else ""
            lines.append(f"- {schedule['label']}: {schedule['start_date']} ~ {schedule['end_date']}{status_text} {marker}")
    if not deadline and not schedule_chunks:
        lines.append("- 날짜 계산 또는 신청기간 근거가 부족합니다. 최신 학사일정/공지 확인이 필요합니다.")

    lines.extend(["", "[문의처 추천]"])
    for contact in contacts:
        phone = f" ({contact['phone']})" if contact.get("phone") else ""
        lines.append(f"- {contact.get('label', '문의')}: {contact.get('name')}{phone}")

    lines.extend(["", "[다음 행동]"])
    if next_actions:
        for action in next_actions:
            lines.append(f"- {action['label']}: {action['description']}")
    else:
        lines.append("- 공식 근거를 확인한 뒤 필요한 절차를 직접 진행하세요.")

    lines.extend(["", "[근거]"])
    for source in citations:
        excerpt = (source.get("text") or "").strip()
        if len(excerpt) > 140:
            excerpt = excerpt[:137] + "..."
        lines.append(f"- [{source['id']}] {source['title']} / {source['url']} / {excerpt}")

    lines.extend(
        [
            "",
            "[주의]",
            "최종 처리는 국민대학교 공식 포털, 담당 부서, 학과사무실 또는 담당 교강사 확인이 필요합니다. 실제 개인정보나 로그인 정보는 입력하지 마세요.",
        ]
    )
    return {
        "answer": "\n".join(lines),
        "citations": citations,
        "checklist": checklist,
        "contacts": contacts,
        "deadline": deadline,
    }


def _build_summary(query: str, issue_type: str, chunks: list[dict], labels: dict[str, str], deadline: dict | None) -> str:
    if not chunks:
        return "공식 문서 근거가 부족하므로 확인이 필요합니다."

    primary = chunks[0]
    marker = cite(primary, labels)
    if issue_type == "attendance":
        military = _first_chunk(chunks, lambda c: "예비군" in " ".join(c.get("keywords", [])))
        military_marker = cite(military, labels)
        extra = f" 제출기한 계산 결과는 {deadline['deadline']}입니다." if deadline else ""
        return f"출석인정 관련 공식 근거를 확인했습니다. 예비군 훈련은 출석인정 신청 가능 사유에 해당할 수 있으며{military_marker}, 사유 발생 7일 이내 신청서와 증빙서류 제출이 필요합니다.{marker}{extra}"
    if issue_type == "leave_return":
        return f"휴학/복학 관련 공식 안내를 확인했습니다. 신청 경로와 필요서류는 질문의 휴학/복학 유형에 따라 달라지며, ON국민 포털의 휴학/복학신청 경로를 우선 확인해야 합니다.{marker}"
    if issue_type == "course_registration":
        return f"수강신청/폐강 관련 공식 공지를 확인했습니다. 수강신청 완료 여부는 수강신청시스템 '나의 시간표' 또는 ON국민 포털 '개인수업시간표 조회' 기준으로 확인합니다.{marker}"
    if issue_type == "registration_tuition":
        return f"등록금 납부/분납 관련 질문은 학사일정과 행정공지, ON국민 포털의 개인 고지서 확인을 함께 봐야 합니다. 에이전트는 공식 경로와 문의처를 안내하고, 개인 납부 상태는 사용자가 포털에서 직접 확인해야 합니다.{marker}"
    if issue_type == "certificate":
        return f"증명서 발급 관련 공식 학생지원 안내를 확인했습니다. 인터넷 증명 발급신청 페이지에서 발급 가능한 증명서와 수수료, 문의처를 확인할 수 있습니다.{marker}"
    if issue_type == "student_id":
        return f"학생증 관련 공식 학생지원 안내를 확인했습니다. 신규/재발급/국제학생증/모바일학생증은 신청 경로와 수령 방식이 다르므로 필요한 유형을 먼저 구분해야 합니다.{marker}"
    if issue_type == "scholarship":
        return f"장학 관련 공식 공지와 학생지원 안내를 확인했습니다. 장학금은 등록금지원, 등록금외지원, 대출 등 성격에 따라 신청 요건과 중복지원 처리가 달라질 수 있습니다.{marker}"
    if issue_type == "portal_access":
        return f"ON국민 포털과 eCampus는 로그인 이후 개인 화면을 사용자가 직접 확인해야 하는 서비스입니다. 에이전트는 공식 로그인 경로와 계정 찾기/문의 흐름까지만 안내합니다.{marker}"
    if issue_type == "schedule":
        return f"학사일정 공식 근거를 확인했습니다. 아래 일정 상태는 오늘 기준으로 계산한 참고 정보이며, 신청/납부/제출이 필요한 항목은 관련 공지와 ON국민 포털에서 다시 확인해야 합니다.{marker}"
    if issue_type == "campus_facility":
        return f"통학버스, 주차, 생활관, 도서관, 식단 같은 생활지원 항목은 공식 안내와 해당 부서/시설 공지를 함께 확인해야 합니다. 예약이나 신청이 필요한 개인 화면은 사용자가 직접 처리해야 합니다.{marker}"
    if issue_type == "academic_record":
        return f"학적부 정정은 정정 항목과 증빙서류에 따라 절차가 달라집니다. 개인정보가 포함된 자료는 에이전트에 입력하지 말고 공식 포털 또는 담당 부서로 직접 제출해야 합니다.{marker}"
    if issue_type == "student_insurance":
        return f"학생보험은 사고/상해 유형, 발생일, 제출서류에 따라 확인이 필요합니다. 진단서나 영수증 같은 민감 서류는 담당 부서 안내에 따라 직접 제출해야 합니다.{marker}"
    if issue_type == "military":
        return f"병무/예비군 관련 공식 안내를 확인했습니다. 훈련으로 수업에 빠지는 경우에는 병무 절차와 별도로 출석인정 신청 가능 여부와 증빙서류도 함께 확인해야 합니다.{marker}"
    if issue_type == "graduation":
        return f"졸업요건은 요람/규정집과 학과별 교육과정 확인이 필요합니다. 실제 판정은 소속 학과와 교무팀 확인이 필요합니다.{marker}"
    return f"관련 공식 근거를 확인했습니다.{marker}"


def _schedule_status(schedule: dict) -> str | None:
    """Describe whether a schedule range is current or upcoming as of today."""
    try:
        start = date.fromisoformat(schedule["start_date"])
        end = date.fromisoformat(schedule["end_date"])
    except Exception:
        return None
    today = date.today()
    if start <= today <= end:
        return "오늘 기준 진행 중"
    if today < start:
        days = (start - today).days
        return f"오늘 기준 {days}일 후 시작"
    return "오늘 기준 종료됨"


def _unique_schedule_chunks(chunks: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for chunk in chunks:
        schedule = chunk.get("schedule") or {}
        key = (
            str(schedule.get("label", "")),
            str(schedule.get("start_date", "")),
            str(schedule.get("end_date", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique
