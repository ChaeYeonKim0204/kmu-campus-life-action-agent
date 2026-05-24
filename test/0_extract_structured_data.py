"""
0_extract_structured_data.py
요람에서 핵심 구조화 데이터를 추출하여 JSON으로 저장합니다.

추출 대상:
  1. 별표5 (p.195~197): 학과별 졸업 최저이수 학점표  → graduation_requirements.json
  2. 별표6 (p.198):     공학인증 심화프로그램 학점표  → engineering_cert_requirements.json
  3. 이수구분 코드표   (p.210 성적증명서 양식 기반)  → grade_category_codes.json

실행: python3 0_extract_structured_data.py
"""

import re
import json
import pdfplumber

PDF_PATH = "2025국민대학교요람_20250910.pdf"


# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────

def clean(s: str) -> str:
    """공백·개행 정리."""
    return re.sub(r"\s+", " ", s).strip()


def to_int(s: str, default: int = 0) -> int:
    try:
        return int(re.sub(r"[^\d]", "", s))
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────
# 1. 별표5 파싱: 학과별 졸업이수학점표
#    PDF 페이지 195 (index 194), 196 (index 195)
# ─────────────────────────────────────────────────────────────

def parse_byeoltable5() -> dict:
    """
    별표5 텍스트를 파싱하여 학과별 졸업이수학점을 구조화.

    PDF 텍스트 구조:
      - 숫자 7개로 끝나는 줄 = 데이터 행 (전공명 + 7개 학점)
      - 숫자 없는 줄 = 대학/학부 맥락 행
    """
    requirements = {}
    notes = []

    # 대학명 목록 (순서 중요: 길이 긴 것 먼저)
    UNIVERSITIES = [
        "글로벌·인문지역대학", "사회과학대학", "법과대학", "경상대학",
        "창의공과대학", "조형대학", "과학기술대학", "예술대학",
        "체육대학", "경영대학", "소프트웨어융합대학", "건축대학",
        "자동차융합대학", "독립학부",
    ]
    # 스페이스-사이 한글 → 연속 한글 정규화 패턴
    # 예: "한 국 어 문 학 부" → "한국어문학부"
    def normalize_spaced_korean(text: str) -> str:
        # 한글 한글자 사이에 공백만 있는 구간을 붙임
        return re.sub(r"(?<=[가-힣])\s+(?=[가-힣])", "", text)

    with pdfplumber.open(PDF_PATH) as pdf:
        current_university = "미분류"
        pending_label = ""  # 줄이 잘린 경우 다음 줄과 합치기 위한 버퍼

        for page_idx in [194, 195, 196]:  # 페이지 195~197
            text = pdf.pages[page_idx].extract_text() or ""

            for raw_line in text.split("\n"):
                line = normalize_spaced_korean(raw_line).strip()
                if not line:
                    continue

                # 대학명 감지
                for univ in UNIVERSITIES:
                    if univ in line:
                        current_university = univ
                        # 대학명을 제거한 나머지를 전공 라벨 후보로
                        line = line.replace(univ, "").strip()
                        break

                # 줄 끝의 숫자 7개 추출 시도
                nums_match = re.search(
                    r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*$",
                    line,
                )
                if nums_match:
                    # 숫자 앞 텍스트가 전공명
                    label_part = line[: nums_match.start()].strip()

                    # 이전 줄에서 이어진 라벨이 있으면 합침
                    if pending_label:
                        label_part = pending_label + " " + label_part
                        pending_label = ""

                    label = normalize_spaced_korean(label_part).strip()

                    # 헤더·주석 행 제외
                    if not label or any(
                        x in label for x in ["구분", "대학", "학부및학과", "기초교양", "핵심교양"]
                    ):
                        continue

                    nums = [int(nums_match.group(i)) for i in range(1, 8)]
                    기초교양, 핵심교양, 자유교양, 교양소계, 전공, 일반선택, 합계 = nums

                    # 합계 유효성 검증
                    if abs((교양소계 + 전공 + 일반선택) - 합계) > 3:
                        continue
                    if 합계 not in (120, 130, 136, 160):
                        continue

                    key = re.sub(r"\s+", "", f"{current_university}_{label}")
                    requirements[key] = _build_entry(
                        current_university, label,
                        기초교양, 핵심교양, 자유교양, 교양소계, 전공, 일반선택, 합계,
                    )
                else:
                    # 숫자가 없는 줄 - 다음 줄과 합쳐질 라벨 후보
                    text_only = re.sub(r"\d+", "", line).strip()
                    if (
                        text_only
                        and len(text_only) >= 2
                        and not any(x in text_only for x in ["❙", "요람", "학사", "별표", "비고", "※", "1.", "2.", "3.", "4."])
                    ):
                        pending_label = text_only
                    else:
                        pending_label = ""

    return {"departments": requirements, "notes": notes, "source_pages": [195, 196, 197]}


