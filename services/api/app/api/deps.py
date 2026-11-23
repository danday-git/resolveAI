from uuid import UUID

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.core.ai_settings import effective_settings
from app.core.config import Settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.models import Incident, User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    resolveai_session: str | None = Cookie(default=None),
) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization else resolveai_session
    if not token:
        raise ApiError(401, "UNAUTHORIZED", "Authentication required")
    try:
        user_id, issued_at = decode_access_token(token)
    except TimeoutError:
        raise ApiError(401, "TOKEN_EXPIRED", "Session expired") from None
    except ValueError:
        raise ApiError(401, "UNAUTHORIZED", "Invalid authentication token") from None
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise ApiError(401, "UNAUTHORIZED", "Invalid authentication token")
    if user.password_changed_at and issued_at < user.password_changed_at:
        raise ApiError(401, "TOKEN_EXPIRED", "Session expired")
    request.state.user_id = user.id
    return user


def get_owned[ModelT](db: Session, model: type[ModelT], object_id: UUID, user: User) -> ModelT:
    instance = db.get(model, object_id)
    if instance is None:
        raise ApiError(404, "NOT_FOUND", "Resource not found")
    owner_id = getattr(instance, "owner_id", None)
    if owner_id is None and hasattr(instance, "incident_id"):
        incident = db.get(Incident, instance.incident_id)
        owner_id = getattr(incident, "owner_id", None)
    if owner_id != user.id:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this resource")
    return instance


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise ApiError(403, "FORBIDDEN", "Administrator role required")
    return user


def missing_llm_consent(user: User) -> list[str]:
    """External providers in use that this user has not agreed to send data to."""
    # Reuse the request's session: a second pool checkout per request can exhaust the pool.
    return effective_settings(object_session(user)).missing_llm_consent(user.llm_consent_providers)


def check_llm_consent(user: User, settings: Settings | None = None) -> None:
    missing = (
        settings.missing_llm_consent(user.llm_consent_providers)
        if settings is not None
        else missing_llm_consent(user)
    )
    if missing:
        raise ApiError(
            403,
            "LLM_CONSENT_REQUIRED",
            "Allow sending your data to the external model provider on the Account page first",
            {"providers": missing},
        )


def require_llm_consent(user: User = Depends(get_current_user)) -> User:
    check_llm_consent(user)
    return user
