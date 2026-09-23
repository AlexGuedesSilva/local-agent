from agent.tools.contracts import ToolResult
from agent.tools.validation import validate_tool_arguments


def test_calculator_accepts_valid_arguments() -> None:
    result = validate_tool_arguments("calculator", {"expression": "2 + 2"})

    assert result == ToolResult.ok({"expression": "2 + 2"})


def test_calculator_rejects_missing_required_argument() -> None:
    result = validate_tool_arguments("calculator", {})

    assert result.success is False
    assert "expression" in (result.error or "")


def test_calculator_rejects_unknown_argument() -> None:
    result = validate_tool_arguments(
        "calculator", {"expression": "2 + 2", "precision": 2}
    )

    assert result.success is False
    assert "precision" in (result.error or "")


def test_calculator_rejects_invalid_argument_type() -> None:
    result = validate_tool_arguments("calculator", {"expression": 4})

    assert result.success is False
    assert "string" in (result.error or "")


def test_get_current_time_accepts_no_arguments() -> None:
    result = validate_tool_arguments("get_current_time", {})

    assert result == ToolResult.ok({})


def test_get_current_time_rejects_unknown_argument() -> None:
    result = validate_tool_arguments("get_current_time", {"timezone": "UTC"})

    assert result.success is False
    assert "timezone" in (result.error or "")
