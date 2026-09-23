from datetime import datetime
from agent.tools.contracts import ToolResult


def calculator(expression: str) -> ToolResult:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return ToolResult.ok(str(result))
    except Exception as error:
        return ToolResult.failure(f"Erro ao calcular: {error}")


def get_current_time() -> ToolResult:
    return ToolResult.ok(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
