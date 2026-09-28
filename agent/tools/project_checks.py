"""Project-configured checks with exact-command confirmation and bounded output."""

import os
import subprocess
from typing import Any

from agent.config import ProjectProfile, ProjectProfileError, workspace_root
from agent.tools.contracts import ToolResult

_CHECK_NAMES = {"test", "lint", "format", "build"}
_MAX_OUTPUT_CHARS = 20_000
_TIMEOUT_SECONDS = 180


def project_check_confirmation(check_name: str) -> ToolResult:
    """Resolve and describe the exact configured command before approval."""
    profile_result = _resolve_check(check_name)
    if not profile_result.success:
        return profile_result
    assert isinstance(profile_result.data, dict)
    argv = profile_result.data["argv"]
    display_command = " ".join(_quote_argument(part) for part in argv)
    return ToolResult.ok(
        {
            "argv": argv,
            "workspace": str(profile_result.data["workspace"]),
            "description": (
                f"Executar verificação '{check_name}' do projeto {profile_result.data['name']} "
                f"(limite {_TIMEOUT_SECONDS}s):\n{display_command}"
            ),
        }
    )


def run_project_check(check_name: str) -> ToolResult:
    """Placeholder execution path; Agent uses the approved preview snapshot."""
    return ToolResult.failure(
        "A verificação de projeto só pode ser executada após confirmação explícita."
    )


def run_confirmed_project_check(
    arguments: dict[str, Any], preview: dict[str, Any]
) -> ToolResult:
    """Run only the command that was shown in the approved preview."""
    check_name = arguments.get("check_name")
    if check_name not in _CHECK_NAMES:
        return ToolResult.failure("Tipo de verificação inválido.")
    try:
        current_root = workspace_root()
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Workspace inválido: {error}")
    if str(current_root) != preview.get("workspace"):
        return ToolResult.failure("O workspace mudou depois da revisão. Solicite nova confirmação.")
    argv = preview.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(part, str) for part in argv):
        return ToolResult.failure("O comando aprovado está inválido.")
    try:
        completed = subprocess.run(
            argv,
            cwd=current_root,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            check=False,
            env={**os.environ, "PY_COLORS": "0", "NO_COLOR": "1"},
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return ToolResult.failure(
            f"Verificação excedeu {_TIMEOUT_SECONDS}s.\n{_limit_output(output)}"
        )
    except OSError as error:
        return ToolResult.failure(f"Não foi possível executar a verificação: {error}")

    return ToolResult.ok(
        {
            "check": check_name,
            "exit_code": completed.returncode,
            "output": _limit_output(completed.stdout),
            "output_truncated": len(completed.stdout) > _MAX_OUTPUT_CHARS,
        }
    )


def _resolve_check(check_name: str) -> ToolResult:
    if check_name not in _CHECK_NAMES:
        return ToolResult.failure("check_name deve ser test, lint, format ou build.")
    try:
        profile = ProjectProfile.load()
    except ProjectProfileError as error:
        return ToolResult.failure(str(error))
    argv = profile.command_for(check_name)
    if argv is None:
        return ToolResult.failure(
            f"Verificação '{check_name}' não configurada em .local-agent.json."
        )
    return ToolResult.ok({"argv": list(argv), "workspace": profile.root, "name": profile.name})


def _limit_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output or "(sem saída)"
    return output[:_MAX_OUTPUT_CHARS] + "\n[saída cortada]"


def _quote_argument(argument: str) -> str:
    if argument.replace("_", "").replace("-", "").replace(".", "").isalnum():
        return argument
    return '"' + argument.replace('"', '\\"') + '"'
