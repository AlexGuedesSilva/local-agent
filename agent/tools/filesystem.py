import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from dotenv import load_dotenv

from agent.tools.contracts import ToolResult

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MAX_FILE_BYTES = 100_000


def _workspace_root() -> Path:
    load_dotenv()
    configured_root = os.getenv("LOCAL_AGENT_WORKSPACE", ".")
    root = Path(configured_root).expanduser()
    if not root.is_absolute():
        root = _PROJECT_ROOT / root
    return root.resolve(strict=True)


def _is_absolute_or_has_parent(path: str) -> bool:
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    is_absolute = (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive or windows_path.root)
    )
    has_parent = ".." in posix_path.parts or ".." in windows_path.parts
    return is_absolute or has_parent


def list_directory(path: str) -> ToolResult:
    """List names and entry types in a directory inside the configured workspace."""
    if not isinstance(path, str) or not path or "\x00" in path:
        return ToolResult.failure("O caminho do diretório é inválido.")
    if _is_absolute_or_has_parent(path):
        return ToolResult.failure(
            "Use um caminho relativo ao workspace, sem caminhos absolutos ou '..'."
        )

    try:
        workspace = _workspace_root()
        target = (workspace / Path(path)).resolve(strict=True)
        if not target.is_relative_to(workspace):
            return ToolResult.failure("O caminho solicitado está fora do workspace.")
        if not target.is_dir():
            return ToolResult.failure("O caminho informado não é um diretório.")

        entries = sorted(target.iterdir(), key=lambda item: item.name.casefold())
        lines: list[str] = []
        for entry in entries:
            if entry.is_symlink():
                entry_type = "link"
            elif entry.is_dir():
                entry_type = "diretório"
            else:
                entry_type = "arquivo"
            lines.append(f"{entry_type}: {entry.name}")

        if not lines:
            return ToolResult.ok("O diretório está vazio.")
        return ToolResult.ok("\n".join(lines))
    except FileNotFoundError:
        return ToolResult.failure("O diretório solicitado não existe.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível listar o diretório: {error}")
    except Exception as error:
        return ToolResult.failure(f"Erro inesperado ao listar o diretório: {error}")


def read_file(path: str) -> ToolResult:
    """Read a small UTF-8 text file inside the configured workspace."""
    if not isinstance(path, str) or not path or "\x00" in path:
        return ToolResult.failure("O caminho do arquivo é inválido.")
    if _is_absolute_or_has_parent(path):
        return ToolResult.failure(
            "Use um caminho relativo ao workspace, sem caminhos absolutos ou '..'."
        )
    try:
        workspace = _workspace_root()
        target = (workspace / Path(path)).resolve(strict=True)
        if not target.is_relative_to(workspace):
            return ToolResult.failure("O caminho solicitado está fora do workspace.")
        if not target.is_file():
            return ToolResult.failure("O caminho informado não é um arquivo.")
        max_bytes = int(os.getenv("LOCAL_AGENT_MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE_BYTES)))
        if max_bytes < 1:
            return ToolResult.failure("LOCAL_AGENT_MAX_FILE_BYTES deve ser maior que zero.")
        if target.stat().st_size > max_bytes:
            return ToolResult.failure(f"O arquivo excede o limite de {max_bytes} bytes.")
        content = target.read_bytes()
        if len(content) > max_bytes:
            return ToolResult.failure(f"O arquivo excede o limite de {max_bytes} bytes.")
        return ToolResult.ok(content.decode("utf-8"))
    except FileNotFoundError:
        return ToolResult.failure("O arquivo solicitado não existe.")
    except UnicodeDecodeError:
        return ToolResult.failure("O arquivo não está codificado em UTF-8.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível ler o arquivo: {error}")
