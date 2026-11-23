from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import create_reset_token
from app.api.deps import require_admin
from app.core.ai_settings import API_KEY_FIELDS, apply, effective_settings, encrypt
from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import AppSetting, AuditEvent, User
from app.services.llm import factory
from app.services.llm.base import ChatMessage, LLMError

router = APIRouter(prefix="/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None


def _user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "sso": user.oidc_subject is not None,
        "created_at": user.created_at,
    }


@router.get("/users")
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    users = db.scalars(select(User).order_by(User.created_at).limit(limit).offset(offset))
    return {
        "items": [_user(user) for user in users],
        "total": db.scalar(select(func.count()).select_from(User)),
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: UUID,
    body: UserUpdate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    # Lock every admin row so two concurrent demotions cannot both pass the last-admin check.
    admins = db.scalars(
        select(User).where(User.role == "admin", User.is_active).with_for_update()
    ).all()
    target = db.get(User, user_id)
    if target is None:
        raise ApiError(404, "NOT_FOUND", "Resource not found")
    role = body.role or target.role
    active = target.is_active if body.is_active is None else body.is_active
    if target in admins and len(admins) == 1 and (role != "admin" or not active):
        raise ApiError(409, "LAST_ADMIN", "The last active administrator cannot be removed")
    changes = {
        key: value
        for key, value in (("role", role), ("is_active", active))
        if getattr(target, key) != value
    }
    target.role, target.is_active = role, active
    if changes:
        audit(db, request, admin, "admin.user_updated", "user", target.id, **changes)
    db.commit()
    return _user(target)


@router.post("/users/{user_id}/reset-link")
def issue_reset_link(
    user_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    """A one-time link the administrator hands over; it is returned once and never stored."""
    target = db.get(User, user_id)
    if target is None:
        raise ApiError(404, "NOT_FOUND", "Resource not found")
    url = create_reset_token(db, target)
    audit(db, request, admin, "admin.reset_link_issued", "user", target.id)
    db.commit()
    return {"url": url, "expires_in_minutes": 30}


@router.get("/audit")
def list_audit(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    events = db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    )
    return {
        "items": [
            {
                "id": str(event.id),
                "actor_email": event.actor_email,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "detail": event.detail,
                "request_id": event.request_id,
                "created_at": event.created_at,
            }
            for event in events
        ],
        "total": db.scalar(select(func.count()).select_from(AuditEvent)),
    }


class AiUpdate(BaseModel):
    llm_provider: Literal["openai", "anthropic", "ollama", "mock"]
    llm_model: str = Field(min_length=1, max_length=100)
    # None keeps the stored key, "" removes it.
    openai_api_key: str | None = Field(default=None, max_length=500)
    anthropic_api_key: str | None = Field(default=None, max_length=500)


def _ai_view(db: Session) -> dict:
    env = get_settings()
    row = db.get(AppSetting, 1)
    current = apply(row, env)

    def key(field: str) -> dict:
        value = getattr(current, field)
        source = "admin" if row is not None and getattr(row, field) else "env" if value else None
        return {
            "set": value is not None,
            "last4": value.get_secret_value()[-4:] if value else None,
            "source": source,
        }

    return {
        "llm_provider": current.llm_provider,
        "llm_model": current.llm_model,
        "source": "admin" if row is not None else "env",
        "updated_by": row.updated_by if row is not None else None,
        "updated_at": row.updated_at if row is not None else None,
        **{field: key(field) for field in API_KEY_FIELDS},
        "embedding": {
            "provider": env.embedding_provider,
            "model": env.embedding_model,
            "dim": env.embedding_dim,
        },
        "external_llm_providers": current.external_llm_providers,
    }


@router.get("/ai")
def get_ai_settings(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    return _ai_view(db)


@router.put("/ai")
def update_ai_settings(
    body: AiUpdate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    row = db.get(AppSetting, 1, with_for_update=True)
    if row is None:
        row = AppSetting(id=1)
        db.add(row)
    row.llm_provider, row.llm_model = body.llm_provider, body.llm_model.strip()
    changed_keys = []
    for field in API_KEY_FIELDS:
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, encrypt(value.strip()) if value.strip() else None)
            changed_keys.append(field)
    row.updated_by = admin.email
    try:
        factory.get_chat_provider(apply(row, get_settings()))
    except LLMError as exc:
        db.rollback()
        raise ApiError(422, "PROVIDER_NOT_CONFIGURED", str(exc)) from None
    audit(
        db,
        request,
        admin,
        "admin.ai_settings_updated",
        "app_settings",
        "1",
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        keys_changed=changed_keys,
    )
    db.commit()
    return _ai_view(db)


@router.post("/ai/test")
def test_ai_settings(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    """Sends one tiny prompt to the chat provider in use; no user data is involved."""
    settings = effective_settings(db)
    try:
        result = factory.get_chat_provider(settings).chat(
            [
                ChatMessage("system", 'Reply with the JSON object {"ok": true}.'),
                ChatMessage("user", "ping"),
            ],
            max_tokens=20,
        )
    except LLMError as exc:
        return {"ok": False, "error": exc.category, "provider": settings.llm_provider}
    return {
        "ok": True,
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
    }
