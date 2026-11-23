from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.retention import purge_expired
from app.models import (
    Analysis,
    AuditEvent,
    Conversation,
    Incident,
    Message,
    RequestLog,
    User,
)
from app.services.ingestion.pipeline import ingest_document

INCIDENT = {"title": "Checkout 502", "service": "checkout", "severity": "SEV3", "symptoms": "502"}


@pytest.fixture
def external_provider(monkeypatch):
    """Settings say OpenAI; the app still holds the mock providers, so nothing leaves the test."""
    monkeypatch.setattr(get_settings(), "llm_provider", "openai")


def actions() -> list[str]:
    with SessionLocal() as db:
        return list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.created_at)))


def test_local_providers_need_no_consent(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert me["external_llm_providers"] == [] and me["llm_consent_required"] is False
    assert (
        client.post("/api/v1/chat", headers=auth_headers, json={"question": "hi"}).status_code
        == 200
    )
    refused = client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": True})
    assert refused.json()["error"]["code"] == "NO_EXTERNAL_PROVIDER"


def test_external_provider_is_blocked_until_the_user_consents(
    client, auth_headers, external_provider
):
    incident = client.post("/api/v1/incidents", headers=auth_headers, json=INCIDENT).json()
    calls = [
        ("/api/v1/chat", {"json": {"question": "What is in the runbook?"}}),
        (
            "/api/v1/documents",
            {"files": {"file": ("a.md", b"# Runbook\n" + b"restart nginx " * 30)}},
        ),
        (f"/api/v1/incidents/{incident['id']}/analyze", {"json": {}}),
        (f"/api/v1/incidents/{incident['id']}/rca", {"json": {"analysis_id": incident["id"]}}),
    ]
    for path, kwargs in calls:
        response = client.post(path, headers=auth_headers, **kwargs)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "LLM_CONSENT_REQUIRED"
        assert response.json()["error"]["details"] == {"providers": ["openai"]}
    assert client.get("/api/v1/auth/me", headers=auth_headers).json()["llm_consent_required"]

    granted = client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": True})
    assert granted.json()["llm_consent_required"] is False and granted.json()["llm_consent_at"]
    assert client.post(calls[0][0], headers=auth_headers, **calls[0][1]).status_code == 200
    assert client.post(calls[2][0], headers=auth_headers, **calls[2][1]).status_code == 200

    client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": False})
    assert client.post(calls[0][0], headers=auth_headers, **calls[0][1]).status_code == 403
    assert {"consent.llm_granted", "consent.llm_withdrawn"} <= set(actions())


def test_queued_document_is_not_sent_after_consent_is_withdrawn(
    client, auth_headers, external_provider, monkeypatch
):
    monkeypatch.setattr(get_settings(), "ingest_inline", False)
    client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": True})
    upload = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("a.md", b"# Runbook\n" + b"restart nginx " * 30)},
    )
    assert upload.status_code == 202
    client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": False})

    class Embedder:
        def embed(self, texts):
            raise AssertionError("document text was sent without consent")

    ingest_document(upload.json()["id"], embedder=Embedder(), max_attempts=3)
    document = client.get(f"/api/v1/documents/{upload.json()['id']}", headers=auth_headers).json()
    assert (document["status"], document["error_code"]) == ("failed", "CONSENT_REQUIRED")

    # Allowing it again queues the document, because the same file cannot be uploaded twice.
    client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": True})
    document = client.get(f"/api/v1/documents/{upload.json()['id']}", headers=auth_headers).json()
    assert (document["status"], document["error_code"]) == ("queued", None)


def test_eval_account_can_load_fixtures_with_an_external_provider(client, external_provider):
    runner = run_path(str(Path(__file__).resolve().parents[4] / "evals" / "run_eval.py"))
    creds = {"email": runner["EVAL_EMAIL"], "password": runner["_ensure_eval_user"]()}
    token = client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    upload = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.md", b"# Runbook\n" + b"restart nginx " * 30)},
    )
    assert upload.status_code == 202


def test_consent_does_not_carry_over_to_another_provider(
    client, auth_headers, external_provider, monkeypatch
):
    client.put("/api/v1/auth/llm-consent", headers=auth_headers, json={"granted": True})
    monkeypatch.setattr(get_settings(), "llm_provider", "anthropic")
    blocked = client.post("/api/v1/chat", headers=auth_headers, json={"question": "hi"})
    assert blocked.json()["error"]["details"] == {"providers": ["anthropic"]}


