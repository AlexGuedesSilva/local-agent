import os
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

load_dotenv()


class LLMUnavailableError(RuntimeError):
    """Raised when the configured local model endpoint cannot serve requests."""


class LocalLLM:
    """OpenAI-compatible client configured for a local model server."""

    def __init__(self) -> None:
        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
        self.model = os.getenv("LLM_MODEL")

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        try:
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=0.7,
            )
        except APIConnectionError as error:
            raise LLMUnavailableError(
                "Não foi possível conectar ao servidor ou modelo local. "
                "Verifique se o LM Studio está aberto e se o servidor e o modelo estão ativos."
            ) from error
        except APIStatusError as error:
            if error.status_code == 404 or error.status_code >= 500:
                raise LLMUnavailableError(
                    "O servidor ou modelo local não está disponível. "
                    "Verifique se o LM Studio está aberto e se o modelo está carregado."
                ) from error
            raise
