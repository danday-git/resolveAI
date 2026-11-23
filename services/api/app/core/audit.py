from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def audit(
    db: Session,
    request: Request,
    actor: User | None,
    action: str,
    resource_type: str | None = None,
    resource_id: object = None,
    **detail: Any,
) -> None:
    """Records who did what. The caller commits, so the event lands with the change it describes."""
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            detail=detail,
            request_id=getattr(request.state, "request_id", None),
        )
    )
