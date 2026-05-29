"""Student-facing playbooks for KMU-specific practical guidance.

These hints are intentionally separated from official-source retrieval. They
capture student workflow patterns and wording, while final decisions still
belong to official KMU pages, ON국민, departments, or course instructors.
"""

from __future__ import annotations


STUDENT_TERM_ALIASES: dict[str, list[str]] = {
    "ON국민 포털": ["온국민", "on국민", "포털", "종정시", "종합정보", "종합정보시스템"],
    "eCampus": ["이캠", "이캠퍼스", "ecampus", "e-campus", "가상대학", "가대"],
    "학과사무실": ["과사", "학과 사무실", "학과사무실"],
    "모바일학생증": ["모바일 학생증", "모바일학생증", "k-card", "kcard", "케이카드"],
    "수강신청 장바구니": ["장바구니", "수강 바구니", "담아두기"],
    "등록금 납부 확인": ["납부확인", "납부 확인", "등록 확인", "납입 확인"],
    "예비군 출석인정": ["예비군 출석", "훈련필증", "소집통지서", "공결"],
}


ISSUE_PLAYBOOKS: dict[str, dict] = {
    "attendance": {
        "scenario": "수업 결석 사유를 출석인정으로 연결해야 하는 상황",
        "prechecks": [
            "결석일, 수업명, 담당 교강사, 사유 발생일을 먼저 정리합니다.",
            "예비군이면 소집통지서와 훈련필증 중 어떤 증빙을 제출할지 확인합니다.",
            "수업별 LMS 공지나 교수님 안내가 학교 공통 절차보다 더 구체적인지 확인합니다.",
        ],
        "evidence": ["결석일", "수업명", "담당 교강사", "증빙서류 종류", "제출 예정일"],
        "common_mistakes": [
            "예비군 담당 부서 문의와 출석인정 제출처를 같은 것으로 착각하기 쉽습니다.",
            "훈련 참석 사실만으로 자동 출석 처리된다고 가정하면 누락될 수 있습니다.",
        ],
    },
    "course_registration": {
        "scenario": "장바구니, 수강신청, 폐강, 시간표 반영 상태를 구분해야 하는 상황",
        "prechecks": [
            "장바구니 담기와 실제 수강신청 완료는 다른 단계인지 확인합니다.",
            "수강신청시스템의 나의 시간표와 ON국민 개인수업시간표가 같이 반영되는지 봅니다.",
            "폐강 공지가 있으면 본인 신청 내역과 대체 신청 가능 기간을 함께 확인합니다.",
        ],
        "evidence": ["대상 학기", "과목명", "분반", "신청 화면 캡처", "오류 발생 시간"],
        "common_mistakes": [
            "장바구니에 담긴 것을 수강신청 완료로 오해하기 쉽습니다.",
            "폐강 이후에는 시간표에서 사라진 이유를 시스템 오류로 착각할 수 있습니다.",
        ],
    },
    "registration_tuition": {
        "scenario": "고지서, 납부, 분납, 장학 반영 상태를 확인해야 하는 상황",
        "prechecks": [
            "ON국민에서 개인 고지서와 납부 상태를 사용자가 직접 확인합니다.",
            "은행 납부 직후라면 학교 시스템 반영 시간이 있을 수 있어 납부 시간과 영수증을 확인합니다.",
            "장학금, 휴학/복학, 학적 상태가 고지 금액에 영향을 주는지 확인합니다.",
        ],
        "evidence": ["대상 학기", "납부 방식", "납부 일시", "고지서 화면", "은행 영수증 보유 여부"],
        "common_mistakes": [
            "은행 이체 완료와 학교 포털 반영 완료를 같은 시점으로 생각하기 쉽습니다.",
            "장학금 선발 결과와 등록금 고지서 반영 시점이 다를 수 있습니다.",
        ],
    },
    "student_id": {
        "scenario": "학생증 발급, 재발급, 모바일학생증 인증/인식 문제를 처리해야 하는 상황",
        "prechecks": [
            "신규, 재발급, 모바일학생증, 국제학생증 중 어느 유형인지 먼저 구분합니다.",
            "모바일학생증은 포털 사용자등록, 휴대폰 번호, 앱 로그인 상태를 확인합니다.",
            "오프라인 방문이 필요하면 신분증과 신청서 출력 여부를 확인합니다.",
        ],
        "evidence": ["학생증 유형", "현재 학적 상태", "오류 화면", "방문 가능 시간"],
        "common_mistakes": [
            "모바일학생증 문제를 카드 재발급 문제로 잘못 문의하기 쉽습니다.",
            "휴대폰 번호가 포털 정보와 다르면 인증 단계에서 막힐 수 있습니다.",
        ],
    },
    "scholarship": {
        "scenario": "장학 공지, 선발, 지급, 등록금 반영 여부를 확인해야 하는 상황",
        "prechecks": [
            "장학공지에서 신청기간, 제출서류, 성적/소득/재학 요건을 먼저 확인합니다.",
            "국가장학금은 한국장학재단 신청 상태와 학교 반영 상태를 따로 확인합니다.",
            "등록금지원 장학인지 등록금외지원 장학인지 구분합니다.",
        ],
        "evidence": ["장학금명", "대상 학기", "신청 상태", "제출서류 목록", "공지 링크"],
        "common_mistakes": [
            "재단 신청 완료와 학교 최종 반영을 같은 단계로 생각하기 쉽습니다.",
            "등록금외지원 장학은 고지서 금액에 바로 보이지 않을 수 있습니다.",
        ],
    },
    "portal_access": {
        "scenario": "ON국민/eCampus 로그인, 메뉴 접근, 수업 표시 문제를 처리해야 하는 상황",
        "prechecks": [
            "ON국민 포털과 eCampus 중 어느 서비스 문제인지 분리합니다.",
            "비밀번호 찾기와 계정 복구는 공식 페이지에서 사용자가 직접 진행합니다.",
            "eCampus에 강의가 안 보이면 수강신청 완료 여부와 개강/강의 개설 시점을 같이 확인합니다.",
        ],
        "evidence": ["서비스명", "문제 화면", "발생 시간", "수강신청 완료 여부", "브라우저/앱 구분"],
        "common_mistakes": [
            "eCampus 강의 미표시를 무조건 로그인 오류로 보면 원인을 놓칠 수 있습니다.",
            "포털 비밀번호나 학번을 채팅창에 입력하면 안 됩니다.",
        ],
    },
    "campus_facility": {
        "scenario": "통학버스, 주차, 생활관, 도서관, 식단처럼 생활 동선을 확인해야 하는 상황",
        "prechecks": [
            "공식 안내 페이지와 해당 시설 별도 사이트 공지를 함께 확인합니다.",
            "운영시간, 노선, 좌석, 요금, 예약 가능 여부는 수시로 바뀔 수 있습니다.",
            "방문 전에는 오늘 운영 여부와 위치를 다시 확인합니다.",
        ],
        "evidence": ["시설명", "이용일", "출발/도착 위치", "예약 필요 여부", "문의하려는 내용"],
        "common_mistakes": [
            "학기 중 운영표와 방학 운영표를 섞어 보기 쉽습니다.",
            "생활관, 도서관, 식당은 학교 메인 페이지와 별도 공지가 있을 수 있습니다.",
        ],
    },
    "academic_record": {
        "scenario": "학적부 정보 정정이나 증명서 표기 문제를 처리해야 하는 상황",
        "prechecks": [
            "정정 항목이 이름, 영문명, 주소, 생년월일 등 무엇인지 구분합니다.",
            "증빙서류에 개인정보가 있으면 에이전트에 입력하지 말고 공식 경로로 제출합니다.",
            "정정 후 증명서와 포털 화면에 반영됐는지 다시 확인합니다.",
        ],
        "evidence": ["정정 항목", "정정 사유", "증빙서류 종류", "반영 확인이 필요한 증명서"],
        "common_mistakes": [
            "포털 프로필 수정과 학적부 공식 정정을 같은 것으로 착각하기 쉽습니다.",
            "영문명 표기는 증명서 발급 전에 미리 확인하는 편이 안전합니다.",
        ],
    },
    "student_insurance": {
        "scenario": "교내외 활동 중 사고/상해 이후 학생보험 적용 여부를 확인해야 하는 상황",
        "prechecks": [
            "사고 발생일, 장소, 활동 성격을 개인정보 없이 정리합니다.",
            "진단서, 진료비 영수증, 통장사본 등 민감 서류는 담당 부서 안내에 따라 제출합니다.",
            "청구 가능 기간과 보장 제외 항목을 공식 안내에서 확인합니다.",
        ],
        "evidence": ["발생일", "사고 유형", "진료 여부", "영수증 보유 여부", "문의 목적"],
        "common_mistakes": [
            "모든 치료비가 자동 보장된다고 가정하면 안 됩니다.",
            "민감 서류를 채팅창에 올리기보다 담당 부서 제출 경로를 확인해야 합니다.",
        ],
    },
    "military": {
        "scenario": "병무/예비군 절차와 수업 결석 처리를 분리해서 확인해야 하는 상황",
        "prechecks": [
            "예비군 대상 여부와 훈련 일정은 병무/예비군 안내에서 확인합니다.",
            "수업 결석이 생기면 출석인정 신청 절차를 별도로 확인합니다.",
            "소집통지서와 훈련필증을 언제 제출해야 하는지 확인합니다.",
        ],
        "evidence": ["훈련일", "수업 결석 여부", "증빙서류 종류", "문의 대상"],
        "common_mistakes": [
            "예비군 문의처가 출석인정 승인까지 처리한다고 생각하기 쉽습니다.",
            "훈련 전 증빙과 훈련 후 증빙이 다를 수 있습니다.",
        ],
    },
    "schedule": {
        "scenario": "이번 주/이번 달에 실제로 챙겨야 할 학사 일정을 선별해야 하는 상황",
        "prechecks": [
            "학사일정에서 전체 기간을 확인하고, 신청/납부/제출 일정만 따로 표시합니다.",
            "수강신청, 등록, 휴복학은 공지 본문과 ON국민 개인 상태를 함께 확인합니다.",
            "마감일 당일에는 시간 기준이 있는지 공지 본문을 확인합니다.",
        ],
        "evidence": ["확인 기간", "관심 항목", "개인 신청 필요 여부"],
        "common_mistakes": [
            "학사일정의 기간 표시만 보고 실제 신청 가능 시간까지 확인하지 않는 경우가 많습니다.",
            "공통 일정과 본인 학과/학년 대상 일정을 구분해야 합니다.",
        ],
    },
}


