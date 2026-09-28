"""Bounded development commands that require confirmation in the agent core."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.tools.contracts import ToolResult
from agent.tools.filesystem import _is_absolute_or_has_parent, _workspace_root

_MAX_ARGUMENTS = 12
_MAX_ARGUMENT_LENGTH = 500
_MAX_OUTPUT_CHARS = 20_000
_TIMEOUT_SECONDS = 90


def run_command(argv: list[str]) -> ToolResult:
    """Run an allowlisted development command without a shell."""
    validated = _validate_command(argv)
    if not validated.success:
        return validated
    assert isinstance(validated.data, dict)
    executable = validated.data["executable"]
    arguments = validated.data["arguments"]
    workspace = _workspace_root()

    try:
        completed = subprocess.run(
            [executable, *arguments],
            cwd=workspace,
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
            f"Comando excedeu o limite de {_TIMEOUT_SECONDS}s.\n{_limit_output(output)}"
        )
    except OSError as error:
        return ToolResult.failure(f"Não foi possível executar o comando: {error}")

    return ToolResult.ok({
        "exit_code": completed.returncode,
        "output": _limit_output(completed.stdout),
        "output_truncated": len(completed.stdout) > _MAX_OUTPUT_CHARS,
    })


def command_confirmation(argv: list[str]) -> ToolResult:
    """Describe the exact program and arguments that will be run."""
    validated = _validate_command(argv)
    if not validated.success:
        return validated
    command = " ".join(_display_argument(part) for part in argv)
    return ToolResult.ok(f"Executar no workspace ({_TIMEOUT_SECONDS}s máx.):\n{command}")


def _validate_command(argv: Any) -> ToolResult:
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > _MAX_ARGUMENTS
        or any(
            not isinstance(argument, str)
            or not argument
            or "\x00" in argument
            or len(argument) > _MAX_ARGUMENT_LENGTH
            for argument in argv
        )
    ):
        return ToolResult.failure("Informe argv como uma lista de 1 a 12 argumentos válidos.")

    command = argv[0].casefold()
    if command in {"python", "py", "pytest"}:
        if command == "pytest":
            test_paths = argv[1:]
        elif len(argv) >= 3 and argv[1:3] == ["-m", "pytest"]:
            test_paths = argv[3:]
        else:
            return ToolResult.failure(
                "Python só pode ser usado para executar pytest: ['python', '-m', 'pytest', ...]."
            )
        path_result = _validate_test_paths(test_paths)
        if not path_result.success:
            return path_result
        return ToolResult.ok({
            "executable": sys.executable,
            "arguments": ["-m", "pytest", "-q", *test_paths],
        })

    if command == "git" and len(argv) == 2 and argv[1] == "status":
        return ToolResult.ok({
            "executable": "git",
            "arguments": ["-c", "core.fsmonitor=false", "status"],
        })
    if command == "git" and len(argv) == 2 and argv[1] == "diff":
        return ToolResult.ok({
            "executable": "git",
            "arguments": ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv"],
        })

    return ToolResult.failure(
        "Comando não permitido. Disponíveis: python -m pytest [caminho], git status, git diff."
    )


def _validate_test_paths(paths: list[str]) -> ToolResult:
    workspace = _workspace_root()
    for path in paths:
        candidate = Path(path)
        if path.startswith("-") or _is_absolute_or_has_parent(path) or candidate.is_absolute():
            return ToolResult.failure("O caminho de teste deve ser relativo ao workspace e não pode conter '..'.")
        try:
            resolved = (workspace / candidate).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return ToolResult.failure(f"O caminho de teste não existe: {path}")
        if not resolved.is_relative_to(workspace) or not (resolved.is_file() or resolved.is_dir()):
            return ToolResult.failure(f"O caminho de teste não é válido dentro do workspace: {path}")
    return ToolResult.ok(paths)


def _limit_output(output: str) -> str:
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output or "(sem saída)"
    return output[:_MAX_OUTPUT_CHARS] + "\n[saída cortada]"


def _display_argument(argument: str) -> str:
    if argument.replace("_", "").replace("-", "").replace(".", "").isalnum():
        return argument
    return '"' + argument.replace('"', '\\"') + '"'
