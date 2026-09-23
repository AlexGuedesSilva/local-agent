from datetime import datetime

from agent.tools.base import calculator, get_current_time


def test_calculator_returns_result_for_arithmetic_expression() -> None:
    assert calculator("1547 * 37") == "57239"


def test_calculator_reports_invalid_expression() -> None:
    assert calculator("not a valid expression").startswith("Erro ao calcular:")


def test_get_current_time_matches_expected_format() -> None:
    value = get_current_time()
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    assert parsed.strftime("%Y-%m-%d %H:%M:%S") == value
