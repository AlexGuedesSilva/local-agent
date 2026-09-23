from datetime import datetime
from typing import Any

from agent.tools.contracts import ToolResult


def calculator(expression: str) -> ToolResult:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return ToolResult.ok(str(result))
    except Exception as error:
        return ToolResult.failure(f"Erro ao calcular: {error}")


def get_current_time() -> ToolResult:
    return ToolResult.ok(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calcula uma expressão matemática.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expressão matemática, por exemplo: 1547 * 37",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Retorna a data e hora atual da máquina onde o agente está executando.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
