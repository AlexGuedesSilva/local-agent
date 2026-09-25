"""Read-only PostgreSQL query tool for a configured database endpoint."""

import json
import logging
import os
import re
from typing import Any

import psycopg

from agent.tools.contracts import ToolResult

logger = logging.getLogger(__name__)
_READ_QUERY_START = re.compile(r"^(?:SELECT|WITH)\b", re.IGNORECASE)
_DEFAULT_ROW_LIMIT = 100
_MAX_QUERY_LENGTH = 10_000
_MAX_CELL_LENGTH = 2_000
_MAX_RESULT_CHARS = 30_000


def _normalize_query(query: str) -> str | None:
    if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY_LENGTH:
        return None
    statement = query.strip()
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if ";" in statement or not _READ_QUERY_START.match(statement):
        return None
    return statement


def query_database(query: str) -> ToolResult:
    """Execute one bounded SELECT in a read-only PostgreSQL transaction."""
    statement = _normalize_query(query)
    if statement is None:
        return ToolResult.failure(
            "Informe uma única consulta SELECT ou WITH (sem múltiplas instruções)."
        )

    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        return ToolResult.failure(
            "PostgreSQL não configurado. Defina POSTGRES_DSN com o endereço do servidor."
        )
    try:
        row_limit = int(os.getenv("POSTGRES_MAX_ROWS", str(_DEFAULT_ROW_LIMIT)))
        timeout_ms = int(os.getenv("POSTGRES_STATEMENT_TIMEOUT_MS", "5000"))
        connect_timeout = int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "5"))
        if not 1 <= row_limit <= 500 or timeout_ms < 1 or connect_timeout < 1:
            return ToolResult.failure("A configuração de limites PostgreSQL é inválida.")

        with psycopg.connect(dsn, connect_timeout=connect_timeout) as connection:
            connection.read_only = True
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", (f"{timeout_ms}ms",))
                cursor.execute(f"SELECT * FROM ({statement}) AS agent_query LIMIT %s", (row_limit,))
                columns = [column.name for column in cursor.description or []]
                rows = cursor.fetchall()

        values: list[dict[str, Any]] = []
        for row in rows:
            values.append({
                name: (value[:_MAX_CELL_LENGTH] if isinstance(value, str) else value)
                for name, value in zip(columns, row)
            })
        result: dict[str, Any] = {
            "columns": columns,
            "rows": values,
            "row_count": len(rows),
            "row_limit": row_limit,
        }
        output = json.dumps(result, ensure_ascii=False, default=str)
        while len(output) > _MAX_RESULT_CHARS and values:
            values.pop()
            result["truncated"] = True
            output = json.dumps(result, ensure_ascii=False, default=str)
        if len(output) > _MAX_RESULT_CHARS:
            result["columns"] = []
            result["rows"] = []
            result["truncated"] = True
            output = json.dumps(result, ensure_ascii=False)
        return ToolResult.ok(output)
    except Exception as error:
        logger.warning("Consulta PostgreSQL falhou (%s)", type(error).__name__)
        return ToolResult.failure(
            "Não foi possível consultar o PostgreSQL. Verifique conexão, permissões e sintaxe da consulta."
        )
