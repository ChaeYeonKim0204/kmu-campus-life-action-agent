"""Tests for the deterministic 학식 menu parser and its answer-builder integration."""

from agent.answer_builder import build_final_answer
from tools.menu_parser import is_menu_chunk, is_menu_query, parse_menu


def _menu_chunk(text: str, **extra) -> dict:
    base = {
        "chunk_id": "menu_1",
        "doc_id": "campus_life_dorm_library_food",
        "title": "국민대학교 생활관/도서관/오늘의 메뉴",
        "url": "https://www.kookmin.ac.kr/menu",
        "text": text,
        "issue_types": ["campus_facility"],
    }
    base.update(extra)
    return base


SAMPLE = (
    "1코너 SNACK2\n"
    "김말이떡볶이\n￦3300\n"
    "왕만두￦1600\n"
    "[중식] 쫄면&갈비만두 ￦4300\n"
    "[석식] 얼큰국밥\n￦6500\n"
    "[중석식] 뚝배기삼겹구이\n￦5900\n"
)


def test_is_menu_query_matches_cafeteria_terms():
    assert is_menu_query("오늘 학식 메뉴 뭐야")
    assert is_menu_query("학식 식단 알려줘")
    assert not is_menu_query("도서관 열람실 운영시간")


def test_parse_menu_handles_inline_and_newline_prices():
    result = parse_menu([_menu_chunk(SAMPLE)])
    assert result["found"]
    names = {item["name"]: item for item in result["items"]}
    # newline-separated price (이름\n￦가격) must be captured, not just inline
    assert names["김말이떡볶이"]["price"] == "3300"
    assert names["왕만두"]["price"] == "1600"
    assert names["얼큰국밥"]["price"] == "6500"


def test_parse_menu_captures_meal_tags_including_jungseoksik():
    result = parse_menu([_menu_chunk(SAMPLE)])
    meals = {item["name"]: item["meal"] for item in result["items"]}
    assert meals["쫄면&갈비만두"] == "중식"
    assert meals["얼큰국밥"] == "석식"
    assert meals["뚝배기삼겹구이"] == "중석식"


def test_parse_menu_empty_when_no_menu_text():
    assert not parse_menu([_menu_chunk("도서관 열람실 운영시간 안내")])["found"]
    assert not parse_menu([])["found"]


def test_is_menu_chunk_detection():
    assert is_menu_chunk(_menu_chunk(SAMPLE))
    assert not is_menu_chunk(_menu_chunk("주차 안내와 통학버스 노선"))


def _section_lines(answer: str, header: str) -> list[str]:
    """Return the '- ' bullet lines under a section header, up to the next blank line."""
    lines = answer.splitlines()
    start = lines.index(header)
    out = []
    for line in lines[start + 1 :]:
        if line == "":
            break
        if line.startswith("- "):
            out.append(line)
    return out


def test_answer_builder_renders_menu_section_with_citations():
    built = build_final_answer("오늘 학식 메뉴 알려줘", "campus_facility", [_menu_chunk(SAMPLE)], [])
    answer = built["answer"]
    assert "[오늘의 학식]" in answer
    # every rendered menu line inside the section must carry a resolving citation marker
    menu_lines = _section_lines(answer, "[오늘의 학식]")
    assert menu_lines, "menu lines should be rendered"
    assert all(line.rstrip().endswith("]") and "[S" in line for line in menu_lines)


def test_answer_builder_skips_menu_section_for_non_menu_query():
    built = build_final_answer("도서관 열람실 운영시간", "campus_facility", [_menu_chunk(SAMPLE)], [])
    assert "[오늘의 학식]" not in built["answer"]
