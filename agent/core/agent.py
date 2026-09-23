import json
from typing import Any

from agent.llm.client import LLMUnavailableError, LocalLLM
from agent.tools.contracts import ToolResult
from agent.tools.registry import get_tool, get_tools_for_llm
from agent.tools.validation import validate_tool_arguments

MAX_ITERATIONS = 10


class Agent:
    """Coordinate model responses and registered tool calls."""

    def __init__(self) -> None:
        self.llm = LocalLLM()

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
                    "use a ferramenta list_directory com um caminho relativo ao workspace."
                ),
            },
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_ITERATIONS):
            print(f"\n[AGENT] Iteração {iteration + 1}/{MAX_ITERATIONS}")
            print("[AGENT] Enviando mensagem para a LLM...")
            try:
                response = self.llm.chat(messages=messages, tools=get_tools_for_llm())
            except LLMUnavailableError as error:
                print(f"[LLM] {error}")
                return str(error)
            message = response.choices[0].message

            if not message.tool_calls:
                print("[AGENT] A LLM não solicitou ferramentas.\n")
                return message.content

            print("[LLM] A LLM solicitou ferramenta(s).\n")
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

        return "O agente atingiu o limite máximo de iterações."

    @staticmethod
    def _execute_tool(tool_call: Any) -> ToolResult:
        tool_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as error:
            return ToolResult.failure(f"Argumentos JSON inválidos: {error.msg}.")

        print(f"[TOOL] Ferramenta: {tool_name}")
        print(f"[TOOL] Argumentos: {arguments}")

        tool = get_tool(tool_name)
        if tool is None:
            return ToolResult.failure(f"Ferramenta '{tool_name}' não encontrada.")

        validation = validate_tool_arguments(tool, arguments)
        if not validation.success:
            return validation

        try:
            result = tool.execute(**validation.data)
        except Exception as error:
            result = ToolResult.failure(
                f"Erro ao executar a ferramenta '{tool_name}': {error}"
            )

        print(f"[TOOL] Resultado: {result}")
        return result

    @staticmethod
    def _tool_result_content(result: ToolResult) -> str:
        if result.success:
            return str(result.data)
        return f"Erro: {result.error or 'a ferramenta falhou.'}"
