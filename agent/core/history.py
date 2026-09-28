"""SQLite-backed local conversation history."""

import json
import os
import sqlite3
import uuid
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConversationSummary:
    """Small display-friendly description of a saved conversation."""

    conversation_id: str
    title: str
    updated_at: str


def default_history_path() -> Path:
    """Return a per-user database path, outside the project workspace."""
    configured_directory = os.getenv("LOCAL_AGENT_DATA_DIR")
    if configured_directory:
        data_directory = Path(configured_directory).expanduser()
    elif os.getenv("LOCALAPPDATA"):
        data_directory = Path(os.environ["LOCALAPPDATA"]) / "LocalAgent"
    elif os.getenv("XDG_DATA_HOME"):
        data_directory = Path(os.environ["XDG_DATA_HOME"]) / "local-agent"
    else:
        data_directory = Path.home() / ".local" / "share" / "local-agent"
    return data_directory / "history.sqlite3"


class ConversationHistory:
    """Persist conversation messages and titles in a local SQLite database."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or default_history_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    summary_message_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    message_json TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, position)
                )
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(conversations)")}
            if "summary" not in columns:
                connection.execute("ALTER TABLE conversations ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
            if "summary_message_count" not in columns:
                connection.execute("ALTER TABLE conversations ADD COLUMN summary_message_count INTEGER NOT NULL DEFAULT 0")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_conversation(self, title: str = "Nova conversa") -> str:
        conversation_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO conversations (conversation_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, title, now, now),
            )
        return conversation_id

    def latest_conversation_id(self) -> str | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT conversation_id FROM conversations ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return str(row["conversation_id"]) if row else None

    def load_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT message_json FROM messages WHERE conversation_id = ? ORDER BY position",
                (conversation_id,),
            ).fetchall()
        return [json.loads(row["message_json"]) for row in rows]

    def has_conversation(self, conversation_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return row is not None

    def load_summary(self, conversation_id: str) -> str:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT summary FROM conversations WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()
        return str(row["summary"]) if row else ""

    def load_context_summary(self, conversation_id: str) -> tuple[str, int]:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT summary, summary_message_count FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return (str(row["summary"]), int(row["summary_message_count"])) if row else ("", 0)

    def save_summary(self, conversation_id: str, summary: str, summarized_message_count: int = 0) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE conversations SET summary = ?, summary_message_count = ? WHERE conversation_id = ?",
                (summary, summarized_message_count, conversation_id),
            )

    def save_messages(
        self,
        conversation_id: str,
        messages: Sequence[dict[str, Any]],
        title: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE conversations SET title = COALESCE(?, title), updated_at = ? "
                "WHERE conversation_id = ?",
                (title, now, conversation_id),
            )
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            connection.executemany(
                "INSERT INTO messages (conversation_id, position, message_json) VALUES (?, ?, ?)",
                [
                    (conversation_id, position, json.dumps(message, ensure_ascii=False))
                    for position, message in enumerate(messages)
                ],
            )

    def list_conversations(self, limit: int = 20) -> list[ConversationSummary]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT conversation_id, title, updated_at FROM conversations "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            ConversationSummary(
                conversation_id=str(row["conversation_id"]),
                title=str(row["title"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def clear_messages(self, conversation_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            connection.execute(
                "UPDATE conversations SET title = 'Nova conversa', updated_at = ? "
                "WHERE conversation_id = ?",
                (now, conversation_id),
            )
            connection.execute(
                "UPDATE conversations SET summary = '', summary_message_count = 0 WHERE conversation_id = ?",
                (conversation_id,),
            )

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete one conversation and its messages."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
            )
        return cursor.rowcount > 0

    def delete_all_conversations(self) -> int:
        """Delete all conversations and return the number removed."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM conversations")
        return cursor.rowcount
