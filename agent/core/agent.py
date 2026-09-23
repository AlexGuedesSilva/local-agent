import json
from typing import Any

from agent.llm.client import LLMUnavailableError, LocalLLM
from agent.tools.base import TOOLS
from agent.tools.registry import get_tool

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
                    "use a ferramenta get_current_time."
                ),
            },
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_ITERATIONS):
            print(f"\n[AGENT] Iteração {iteration + 1}/{MAX_ITERATIONS}")
            print("[AGENT] Enviando mensagem para a LLM...")
            try:
                response = self.llm.chat(messages=messages, tools=TOOLS)
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
                        "content": result,
                    }
                )

        return "O agente atingiu o limite máximo de iterações."

    @staticmethod
    def _execute_tool(tool_call: Any) -> str:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        print(f"[TOOL] Ferramenta: {tool_name}")
        print(f"[TOOL] Argumentos: {arguments}")

        tool = get_tool(tool_name)
        if tool is None:
            return f"Erro: ferramenta '{tool_name}' não encontrada."

        try:
            result = tool(**arguments)
            print(f"[TOOL] Resultado: {result}")
            return str(result)
        except Exception as error:
            error_message = f"Erro ao executar a ferramenta '{tool_name}': {error}"
            print(f"[TOOL] {error_message}")
            return error_message
