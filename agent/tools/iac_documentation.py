"""Tools for filling the configured Lindt Word template from a Skyone IAC export."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from agent.documentation.skyone_iac import parse_skyone_iac
from agent.tools.contracts import ToolResult
from agent.tools.filesystem import (
    _is_absolute_or_has_parent,
    _workspace_root,
    _has_symlink_component,
)

logger = logging.getLogger(__name__)
_DEFAULT_MAX_IAC_BYTES = 2_000_000


def iac_documentation_confirmation(
    source_path: str, output_path: str | None = None
) -> ToolResult:
    """Describe the new document that will be written after user approval."""
    destination = output_path or f"{Path(source_path).stem}_documentacao.docx"
    return ToolResult.ok({
        "description": (
            f"Gerar uma nova especificação Word a partir de '{source_path}' em '{destination}'. "
            "O modelo configurado será preservado; campos ausentes ou inferidos ficarão marcados para revisão."
        )
    })


def fill_skyone_iac_template(
    source_path: str,
    output_path: str | None = None,
) -> ToolResult:
    """Fill a new Word specification from an IAC JSON file in the workspace."""
    if not isinstance(source_path, str) or not source_path or _is_absolute_or_has_parent(source_path):
        return ToolResult.failure("Use um caminho relativo ao workspace para o arquivo IAC.")

    load_dotenv()
    template_setting = os.getenv("LOCAL_AGENT_SKYONE_TEMPLATE", "").strip()
    if not template_setting:
        return ToolResult.failure(
            "Modelo Lindt não configurado. Defina LOCAL_AGENT_SKYONE_TEMPLATE com o caminho relativo do DOCX dentro do workspace."
        )
    if _is_absolute_or_has_parent(template_setting):
        return ToolResult.failure("LOCAL_AGENT_SKYONE_TEMPLATE deve ser relativo ao workspace e não pode conter '..'.")

    if output_path is not None and (
        not isinstance(output_path, str)
        or not output_path
        or _is_absolute_or_has_parent(output_path)
    ):
        return ToolResult.failure("Use um caminho relativo ao workspace para o DOCX de saída.")

    try:
        workspace = _workspace_root()
        source_relative = Path(source_path)
        template_relative = Path(template_setting)
        if _has_symlink_component(workspace, source_relative):
            return ToolResult.failure("O caminho do arquivo IAC não pode conter links simbólicos.")
        if _has_symlink_component(workspace, template_relative):
            return ToolResult.failure("O caminho do modelo não pode conter links simbólicos.")

        source = (workspace / source_relative).resolve(strict=True)
        template = (workspace / template_relative).resolve(strict=True)
        if not source.is_relative_to(workspace) or not template.is_relative_to(workspace):
            return ToolResult.failure("O arquivo IAC e o modelo devem permanecer dentro do workspace.")
        if not source.is_file() or not template.is_file():
            return ToolResult.failure("O arquivo IAC ou o modelo Word não é um arquivo válido.")
        if template.suffix.casefold() != ".docx":
            return ToolResult.failure("O modelo configurado deve ter extensão .docx.")

        max_bytes = int(os.getenv("LOCAL_AGENT_MAX_IAC_BYTES", str(_DEFAULT_MAX_IAC_BYTES)))
        if max_bytes < 1:
            return ToolResult.failure("LOCAL_AGENT_MAX_IAC_BYTES deve ser maior que zero.")
        if source.stat().st_size > max_bytes:
            return ToolResult.failure(f"O arquivo IAC excede o limite de {max_bytes} bytes.")
        content = source.read_bytes()
        if len(content) > max_bytes:
            return ToolResult.failure(f"O arquivo IAC excede o limite de {max_bytes} bytes.")
        modules = parse_skyone_iac(content.decode("utf-8-sig"))

        if output_path is None:
            output_relative = source_relative.with_name(f"{source_relative.stem}_documentacao.docx")
        else:
            output_relative = Path(output_path)
        if output_relative.suffix.casefold() != ".docx":
            return ToolResult.failure("O arquivo de saída deve ter extensão .docx.")
        if _has_symlink_component(workspace, output_relative.parent):
            return ToolResult.failure("O caminho de saída não pode conter links simbólicos.")
        output_parent = (workspace / output_relative.parent).resolve(strict=True)
        if not output_parent.is_relative_to(workspace):
            return ToolResult.failure("O diretório de saída está fora do workspace.")
        destination = output_parent / output_relative.name
        if destination in (source, template):
            return ToolResult.failure("A saída não pode sobrescrever o IAC nem o modelo.")
        if destination.exists():
            return ToolResult.failure("O arquivo de saída já existe; nenhum arquivo foi sobrescrito.")

        from agent.documentation.lindt_template import create_filled_lindt_template

        generated = create_filled_lindt_template(str(template), modules)
        with destination.open("xb") as output_file:
            output_file.write(generated)
        logger.info("Documento IAC criado em %s", destination.relative_to(workspace))
        return ToolResult.ok(
            f"Documento Word criado em {destination.relative_to(workspace).as_posix()} "
            f"com {len(modules)} componentes. Revise os itens marcados para confirmação."
        )
    except FileNotFoundError:
        return ToolResult.failure("O arquivo IAC, o modelo ou o diretório de saída não existe no workspace.")
    except UnicodeDecodeError:
        return ToolResult.failure("O IAC não está codificado em UTF-8.")
    except (OSError, RuntimeError, ValueError) as error:
        logger.warning("Não foi possível preencher o modelo IAC: %s", error)
        return ToolResult.failure(f"Não foi possível preencher o modelo Word: {error}")
    except Exception:
        logger.exception("Falha inesperada ao preencher o modelo IAC")
        return ToolResult.failure("Falha inesperada ao gerar o documento. Consulte os logs.")
