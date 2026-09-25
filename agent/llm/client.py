import os
from typing import Any

from dotenv import load_dotenv
import logging

from openai import APIConnectionError, APIStatusError, OpenAI

load_dotenv()
logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when the configured local model endpoint cannot serve requests."""


class LocalLLM:
    """OpenAI-compatible client configured for a local model server."""

    def __init__(self) -> None:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:1234/v1"),
            api_key=os.getenv("LLM_API_KEY", "lm-studio"),
            timeout=timeout,
        )
        self.model = os.getenv("LLM_MODEL")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        if not self.model:
            raise LLMUnavailableError(
                "LLM_MODEL não está configurado. Defina o identificador do modelo no arquivo .env."
            )
        try:
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=self.temperature,
            )
        except APIConnectionError as error:
            logger.warning("Falha de conexão com o endpoint LLM: %s", error)
            raise LLMUnavailableError(
                "Não foi possível conectar ao servidor ou modelo local. "
                "Verifique se o LM Studio está aberto e se o servidor e o modelo estão ativos."
            ) from error
        except APIStatusError as error:
            logger.warning("Endpoint LLM retornou status HTTP %s", error.status_code)
            raise LLMUnavailableError(
                f"O servidor LLM retornou HTTP {error.status_code}. "
                "Verifique o endpoint, o modelo e a configuração do servidor."
            ) from error
