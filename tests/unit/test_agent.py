from typing import Any

from agent.core.agent import Agent
from agent.llm.client import LLMUnavailableError


class UnavailableThenReadyLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.calls += 1
        if self.calls == 1:
            raise LLMUnavailableError("Servidor/modelo local indisponível.")
        message = type("Message", (), {"tool_calls": None, "content": "Resposta disponível."})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


def test_agent_reports_llm_unavailable_and_remains_usable(capsys: Any) -> None:
    agent = Agent()
    fake = UnavailableThenReadyLLM()
    agent.llm = fake  # type: ignore[assignment]

    unavailable = agent.run("Olá")
    printed = capsys.readouterr().out
    recovered = agent.run("Tente novamente")

    assert "indisponível" in unavailable
    assert "indisponível" in printed
    assert recovered == "Resposta disponível."
