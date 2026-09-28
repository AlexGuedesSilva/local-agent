from pathlib import Path

import pytest

from agent.core.history import ConversationHistory
import main


def test_startup_lists_and_executes_conversation_search_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_DATA_DIR", str(tmp_path))
    store = ConversationHistory()
    conversation_id = store.create_conversation("Decisão técnica")
    store.save_messages(
        conversation_id,
        [{"role": "user", "content": "Escolhemos SQLite para salvar conversas."}],
        title="Decisão técnica",
    )
    inputs = iter(["/buscar-conversas SQLite", "sair"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    class FakeAgent:
        def __init__(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(main, "Agent", FakeAgent)

    main.main()

    output = capsys.readouterr().out
    assert "/buscar-conversas TERMO" in output
    assert conversation_id in output
    assert "Escolhemos SQLite para salvar conversas." in output


def test_search_command_without_term_shows_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOCAL_AGENT_DATA_DIR", str(tmp_path))
    inputs = iter(["/buscar-conversas", "sair"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    class FakeAgent:
        def __init__(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(main, "Agent", FakeAgent)

    main.main()

    output = capsys.readouterr().out
    assert "Uso: /buscar-conversas TERMO" in output
