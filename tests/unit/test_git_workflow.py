from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.tools.git_workflow import (
    git_commit_confirmation,
    git_create_branch_confirmation,
    git_push_confirmation,
    git_stage_confirmation,
    run_confirmed_git_action,
)


def test_git_actions_show_approved_arguments_and_never_use_shell(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / ".git").mkdir()
    tracked_file = tmp_path / "example.py"
    tracked_file.write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(tmp_path))
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls.append((argv, kwargs))
        output = ""
        if "diff" in argv:
            output = "diff --git a/example.py b/example.py\n+print('changed')"
        elif "--show-current" in argv:
            output = "codex/sample\n"
        return SimpleNamespace(returncode=0, stdout=output)

    monkeypatch.setattr("agent.tools.git_workflow.subprocess.run", fake_run)

    branch_preview = git_create_branch_confirmation("codex/feature")
    assert branch_preview.success is True
    assert "codex/feature" in branch_preview.data["description"]
    branch_result = run_confirmed_git_action({"branch_name": "codex/feature"}, branch_preview.data)

    stage_preview = git_stage_confirmation(["example.py"])
    assert stage_preview.success is True
    stage_result = run_confirmed_git_action({"paths": ["example.py"]}, stage_preview.data)

    commit_preview = git_commit_confirmation("feat: update example")
    assert commit_preview.success is True
    assert "diff --git" in commit_preview.data["description"]
    commit_result = run_confirmed_git_action({"message": "feat: update example"}, commit_preview.data)

    push_preview = git_push_confirmation()
    assert push_preview.success is True
    assert "codex/sample" in push_preview.data["description"]
    assert "origin" in push_preview.data["description"]
    assert "force" in push_preview.data["description"]
    push_result = run_confirmed_git_action({}, push_preview.data)

    assert all(result.success for result in (branch_result, stage_result, commit_result, push_result))
    assert all(options["shell"] is False for _, options in calls)
    assert calls[2][0][-3:] == ["switch", "-c", "codex/feature"]
    assert calls[3][0][-3:] == ["add", "--", "example.py"]
    assert calls[5][0][-3:] == ["commit", "-m", "feat: update example"]
    assert calls[7][0][-3:] == ["push", "origin", "codex/sample"]


def test_git_stage_paths_rejects_escape_and_git_metadata(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(tmp_path))

    assert git_stage_confirmation(["../secret.txt"]).success is False
    assert git_stage_confirmation([".git/config"]).success is False


def test_commit_preview_requires_staged_changes(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        "agent.tools.git_workflow.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )

    result = git_commit_confirmation("feat: nothing")

    assert result.success is False
    assert "Não há alterações preparadas" in (result.error or "")
