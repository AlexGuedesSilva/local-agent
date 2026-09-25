import json
import logging
import os
from collections.abc import Callable
from typing import Any

from agent.llm.client import LLMUnavailableError, LocalLLM
from agent.tools.contracts import ToolResult
from agent.tools.registry import get_tool, get_tools_for_llm
from agent.tools.validation import validate_tool_arguments

logger = logging.getLogger(__name__)
MAX_ITERATIONS = int(os.getenv("LOCAL_AGENT_MAX_ITERATIONS", "10"))


class Agent:
    """Coordinate model responses and registered tool calls."""

    def __init__(self, confirm_action: Callable[[str], bool] | None = None) -> None:
        self.llm = LocalLLM()
        self.confirm_action = confirm_action or (lambda _description: False)

    def run(self, user_input: str) -> str:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Você é um agente local de IA. "
                    "Quando precisar realizar cálculos matemáticos, "
                    "use a ferramenta calculator. "
                    "Quando o usuário perguntar a data ou hora atual, "
                    "use a ferramenta get_current_time. "
                    "Quando pedir para listar o conteúdo de um diretório, "
                    "use a ferramenta list_directory com um caminho relativo ao workspace. "
                    "Para localizar código, use search_workspace; para ler partes de um arquivo, "
                    "use read_file com caminho relativo e, quando útil, intervalo de linhas. "
                    "Para consultar dados, use query_database apenas com uma consulta SELECT ou WITH; "
                    "não proponha comandos que alterem o banco."
                    " Para mover ou renomear itens, chame move_path; a aplicação exigirá "
                    "confirmação explícita e não sobrescreverá destinos existentes. "
                    "Só diga que uma ação foi concluída se a ferramenta confirmar sucesso."
                ),
            },
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_ITERATIONS):
            logger.debug("Iteração %s/%s", iteration + 1, MAX_ITERATIONS)
            try:
                response = self.llm.chat(messages=messages, tools=get_tools_for_llm())
            except LLMUnavailableError as error:
                logger.warning("LLM indisponível: %s", error)
                return str(error)
            except Exception:
                logger.exception("Falha inesperada ao consultar a LLM")
                return "Ocorreu um erro inesperado ao consultar o modelo local. Consulte os logs."

            try:
                message = response.choices[0].message
            except (AttributeError, IndexError, TypeError):
                logger.exception("Resposta LLM em formato inesperado")
                return "O modelo local retornou uma resposta em formato inesperado."

            if not message.tool_calls:
                if isinstance(message.content, str) and message.content.strip():
                    return message.content
                logger.warning("Resposta LLM sem conteúdo e sem chamadas de ferramenta")
                return "O modelo local retornou uma resposta vazia. Tente novamente."

            messages.append(message)
            for tool_call in message.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self._tool_result_content(result),
                    }
                )

        logger.warning("Agente atingiu limite de %s iterações", MAX_ITERATIONS)
        return "O agente atingiu o limite máximo de iterações."

    def _execute_tool(self, tool_call: Any) -> ToolResult:
        try:
            tool_name = tool_call.function.name
            raw_arguments = tool_call.function.arguments
        except (AttributeError, TypeError):
            logger.warning("A LLM retornou uma chamada de ferramenta malformada")
            return ToolResult.failure("Chamada de ferramenta malformada.")
        try:
            arguments = json.loads(raw_arguments)
        except (json.JSONDecodeError, TypeError) as error:
            detail = error.msg if isinstance(error, json.JSONDecodeError) else "formato inválido"
            return ToolResult.failure(f"Argumentos JSON inválidos: {detail}.")

        logger.info("Executando ferramenta %s", tool_name)

        tool = get_tool(tool_name)
        if tool is None:
            return ToolResult.failure(f"Ferramenta '{tool_name}' não encontrada.")

        validation = validate_tool_arguments(tool, arguments)
        if not validation.success:
            return validation

        if getattr(tool, "requires_confirmation", False):
            description = (
                f"Mover '{validation.data['source']}' para "
                f"'{validation.data['destination']}' dentro do workspace"
            )
            try:
                if not self.confirm_action(description):
                    return ToolResult.failure("Ação cancelada ou não autorizada pelo usuário.")
            except (EOFError, KeyboardInterrupt):
                logger.info("Confirmação de ação interrompida pelo usuário")
                return ToolResult.failure("Ação cancelada pelo usuário.")

        try:
            result = tool.execute(**validation.data)
        except Exception as error:
            logger.exception("Falha ao executar ferramenta %s", tool_name)
            result = ToolResult.failure(
                f"Erro ao executar a ferramenta '{tool_name}'."
            )

        logger.debug("Ferramenta %s concluída (success=%s)", tool_name, result.success)
        return result

    @staticmethod
    def _tool_result_content(result: ToolResult) -> str:
        if result.success:
            return str(result.data)
        return f"Erro: {result.error or 'a ferramenta falhou.'}"
