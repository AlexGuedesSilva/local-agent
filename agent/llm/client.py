from typing import Any

from dotenv import load_dotenv
import logging

from openai import APIConnectionError, APIStatusError, OpenAI
from agent.config import Settings

load_dotenv()
logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when the configured local model endpoint cannot serve requests."""


class LocalLLM:
    """OpenAI-compatible client configured for a local model server."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or Settings.from_env()
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
        )
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature

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
