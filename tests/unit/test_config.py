import pytest

from agent.config import ConfigurationError, Settings


def test_settings_load_valid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_AGENT_MAX_ITERATIONS", "4")
    monkeypatch.setenv("LOCAL_AGENT_MAX_CONTEXT_CHARS", "5000")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")

    settings = Settings.from_env()

    assert settings.max_iterations == 4
    assert settings.max_context_chars == 5000
    assert settings.llm_temperature == 0


@pytest.mark.parametrize(
    ("name", "value"),
    [("LOCAL_AGENT_MAX_ITERATIONS", "bad"), ("LLM_TIMEOUT_SECONDS", "0"),
     ("LOCAL_AGENT_MAX_CONTEXT_CHARS", "2")],
)
def test_settings_reject_invalid_environment(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError):
        Settings.from_env()
