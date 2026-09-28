import difflib
import hashlib
import os
import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import tempfile
from typing import Any

from dotenv import load_dotenv

from agent.tools.contracts import ToolResult

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MAX_FILE_BYTES = 100_000
_DEFAULT_MAX_SEARCH_FILES = 5_000
_DEFAULT_MAX_SEARCH_RESULTS = 50
_DEFAULT_MAX_SEARCH_BYTES = 5_000_000
_MAX_EDIT_DIFF_CHARS = 30_000
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
        skipped = 0
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
                        skipped += 1
                        continue
                    if resolved.stat().st_size > max_bytes:
                        skipped += 1
                        continue
                    content = resolved.read_bytes()
                    if len(content) > max_bytes:
                        skipped += 1
                        continue
                    total_bytes += len(content)
                    if total_bytes > max_search_bytes:
                        truncated = True
                        break
                    text = content.decode("utf-8")
                except (OSError, RuntimeError, UnicodeDecodeError):
                    skipped += 1
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
            if skipped:
                message += f" {skipped} arquivo(s) foram ignorados por limite ou formato não suportado."
            if truncated:
                message += " A busca atingiu um limite; nem todos os arquivos foram verificados."
            return ToolResult.ok(message)
        suffix = "\n(Resultados limitados.)" if truncated else ""
        if skipped:
            suffix += f"\n({skipped} arquivo(s) foram ignorados por limite ou formato não suportado.)"
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


def preview_file_edit(path: str, old_text: str, new_text: str) -> ToolResult:
    """Build a bounded unified diff and a fingerprint for a proposed file edit."""
    prepared = _prepare_file_edit(path, old_text, new_text)
    if not prepared.success:
        return prepared
    assert isinstance(prepared.data, dict)
    return ToolResult.ok({
        "diff": prepared.data["diff"],
        "expected_sha256": prepared.data["expected_sha256"],
        "new_content": prepared.data["new_content"],
        "original_content": prepared.data["original_content"],
    })


def edit_file(path: str, old_text: str, new_text: str) -> ToolResult:
    """Replace one exact text occurrence in a workspace file."""
    prepared = preview_file_edit(path, old_text, new_text)
    if not prepared.success:
        return prepared
    assert isinstance(prepared.data, dict)
    return apply_confirmed_file_edit(
        {"path": path},
        prepared.data,
    )


def preview_file_edits(changes: list[dict[str, str]]) -> ToolResult:
    """Prepare one bounded diff for a set of distinct workspace files."""
    if not isinstance(changes, list) or not 1 <= len(changes) <= 10:
        return ToolResult.failure("Informe de 1 a 10 alterações de arquivo.")
    items: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    diffs: list[str] = []
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"path", "old_text", "new_text"}:
            return ToolResult.failure("Cada alteração precisa conter apenas path, old_text e new_text.")
        path = change["path"]
        if not isinstance(path, str):
            return ToolResult.failure("O caminho de cada alteração precisa ser texto.")
        normalized_path = os.path.normcase(Path(path).as_posix())
        if normalized_path in seen_paths:
            return ToolResult.failure("Cada arquivo pode aparecer somente uma vez na mesma edição.")
        seen_paths.add(normalized_path)
        prepared = preview_file_edit(path, change["old_text"], change["new_text"])
        if not prepared.success:
            return ToolResult.failure(f"{path}: {prepared.error}")
        assert isinstance(prepared.data, dict)
        items.append({"path": path, **prepared.data})
        diffs.append(str(prepared.data["diff"]))
    combined_diff = "\n".join(diffs)
    if len(combined_diff) > _MAX_EDIT_DIFF_CHARS:
        return ToolResult.failure(
            f"O diff combinado excede {_MAX_EDIT_DIFF_CHARS} caracteres. Divida em alterações menores."
        )
    return ToolResult.ok(
        {
            "description": f"Editar {len(items)} arquivo(s) após revisar o diff:\n\n{combined_diff}",
            "items": items,
        }
    )


def edit_files(changes: list[dict[str, str]]) -> ToolResult:
    """Apply several reviewed exact-text edits to workspace files."""
    return ToolResult.failure("As edições múltiplas precisam passar pela confirmação do agente.")


def apply_confirmed_file_edits(
    arguments: dict[str, Any], preview: dict[str, Any]
) -> ToolResult:
    """Apply reviewed edits after checking every source, rolling back on failure."""
    items = preview.get("items")
    changes = arguments.get("changes")
    if not isinstance(items, list) or not isinstance(changes, list) or len(items) != len(changes):
        return ToolResult.failure("A prévia das edições não corresponde aos argumentos.")

    for change, item in zip(changes, items):
        if (
            not isinstance(change, dict)
            or not isinstance(item, dict)
            or change.get("path") != item.get("path")
        ):
            return ToolResult.failure("A lista de arquivos mudou depois da revisão.")
        current = preview_file_edit(
            item["path"], item["original_content"], item["new_content"]
        )
        if not current.success or current.data["expected_sha256"] != item["expected_sha256"]:
            return ToolResult.failure(
                f"O arquivo '{item['path']}' mudou depois da revisão. Gere um novo diff."
            )

    applied: list[dict[str, str]] = []
    for item in items:
        result = apply_confirmed_file_edit(
            {"path": item["path"]},
            {
                "expected_sha256": item["expected_sha256"],
                "new_content": item["new_content"],
            },
        )
        if not result.success:
            rollback_succeeded = True
            for previous in reversed(applied):
                rollback = apply_confirmed_file_edit(
                    {"path": previous["path"]},
                    {
                        "expected_sha256": hashlib.sha256(
                            previous["new_content"].encode("utf-8")
                        ).hexdigest(),
                        "new_content": previous["original_content"],
                    },
                )
                rollback_succeeded = rollback.success and rollback_succeeded
            detail = "As gravações anteriores foram revertidas." if rollback_succeeded else (
                "Uma gravação falhou e nem todas as alterações anteriores puderam ser revertidas."
            )
            return ToolResult.failure(f"{result.error} {detail}")
        applied.append(item)
    return ToolResult.ok(f"{len(applied)} arquivo(s) atualizado(s) após confirmação.")