def _parse_table_rows(table: list, requirements: dict, notes: list):
    """pdfplumber 테이블 행 파싱."""
    current_university = ""
    current_dept = ""

    for row in table:
        if not row:
            continue
        row = [clean(str(c or "")) for c in row]

        # 대학명 행 감지 (숫자가 없는 행)
        if row and not any(c.isdigit() for c in " ".join(row)):
            text = " ".join(r for r in row if r)
            if "대학" in text or "학부" in text:
                if "대학" in text and not any(x in text for x in ["교양", "전공", "선택", "합계"]):
                    current_university = text
            continue

        # 숫자 6개 이상 포함된 행 = 데이터 행
        nums = [to_int(c) for c in row if re.search(r"^\d+$", c)]
        if len(nums) >= 4:
            label_parts = [c for c in row if c and not re.search(r"^\d+$", c)]
            label = " ".join(label_parts)

            if len(nums) >= 7:
                key = _make_key(current_university, label)
                requirements[key] = _build_entry(
                    current_university, label, nums[0], nums[1], nums[2],
                    nums[3], nums[4], nums[5], nums[6]
                )
            elif len(nums) >= 6:
                key = _make_key(current_university, label)
                requirements[key] = _build_entry(
                    current_university, label, nums[0], nums[1], nums[2],
                    nums[3], nums[4], 0, nums[5]
                )


def _parse_text_rows(text: str, requirements: dict):
    """텍스트에서 정규식으로 학과별 데이터 파싱."""
    current_university = ""

    # 대학명 패턴
    univ_pattern = re.compile(
        r"(글로벌·인문지역대학|사회과학대학|법과대학|경상대학|창의공과대학|조형대학|"
        r"과학기술대학|예술대학|체육대학|경영대학|소프트웨어융합대학|건축대학|"
        r"자동차융합대학|독립학부)"
    )

    # 숫자 패턴: 전공명 + 7개 숫자
    # 예: "소프트웨어전공 7 15 2 24 66 46 136"
    row_pattern = re.compile(
        r"([가-힣A-Za-z\s·‧·\-\.\/\(\)]+?)\s+"
        r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})"
    )

    lines = text.split("\n")
    for line in lines:
        univ_match = univ_pattern.search(line)
        if univ_match:
            current_university = univ_match.group(1)

        match = row_pattern.search(line)
        if match:
            label = clean(match.group(1))
            # 헤더 행 제외
            if any(x in label for x in ["대학", "구분", "교양", "전공", "선택", "합계", "소계"]):
                continue
            if len(label) < 2:
                continue

            기초교양 = to_int(match.group(2))
            핵심교양 = to_int(match.group(3))
            자유교양 = to_int(match.group(4))
            교양소계 = to_int(match.group(5))
            전공     = to_int(match.group(6))
            일반선택 = to_int(match.group(7))
            합계     = to_int(match.group(8))

            # 합계 검증 (교양소계 + 전공 + 일반선택 ≈ 합계)
            if abs((교양소계 + 전공 + 일반선택) - 합계) > 5:
                continue

            key = _make_key(current_university, label)
            if key not in requirements or requirements[key].get("합계", 0) == 0:
                requirements[key] = _build_entry(
                    current_university, label,
                    기초교양, 핵심교양, 자유교양, 교양소계, 전공, 일반선택, 합계
                )


