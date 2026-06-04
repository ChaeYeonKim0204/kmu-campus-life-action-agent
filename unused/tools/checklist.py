"""Checklist generation from grounded policy chunks."""

from __future__ import annotations


def generate_checklist(issue_type: str, policy_chunks: list[dict]) -> dict:
    """Generate action items and required documents from official chunks."""
    documents: list[str] = []
    tasks: list[str] = []
    paths: list[str] = []
    submit_to: list[str] = []

    for chunk in policy_chunks:
        for document in chunk.get("required_documents", []) or []:
            if document not in documents:
                documents.append(document)
        path = chunk.get("application_path")
        if path and path not in paths:
            paths.append(path)
        target = chunk.get("submit_to")
        if target and target not in submit_to:
            submit_to.append(target)

    if issue_type == "attendance":
        tasks.extend(["결석 사유와 날짜를 확인합니다.", "출석인정신청서와 증빙서류를 준비합니다.", "기한 내 담당 교강사에게 제출합니다."])
    elif issue_type == "leave_return":
        tasks.extend(["휴학/복학 유형과 신청 기간을 확인합니다.", "ON국민 포털 신청 경로를 확인합니다.", "필요 서류가 있는 경우 제출 전 원본/사본 요건을 확인합니다."])
    elif issue_type == "course_registration":
        tasks.extend(["수강신청시스템 나의 시간표 또는 ON국민 개인수업시간표를 확인합니다.", "폐강 공지가 있는 경우 본인 수강신청 내역을 다시 확인합니다."])
    elif issue_type == "registration_tuition":
        tasks.extend(["대상 학기의 등록기간과 납부/분납 공지를 확인합니다.", "ON국민 포털에서 고지서와 납부 상태를 직접 확인합니다.", "장학금 또는 휴학 상태가 등록금에 영향을 주는지 확인합니다."])
    elif issue_type == "certificate":
        tasks.extend(["필요한 증명서 종류를 고릅니다.", "인터넷 증명 발급신청 페이지에서 발급 가능 여부를 확인합니다.", "수수료 및 원본확인 방법을 확인합니다."])
    elif issue_type == "student_id":
        tasks.extend(["신규, 재발급, 국제학생증, 모바일학생증 중 필요한 유형을 고릅니다.", "ON국민 포털 또는 우리WON뱅킹 신청 경로를 확인합니다.", "신분증, 신청서, 카드 수령 방식 등 준비물을 확인합니다."])
    elif issue_type == "scholarship":
        tasks.extend(["장학공지에서 장학금 성격과 신청기간을 확인합니다.", "등록금지원/등록금외지원/대출/기타 구분을 확인합니다.", "한국장학재단 또는 학생지원팀 안내가 필요한 항목인지 확인합니다."])
    elif issue_type == "portal_access":
        tasks.extend(["ON국민 포털 또는 eCampus 로그인 페이지에서 서비스 구분을 확인합니다.", "아이디/비밀번호 찾기는 사용자가 공식 페이지에서 직접 진행합니다.", "개인정보와 로그인 정보는 에이전트에 입력하지 않습니다."])
    elif issue_type == "schedule":
        tasks.extend(["오늘 기준 진행 중인 학사일정과 다가오는 마감을 확인합니다.", "수강신청, 등록, 휴학/복학처럼 신청이 필요한 일정은 공식 공지와 함께 확인합니다.", "개인 신청 상태는 ON국민 포털에서 직접 확인합니다."])
    elif issue_type == "campus_facility":
        tasks.extend(["통학버스, 주차, 생활관, 도서관, 식단 중 필요한 생활지원 항목을 구분합니다.", "공식 안내 페이지에서 운영시간, 신청대상, 이용방법을 확인합니다.", "공지성 변경사항은 KMU 소식 또는 해당 부서 공지를 함께 확인합니다."])
    elif issue_type == "academic_record":
        tasks.extend(["정정하려는 학적 정보 항목을 확인합니다.", "학적부 정정 공식 안내에서 신청 경로와 증빙서류를 확인합니다.", "개명, 생년월일, 주소 등 개인정보가 포함된 자료는 공식 포털이나 담당 부서에 직접 제출합니다."])
    elif issue_type == "student_insurance":
        tasks.extend(["사고/상해 발생일과 상황을 정리합니다.", "학생보험 적용 대상과 제출서류를 공식 안내에서 확인합니다.", "진단서, 진료비 영수증 등 민감 서류는 담당 부서 안내에 따라 직접 제출합니다."])
    elif issue_type == "military":
        tasks.extend(["병무/예비군 관련 메뉴에서 본인 대상 여부와 절차를 확인합니다.", "훈련으로 수업에 빠지는 경우 출석인정 절차도 함께 확인합니다.", "소집통지서 또는 훈련필증 등 증빙서류를 준비합니다."])
    elif issue_type == "graduation":
        tasks.extend(["요람/규정집에서 소속 학과 졸업요건을 확인합니다.", "총 이수학점, 전공 이수학점, 필수과목, 교양영역을 나누어 점검합니다.", "최종 졸업 판정은 소속 학과사무실 또는 교무팀에 확인합니다."])
    elif issue_type == "contact":
        tasks.extend(["문의 주제에 맞는 담당 부서를 고릅니다.", "개인정보를 제외한 질문 요약을 준비합니다.", "공식 포털 또는 담당 부서 안내에 따라 후속 확인을 진행합니다."])
    else:
        tasks.append("공식 근거와 담당 부서를 확인합니다.")

    return {
        "tasks": tasks,
        "required_documents": documents,
        "application_paths": paths,
        "submit_to": submit_to,
    }
