from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import exists

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import (
    Analysis,
    AuditEvent,
    Conversation,
    Incident,
    LLMRequest,
    RCAReport,
    RequestLog,
)


def purge_expired() -> dict[str, int]:
    """Deletes records older than their RETENTION_*_DAYS. Documents are never purged: the
    knowledge base is reference material its owner removes."""
    settings = get_settings()
    now = datetime.now(UTC)
    # Analyses, RCA reports and messages go with their parent through ON DELETE CASCADE,
    # so a parent is kept while anything under it is newer than the cutoff.
    rules: list[tuple[str, Any, Any, int, list[Any]]] = [
        (
            "incidents",
            Incident,
            Incident.updated_at,
            settings.retention_incident_days,
            [
                (Analysis.incident_id == Incident.id, Analysis.created_at),
                (RCAReport.incident_id == Incident.id, RCAReport.updated_at),
            ],
        ),
        (
            "conversations",
            Conversation,
            Conversation.created_at,
            settings.retention_conversation_days,
            [],
        ),
        ("llm_requests", LLMRequest, LLMRequest.created_at, settings.retention_log_days, []),
        ("request_logs", RequestLog, RequestLog.created_at, settings.retention_log_days, []),
        ("audit_events", AuditEvent, AuditEvent.created_at, settings.retention_audit_days, []),
    ]
    deleted: dict[str, int] = {}
    with SessionLocal() as db:
        for name, model, column, days, children in rules:
            if days > 0:
                cutoff = now - timedelta(days=days)
                recent = [exists().where(link, changed >= cutoff) for link, changed in children]
                count = (
                    db.query(model)
                    .filter(column < cutoff, *(~child for child in recent))
                    .delete(synchronize_session=False)
                )
                if count:
                    deleted[name] = count
        if deleted:
            db.add(AuditEvent(action="retention.purged", detail=deleted))
        db.commit()
    return deleted
