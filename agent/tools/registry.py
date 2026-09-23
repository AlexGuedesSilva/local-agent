from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import Tool, ToolResult
from agent.tools.filesystem import list_directory


@dataclass(frozen=True)
class RegisteredTool:
    """A tool's identity, LLM metadata, argument schema, and implementation."""

    name: str
    description: str
    parameters: dict[str, Any]
    function: Callable[..., ToolResult]

    def execute(self, **arguments: Any) -> ToolResult:
        return self.function(**arguments)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_TOOL_DEFINITIONS = (
    RegisteredTool(
        name=calculator.__name__,
        description="Calcula uma expressão matemática.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expressão matemática, por exemplo: 1547 * 37",
                }
            },
            "required": ["expression"],
        },
        function=calculator,
    ),
    RegisteredTool(
        name=get_current_time.__name__,
        description="Retorna a data e hora atual da máquina onde o agente está executando.",
        parameters={"type": "object", "properties": {}},
        function=get_current_time,
    ),
    RegisteredTool(
        name=list_directory.__name__,
        description=(
            "Lista arquivos, diretórios e links em um diretório relativo ao workspace permitido. "
            "Não use caminhos absolutos nem '..'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho relativo ao workspace; use '.' para a raiz.",
                }
            },
            "required": ["path"],
        },
        function=list_directory,
    ),
)
TOOL_REGISTRY: dict[str, RegisteredTool] = {
    tool.name: tool for tool in _TOOL_DEFINITIONS
}


def get_tool(tool_name: str) -> Tool | None:
    return TOOL_REGISTRY.get(tool_name)


def get_tools_for_llm() -> list[dict[str, Any]]:
    return [tool.to_openai_tool() for tool in TOOL_REGISTRY.values()]
