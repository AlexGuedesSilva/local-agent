import json
from types import SimpleNamespace
from typing import Any

from agent.tools.contracts import ToolResult
from agent.tools.database import _normalize_query, query_database


def test_query_validation_accepts_single_select_and_rejects_writes() -> None:
    assert _normalize_query("SELECT id FROM users;") == "SELECT id FROM users"
    assert _normalize_query("WITH x AS (SELECT 1) SELECT * FROM x") is not None
    assert _normalize_query("DELETE FROM users") is None
    assert _normalize_query("SELECT 1; SELECT 2") is None


def test_query_database_requires_connection_configuration(monkeypatch: Any) -> None:
    monkeypatch.delenv("POSTGRES_DSN", raising=False)

    result = query_database("SELECT 1")

    assert result == ToolResult.failure(
        "PostgreSQL não configurado. Defina POSTGRES_DSN com o endereço do servidor."
    )


def test_query_database_executes_bounded_read_only_query(monkeypatch: Any) -> None:
    class FakeCursor:
        description = [SimpleNamespace(name="answer")]

        def __init__(self) -> None:
            self.statements: list[tuple[str, Any]] = []

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def execute(self, query: str, params: Any = None) -> None:
            self.statements.append((query, params))

        def fetchall(self) -> list[tuple[int]]:
            return [(42,)]

    class FakeConnection:
        read_only = False

        def __init__(self) -> None:
            self.fake_cursor = FakeCursor()

        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return self.fake_cursor

    connection = FakeConnection()
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://test")
    monkeypatch.setattr("agent.tools.database.psycopg.connect", lambda *args, **kwargs: connection)

    result = query_database("SELECT 42 AS answer")

    assert result.success is True
    assert connection.read_only is True
    assert "LIMIT %s" in connection.fake_cursor.statements[1][0]
    assert json.loads(result.data)["rows"] == [{"answer": 42}]
