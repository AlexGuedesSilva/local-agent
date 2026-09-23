from collections.abc import Callable
from typing import Any

from agent.tools.base import calculator, get_current_time

TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "calculator": calculator,
    "get_current_time": get_current_time,
}


def get_tool(tool_name: str) -> Callable[..., Any] | None:
    return TOOL_FUNCTIONS.get(tool_name)
