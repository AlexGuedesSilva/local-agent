"""Explicitly confirmed Git branch, staging, commit, and push operations."""

import os
import subprocess
from pathlib import Path
from typing import Any

from agent.config import workspace_root
from agent.tools.contracts import ToolResult
from agent.tools.filesystem import _has_symlink_component, _is_absolute_or_has_parent

_TIMEOUT_SECONDS = 90
_MAX_OUTPUT_CHARS = 20_000
_MAX_PATHS = 20


def git_create_branch(branch_name: str) -> ToolResult:
    """Create a branch after the Agent has presented an approval preview."""
    return ToolResult.failure("Criar branch exige confirmação explícita.")


def git_stage_paths(paths: list[str]) -> ToolResult:
    """Stage a bounded list of exact files after the Agent has presented them."""
    return ToolResult.failure("Preparar arquivos para commit exige confirmação explícita.")


def git_commit_changes(message: str) -> ToolResult:
    """Commit already staged changes after the Agent has shown their diff."""
    return ToolResult.failure("Criar commit exige confirmação explícita.")


def git_push_branch() -> ToolResult:
    """Push the current branch to origin after explicit approval."""
    return ToolResult.failure("Enviar alterações exige confirmação explícita.")


def git_create_branch_confirmation(branch_name: str) -> ToolResult:
    if not isinstance(branch_name, str) or not 1 <= len(branch_name) <= 100:
        return ToolResult.failure("O nome da branch deve conter de 1 a 100 caracteres.")
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root = root_result.data
    validation = _run_git(["check-ref-format", "--branch", branch_name], root)
    if not validation.success or validation.data["exit_code"] != 0:
        return ToolResult.failure("O nome informado não é válido para uma branch Git.")
    existing = _run_git(["branch", "--list", branch_name], root)
    if not existing.success:
        return existing
    if existing.data["output"].strip():
        return ToolResult.failure("Essa branch já existe localmente.")
    return _preview(
        root,
        ["switch", "-c", branch_name],
        f"Criar a branch local '{branch_name}'. As alterações atuais no workspace permanecem no diretório de trabalho.",
    )


def git_stage_confirmation(paths: list[str]) -> ToolResult:
    validation = _validate_paths(paths)
    if not validation.success:
        return validation
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root: Path = root_result.data
    listed = "\n".join(f"- {path}" for path in paths)
    return _preview(
        root,
        ["add", "--", *paths],
        f"Preparar estes arquivos exatos para o próximo commit:\n{listed}",
    )


def git_commit_confirmation(message: str) -> ToolResult:
    if (
        not isinstance(message, str)
        or not message.strip()
        or len(message) > 200
        or "\x00" in message
    ):
        return ToolResult.failure("A mensagem do commit deve conter de 1 a 200 caracteres.")
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root: Path = root_result.data
    staged = _run_git(["diff", "--cached", "--no-ext-diff", "--no-textconv"], root)
    if not staged.success:
        return staged
    if not staged.data["output"].strip():
        return ToolResult.failure("Não há alterações preparadas para commit.")
    diff = staged.data["output"][:_MAX_OUTPUT_CHARS]
    return _preview(
        root,
        ["commit", "-m", message],
        f"Criar commit com a mensagem:\n{message}\n\nDiff preparado:\n{diff}",
    )


def git_push_confirmation() -> ToolResult:
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root: Path = root_result.data
    branch_result = _run_git(["branch", "--show-current"], root)
    if not branch_result.success or branch_result.data["exit_code"] != 0:
        return ToolResult.failure("Não foi possível identificar a branch atual.")
    branch = branch_result.data["output"].strip()
    if not branch:
        return ToolResult.failure("Não é possível enviar commits de HEAD destacado.")
    return _preview(
        root,
        ["push", "origin", branch],
        f"Enviar a branch '{branch}' para o remoto 'origin'. Nenhuma opção de force será usada.",
    )


def run_confirmed_git_action(
    arguments: dict[str, Any], preview: dict[str, Any]
) -> ToolResult:
    """Execute only the exact Git arguments shown in a confirmed preview."""
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root: Path = root_result.data
    if str(root) != preview.get("workspace"):
        return ToolResult.failure("O workspace mudou depois da revisão. Solicite nova confirmação.")
    argv = preview.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(part, str) for part in argv):
        return ToolResult.failure("A ação Git aprovada está inválida.")
    result = _run_git(argv, root)
    if not result.success:
        return result
    if result.data["exit_code"] != 0:
        return ToolResult.failure(result.data["output"] or "A ação Git retornou erro.")
    return result


def _repository_root() -> ToolResult:
    try:
        root = workspace_root()
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Workspace inválido: {error}")
    if not (root / ".git").exists():
        return ToolResult.failure("As ações Git só estão disponíveis em um repositório Git.")
    return ToolResult.ok(root)


def _validate_paths(paths: Any) -> ToolResult:
    if not isinstance(paths, list) or not 1 <= len(paths) <= _MAX_PATHS:
        return ToolResult.failure("Informe de 1 a 20 caminhos de arquivo.")
    if any(
        not isinstance(path, str)
        or not path
        or len(path) > 500
        or "\x00" in path
        or path.startswith("-")
        or _is_absolute_or_has_parent(path)
        or any(part.casefold() == ".git" for part in Path(path).parts)
        for path in paths
    ):
        return ToolResult.failure("Use caminhos relativos, distintos e sem '..' ou componentes .git.")
    if len(set(paths)) != len(paths):
        return ToolResult.failure("Os caminhos de arquivo precisam ser distintos.")
    root_result = _repository_root()
    if not root_result.success:
        return root_result
    root: Path = root_result.data
    for path in paths:
        candidate = root / Path(path)
        if _has_symlink_component(root, Path(path)) or (
            candidate.exists() and not candidate.is_file()
        ):
            return ToolResult.failure(f"O caminho deve apontar para um arquivo regular: {path}")
        if not candidate.exists():
            tracked = _run_git(["ls-files", "--error-unmatch", "--", path], root)
            if not tracked.success or tracked.data["exit_code"] != 0:
                return ToolResult.failure(f"O arquivo não existe nem está versionado: {path}")
    return ToolResult.ok(paths)


def _preview(root: Path, argv: list[str], description: str) -> ToolResult:
    return ToolResult.ok(
        {"workspace": str(root), "argv": argv, "description": description}
    )


def _run_git(arguments: list[str], root: Path) -> ToolResult:
    try:
        completed = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", *arguments],
            cwd=root,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except subprocess.TimeoutExpired:
        return ToolResult.failure(f"A ação Git excedeu {_TIMEOUT_SECONDS}s.")
    except OSError as error:
        return ToolResult.failure(f"Não foi possível executar Git: {error}")
    output = completed.stdout
    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n[saída cortada]"
    return ToolResult.ok({"exit_code": completed.returncode, "output": output})
