import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent.core.agent import Agent
from agent.core.history import ConversationHistory
import main


def test_terminal_workflow_edits_checks_persists_and_searches_project_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "sample-project"
    source_directory = workspace / "src"
    source_directory.mkdir(parents=True)
    first = source_directory / "models.py"
    second = source_directory / "api.py"
    first.write_text("MODEL = 'old_model'\n", encoding="utf-8")
    second.write_text("MODEL_NAME = 'old_model'\n", encoding="utf-8")
    (workspace / ".local-agent.json").write_text(
        json.dumps({"name": "sample-project", "checks": {"test": ["python", "-m", "pytest"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(workspace))
    monkeypatch.setenv("LOCAL_AGENT_DATA_DIR", str(tmp_path / "agent-data"))

    calls: list[list[str]] = []

    def fake_check(argv: list[str], **kwargs: Any) -> Any:
        calls.append(argv)
        assert kwargs["cwd"] == workspace
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout="4 passed\n")

    monkeypatch.setattr("agent.tools.project_checks.subprocess.run", fake_check)
    monkeypatch.setattr("agent.core.agent.LocalLLM", lambda _settings: object())

    class ScriptedLLM:
        def __init__(self) -> None:
            self.turn = 0

        def chat(self, messages: list[dict[str, Any]], tools: Any = None) -> Any:
            self.turn += 1
            if self.turn == 1:
                name = "edit_files"
                arguments = {
                    "changes": [
                        {
                            "path": "src/models.py",
                            "old_text": "old_model",
                            "new_text": "users_v2",
                        },
                        {
                            "path": "src/api.py",
                            "old_text": "old_model",
                            "new_text": "users_v2",
                        },
                    ]
                }
            elif self.turn == 2:
                name = "run_project_check"
                arguments = {"check_name": "test"}
            else:
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        tool_calls=None,
                        content="Arquivos atualizados e verificação concluída.",
                    ))]
                )
            tool_call = SimpleNamespace(
                id=f"call-{self.turn}",
                function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
            )

    def create_agent(
        confirm_action: Any = None, settings: Any = None
    ) -> Agent:
        agent = Agent(confirm_action=confirm_action, settings=settings)
        agent.llm = ScriptedLLM()  # type: ignore[assignment]
        return agent

    monkeypatch.setattr(main, "Agent", create_agent)
    confirmations: list[str] = []
    inputs = iter([
        "Atualize o modelo e a API para users_v2; a decisão de arquitetura foi registrar clientes.",
        "s",
        "s",
        "/buscar-conversas registrar clientes",
        "sair",
    ])

    def fake_input(prompt: str) -> str:
        if "Confirma esta ação?" in prompt:
            confirmations.append(prompt)
        return next(inputs)

    monkeypatch.setattr("builtins.input", fake_input)

    main.main()

    output = capsys.readouterr().out
    assert first.read_text(encoding="utf-8") == "MODEL = 'users_v2'\n"
    assert second.read_text(encoding="utf-8") == "MODEL_NAME = 'users_v2'\n"
    assert calls == [["python", "-m", "pytest"]]
    assert len(confirmations) == 2
    assert "diff" in output.casefold()
    assert "Arquivos atualizados e verificação concluída." in output
    assert "registrar clientes" in output

    store = ConversationHistory(project_root=workspace)
    assert store.latest_conversation_id() is not None
    assert store.search_conversations("users_v2")
