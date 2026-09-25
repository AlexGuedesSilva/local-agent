import os
import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath

from dotenv import load_dotenv

from agent.tools.contracts import ToolResult

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MAX_FILE_BYTES = 100_000
_DEFAULT_MAX_SEARCH_FILES = 5_000
_DEFAULT_MAX_SEARCH_RESULTS = 50
_DEFAULT_MAX_SEARCH_BYTES = 5_000_000
_SKIPPED_DIRECTORIES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
}


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


def _has_symlink_component(workspace: Path, relative_path: Path) -> bool:
    current = workspace
    for part in relative_path.parts:
        if part in ("", "."):
            continue
        current = current / part
        if current.is_symlink():
            return True
    return False


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


def read_file(path: str, start_line: int = 1, line_count: int | None = None) -> ToolResult:
    """Read a small UTF-8 text file inside the configured workspace."""
    if not isinstance(path, str) or not path or "\x00" in path:
        return ToolResult.failure("O caminho do arquivo é inválido.")
    if _is_absolute_or_has_parent(path):
        return ToolResult.failure(
            "Use um caminho relativo ao workspace, sem caminhos absolutos ou '..'."
        )
    if isinstance(start_line, bool) or not isinstance(start_line, int) or start_line < 1:
        return ToolResult.failure("start_line deve ser um inteiro maior que zero.")
    if line_count is not None and (
        isinstance(line_count, bool) or not isinstance(line_count, int) or not 1 <= line_count <= 500
    ):
        return ToolResult.failure("line_count deve estar entre 1 e 500.")
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
        lines = content.decode("utf-8").splitlines()
        if line_count is None and start_line == 1:
            return ToolResult.ok("\n".join(lines))
        selected = lines[start_line - 1 : start_line - 1 + (line_count or 500)]
        return ToolResult.ok("\n".join(selected))
    except FileNotFoundError:
        return ToolResult.failure("O arquivo solicitado não existe.")
    except UnicodeDecodeError:
        return ToolResult.failure("O arquivo não está codificado em UTF-8.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível ler o arquivo: {error}")


def search_workspace(
    query: str,
    path: str = ".",
    file_pattern: str = "*",
    max_results: int = _DEFAULT_MAX_SEARCH_RESULTS,
) -> ToolResult:
    """Find literal, case-insensitive matches in bounded UTF-8 workspace files."""
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return ToolResult.failure("A busca deve conter entre 1 e 500 caracteres.")
    if not isinstance(path, str) or not path or "\x00" in path or _is_absolute_or_has_parent(path):
        return ToolResult.failure("Use um caminho relativo ao workspace, sem '..'.")
    if not isinstance(file_pattern, str) or not file_pattern or len(file_pattern) > 100:
        return ToolResult.failure("O padrão de arquivo é inválido.")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 200:
        return ToolResult.failure("max_results deve estar entre 1 e 200.")
    try:
        workspace = _workspace_root()
        search_root = (workspace / Path(path)).resolve(strict=True)
        if not search_root.is_relative_to(workspace):
            return ToolResult.failure("O caminho solicitado está fora do workspace.")
        if not search_root.is_dir():
            return ToolResult.failure("O caminho informado não é um diretório.")

        max_bytes = int(os.getenv("LOCAL_AGENT_MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE_BYTES)))
        max_search_bytes = int(os.getenv("LOCAL_AGENT_MAX_SEARCH_BYTES", str(_DEFAULT_MAX_SEARCH_BYTES)))
        if max_bytes < 1 or max_search_bytes < 1:
            return ToolResult.failure("Os limites de leitura e busca devem ser maiores que zero.")
        needle = query.casefold()
        matches: list[str] = []
        scanned = 0
        total_bytes = 0
        truncated = False
        for directory, dirnames, filenames in os.walk(search_root, followlinks=False):
            dirnames[:] = [name for name in dirnames if name not in _SKIPPED_DIRECTORIES and not name.startswith(".")]
            for filename in sorted(filenames, key=str.casefold):
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                scanned += 1
                if scanned > _DEFAULT_MAX_SEARCH_FILES:
                    truncated = True
                    break
                candidate = Path(directory) / filename
                try:
                    resolved = candidate.resolve(strict=True)
                    if not resolved.is_relative_to(workspace) or not resolved.is_file():
                        continue
                    if resolved.stat().st_size > max_bytes:
                        continue
                    content = resolved.read_bytes()
                    if len(content) > max_bytes:
                        continue
                    total_bytes += len(content)
                    if total_bytes > max_search_bytes:
                        truncated = True
                        break
                    text = content.decode("utf-8")
                except (OSError, RuntimeError, UnicodeDecodeError):
                    continue
                rel_path = resolved.relative_to(workspace).as_posix()
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if needle in line.casefold():
                        matches.append(f"{rel_path}:{line_number}: {line[:300]}")
                        if len(matches) >= max_results:
                            truncated = True
                            break
                if len(matches) >= max_results or scanned >= _DEFAULT_MAX_SEARCH_FILES:
                    truncated = True
                    break
            if len(matches) >= max_results or scanned >= _DEFAULT_MAX_SEARCH_FILES or truncated:
                break
        if not matches:
            message = "Nenhuma ocorrência encontrada nos arquivos analisados."
            if truncated:
                message += " A busca atingiu um limite; nem todos os arquivos foram verificados."
            return ToolResult.ok(message)
        suffix = "\n(Resultados limitados.)" if truncated else ""
        return ToolResult.ok("\n".join(matches) + suffix)
    except FileNotFoundError:
        return ToolResult.failure("O diretório solicitado não existe.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível pesquisar o workspace: {error}")


def move_path(source: str, destination: str) -> ToolResult:
    """Move a file or directory between paths contained in the workspace."""
    for candidate in (source, destination):
        if (
            not isinstance(candidate, str)
            or not candidate
            or "\x00" in candidate
            or _is_absolute_or_has_parent(candidate)
        ):
            return ToolResult.failure("Use caminhos relativos ao workspace, sem '..'.")
    try:
        workspace = _workspace_root()
        source_path = workspace / Path(source)
        if _has_symlink_component(workspace, Path(source)):
            return ToolResult.failure("Mover links simbólicos não é permitido.")
        resolved_source = source_path.resolve(strict=True)
        if not resolved_source.is_relative_to(workspace):
            return ToolResult.failure("A origem está fora do workspace.")
        if resolved_source == workspace:
            return ToolResult.failure("Não é permitido mover a raiz do workspace.")

        destination_path = workspace / Path(destination)
        if _has_symlink_component(workspace, Path(destination).parent):
            return ToolResult.failure("Usar links simbólicos no caminho de destino não é permitido.")
        destination_parent = destination_path.parent.resolve(strict=True)
        if not destination_parent.is_relative_to(workspace):
            return ToolResult.failure("O destino está fora do workspace.")
        resolved_destination = destination_parent / destination_path.name
        if resolved_destination == resolved_source:
            return ToolResult.failure("A origem e o destino são iguais.")
        if resolved_destination.exists():
            return ToolResult.failure("O destino já existe; nenhum arquivo foi sobrescrito.")
        if resolved_source.is_dir() and resolved_destination.is_relative_to(resolved_source):
            return ToolResult.failure("Não é permitido mover uma pasta para dentro dela mesma.")

        resolved_source.rename(resolved_destination)
        return ToolResult.ok(
            f"Movido: {resolved_source.relative_to(workspace).as_posix()} -> "
            f"{resolved_destination.relative_to(workspace).as_posix()}"
        )
    except FileNotFoundError:
        return ToolResult.failure("A origem ou a pasta de destino não existe.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível mover o item: {error}")
