from pathlib import Path

from agent.core.history import ConversationHistory
from agent.tools.conversations import search_conversations


def test_search_conversations_reads_saved_history_from_configured_data_directory(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_DATA_DIR", str(tmp_path))  # type: ignore[attr-defined]
    history = ConversationHistory()
    conversation_id = history.create_conversation("Old discussion")
    history.save_messages(
        conversation_id,
        [{"role": "user", "content": "We chose SQLite for conversation storage."}],
        title="Old discussion",
    )

    result = search_conversations("SQLite")

    assert result.success is True
    assert result.data[0]["conversation_id"] == conversation_id
    assert result.data[0]["excerpt"] == "We chose SQLite for conversation storage."


def test_search_conversations_validates_query_and_result_limit() -> None:
    assert search_conversations(" ").success is False
    assert search_conversations("valid", max_results=6).success is False
