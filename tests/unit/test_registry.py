from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import ToolResult
from agent.tools.registry import get_tool


def test_get_tool_returns_registered_tools() -> None:
    assert get_tool("calculator") is calculator
    assert get_tool("get_current_time") is get_current_time
    assert calculator.__name__ == "calculator"
    assert calculator("2 + 2") == ToolResult.ok("4")


def test_get_tool_returns_none_for_unknown_name() -> None:
    assert get_tool("missing") is None