def apply_confirmed_file_edit(
    arguments: dict[str, Any], preview: dict[str, Any]
) -> ToolResult:
    """Write a reviewed edit only if the source file has not changed."""
    path = arguments["path"]
    try:
        workspace = _workspace_root()
        relative_path = Path(path)
        if _has_symlink_component(workspace, relative_path):
            return ToolResult.failure("Editar arquivos que usam links simbólicos não é permitido.")
        target = (workspace / relative_path).resolve(strict=True)
        if not target.is_relative_to(workspace) or not target.is_file():
            return ToolResult.failure("O arquivo não é um arquivo regular dentro do workspace.")
        current_bytes = target.read_bytes()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        if current_hash != preview["expected_sha256"]:
            return ToolResult.failure(
                "O arquivo mudou depois da revisão. Peça uma nova leitura e gere outro diff."
            )

        new_content = preview["new_content"].encode("utf-8")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(new_content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, stat.S_IMODE(target.stat().st_mode))
            latest_bytes = target.read_bytes()
            if hashlib.sha256(latest_bytes).hexdigest() != preview["expected_sha256"]:
                return ToolResult.failure(
                    "O arquivo mudou durante a gravação. A edição foi cancelada; gere outro diff."
                )
            os.replace(temporary_path, target)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return ToolResult.ok(f"Arquivo atualizado: {path}")
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível aplicar a edição: {error}")


def _prepare_file_edit(path: str, old_text: str, new_text: str) -> ToolResult:
    if (
        not isinstance(path, str)
        or not path
        or "\x00" in path
        or _is_absolute_or_has_parent(path)
    ):
        return ToolResult.failure("Use um caminho relativo ao workspace, sem caminhos absolutos ou '..'.")
    if not isinstance(old_text, str) or not old_text:
        return ToolResult.failure("old_text precisa conter o trecho exato a substituir.")
    if not isinstance(new_text, str):
        return ToolResult.failure("new_text precisa ser um texto.")
    if len(old_text) > _DEFAULT_MAX_FILE_BYTES or len(new_text) > _DEFAULT_MAX_FILE_BYTES:
        return ToolResult.failure("O trecho antigo ou novo excede o limite de edição permitido.")

    try:
        workspace = _workspace_root()
        relative_path = Path(path)
        if _has_symlink_component(workspace, relative_path):
            return ToolResult.failure("Editar arquivos que usam links simbólicos não é permitido.")
        target = (workspace / relative_path).resolve(strict=True)
        if not target.is_relative_to(workspace):
            return ToolResult.failure("O arquivo solicitado está fora do workspace.")
        if not target.is_file():
            return ToolResult.failure("O caminho informado não é um arquivo.")

        max_bytes = int(os.getenv("LOCAL_AGENT_MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE_BYTES)))
        if max_bytes < 1:
            return ToolResult.failure("LOCAL_AGENT_MAX_FILE_BYTES deve ser maior que zero.")
        original_bytes = target.read_bytes()
        if len(original_bytes) > max_bytes:
            return ToolResult.failure(f"O arquivo excede o limite de {max_bytes} bytes.")
        original = original_bytes.decode("utf-8")
        if (
            ("\r\n" in original and any(
                marker in original.replace("\r\n", "") for marker in ("\n", "\r")
            ))
            or ("\r" in original and "\r\n" not in original)
        ):
            return ToolResult.failure(
                "O arquivo mistura estilos de quebra de linha; edite-o manualmente para preservar o formato."
            )
        newline = "\r\n" if "\r\n" in original else "\n"
        normalized_original = original.replace("\r\n", "\n").replace("\r", "\n")
        normalized_old = old_text.replace("\r\n", "\n").replace("\r", "\n")
        normalized_new = new_text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized_original.count(normalized_old) != 1:
            return ToolResult.failure(
                "O trecho antigo precisa aparecer exatamente uma vez. Leia o arquivo e tente novamente."
            )

        updated = normalized_original.replace(normalized_old, normalized_new, 1)
        if len(updated.encode("utf-8")) > max_bytes:
            return ToolResult.failure(f"O arquivo alterado excederia o limite de {max_bytes} bytes.")
        diff = "".join(
            difflib.unified_diff(
                normalized_original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        if not diff:
            return ToolResult.failure("A alteração proposta não muda o conteúdo do arquivo.")
        if len(diff) > _MAX_EDIT_DIFF_CHARS:
            return ToolResult.failure(
                f"O diff excede {_MAX_EDIT_DIFF_CHARS} caracteres. Faça uma alteração menor."
            )
        restored_newlines = updated.replace("\n", newline)
        return ToolResult.ok({
            "diff": diff,
            "expected_sha256": hashlib.sha256(original_bytes).hexdigest(),
            "new_content": restored_newlines,
            "original_content": original,
        })
    except FileNotFoundError:
        return ToolResult.failure("O arquivo solicitado não existe.")
    except UnicodeDecodeError:
        return ToolResult.failure("O arquivo não está codificado em UTF-8.")
    except (OSError, RuntimeError, ValueError) as error:
        return ToolResult.failure(f"Não foi possível preparar a edição: {error}")
