from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import Tool

TOOL_FUNCTIONS: dict[str, Tool] = {
    "calculator": calculator,
    "get_current_time": get_current_time,
}


def get_tool(tool_name: str) -> Tool | None:
    return TOOL_FUNCTIONS.get(tool_name)