SCENARIO_OVERRIDES: list[dict] = [
    {
        "issue_type": "portal_access",
        "signals": ["강의 안", "강의가 안", "수업 안", "과목 안", "안 떠", "안보", "안 보", "이캠", "ecampus"],
        "scenario": "eCampus에 강의가 보이지 않는 상황",
        "prechecks": [
            "수강신청이 실제 완료됐는지 수강신청시스템 나의 시간표에서 먼저 확인합니다.",
            "개강 직후라면 담당 교강사가 eCampus 강의를 아직 공개하지 않았을 수 있습니다.",
            "같은 문제가 계속되면 과목명, 분반, 발생 시간, 화면 캡처를 준비해 문의합니다.",
        ],
        "common_mistakes": [
            "eCampus 미표시를 비밀번호 문제로만 보고 수강신청 완료 여부를 놓치기 쉽습니다.",
        ],
    },
    {
        "issue_type": "registration_tuition",
        "signals": ["납부확인", "납부 확인", "안 떠", "안떠", "반영", "입금했", "냈는데"],
        "scenario": "등록금을 냈는데 포털에 납부 확인이 바로 보이지 않는 상황",
        "prechecks": [
            "은행 영수증 또는 이체 완료 화면의 납부 일시를 확인합니다.",
            "ON국민 고지서/납부 상태 화면을 사용자가 직접 다시 확인합니다.",
            "반영 지연 가능성이 있으므로 납부 방식과 시간대를 적어두고 문의합니다.",
        ],
        "common_mistakes": [
            "은행 납부 완료와 학교 시스템 반영 완료를 같은 시점으로 오해하기 쉽습니다.",
        ],
    },
    {
        "issue_type": "student_id",
        "signals": ["안 찍", "안찍", "인식", "태그", "qr", "모바일"],
        "scenario": "모바일학생증 또는 K-CARD가 인식되지 않는 상황",
        "prechecks": [
            "모바일학생증 앱 로그인 상태와 포털 휴대폰 번호 일치 여부를 확인합니다.",
            "실물 카드 문제인지 모바일 인증 문제인지 구분합니다.",
            "오류 화면과 이용 장소를 기록해 종합서비스센터 문의 전에 정리합니다.",
        ],
        "common_mistakes": [
            "모바일 인증 문제를 실물 카드 재발급 문제로 문의하면 처리가 늦어질 수 있습니다.",
        ],
    },
]