def _make_key(university: str, label: str) -> str:
    """학과 고유 키 생성 (공백 제거)."""
    dept = re.sub(r"\s+", "", label)
    univ = re.sub(r"\s+", "", university) if university else "미분류"
    return f"{univ}_{dept}"


def _build_entry(univ, label, 기초교양, 핵심교양, 자유교양, 교양소계, 전공, 일반선택, 합계):
    return {
        "대학": univ,
        "학과_전공명": label,
        "교양": {
            "기초교양": 기초교양,
            "핵심교양": 핵심교양,
            "자유교양": 자유교양,
            "소계": 교양소계,
        },
        "전공_최저": 전공,
        "일반선택": 일반선택,
        "졸업_최저합계": 합계,
        "비고": _get_graduation_notes(합계),
    }


def _get_graduation_notes(total: int) -> str:
    notes = {
        120: "총 120학점 이상 (KMU International Business School, 기업경영전공 등)",
        130: "총 130학점 이상 (인문·사회·예술 계열 일반)",
        136: "총 136학점 이상 (공학·과학기술·체육·소프트웨어 계열)",
        160: "총 160학점 이상 (건축학부 건축설계전공, 5년제)",
    }
    return notes.get(total, f"총 {total}학점 이상")


# ─────────────────────────────────────────────────────────────
# 2. 별표6 파싱: 공학인증 심화프로그램
#    PDF 페이지 198 (index 197)
# ─────────────────────────────────────────────────────────────

def parse_byeoltable6() -> dict:
    """공학교육인증 심화프로그램 졸업 최저이수 학점표 파싱."""
    engineering_cert = {}

    with pdfplumber.open(PDF_PATH) as pdf:
        text = pdf.pages[197].extract_text() or ""

    # 공학인증 대상 전공 파싱
    row_pattern = re.compile(
        r"([가-힣\s]+전\s*공)\s+"  # 전공명
        r"(\d+)\s+"               # 필수(기초교양)
        r"(\d+)\s+"               # 수학기초과학 필수
        r"(\d+)\s+"               # 심화필수
        r"(\d+)\s+"               # 심화선택
        r"(\d+)\s+"               # 소계
        r"[-\d]+\s+"              # 기초교양 핵심교양
        r"(\d+)\s+"               # 자유교양
        r"[-\d]+\s+"              # 전공
        r"(\d+)\s+"               # 일반선택
        r"(\d+)"                  # 합계
    )

    for match in row_pattern.finditer(text):
        name = clean(match.group(1))
        engineering_cert[name] = {
            "전공명": name,
            "기초교양_필수": to_int(match.group(2)),
            "MSC_필수": to_int(match.group(3)),
            "공학주제_심화필수": to_int(match.group(4)),
            "공학주제_심화선택": to_int(match.group(5)),
            "공학주제_소계": to_int(match.group(6)),
            "자유교양": to_int(match.group(7)),
            "일반선택": to_int(match.group(8)),
            "합계": to_int(match.group(9)),
        }

    return {"programs": engineering_cert, "source_page": 198}


# ─────────────────────────────────────────────────────────────
# 3. 성적증명서 이수구분 코드표 (고정 데이터)
# ─────────────────────────────────────────────────────────────

