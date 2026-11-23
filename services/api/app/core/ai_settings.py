import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models import AppSetting

API_KEY_FIELDS = ("openai_api_key", "anthropic_api_key")


def _fernet(settings: Settings) -> Fernet:
    # shortcut: the key derives from JWT_SECRET, so rotating it makes stored API keys unreadable
    # (they then count as missing and must be entered again on the AI provider page).
    secret = settings.jwt_secret.get_secret_value().encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"app-settings:" + secret).digest()))


def encrypt(value: str, settings: Settings | None = None) -> str:
    return _fernet(settings or get_settings()).encrypt(value.encode()).decode()


def decrypt(value: str | None, settings: Settings | None = None) -> str | None:
    if not value:
        return None
    try:
        return _fernet(settings or get_settings()).decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def apply(row: AppSetting | None, settings: Settings) -> Settings:
    if row is None:
        return settings
    update: dict = {"llm_provider": row.llm_provider, "llm_model": row.llm_model}
    for field in API_KEY_FIELDS:
        plain = decrypt(getattr(row, field), settings)
        if plain:
            update[field] = SecretStr(plain)
    return settings.model_copy(update=update)


def effective_settings(db: Session | None = None) -> Settings:
    """Environment settings with the administrator's chat provider, model and keys on top."""
    if db is not None:
        return apply(db.get(AppSetting, 1), get_settings())
    with SessionLocal() as session:
        return apply(session.get(AppSetting, 1), get_settings())
