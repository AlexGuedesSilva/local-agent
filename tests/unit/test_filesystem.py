from pathlib import Path

import pytest

from agent.tools.contracts import ToolResult
from agent.tools.filesystem import list_directory, move_path, read_file, search_workspace


def test_lists_workspace_root(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "notes.txt").write_text(
        "temporary test content", encoding="utf-8"
    )
    (isolated_temp_dir / "project").mkdir()
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = list_directory(".")

    assert result.success is True
    assert "arquivo: notes.txt" in result.data
    assert "diretório: project" in result.data


def test_lists_valid_subdirectory(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = isolated_temp_dir / "project"
    project.mkdir()
    (project / "main.py").write_text("pass", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = list_directory("project")

    assert result.success is True
    assert result.data == "arquivo: main.py"


def test_missing_directory_returns_failure(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = list_directory("missing")

    assert result == ToolResult.failure("O diretório solicitado não existe.")


def test_file_path_returns_failure(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "notes.txt").write_text("temporary", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = list_directory("notes.txt")

    assert result.success is False
    assert "não é um diretório" in (result.error or "")


@pytest.mark.parametrize("path", ["..", "../outside", "nested/../../outside"])
def test_parent_path_is_rejected_before_workspace_access(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_workspace_access() -> Path:
        raise AssertionError("Workspace must not be accessed for parent paths")

    monkeypatch.setattr("agent.tools.filesystem._workspace_root", unexpected_workspace_access)

    result = list_directory(path)

    assert result.success is False
    assert ".." in (result.error or "")


def test_windows_style_escape_is_rejected_before_workspace_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_workspace_access() -> Path:
        raise AssertionError("Workspace must not be accessed for parent paths")

    monkeypatch.setattr("agent.tools.filesystem._workspace_root", unexpected_workspace_access)

    result = list_directory(r"..\..\outside")

    assert result.success is False


@pytest.mark.parametrize("path", ["C:\\Windows", r"\\server\share", "/etc"])
def test_absolute_path_is_rejected_before_workspace_access(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_workspace_access() -> Path:
        raise AssertionError("Workspace must not be accessed for absolute paths")

    monkeypatch.setattr("agent.tools.filesystem._workspace_root", unexpected_workspace_access)

    result = list_directory(path)

    assert result.success is False
    assert "relativo" in (result.error or "")


def test_invalid_path_and_unexpected_filesystem_error_return_failure(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    assert list_directory("bad\x00path").success is False

    def fail_to_list(self: Path):
        raise PermissionError("test filesystem error")

    monkeypatch.setattr(Path, "iterdir", fail_to_list)
    result = list_directory(".")

    assert result.success is False
    assert "test filesystem error" in (result.error or "")


def test_resolved_path_cannot_escape_workspace(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = isolated_temp_dir / "workspace"
    outside = isolated_temp_dir / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("temporary", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(workspace))
    original_resolve = Path.resolve

    def resolve_outside_link(path: Path, strict: bool = False) -> Path:
        if path == workspace / "outside-link":
            return outside
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_outside_link)

    result = list_directory("outside-link")

    assert result.success is False
    assert "fora do workspace" in (result.error or "")


def test_reads_utf8_file_inside_workspace(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "source.py").write_text("print('olá')", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    assert read_file("source.py") == ToolResult.ok("print('olá')")


def test_read_file_rejects_parent_paths_and_directories(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "folder").mkdir()
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    assert read_file("../outside").success is False
    assert "não é um arquivo" in (read_file("folder").error or "")


def test_read_file_enforces_configured_size_limit(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "large.txt").write_text("12345", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))
    monkeypatch.setenv("LOCAL_AGENT_MAX_FILE_BYTES", "4")

    result = read_file("large.txt")

    assert result.success is False
    assert "limite" in (result.error or "")


def test_read_file_rejects_non_utf8_files(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "binary.dat").write_bytes(b"\xff\xfe")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = read_file("binary.dat")

    assert result.success is False
    assert "UTF-8" in (result.error or "")


def test_read_file_returns_requested_line_range(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "source.py").write_text("uno\ndos\ntres\ncuatro", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    assert read_file("source.py", start_line=2, line_count=2) == ToolResult.ok("dos\ntres")


def test_search_workspace_finds_literal_matches_and_skips_dependencies(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "src").mkdir()
    (isolated_temp_dir / "src" / "app.py").write_text("def Greeting():\n    pass\n", encoding="utf-8")
    (isolated_temp_dir / "node_modules").mkdir()
    (isolated_temp_dir / "node_modules" / "vendor.py").write_text("Greeting", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = search_workspace("greeting", file_pattern="*.py")

    assert result.success is True
    assert result.data == "src/app.py:1: def Greeting():"


def test_search_workspace_rejects_escape_paths(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = search_workspace("needle", path="../")

    assert result.success is False


def test_move_path_moves_file_inside_workspace(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "inbox").mkdir()
    (isolated_temp_dir / "inbox" / "note.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    result = move_path("inbox/note.txt", "note.txt")

    assert result.success is True
    assert (isolated_temp_dir / "note.txt").read_text(encoding="utf-8") == "hello"
    assert not (isolated_temp_dir / "inbox" / "note.txt").exists()


def test_move_path_refuses_existing_destination_and_escape(
    isolated_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (isolated_temp_dir / "source.txt").write_text("source", encoding="utf-8")
    (isolated_temp_dir / "existing.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setenv("LOCAL_AGENT_WORKSPACE", str(isolated_temp_dir))

    collision = move_path("source.txt", "existing.txt")
    escape = move_path("source.txt", "../outside.txt")

    assert collision.success is False
    assert (isolated_temp_dir / "existing.txt").read_text(encoding="utf-8") == "keep"
    assert escape.success is False
    assert (isolated_temp_dir / "source.txt").exists()
