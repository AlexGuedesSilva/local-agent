from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent.tools.base import calculator, get_current_time
from agent.tools.contracts import Tool, ToolResult
from agent.tools.database import query_database
from agent.tools.filesystem import list_directory, read_file, search_workspace


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
    RegisteredTool(
        name=read_file.__name__,
        description=(
            "Lê o conteúdo de um arquivo de texto UTF-8 dentro do workspace permitido. "
            "Há um limite configurável de tamanho; não use caminhos absolutos nem '..'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho relativo ao workspace do arquivo.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Primeira linha (base 1), padrão 1.",
                },
                "line_count": {
                    "type": "integer",
                    "description": "Quantidade de linhas, máximo 500; omitido lê o arquivo inteiro dentro do limite de bytes.",
                },
            },
            "required": ["path"],
        },
        function=read_file,
    ),
    RegisteredTool(
        name=search_workspace.__name__,
        description=(
            "Pesquisa texto literal sem diferenciar maiúsculas no conteúdo de arquivos UTF-8 "
            "do workspace. Ignora diretórios ocultos e dependências; limite de resultados."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto a localizar."},
                "path": {"type": "string", "description": "Diretório relativo inicial; padrão '.'."},
                "file_pattern": {"type": "string", "description": "Padrão glob de nome, como '*.py'; padrão '*'."},
                "max_results": {"type": "integer", "description": "Máximo de ocorrências, entre 1 e 200; padrão 50."},
            },
            "required": ["query"],
        },
        function=search_workspace,
    ),
    RegisteredTool(
        name=query_database.__name__,
        description=(
            "Consulta o banco PostgreSQL configurado. Aceita somente uma consulta SELECT/WITH, "
            "em transação read-only, com limite de tempo e quantidade de linhas."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Uma consulta PostgreSQL SELECT ou WITH."}
            },
            "required": ["query"],
        },
        function=query_database,
    ),
)
TOOL_REGISTRY: dict[str, RegisteredTool] = {
    tool.name: tool for tool in _TOOL_DEFINITIONS
}


def get_tool(tool_name: str) -> Tool | None:
    return TOOL_REGISTRY.get(tool_name)


def get_tools_for_llm() -> list[dict[str, Any]]:
    return [tool.to_openai_tool() for tool in TOOL_REGISTRY.values()]
