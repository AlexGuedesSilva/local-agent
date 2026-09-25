from dataclasses import replace
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import pytest

from agent.core.agent import Agent
from agent.llm.client import LLMUnavailableError
from agent.tools.contracts import ToolResult
from agent.tools.registry import get_tool


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


def test_agent_reports_llm_unavailable_and_remains_usable(caplog: pytest.LogCaptureFixture) -> None:
    agent = Agent()
    fake = UnavailableThenReadyLLM()
    agent.llm = fake  # type: ignore[assignment]

    unavailable = agent.run("Olá")
    recovered = agent.run("Tente novamente")

    assert "indisponível" in unavailable
    assert "LLM indisponível" in caplog.text
    assert recovered == "Resposta disponível."


def test_agent_handles_empty_model_response() -> None:
    agent = Agent()

    class EmptyLLM:
        def chat(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
        ) -> Any:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content=None))]
            )

    agent.llm = EmptyLLM()  # type: ignore[assignment]

    assert "resposta vazia" in agent.run("Olá")


class ToolCallingLLM:
    def __init__(
        self,
        arguments: str = '{"expression": "2 + 2"}',
        tool_name: str = "calculator",
    ) -> None:
        self.calls = 0
        self.messages_after_tool: list[dict[str, Any]] = []
        self.arguments = arguments
        self.tool_name = tool_name
        self.tools_sent_to_llm: list[dict[str, Any]] | None = None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.calls += 1
        if self.calls == 1:
            self.tools_sent_to_llm = tools
            call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name=self.tool_name,
                    arguments=self.arguments,
                ),
            )
            message = SimpleNamespace(tool_calls=[call], content=None)
        else:
            self.messages_after_tool = messages
            message = SimpleNamespace(tool_calls=None, content="Done")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_agent_sends_successful_tool_result_to_llm() -> None:
    agent = Agent()
    fake_llm = ToolCallingLLM()
    agent.llm = fake_llm  # type: ignore[assignment]

    response = agent.run("2 + 2")

    assert response == "Done"
    assert fake_llm.tools_sent_to_llm is not None
    assert [tool["function"]["name"] for tool in fake_llm.tools_sent_to_llm] == [
        "calculator",
        "get_current_time",
        "list_directory",
        "read_file",
        "search_workspace",
        "query_database",
        "move_path",
    ]
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

    registered_tool = get_tool("calculator")
    assert registered_tool is not None
    monkeypatch.setattr(
        "agent.core.agent.get_tool",
        lambda name: replace(registered_tool, function=broken_tool),
    )

    response = agent.run("2 + 2")

    assert response == "Done"
    assert fake_llm.messages_after_tool[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "Erro: Erro ao executar a ferramenta 'calculator'.",
    }


def test_agent_does_not_execute_tool_with_invalid_arguments_and_sends_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = Agent()
    fake_llm = ToolCallingLLM(arguments="{}")
    agent.llm = fake_llm  # type: ignore[assignment]
    executions: list[dict[str, Any]] = []

    def tracked_tool(**kwargs: Any) -> ToolResult:
        executions.append(kwargs)
        return ToolResult.ok("should not run")

    registered_tool = get_tool("calculator")
    assert registered_tool is not None
    monkeypatch.setattr(
        "agent.core.agent.get_tool",
        lambda name: replace(registered_tool, function=tracked_tool),
    )

    response = agent.run("2 + 2")

    assert response == "Done"
    assert executions == []
    tool_message = fake_llm.messages_after_tool[-1]
    assert tool_message["role"] == "tool"
    assert "Erro:" in tool_message["content"]
    assert "expression" in tool_message["content"]


def test_agent_executes_list_directory_tool(
    monkeypatch: pytest.MonkeyPatch, isolated_temp_dir: Path
) -> None:
    (isolated_temp_dir / "readme.txt").write_text("temporary", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    agent = Agent()
    fake_llm = ToolCallingLLM(arguments='{"path": "."}', tool_name="list_directory")
    agent.llm = fake_llm  # type: ignore[assignment]

    response = agent.run("Liste os arquivos do diretório atual.")

    assert response == "Done"
    assert fake_llm.messages_after_tool[-1]["content"] == "arquivo: readme.txt"


def test_agent_requires_confirmation_before_moving_path(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "inbox").mkdir()
    (isolated_temp_dir / "inbox" / "note.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    confirmations: list[str] = []
    agent = Agent(confirm_action=lambda description: confirmations.append(description) or True)
    fake_llm = ToolCallingLLM(
        arguments='{"source": "inbox/note.txt", "destination": "note.txt"}',
        tool_name="move_path",
    )
    agent.llm = fake_llm  # type: ignore[assignment]

    response = agent.run("Mova minha anotação para a raiz.")

    assert response == "Done"
    assert confirmations == ["Mover 'inbox/note.txt' para 'note.txt' dentro do workspace"]
    assert (isolated_temp_dir / "note.txt").exists()


def test_agent_cancels_move_when_confirmation_is_denied(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "note.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    agent = Agent(confirm_action=lambda _description: False)
    fake_llm = ToolCallingLLM(
        arguments='{"source": "note.txt", "destination": "moved.txt"}',
        tool_name="move_path",
    )
    agent.llm = fake_llm  # type: ignore[assignment]

    response = agent.run("Mova o arquivo.")

    assert response == "Done"
    assert (isolated_temp_dir / "note.txt").exists()
    assert not (isolated_temp_dir / "moved.txt").exists()
    assert "cancelada" in fake_llm.messages_after_tool[-1]["content"]
