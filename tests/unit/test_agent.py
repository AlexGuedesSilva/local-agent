from typing import Any
from types import SimpleNamespace

import pytest

from agent.core.agent import Agent
from agent.llm.client import LLMUnavailableError
from agent.tools.contracts import ToolResult


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


class ToolCallingLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.messages_after_tool: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.calls += 1
        if self.calls == 1:
            call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="calculator",
                    arguments='{"expression": "2 + 2"}',
                ),
            )
            message = SimpleNamespace(tool_calls=[call], content=None)
        else:
            self.messages_after_tool = messages
            message = SimpleNamespace(tool_calls=None, content="Done")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_agent_sends_successful_tool_result_to_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = Agent()
    fake_llm = ToolCallingLLM()
    agent.llm = fake_llm  # type: ignore[assignment]
    monkeypatch.setattr(
        "agent.core.agent.get_tool",
        lambda name: lambda **kwargs: ToolResult.ok("4"),
    )

    response = agent.run("2 + 2")

    assert response == "Done"
    assert fake_llm.messages_after_tool[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "4",
    }


def test_agent_converts_unexpected_tool_exception_and_sends_error_to_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = Agent()
    fake_llm = ToolCallingLLM()
    agent.llm = fake_llm  # type: ignore[assignment]

    def broken_tool(**kwargs: Any) -> ToolResult:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr("agent.core.agent.get_tool", lambda name: broken_tool)

    response = agent.run("2 + 2")

    assert response == "Done"
    assert fake_llm.messages_after_tool[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "Erro: Erro ao executar a ferramenta 'calculator': unexpected failure",
    }
