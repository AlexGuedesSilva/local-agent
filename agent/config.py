"""Validated environment-backed application settings."""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when an environment setting is malformed or out of range."""


class ProjectProfileError(ValueError):
    """Raised when a project profile is invalid or unsafe to use."""


@dataclass(frozen=True)
class ProjectProfile:
    """Small project-local profile with explicitly configured checks."""

    root: Path
    name: str
    checks: dict[str, tuple[str, ...]]

    @classmethod
    def load(cls, root: Path | None = None) -> "ProjectProfile":
        project_root = (root or workspace_root()).resolve(strict=True)
        profile_path = project_root / ".local-agent.json"
        if not profile_path.exists():
            return cls(root=project_root, name=project_root.name, checks={})
        try:
            if profile_path.stat().st_size > 32_000:
                raise ProjectProfileError(".local-agent.json excede o limite de 32 KB.")
            data = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProjectProfileError("Não foi possível ler .local-agent.json como JSON UTF-8 válido.") from error
        if not isinstance(data, dict):
            raise ProjectProfileError(".local-agent.json deve conter um objeto JSON.")
        name = data.get("name", project_root.name)
        checks = data.get("checks", {})
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ProjectProfileError("O nome do projeto precisa conter de 1 a 100 caracteres.")
        if not isinstance(checks, dict) or any(key not in {"test", "lint", "format", "build"} for key in checks):
            raise ProjectProfileError("checks aceita somente test, lint, format e build.")
        validated_checks: dict[str, tuple[str, ...]] = {}
        for check_name, argv in checks.items():
            if (
                not isinstance(argv, list)
                or not 1 <= len(argv) <= 12
                or any(
                    not isinstance(part, str)
                    or not part
                    or len(part) > 500
                    or "\x00" in part
                    or "\n" in part
                    or "\r" in part
                    for part in argv
                )
            ):
                raise ProjectProfileError(f"O comando '{check_name}' deve ser uma lista de 1 a 12 argumentos.")
            validated_checks[check_name] = tuple(argv)
        return cls(root=project_root, name=name.strip(), checks=validated_checks)

    def command_for(self, check_name: str) -> tuple[str, ...] | None:
        """Return one explicitly configured command, if present."""
        return self.checks.get(check_name)


def workspace_root() -> Path:
    """Resolve the configured project workspace using the file-tool default."""
    configured_root = Path(os.getenv("LOCAL_AGENT_WORKSPACE", ".")).expanduser()
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[1] / configured_root
    return configured_root.resolve(strict=True)


def workspace_root() -> Path:
    """Resolve the configured project workspace using the file-tool default."""
    configured_root = Path(os.getenv("LOCAL_AGENT_WORKSPACE", ".")).expanduser()
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[1] / configured_root
    return configured_root.resolve(strict=True)


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
