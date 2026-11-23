import time
from collections.abc import Callable

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


class OllamaChatProvider(ChatProvider):
    name = "ollama"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = settings.llm_model or "qwen2.5:1.5b"
        self.base_url = settings.ollama_base_url.rstrip("/")
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
        body = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "format": "json" if json_mode else "",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or self.max_output_tokens,
            },
        }
        started = time.perf_counter()
        data, retries = post_json(
            self.client,
            f"{self.base_url}/api/chat",
            body,
            {},
            self.timeout,
            self.retries,
            self.sleep,
        )
        try:
            return ChatResult(
                data["message"]["content"],
                int(data.get("prompt_eval_count", 0)),
                int(data.get("eval_count", 0)),
                int((time.perf_counter() - started) * 1000),
                retries,
                self.name,
                self.model,
            )
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Ollama returned an invalid chat response") from None


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = settings.embedding_model or "nomic-embed-text"
        self.dimension = settings.embedding_dim
        self.batch_size = settings.embedding_batch_size
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.timeout = settings.llm_timeout_seconds
        self.retries = settings.llm_max_retries
        self.client = client or httpx.Client()
        self.sleep = sleep

    def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []
        tokens = retries = 0
        started = time.perf_counter()
        for start in range(0, len(texts), self.batch_size):
            data, attempt_count = post_json(
                self.client,
                f"{self.base_url}/api/embed",
                {"model": self.model, "input": texts[start : start + self.batch_size]},
                {},
                self.timeout,
                self.retries,
                self.sleep,
            )
            try:
                vectors.extend(data["embeddings"])
                tokens += int(data.get("prompt_eval_count", 0) or 0)
                retries += attempt_count
            except (KeyError, TypeError, ValueError):
                raise ProviderError("Ollama returned an invalid embedding response") from None
        return EmbeddingResult(
            vectors,
            tokens,
            int((time.perf_counter() - started) * 1000),
            retries,
            self.name,
            self.model,
        )
