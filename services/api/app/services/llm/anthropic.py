import time
from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.services.llm.base import ChatMessage, ChatProvider, ChatResult, ProviderError
from app.services.llm.http import post_json


class AnthropicChatProvider(ChatProvider):
    name = "anthropic"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = settings.llm_model or "claude-haiku-4-5"
        self.base_url = settings.anthropic_base_url.rstrip("/")
        self.key = (
            settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        )
        self.timeout = settings.llm_timeout_seconds
        self.retries = settings.llm_max_retries
        self.max_output_tokens = settings.llm_max_output_tokens
        self.client = client or httpx.Client()
        self.sleep = sleep

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = True,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> ChatResult:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        if json_mode:
            system = f"{system}\n\nRespond with a single JSON object only."
        body = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_output_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages if m.role != "system"
            ],
        }
        started = time.perf_counter()
        data, retries = post_json(
            self.client,
            f"{self.base_url}/v1/messages",
            body,
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            self.timeout,
            self.retries,
            self.sleep,
        )
        try:
            text = "".join(
                block["text"] for block in data["content"] if block.get("type") == "text"
            )
            return ChatResult(
                text,
                int(data["usage"]["input_tokens"]),
                int(data["usage"]["output_tokens"]),
                int((time.perf_counter() - started) * 1000),
                retries,
                self.name,
                self.model,
            )
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Anthropic returned an invalid chat response") from None
