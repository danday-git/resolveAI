from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int
    provider: str
    model: str


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    input_tokens: int
    latency_ms: int
    retries: int
    provider: str
    model: str


class LLMError(Exception):
    category: str


class ProviderTimeout(LLMError):
    category = "timeout"


class ProviderRateLimited(LLMError):
    category = "rate_limited"


class ProviderAuthError(LLMError):
    category = "auth"


class ProviderError(LLMError):
    category = "provider_error"


class InvalidModelOutput(LLMError):
    category = "invalid_output"


class ConfigError(LLMError):
    category = "config"


class ChatProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = True,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> ChatResult: ...


class EmbeddingProvider(ABC):
    name: str
    model: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult: ...
