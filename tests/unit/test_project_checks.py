import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.core.agent import Agent
from agent.config import ProjectProfile, ProjectProfileError
from agent.tools.project_checks import (
    project_check_confirmation,
    run_confirmed_project_check,
    run_project_check,
)


def test_project_profile_loads_named_checks_and_rejects_invalid_commands(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / ".local-agent.json"
    profile_path.write_text(
        json.dumps({"name": "sample", "checks": {"test": ["python", "-m", "pytest"]}}),
        encoding="utf-8",
    )

    profile = ProjectProfile.load(tmp_path)
    assert profile.name == "sample"
    assert profile.command_for("test") == ("python", "-m", "pytest")
    assert profile.command_for("lint") is None

    profile_path.write_text(json.dumps({"checks": {"test": []}}), encoding="utf-8")
    try:
        ProjectProfile.load(tmp_path)
    except ProjectProfileError as error:
        assert "lista de 1 a 12" in str(error)
    else:
        raise AssertionError("empty commands must be rejected")

    profile_path.write_text(json.dumps({"checks": {"deploy": ["deploy"]}}), encoding="utf-8")
    try:
        ProjectProfile.load(tmp_path)
    except ProjectProfileError as error:
        assert "test, lint, format e build" in str(error)
    else:
        raise AssertionError("unsupported check names must be rejected")


def test_project_check_requires_preview_and_uses_approved_snapshot(
    tmp_path: Path, monkeypatch: Any
) -> None:
    profile_path = tmp_path / ".local-agent.json"
    profile_path.write_text(
        json.dumps({"name": "sample", "checks": {"test": ["python", "-m", "pytest"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(tmp_path))
    preview = project_check_confirmation("test")
    assert preview.success is True
    assert "python -m pytest" in preview.data["description"]
    assert run_project_check("test").success is False

    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="3 passed\n")

    monkeypatch.setattr("agent.tools.project_checks.subprocess.run", fake_run)
    profile_path.write_text(
        json.dumps({"name": "changed", "checks": {"test": ["unsafe-new-command"]}}),
        encoding="utf-8",
    )
    result = run_confirmed_project_check({"check_name": "test"}, preview.data)

    assert result.success is True
    assert calls[0][0] == ["python", "-m", "pytest"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["cwd"] == tmp_path


def test_agent_shows_project_check_command_before_execution(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / ".local-agent.json").write_text(
        json.dumps({"name": "sample", "checks": {"test": ["python", "-m", "pytest"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(tmp_path))
    confirmations: list[str] = []

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, messages: list[dict[str, Any]], tools: Any = None) -> Any:
            self.calls += 1
            if self.calls == 1:
                message = SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(
                        id="check-1",
                        function=SimpleNamespace(
                            name="run_project_check", arguments='{"check_name":"test"}'
                        ),
                    )],
                )
            else:
                assert "exit_code" in messages[-1]["content"]
                message = SimpleNamespace(content="Verificação concluída.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(
        "agent.tools.project_checks.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="3 passed"),
    )
    agent = Agent(confirm_action=lambda text: confirmations.append(text) or True)
    agent.llm = FakeLLM()  # type: ignore[assignment]

    assert agent.run("Rode os testes configurados") == "Verificação concluída."
    assert "python -m pytest" in confirmations[0]
