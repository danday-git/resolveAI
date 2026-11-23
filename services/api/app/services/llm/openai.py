import time
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import Settings
from app.services.llm.base import (
    ChatMessage,
    ChatProvider,
    ChatResult,
    EmbeddingProvider,
    EmbeddingResult,
    ProviderError,
)
from app.services.llm.http import post_json


class OpenAIChatProvider(ChatProvider):
    name = "openai"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = settings.llm_model or "gpt-4o-mini"
        self.base_url = settings.openai_base_url.rstrip("/")
        self.key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        self.timeout = settings.llm_timeout_seconds
        self.retries = settings.llm_max_retries
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
        body = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens or 800,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        data, retries = post_json(
            self.client,
            f"{self.base_url}/chat/completions",
            body,
            {"Authorization": f"Bearer {self.key}"},
            self.timeout,
            self.retries,
            self.sleep,
        )
        try:
            text = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            return ChatResult(
                text=text,
                input_tokens=int(usage["prompt_tokens"]),
                output_tokens=int(usage["completion_tokens"]),
                latency_ms=int((time.perf_counter() - started) * 1000),
                retries=retries,
                provider=self.name,
                model=self.model,
            )
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("OpenAI returned an invalid chat response") from None


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = settings.embedding_model or "text-embedding-3-small"
        self.dimension = settings.embedding_dim
        self.batch_size = settings.embedding_batch_size
        self.base_url = settings.openai_base_url.rstrip("/")
        self.key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        self.timeout = settings.llm_timeout_seconds
        self.retries = settings.llm_max_retries
        self.client = client or httpx.Client()
        self.sleep = sleep

    def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []
        tokens = retries = 0
        started = time.perf_counter()
        for start in range(0, len(texts), self.batch_size):
            body: dict[str, Any] = {
                "model": self.model,
                "input": texts[start : start + self.batch_size],
            }
            if self.model.startswith("text-embedding-3-"):
                body["dimensions"] = self.dimension
            data, attempt_count = post_json(
                self.client,
                f"{self.base_url}/embeddings",
                body,
                {"Authorization": f"Bearer {self.key}"},
                self.timeout,
                self.retries,
                self.sleep,
            )
            try:
                vectors.extend(item["embedding"] for item in data["data"])
                tokens += int(data["usage"]["prompt_tokens"])
                retries += attempt_count
            except (KeyError, TypeError, ValueError):
                raise ProviderError("OpenAI returned an invalid embedding response") from None
        return EmbeddingResult(
            vectors,
            tokens,
            int((time.perf_counter() - started) * 1000),
            retries,
            self.name,
            self.model,
        )
