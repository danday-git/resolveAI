from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: UUID) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_ttl_minutes)
    token = jwt.encode(
        # iat keeps its fraction: a password change has to end sessions opened in the same second.
        {"sub": str(user_id), "iat": now.timestamp(), "exp": expires},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    return token, expires


def decode_access_token(token: str) -> tuple[UUID, datetime]:
    """Returns the user id and when the token was issued."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        raise ValueError("invalid") from None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise ValueError("invalid") from None
    if datetime.fromtimestamp(exp, UTC) <= datetime.now(UTC):
        raise TimeoutError("expired")
    try:
        return UUID(str(payload["sub"])), datetime.fromtimestamp(payload["iat"], UTC)
    except (KeyError, ValueError, TypeError):
        raise ValueError("invalid") from None
