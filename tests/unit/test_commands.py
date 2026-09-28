from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.tools.commands import command_confirmation, run_command


def test_run_command_executes_approved_command_without_shell(
    isolated_temp_dir: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="51 passed\n")

    monkeypatch.setattr("agent.tools.commands.subprocess.run", fake_run)

    result = run_command(["python", "-m", "pytest"])

    assert result.success is True
    assert result.data["exit_code"] == 0
    command, options = calls[0]
    assert command[1:4] == ["-m", "pytest", "-q"]
    assert options["shell"] is False
    assert options["cwd"] == isolated_temp_dir
    assert "90s" in str(command_confirmation(["python", "-m", "pytest"]).data)


def test_run_command_rejects_shell_and_arbitrary_python(
    isolated_temp_dir: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    shell_command = run_command(["python", "-m", "pytest", "&&", "whoami"])
    arbitrary_python = run_command(["python", "-c", "print('unsafe')"])
    arbitrary_executable = run_command(["powershell", "-Command", "Get-ChildItem"])

    assert shell_command.success is False
    assert arbitrary_python.success is False
    assert arbitrary_executable.success is False


def test_run_command_rejects_test_paths_outside_workspace(
    isolated_temp_dir: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = run_command(["python", "-m", "pytest", "../outside"])

    assert result.success is False
    assert "relativo" in (result.error or "")
