"""Validated environment-backed application settings."""

from dataclasses import dataclass
import logging
import os


class ConfigurationError(ValueError):
    """Raised when an environment setting is malformed or out of range."""


def _integer(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} precisa ser um número inteiro.") from error
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"entre {minimum} e {maximum}" if maximum is not None else f"maior ou igual a {minimum}"
        raise ConfigurationError(f"{name} precisa estar {bound}.")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} precisa ser numérico.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} precisa ser maior que zero.")
    return value


def _temperature() -> float:
    raw = os.getenv("LLM_TEMPERATURE", "0.2")
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError("LLM_TEMPERATURE precisa ser numérico.") from error
    if not 0 <= value <= 2:
        raise ConfigurationError("LLM_TEMPERATURE deve estar entre 0 e 2.")
    return value


@dataclass(frozen=True)
class Settings:
    """Application settings, parsed once at the composition boundary."""

    max_iterations: int = 10
    max_context_chars: int = 60_000
    log_level: str = "WARNING"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str | None = None
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "Settings":
        level = os.getenv("LOCAL_AGENT_LOG_LEVEL", "WARNING").upper()
        if level not in logging._nameToLevel:
            raise ConfigurationError("LOCAL_AGENT_LOG_LEVEL deve ser DEBUG, INFO, WARNING, ERROR ou CRITICAL.")
        temperature = _temperature()
        return cls(
            max_iterations=_integer("LOCAL_AGENT_MAX_ITERATIONS", 10, 1, 100),
            max_context_chars=_integer("LOCAL_AGENT_MAX_CONTEXT_CHARS", 60_000, 1_000, 2_000_000),
            log_level=level,
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:1234/v1"),
            llm_api_key=os.getenv("LLM_API_KEY", "lm-studio"),
            llm_model=os.getenv("LLM_MODEL"),
            llm_timeout_seconds=_positive_float("LLM_TIMEOUT_SECONDS", 120),
            llm_temperature=temperature,
        )