def test_mutations_are_audited_without_content(client, auth_headers):
    upload = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("secret-name.md", b"# Runbook\n" + b"restart nginx " * 30)},
    ).json()
    incident = client.post("/api/v1/incidents", headers=auth_headers, json=INCIDENT).json()
    base = f"/api/v1/incidents/{incident['id']}"
    client.patch(base, headers=auth_headers, json={"title": "Checkout 502 again"})
    analysis = client.post(f"{base}/analyze", headers=auth_headers, json={}).json()
    rca = client.post(f"{base}/rca", headers=auth_headers, json={"analysis_id": analysis["id"]})
    body = {
        **rca.json()["body_json"],
        "confirmed_cause": "Upstream down",
        "evidence_appendix": [{"ref": "obs-1", "excerpt": "Connection refused"}],
    }
    edited = client.patch(f"{base}/rca", headers=auth_headers, json={"body_json": body}).json()
    client.post(
        f"{base}/rca/confirm",
        headers=auth_headers,
        json={"expected_updated_at": edited["updated_at"], "reviewer_acknowledgement": True},
    )
    client.delete(f"/api/v1/documents/{upload['id']}", headers=auth_headers)
    client.delete(base, headers=auth_headers)

    with SessionLocal() as db:
        events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))
    assert [e.action for e in events if not e.action.startswith("auth.")] == [
        "document.uploaded",
        "incident.created",
        "incident.updated",
        "incident.analyzed",
        "rca.generated",
        "rca.edited",
        "rca.confirmed",
        "document.deleted",
        "incident.deleted",
    ]
    updated = next(e for e in events if e.action == "incident.updated")
    assert updated.resource_id == incident["id"] and updated.detail == {"fields": ["title"]}
    # Administrators read this log, and they must not see other users' content through it.
    assert "secret-name" not in str([e.detail for e in events])
    assert "Checkout" not in str([e.detail for e in events])


def test_retention_deletes_only_what_is_older_than_the_setting(client, auth_headers, monkeypatch):
    old = datetime.now(UTC) - timedelta(days=40)
    stale = client.post("/api/v1/incidents", headers=auth_headers, json=INCIDENT).json()["id"]
    fresh = client.post("/api/v1/incidents", headers=auth_headers, json=INCIDENT).json()["id"]
    # An old incident whose RCA was drafted today is still being worked on.
    worked = client.post("/api/v1/incidents", headers=auth_headers, json=INCIDENT).json()["id"]
    analysis = client.post(f"/api/v1/incidents/{worked}/analyze", headers=auth_headers, json={})
    rca = client.post(
        f"/api/v1/incidents/{worked}/rca",
        headers=auth_headers,
        json={"analysis_id": analysis.json()["id"]},
    )
    assert rca.status_code < 300
    with SessionLocal() as db:
        db.execute(update(Incident).where(Incident.id.in_([stale, worked])).values(updated_at=old))
        db.execute(update(Analysis).values(created_at=old))
        db.execute(update(RequestLog).values(created_at=old))
        db.commit()

    assert purge_expired() == {}  # every setting defaults to 0: keep forever
    assert client.get(f"/api/v1/incidents/{stale}", headers=auth_headers).status_code == 200

    monkeypatch.setattr(get_settings(), "retention_incident_days", 30)
    assert purge_expired() == {"incidents": 1}
    assert client.get(f"/api/v1/incidents/{stale}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/v1/incidents/{fresh}", headers=auth_headers).status_code == 200
    assert client.get(f"/api/v1/incidents/{worked}/rca", headers=auth_headers).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(RequestLog.id).limit(1)) is not None  # logs: still unlimited
        purge = db.scalar(select(AuditEvent).where(AuditEvent.action == "retention.purged"))
        assert purge.actor_id is None and purge.detail == {"incidents": 1}
        assert db.scalar(select(User.id).limit(1)) is not None


def test_retention_keeps_a_conversation_that_is_still_in_use(client, auth_headers, monkeypatch):
    def ask(conversation_id=None):
        body = {"question": "What is in the runbook?", "conversation_id": conversation_id}
        return client.post("/api/v1/chat", headers=auth_headers, json=body).json()

    continued, abandoned = ask()["conversation_id"], ask()["conversation_id"]
    old = datetime.now(UTC) - timedelta(days=40)
    with SessionLocal() as db:
        db.execute(update(Conversation).values(created_at=old))
        db.execute(update(Message).values(created_at=old))
        db.commit()
    ask(continued)

    monkeypatch.setattr(get_settings(), "retention_conversation_days", 30)
    assert purge_expired() == {"conversations": 1}
    path = "/api/v1/conversations/{}/messages"
    kept = client.get(path.format(continued), headers=auth_headers).json()["items"]
    assert len(kept) == 4
    assert client.get(path.format(abandoned), headers=auth_headers).status_code == 404