def detect_student_terms(query: str) -> list[str]:
    """Return canonical KMU student terms mentioned in informal wording."""
    normalized = (query or "").lower()
    detected: list[str] = []
    for canonical, aliases in STUDENT_TERM_ALIASES.items():
        if any(alias.lower() in normalized for alias in aliases):
            detected.append(canonical)
    return detected


def get_student_playbook(query: str, issue_type: str) -> dict:
    """Return practical student-facing guidance for a classified issue."""
    normalized = (query or "").lower()
    base = dict(ISSUE_PLAYBOOKS.get(issue_type, {}))
    for override in SCENARIO_OVERRIDES:
        if issue_type != override["issue_type"]:
            continue
        if all(signal.lower() in normalized for signal in override["signals"][:1]) or any(
            signal.lower() in normalized for signal in override["signals"]
        ):
            merged = dict(base)
            merged.update({key: value for key, value in override.items() if key not in {"signals", "issue_type"}})
            base = merged
            break
    if not base:
        base = {
            "scenario": "공식 근거와 담당 부서를 확인해야 하는 상황",
            "prechecks": ["질문을 담당 부서가 확인할 수 있는 수준으로 개인정보 없이 정리합니다."],
            "evidence": ["문의 주제", "확인한 공식 페이지", "질문 요약"],
            "common_mistakes": ["개인정보나 로그인 정보를 채팅창에 입력하지 않습니다."],
        }
    base["student_terms"] = detect_student_terms(query)
    return base
