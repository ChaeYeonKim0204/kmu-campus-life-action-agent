from tools.deadline import calculate_deadline, extract_event_date


def test_calculate_deadline():
    result = calculate_deadline("2026-05-15", 7)
    assert result["deadline"] == "2026-05-22"


def test_extract_korean_date():
    assert extract_event_date("5월 15일에 예비군 때문에 결석") == "2026-05-15"

