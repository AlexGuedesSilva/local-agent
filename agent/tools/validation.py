from typing import Any

from agent.tools.base import TOOLS
from agent.tools.contracts import ToolResult

_TOOL_PARAMETERS = {
    definition["function"]["name"]: definition["function"]["parameters"]
    for definition in TOOLS
}
_VALUE_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def validate_tool_arguments(tool_name: str, arguments: Any) -> ToolResult:
    """Validate required, declared, and basic typed arguments for a tool."""
    parameters = _TOOL_PARAMETERS.get(tool_name)
    if parameters is None:
        return ToolResult.failure(f"Definição da ferramenta '{tool_name}' não encontrada.")
    if not isinstance(arguments, dict):
        return ToolResult.failure("Os argumentos da ferramenta devem ser um objeto.")

    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    missing = [name for name in required if name not in arguments]
    if missing:
        names = ", ".join(missing)
        return ToolResult.failure(f"Argumentos obrigatórios ausentes: {names}.")

    unknown = [name for name in arguments if name not in properties]
    if unknown:
        names = ", ".join(unknown)
        return ToolResult.failure(f"Argumentos desconhecidos: {names}.")

    for name, value in arguments.items():
        schema_type = properties[name].get("type")
        expected_type = _VALUE_TYPES.get(schema_type)
        if expected_type is None:
            continue
        if schema_type in ("integer", "number") and isinstance(value, bool):
            return ToolResult.failure(
                f"Tipo inválido para '{name}': esperado {schema_type}."
            )
        if not isinstance(value, expected_type):
            return ToolResult.failure(
                f"Tipo inválido para '{name}': esperado {schema_type}."
            )

    return ToolResult.ok(arguments)
