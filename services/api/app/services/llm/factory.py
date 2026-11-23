from functools import lru_cache

from app.core.config import Settings
from app.services.llm.anthropic import AnthropicChatProvider
from app.services.llm.base import ChatProvider, ConfigError, EmbeddingProvider
from app.services.llm.mock import MockChatProvider, MockEmbeddingProvider
from app.services.llm.ollama import OllamaChatProvider, OllamaEmbeddingProvider
from app.services.llm.openai import OpenAIChatProvider, OpenAIEmbeddingProvider

KNOWN_EMBEDDING_DIMS = {
    ("openai", "text-embedding-ada-002"): 1536,
    ("ollama", "nomic-embed-text"): 768,
    ("ollama", "mxbai-embed-large"): 1024,
}


@lru_cache(maxsize=16)
def _chat(provider: str, model: str, api_key: str, base_url: str, timeout: float, retries: int):
    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider=provider,
        llm_model=model,
        openai_api_key=api_key or None,
        openai_base_url=base_url if provider == "openai" else "https://api.openai.com/v1",
        anthropic_api_key=api_key or None,
        anthropic_base_url=base_url if provider == "anthropic" else "https://api.anthropic.com",
        ollama_base_url=base_url if provider == "ollama" else "http://localhost:11434",
        llm_timeout_seconds=timeout,
        llm_max_retries=retries,
    )
    if provider == "openai":
        return OpenAIChatProvider(settings)
    if provider == "anthropic":
        return AnthropicChatProvider(settings)
    if provider == "ollama":
        return OllamaChatProvider(settings)
    return MockChatProvider(model)


@lru_cache(maxsize=16)
def _embedding(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    timeout: float,
    retries: int,
    dimension: int,
    batch_size: int,
):
    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider="mock",
        embedding_provider=provider,
        embedding_model=model,
        openai_api_key=api_key or None,
        openai_base_url=base_url if provider == "openai" else "https://api.openai.com/v1",
        ollama_base_url=base_url if provider == "ollama" else "http://localhost:11434",
        embedding_dim=dimension,
        llm_timeout_seconds=timeout,
        llm_max_retries=retries,
        embedding_batch_size=batch_size,
    )
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    if provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    return MockEmbeddingProvider(dimension, batch_size, model)


def get_chat_provider(settings: Settings) -> ChatProvider:
    provider = settings.llm_provider
    key = ""
    base_url = ""
    if provider == "openai":
        if settings.openai_api_key is None:
            raise ConfigError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        key, base_url = settings.openai_api_key.get_secret_value(), settings.openai_base_url
    elif provider == "anthropic":
        if settings.anthropic_api_key is None:
            raise ConfigError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic")
        key, base_url = settings.anthropic_api_key.get_secret_value(), settings.anthropic_base_url
    elif provider == "ollama":
        base_url = settings.ollama_base_url
    return _chat(
        provider,
        settings.llm_model or "",
        key,
        base_url,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
    )


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider or "openai"
    if provider == "anthropic":
        raise ConfigError(
            "Anthropic has no embeddings API; set EMBEDDING_PROVIDER=openai|ollama|mock"
        )
    key = ""
    base_url = ""
    if provider == "openai":
        if settings.openai_api_key is None:
            raise ConfigError("OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai")
        key, base_url = settings.openai_api_key.get_secret_value(), settings.openai_base_url
    elif provider == "ollama":
        base_url = settings.ollama_base_url
    model = settings.embedding_model or ""
    expected = KNOWN_EMBEDDING_DIMS.get((provider, model))
    if expected and settings.embedding_dim != expected:
        raise ConfigError(
            f"EMBEDDING_DIM={settings.embedding_dim} does not match {provider} model {model} "
            f"dimension {expected}"
        )
    return _embedding(
        provider,
        model,
        key,
        base_url,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
        settings.embedding_dim,
        settings.embedding_batch_size,
    )
