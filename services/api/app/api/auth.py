from threading import Lock
from time import monotonic
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.security import create_access_token, verify_password
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts: dict[str, list[float]] = {}
_lock = Lock()


class LoginRequest(BaseModel):
    email: str
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        local, separator, domain = value.rpartition("@")
        local_domain = domain.lower().endswith(".local")
        candidate = f"{local}@{domain[:-6]}.example" if separator and local_domain else value
        try:
            normalized = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError:
            raise ValueError("Invalid email address") from None
        if local_domain:
            return f"{normalized.local_part}@{domain.lower()}"
        return normalized.normalized


def _check_login_limit(key: str) -> None:
    now = monotonic()
    with _lock:
        recent = [stamp for stamp in _attempts.get(key, []) if now - stamp < 60]
        if recent:
            _attempts[key] = recent
        else:
            _attempts.pop(key, None)
        rate_limited = len(recent) >= 10
        if not rate_limited:
            recent.append(now)
            _attempts[key] = recent
        if len(_attempts) > 10_000:
            for attempt_key, stamps in list(_attempts.items()):
                if not any(now - stamp < 60 for stamp in stamps):
                    del _attempts[attempt_key]
        if rate_limited:
            raise ApiError(429, "RATE_LIMITED", "Too many login attempts")


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    key = f"{body.email.lower()}:{request.client.host if request.client else ''}"
    _check_login_limit(key)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password.get_secret_value(), user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    token, expires_at = create_access_token(user.id)
    response.set_cookie(
        "resolveai_session",
        token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/",
        expires=expires_at,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": {"id": str(user.id), "email": user.email},
    }


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("resolveai_session", path="/", httponly=True, samesite="strict")


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return {"id": str(user.id), "email": user.email}
