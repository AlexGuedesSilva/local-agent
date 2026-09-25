from datetime import datetime
import pytest

from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import ToolResult


def test_calculator_returns_result_for_arithmetic_expression() -> None:
    result = calculator("1547 * 37")

    assert result == ToolResult.ok("57239")


def test_calculator_reports_invalid_expression() -> None:
    result = calculator("not a valid expression")

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Erro ao calcular:")


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').getcwd()", "2 ** 1000000", "2 +", ""],
)
def test_calculator_rejects_unsafe_or_unbounded_expressions(expression: str) -> None:
    result = calculator(expression)

    assert result.success is False
    assert result.error is not None


def test_calculator_supports_parentheses_and_unary_operators() -> None:
    assert calculator("-(2 + 3) * 4") == ToolResult.ok("-20")


def test_get_current_time_matches_expected_format() -> None:
    result = get_current_time()

    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, str)
    parsed = datetime.strptime(result.data, "%Y-%m-%d %H:%M:%S")
    assert parsed.strftime("%Y-%m-%d %H:%M:%S") == result.data


def test_tool_result_has_success_and_failure_constructors() -> None:
    success = ToolResult.ok({"answer": 42})
    failure = ToolResult.failure("calculation failed")

    assert success.success is True
    assert success.data == {"answer": 42}
    assert success.error is None
    assert failure.success is False
    assert failure.data is None
    assert failure.error == "calculation failed"
