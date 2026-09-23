from agent.tools.contracts import ToolResult
from agent.tools.registry import get_tool
from agent.tools.validation import validate_tool_arguments


def test_calculator_accepts_valid_arguments() -> None:
    tool = get_tool("calculator")
    assert tool is not None
    result = validate_tool_arguments(tool, {"expression": "2 + 2"})

    assert result == ToolResult.ok({"expression": "2 + 2"})


def test_calculator_rejects_missing_required_argument() -> None:
    tool = get_tool("calculator")
    assert tool is not None
    result = validate_tool_arguments(tool, {})

    assert result.success is False
    assert "expression" in (result.error or "")


def test_calculator_rejects_unknown_argument() -> None:
    tool = get_tool("calculator")
    assert tool is not None
    result = validate_tool_arguments(tool, {"expression": "2 + 2", "precision": 2})

    assert result.success is False
    assert "precision" in (result.error or "")


def test_calculator_rejects_invalid_argument_type() -> None:
    tool = get_tool("calculator")
    assert tool is not None
    result = validate_tool_arguments(tool, {"expression": 4})

    assert result.success is False
    assert "string" in (result.error or "")


def test_get_current_time_accepts_no_arguments() -> None:
    tool = get_tool("get_current_time")
    assert tool is not None
    result = validate_tool_arguments(tool, {})

    assert result == ToolResult.ok({})


def test_get_current_time_rejects_unknown_argument() -> None:
    tool = get_tool("get_current_time")
    assert tool is not None
    result = validate_tool_arguments(tool, {"timezone": "UTC"})

    assert result.success is False
    assert "timezone" in (result.error or "")
