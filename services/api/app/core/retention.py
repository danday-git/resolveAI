from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import AuditEvent, Conversation, Incident, LLMRequest, RequestLog


def purge_expired() -> dict[str, int]:
    """Deletes records older than their RETENTION_*_DAYS. Documents are never purged: the
    knowledge base is reference material its owner removes."""
    settings = get_settings()
    now = datetime.now(UTC)
    # Incidents age from their last change, so one still being worked on is not deleted.
    # Analyses, RCA reports and messages go with their parent through ON DELETE CASCADE.
    rules = [
        ("incidents", Incident, Incident.updated_at, settings.retention_incident_days),
        (
            "conversations",
            Conversation,
            Conversation.created_at,
            settings.retention_conversation_days,
        ),
        ("llm_requests", LLMRequest, LLMRequest.created_at, settings.retention_log_days),
        ("request_logs", RequestLog, RequestLog.created_at, settings.retention_log_days),
        ("audit_events", AuditEvent, AuditEvent.created_at, settings.retention_audit_days),
    ]
    deleted: dict[str, int] = {}
    with SessionLocal() as db:
        for name, model, column, days in rules:
            if days > 0:
                count = (
                    db.query(model)
                    .filter(column < now - timedelta(days=days))
                    .delete(synchronize_session=False)
                )
                if count:
                    deleted[name] = count
        if deleted:
            db.add(AuditEvent(action="retention.purged", detail=deleted))
        db.commit()
    return deleted
