"""Kookmin student-support guide crawler."""

from crawler.base import BaseCrawler, SourcePage


class KMUStudentSupportCrawler(BaseCrawler):
    """Crawler adapter for student-support guide pages."""

    source_type = "student_support"
    source_tier = 3
    max_pages_per_run = 10
    pages = [
        SourcePage(
            doc_id="student_support_certificate",
            title="국민대학교 증명서 발급",
            url="https://www.kookmin.ac.kr/comm/menu/user/00078abe6af76fde00965b928c8c9067/content/index.do",
            department="종합서비스센터",
            fallback_text=(
                "인터넷 증명 발급 신청을 통해 제 증명서를 출력할 수 있으며, 성적, 재학, 휴학, 수료, 제적, "
                "졸업예정, 졸업 등 증명서가 안내되어 있다. 졸업예정증명서는 학사과정 수료생 또는 일정 차수 "
                "등록을 필하고 총취득학점과 최종학기 수강신청학점의 합이 졸업에 필요한 최저이수학점수 이상인 "
                "자에게 발급되는 것으로 안내되어 있다."
            ),
            keywords=["증명서", "인터넷신청", "졸업예정증명서", "성적증명서", "재학증명서"],
            search_hints=["졸업예정증명서 어디서 뽑아", "성적증명서 발급", "증명서 인터넷 발급"],
            issue_types=["certificate", "graduation"],
            application_path="국민대학교 인터넷 증명 발급신청 페이지",
            contacts=[
                {"label": "학적 관련 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4050"},
                {"label": "증명발급 시스템/수수료 결제 문의", "name": "한국정보인증(주)", "phone": "1644-2378"},
            ],
            actions=["certificate_issue_guide"],
        ),
        SourcePage(
            doc_id="student_support_student_id",
            title="국민대학교 학생증 안내",
            url="https://www.kookmin.ac.kr/comm/menu/user/94b1d470ab2b5edab2c55aa201d2ba28/content/index.do",
            department="종합서비스센터",
            fallback_text=(
                "국민대학교 학생증은 도서관, 전산실 등 교내시설 이용에 필요하며 우리은행 현금카드 및 "
                "전자화폐 기능을 포함할 수 있다. 신입생 등 신규 발급은 우리WON뱅킹 앱에서 대학 학생증 "
                "카드 신청을 진행하고, 기존 재학생과 휴학생은 종합서비스센터에서 당일 개별발급 절차를 "
                "확인한다. 모바일학생증은 국민대학교 모바일학생증 앱과 ON국민 포털 사용자등록, 휴대폰 번호 "
                "일치 여부 확인이 필요하다."
            ),
            keywords=["학생증", "모바일학생증", "우리WON뱅킹", "재발급", "국제학생증", "K-CARD"],
            search_hints=["학생증 재발급 어디서 해", "모바일학생증 발급", "학생증 신규 발급"],
            issue_types=["student_id", "student_support", "portal_access"],
            application_path="ON국민 포털 > KCARD > ID카드 > MY ID카드 또는 우리WON뱅킹 대학 학생증 카드 신청",
            required_documents=["신분증", "학생증 발급 신청서", "사진 변경 필요 시 학과 또는 대학원 교학팀 확인"],
            contacts=[{"label": "학생증 발급 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4060"}],
            actions=["student_id_issue_guide"],
        ),
        SourcePage(
            doc_id="portal_ecampus_login_boundary",
            title="국민대학교 ON국민 포털/eCampus 로그인 경계",
            url="https://portal.kookmin.ac.kr/",
            department="정보서비스/포털 안내",
            fallback_text=(
                "ON국민 포털은 국민인을 위한 Online Platform으로 아이디와 비밀번호로 로그인하며, "
                "사용자 등록, 아이디 찾기, 비밀번호 찾기 메뉴가 제공된다. eCampus 가상대학은 포털 통합ID와 "
                "비밀번호로 로그인하는 서비스이며 포털 계정 찾기 링크가 제공된다. 에이전트는 로그인 이후 "
                "개인 화면에 접근하지 않고, 포털 ID/PW 등 로그인 정보 입력을 요청하지 않는다."
            ),
            keywords=["ON국민", "포털", "eCampus", "가상대학", "로그인", "아이디 찾기", "비밀번호 찾기"],
            search_hints=["포털 비밀번호 찾기", "eCampus 로그인", "가상대학 어디로 들어가"],
            issue_types=["portal_access"],
            application_path="ON국민 포털 로그인 또는 eCampus 로그인 페이지에서 사용자 등록/아이디 찾기/비밀번호 찾기 직접 진행",
            actions=["portal_access_checklist"],
        ),
        SourcePage(
            doc_id="student_support_academic_record",
            title="국민대학교 학적부 정정",
            url="https://www.kookmin.ac.kr/comm/menu/user/b239facb8677a3aa5cf3253fa0a5156e/content/index.do",
            department="종합서비스센터",
            fallback_text=(
                "학적부 정정은 학생의 학적 정보가 변경되었거나 정정이 필요한 경우 공식 안내에 따라 "
                "신청한다. 이름, 영문명, 주소 등 정정 항목별로 필요한 증빙서류와 신청 경로가 다를 수 "
                "있으므로 개인정보가 포함된 자료는 에이전트에 입력하지 말고 공식 포털 또는 담당 부서로 "
                "직접 제출해야 한다."
            ),
            keywords=["학적부 정정", "학적부", "개명", "영문명", "주소 변경", "종합서비스센터"],
            search_hints=["학적부 정정", "이름 변경", "영문명 바꾸기"],
            issue_types=["academic_record", "student_support"],
            application_path="국민대학교 학적부 정정 공식 안내 또는 ON국민 포털 관련 메뉴",
            required_documents=["정정 항목별 증빙서류"],
            contacts=[{"label": "학적부 정정 문의", "name": "종합서비스센터", "phone": "02-910-4046, 4050"}],
            actions=["academic_record_correction_checklist"],
        ),
        SourcePage(
            doc_id="student_support_insurance",
            title="국민대학교 학생보험",
            url="https://www.kookmin.ac.kr/comm/menu/user/9a6d6454c077867eed861502a796c24c/content/index.do",
            department="학생지원 담당 부서",
            fallback_text=(
                "학생보험은 재학생의 사고나 상해 발생 시 공식 안내에 따라 적용 대상, 청구 가능 항목, "
                "제출서류를 확인해야 한다. 진단서, 진료비 영수증, 통장사본 등 민감 자료는 에이전트에 "
                "입력하지 말고 담당 부서 안내에 따라 직접 제출해야 한다."
            ),
            keywords=["학생보험", "보험", "상해", "사고", "진단서", "진료비"],
            search_hints=["학생보험 청구", "교내에서 다쳤어", "상해 보험"],
            issue_types=["student_insurance", "student_support"],
            required_documents=["진단서 또는 진료확인서", "진료비 영수증", "담당 부서가 요구하는 추가 서류"],
            actions=["student_insurance_checklist"],
        ),
        SourcePage(
            doc_id="student_support_military",
            title="국민대학교 병무/예비군",
            url="https://www.kookmin.ac.kr/comm/menu/user/0f4599e39a8b492a409322ac8e60f140/content/index.do",
            department="병무/예비군 담당 부서",
            fallback_text=(
                "병무/예비군 안내는 예비군 훈련, 병무 관련 확인, 준비서류 등 병역 관련 학교생활 절차를 "
                "확인하는 공식 안내다. 예비군 훈련으로 수업에 출석하지 못하는 경우 병무 절차와 함께 "
                "출석인정 신청 가능 여부, 제출기한, 소집통지서 또는 훈련필증 등 증빙서류를 확인해야 한다."
            ),
            keywords=["병무", "예비군", "군", "훈련", "소집통지서", "훈련필증"],
            search_hints=["예비군 어디에 문의", "병무 안내", "예비군 훈련 출석"],
            issue_types=["military", "attendance", "student_support"],
            required_documents=["소집통지서 또는 훈련필증"],
            contacts=[{"label": "병무/예비군 문의", "name": "병무/예비군 담당 부서"}],
            actions=["military_service_checklist", "draft_attendance_recognition_form"],
        ),
        SourcePage(
            doc_id="campus_life_transport_parking",
            title="국민대학교 통학버스/주차 안내",
            url="https://www.kookmin.ac.kr/comm/menu/user/640df1d2662a8972d4b32237c68f9e42/content/index.do",
            department="생활지원/시설 담당 부서",
            fallback_text=(
                "통학버스와 주차 안내는 학생 생활지원 영역의 공식 정보로 노선, 운행시간, 이용대상, "
                "주차 절차처럼 시점에 따라 달라질 수 있는 항목을 확인해야 한다. 최신 운행 변경이나 "
                "신청/등록이 필요한 항목은 공식 안내와 관련 공지를 함께 확인한다."
            ),
            keywords=["통학버스", "셔틀버스", "셔틀", "주차", "주차안내", "노선", "운행시간"],
            search_hints=["통학버스 시간", "셔틀버스 노선", "주차 안내"],
            issue_types=["campus_facility"],
            application_path="국민대학교 대학생활 > 생활지원 > 통학버스/주차 안내",
            actions=["campus_facility_guide"],
        ),
        SourcePage(
            doc_id="campus_life_dorm_library_food",
            title="국민대학교 생활관/도서관/오늘의 메뉴",
            url="https://www.kookmin.ac.kr/user/unLvlh/lvlhSpor/todayMenu/index.do",
            department="생활지원/생활관/성곡도서관",
            fallback_text=(
                "대학생활 생활지원 메뉴에서는 오늘의 메뉴, 교내복지시설, 공동전산실, 웰니스센터, "
                "생활관, 도서관 열람석 등 학생 생활에 필요한 정보를 확인할 수 있다. 생활관과 도서관처럼 "
                "별도 사이트 또는 예약/조회 화면이 있는 항목은 사용자가 공식 사이트에서 최신 공지와 개인 "
                "상태를 직접 확인해야 한다."
            ),
            keywords=["오늘의 메뉴", "식단", "생활관", "기숙사", "도서관", "열람석", "성곡도서관", "웰니스센터"],
            search_hints=["오늘의 메뉴", "기숙사 공지", "도서관 열람석"],
            issue_types=["campus_facility"],
            application_path="국민대학교 대학생활 > 생활지원 메뉴와 생활관/성곡도서관 공식 사이트",
            contacts=[
                {"label": "생활관 문의", "name": "생활관"},
                {"label": "도서관 문의", "name": "성곡도서관"},
            ],
            actions=["campus_facility_guide"],
        )
    ]