def build_grade_category_codes() -> dict:
    """성적증명서의 이수구분 코드 → 의미 매핑 (p.210 양식 기반)."""
    return {
        "codes": {
            "A": "교양필수",
            "B": "기초공통",
            "C": "전공필수",
            "D": "전공선택",
            "E": "교양선택",
            "F": "일반선택",
            "G": "부전공",
            "H": "교직",
            "J": "복수전공",
            "K": "교양기초",
            "L": "계열교양",
            "M": "학부기초",
            "V": "기초교양",
            "X": "전공기초교양",
            "Y": "핵심교양",
            "Z": "자유교양",
            "PL": "제2전공_계열교양",
            "PX": "제2전공_전공기초교양",
            "PM": "제2전공_학부기초",
            "PN": "제2전공_전공",
            "QL": "제3전공_계열교양",
            "QX": "제3전공_전공기초교양",
            "QM": "제3전공_학부기초",
            "QN": "제3전공_전공",
            "RM": "연계융합전공_기초",
            "RN": "연계융합전공_전공",
        },
        "graduation_relevant_map": {
            "기초교양": ["A", "B", "K", "V"],
            "핵심교양": ["Y"],
            "자유교양": ["E", "L", "Z"],
            "전공": ["C", "D", "M", "X"],
            "일반선택": ["F"],
            "부전공": ["G"],
            "다전공": ["PL", "PX", "PM", "PN", "QL", "QX", "QM", "QN"],
            "교직": ["H"],
        },
        "grade_points": {
            "A+": 4.5, "A": 4.0, "A0": 4.0,
            "B+": 3.5, "B": 3.0, "B0": 3.0,
            "C+": 2.5, "C": 2.0, "C0": 2.0,
            "D+": 1.5, "D": 1.0, "D0": 1.0,
            "F":  0.0,
            "P": None, "N": None, "R": None, "W": None,
        },
        "passing_grades": ["A+", "A", "A0", "B+", "B", "B0", "C+", "C", "C0", "D+", "D", "D0", "P"],
    }


# ─────────────────────────────────────────────────────────────
# 4. 핵심교양 영역 구성 (학사규정 제7조 기반 고정 데이터)
# ─────────────────────────────────────────────────────────────

def build_core_liberal_arts() -> dict:
    """핵심교양 5개 영역 - 각 영역별 3학점 이상 필수."""
    return {
        "총_최저이수학점": 15,
        "영역별_최저학점": 3,
        "영역": {
            "인문Ⅰ": "인문학적 사고와 가치 탐구",
            "인문Ⅱ": "역사·철학·윤리적 사고",
            "소통": "의사소통과 표현 능력",
            "글로벌": "외국어 및 글로벌 이해",
            "창의": "창의적 문제해결과 융합",
        },
        "비고": "핵심교양 15학점은 5개 영역에서 각 3학점 이상 이수해야 함",
    }


# ─────────────────────────────────────────────────────────────
# 5. 검색용 정규화 인덱스 생성
# ─────────────────────────────────────────────────────────────

def _tokenize_dept_name(name: str) -> list[str]:
    """
    학과명을 의미 단위 토큰으로 분리.
    "소프트웨어학부소프트웨어전공" → ["소프트웨어학부", "소프트웨어전공", "소프트웨어"]
    """
    tokens = set()
    # 전체 이름 추가
    tokens.add(name)

    # 학문 단위 접미사로 분리
    suffixes = ["학부", "전공", "학과", "학원", "대학", "학교"]
    # 접미사 기준으로 분할
    parts = re.split(r"(?<=[가-힣])(?=학부|전공|학과|대학원|대학|학원)", name)
    for part in parts:
        p = part.strip()
        if len(p) >= 2:
            tokens.add(p)
            # 접미사 제거한 핵심어도 추가
            for sfx in suffixes:
                if p.endswith(sfx):
                    core = p[: -len(sfx)]
                    if len(core) >= 2:
                        tokens.add(core)

    # 영문 토큰 (KMU, International 등)
    eng_tokens = re.findall(r"[A-Za-z]{2,}", name)
    tokens.update(eng_tokens)

    return [t for t in tokens if len(t) >= 2]


def build_search_index(requirements: dict) -> dict:
    """학과명 키워드로 빠르게 검색하기 위한 역색인."""
    index = {}
    for key, entry in requirements["departments"].items():
        name = entry["학과_전공명"]
        tokens = _tokenize_dept_name(name)
        for token in tokens:
            if token not in index:
                index[token] = []
            if key not in index[token]:
                index[token].append(key)

    return index


