"""Ingestion worker: `python -m app.worker`. The documents table is the queue."""

import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.limits import purge_rate_limits
from app.core.observability import init_sentry
from app.models import Document, DocumentStatus
from app.services.ingestion.pipeline import _fail, ingest_document
from app.services.llm.base import EmbeddingProvider

logger = logging.getLogger(__name__)


def run_once(embedder: EmbeddingProvider | None = None) -> bool:
    """Claims and ingests one due document. Returns False when nothing is due."""
    settings = get_settings()
    now = datetime.now(UTC)
    # shortcut: no heartbeat, so one ingestion longer than INGEST_LOCK_MINUTES is taken over by
    # a second worker; raise the setting or add a heartbeat if documents get that slow.
    stale = now - timedelta(minutes=settings.ingest_lock_minutes)
    with SessionLocal() as db:
        document = db.scalar(
            select(Document)
            .where(
                or_(
                    and_(
                        Document.status == DocumentStatus.QUEUED,
                        or_(Document.next_attempt_at.is_(None), Document.next_attempt_at <= now),
                    ),
                    # A worker that died mid-document leaves it processing with an old lock.
                    and_(
                        Document.status == DocumentStatus.PROCESSING,
                        or_(Document.locked_at.is_(None), Document.locked_at < stale),
                    ),
                )
            )
            .order_by(Document.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if document is None:
            return False
        if document.attempts >= settings.ingest_max_attempts:
            _fail(db, document, "INGESTION_FAILED")
            return True
        document.status = DocumentStatus.PROCESSING
        document.locked_at = now
        db.commit()
        document_id = document.id
    ingest_document(document_id, embedder, settings.ingest_max_attempts)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_sentry()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("ingestion worker started")
    housekeeping_due = 0.0
    while running:
        try:
            if time.monotonic() >= housekeeping_due:
                housekeeping_due = time.monotonic() + 60
                purge_rate_limits()
            idle = not run_once()
        except Exception:
            # One bad document or a database restart must not stop the queue.
            logger.exception("ingestion worker iteration failed")
            idle = True
        if idle:
            time.sleep(1)


if __name__ == "__main__":
    main()
