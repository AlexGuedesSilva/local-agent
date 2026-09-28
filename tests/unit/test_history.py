from pathlib import Path
from typing import Any
from types import SimpleNamespace

from agent.core.agent import Agent
from agent.core.history import ConversationHistory


def test_history_survives_store_recreation_and_can_be_cleared(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite3"
    store = ConversationHistory(database_path)
    conversation_id = store.create_conversation()
    messages = [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Oi"},
    ]

    store.save_messages(conversation_id, messages, title="Olá")

    reopened_store = ConversationHistory(database_path)
    assert reopened_store.latest_conversation_id() == conversation_id
    assert reopened_store.load_messages(conversation_id) == messages
    assert reopened_store.list_conversations()[0].title == "Olá"

    reopened_store.clear_messages(conversation_id)
    assert reopened_store.load_messages(conversation_id) == []
    assert reopened_store.list_conversations()[0].title == "Nova conversa"

    reopened_store.save_summary(conversation_id, "preferências importantes")
    assert reopened_store.load_summary(conversation_id) == "preferências importantes"
    reopened_store.clear_messages(conversation_id)
    assert reopened_store.load_summary(conversation_id) == ""


def test_history_can_delete_one_or_all_conversations(tmp_path: Path) -> None:
    store = ConversationHistory(tmp_path / "history.sqlite3")
    first = store.create_conversation("First")
    second = store.create_conversation("Second")
    store.save_messages(first, [{"role": "user", "content": "secret"}])

    assert store.delete_conversation(first) is True
    assert store.delete_conversation(first) is False
    assert store.load_messages(first) == []
    assert store.delete_all_conversations() == 1
    assert store.list_conversations() == []


def test_existing_history_database_is_migrated_with_summary_column(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "old-history.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE conversations (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE messages (conversation_id TEXT NOT NULL, position INTEGER NOT NULL, "
            "message_json TEXT NOT NULL, PRIMARY KEY (conversation_id, position))"
        )
        connection.execute(
            "INSERT INTO conversations VALUES ('legacy', 'Old', 'now', 'now')"
        )

    store = ConversationHistory(path)

    assert store.load_summary("legacy") == ""
    assert store.create_conversation()


def test_agent_appends_tool_exchange_to_persistent_history() -> None:
    agent = Agent()

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0
            self.second_request: list[dict[str, Any]] = []

        def chat(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
        ) -> Any:
            self.calls += 1
            if self.calls == 1:
                tool_call = SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(name="calculator", arguments='{"expression":"2 + 2"}'),
                )
                message = SimpleNamespace(content=None, tool_calls=[tool_call])
            elif self.calls == 2:
                self.second_request = messages
                message = SimpleNamespace(content="Quatro", tool_calls=None)
            else:
                self.second_request = messages
                message = SimpleNamespace(content="Lembro", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    fake_llm = FakeLLM()
    agent.llm = fake_llm  # type: ignore[assignment]
    history: list[dict[str, Any]] = []

    assert agent.run("Quanto é 2 + 2?", history=history) == "Quatro"
    assert [message["role"] for message in history] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert history[1]["tool_calls"][0]["function"]["name"] == "calculator"

    assert agent.run("E a resposta anterior?", history=history) == "Lembro"
    assert fake_llm.second_request[1]["content"] == "Quanto é 2 + 2?"
