from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Document, DocumentStatus
from app.services.llm.base import ProviderTimeout
from app.worker import run_once


class DownEmbedder:
    name, model = "mock", "down"

    def embed(self, texts):
        raise ProviderTimeout("provider is down")


@pytest.fixture
def queued(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ingest_inline", False)
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={
            "file": ("runbook.md", b"Restart app-backend when nginx returns 502.", "text/markdown")
        },
    )
    assert response.json()["status"] == "queued"
    return response.json()["id"]


def document(document_id) -> Document:
    with SessionLocal() as db:
        return db.scalar(select(Document).where(Document.id == document_id))


def make_due(document_id, **changes):
    with SessionLocal() as db:
        row = db.get(Document, document_id)
        for key, value in changes.items():
            setattr(row, key, value)
        db.commit()


def test_worker_ingests_a_queued_upload(queued):
    assert run_once() is True
    assert document(queued).status == DocumentStatus.READY
    assert run_once() is False


def test_worker_retries_with_backoff_then_fails(queued):
    past = datetime.now(UTC) - timedelta(seconds=1)
    for attempt in (1, 2):
        assert run_once(DownEmbedder()) is True
        row = document(queued)
        assert (row.status, row.attempts) == (DocumentStatus.QUEUED, attempt)
        assert row.next_attempt_at > datetime.now(UTC)
        assert run_once(DownEmbedder()) is False  # not due yet
        make_due(queued, next_attempt_at=past)
    assert run_once(DownEmbedder()) is True
    row = document(queued)
    assert (row.status, row.error_code) == (DocumentStatus.FAILED, "EMBEDDING_FAILED")
    assert run_once() is False


def test_worker_recovers_a_document_left_processing_by_a_dead_worker(queued):
    make_due(queued, status=DocumentStatus.PROCESSING, locked_at=datetime.now(UTC), attempts=1)
    assert run_once() is False  # another worker may still hold it
    make_due(queued, locked_at=datetime.now(UTC) - timedelta(hours=1))
    assert run_once() is True
    assert document(queued).status == DocumentStatus.READY


def test_worker_gives_up_on_a_document_that_keeps_killing_it(queued):
    make_due(
        queued,
        status=DocumentStatus.PROCESSING,
        locked_at=datetime.now(UTC) - timedelta(hours=1),
        attempts=get_settings().ingest_max_attempts,
    )
    assert run_once() is True
    assert document(queued).status == DocumentStatus.FAILED
