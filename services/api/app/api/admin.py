from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import create_reset_token
from app.api.deps import require_admin
from app.core.audit import audit
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import AuditEvent, User

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