def find_department(query: str, requirements: dict, search_index: dict) -> list[dict]:
    """
    학과명 쿼리로 졸업요건 검색. 유사도 기반 상위 5개 반환.
    1차: 토큰 정확 매칭
    2차: 학과명 문자열에 쿼리 포함 여부 (부분 매칭 폴백)
    """
    query_clean = re.sub(r"\s+", "", query)  # 공백 제거한 쿼리
    query_tokens = re.findall(r"[가-힣A-Za-z0-9]+", query)
    candidates: dict[str, int] = {}

    # 1차: 인덱스 토큰 매칭
    for token in query_tokens:
        if token in search_index:
            for key in search_index[token]:
                candidates[key] = candidates.get(key, 0) + 2

    # 2차: 학과명 문자열에 쿼리 포함 여부 (공백 제거 후 비교)
    if not candidates or len(candidates) < 3:
        for key, entry in requirements["departments"].items():
            name_clean = re.sub(r"\s+", "", entry["학과_전공명"])
            if query_clean in name_clean or name_clean in query_clean:
                candidates[key] = candidates.get(key, 0) + 1
            # 개별 토큰이 학과명에 포함되는지
            for token in query_tokens:
                if len(token) >= 2 and token in name_clean:
                    candidates[key] = candidates.get(key, 0) + 1

    sorted_keys = sorted(candidates.items(), key=lambda x: -x[1])
    results = []
    for key, score in sorted_keys[:5]:
        entry = requirements["departments"][key].copy()
        entry["_match_score"] = score
        entry["_key"] = key
        results.append(entry)

    return results


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("국민대학교 요람 구조화 데이터 추출")
    print("=" * 60)

    # 1. 별표5 추출
    print("\n[1/4] 별표5: 학과별 졸업이수학점 추출 중...")
    requirements = parse_byeoltable5()
    dept_count = len(requirements["departments"])
    print(f"      → {dept_count}개 학과/전공 파싱 완료")

    with open("graduation_requirements.json", "w", encoding="utf-8") as f:
        json.dump(requirements, f, ensure_ascii=False, indent=2)
    print("      → graduation_requirements.json 저장 완료")

    # 2. 별표6 추출
    print("\n[2/4] 별표6: 공학인증 심화프로그램 추출 중...")
    eng_cert = parse_byeoltable6()
    print(f"      → {len(eng_cert['programs'])}개 프로그램 파싱 완료")

    with open("engineering_cert_requirements.json", "w", encoding="utf-8") as f:
        json.dump(eng_cert, f, ensure_ascii=False, indent=2)
    print("      → engineering_cert_requirements.json 저장 완료")

    # 3. 이수구분 코드
    print("\n[3/4] 이수구분 코드표 생성 중...")
    codes = build_grade_category_codes()
    codes["core_liberal_arts"] = build_core_liberal_arts()

    with open("grade_category_codes.json", "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)
    print("      → grade_category_codes.json 저장 완료")

    # 4. 검색 인덱스
    print("\n[4/4] 검색 인덱스 생성 중...")
    search_index = build_search_index(requirements)

    with open("department_search_index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print("      → department_search_index.json 저장 완료")

    # 샘플 검색 테스트
    print("\n" + "=" * 60)
    print("검색 테스트")
    print("=" * 60)
    test_queries = ["소프트웨어", "경영학", "법학부", "건축설계", "AI디자인"]
    for q in test_queries:
        results = find_department(q, requirements, search_index)
        if results:
            r = results[0]
            print(f"\n'{q}' 검색 결과:")
            print(f"  학과: {r['학과_전공명']}")
            print(f"  대학: {r['대학']}")
            print(f"  교양: 기초{r['교양']['기초교양']} + 핵심{r['교양']['핵심교양']} + 자유{r['교양']['자유교양']} = {r['교양']['소계']}학점")
            print(f"  전공: {r['전공_최저']}학점, 일반선택: {r['일반선택']}학점")
            print(f"  졸업 최저: {r['졸업_최저합계']}학점")
        else:
            print(f"'{q}': 검색 결과 없음")

    print("\n완료!")


if __name__ == "__main__":
    main()
