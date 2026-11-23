import logging
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = "postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai"
    jwt_secret: SecretStr
    jwt_ttl_minutes: int = 480
    demo_user_email: str = "demo@resolveai.local"
    demo_user_password: str | None = None
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 10
    llm_provider: Literal["openai", "anthropic", "ollama", "mock"] = "openai"
    llm_model: str | None = None
    embedding_provider: Literal["openai", "anthropic", "ollama", "mock"] | None = None
    embedding_model: str | None = None
    embedding_dim: int = 1536
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 30
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 800
    embedding_batch_size: int = 64
    llm_pricing_file: str | None = None
    retrieval_top_k: int = 5
    retrieval_min_similarity: float = 0.25
    context_token_budget: int = 3000
    rate_limit_per_minute: int = 30
    daily_budget_usd: float = 1.0
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def empty_secret_is_missing(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def apply_provider_defaults(self) -> "Settings":
        defaults = {
            "openai": ("gpt-4o-mini", "text-embedding-3-small"),
            "anthropic": ("claude-haiku-4-5", "text-embedding-3-small"),
            "ollama": ("qwen2.5:1.5b", "nomic-embed-text"),
            "mock": ("mock-extractive-v1", "mock-hash-v1"),
        }
        if self.llm_model is None:
            self.llm_model = defaults[self.llm_provider][0]
        if self.embedding_provider is None:
            self.embedding_provider = (
                "openai" if self.llm_provider == "anthropic" else self.llm_provider
            )
            if self.llm_provider == "anthropic":
                logger.warning(
                    "Anthropic has no embeddings API; defaulting EMBEDDING_PROVIDER=openai"
                )
        if self.embedding_model is None:
            self.embedding_model = defaults[self.embedding_provider][1]
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
