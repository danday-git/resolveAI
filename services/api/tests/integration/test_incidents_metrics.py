import json
from pathlib import Path
from uuid import UUID

from alembic.config import Config

from alembic import command
from app.core.database import SessionLocal
from app.models import Incident


def test_incident_redaction_and_owner_scoping(client, auth_headers, caplog):
    root = Path(__file__).resolve().parents[4]
    fixture = json.loads((root / "evals/fixtures/incidents/nginx-502.json").read_text())
    secret = "sup3rS3cretValue"
    assert secret in fixture["log_excerpt"]
    response = client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json=fixture,
    )
    assert response.status_code == 201
    incident = response.json()
    assert secret not in response.text
    assert secret not in incident["sanitized_log"]
    assert secret not in caplog.text
    with SessionLocal() as db:
        row = db.get(Incident, UUID(incident["id"]))
        assert row is not None and secret not in (row.sanitized_log or "")


def test_analyze_observations_rca_reset_metrics_and_confirm(client, auth_headers):
    root = Path(__file__).resolve().parents[4]
    fixture = json.loads((root / "evals/fixtures/incidents/nginx-502.json").read_text())
    incident = client.post("/api/v1/incidents", headers=auth_headers, json=fixture).json()
    analysis = client.post(
        f"/api/v1/incidents/{incident['id']}/analyze", headers=auth_headers, json={}
    ).json()
    assert any("Connection refused" in item["excerpt"] for item in analysis["observations"])
    assert all(item["status"] == "suspected" for item in analysis["hypotheses"])
    assert (
        client.post(
            f"/api/v1/incidents/{incident['id']}/rca/confirm",
            headers=auth_headers,
            json={"reviewer_acknowledgement": False},
        ).status_code
        == 422
    )
    draft = client.post(
        f"/api/v1/incidents/{incident['id']}/rca",
        headers=auth_headers,
        json={"analysis_id": analysis["id"]},
    ).json()
    assert draft["cause_status"] == "UNCONFIRMED"
    invalid = client.post(
        f"/api/v1/incidents/{incident['id']}/rca/confirm",
        headers=auth_headers,
        json={"reviewer_acknowledgement": True},
    )
    assert invalid.status_code == 422
    body = {
        **draft["body_json"],
        "confirmed_cause": "Verified upstream listener failure",
        "evidence_appendix": [{"ref": "obs-1", "excerpt": "Connection refused"}],
    }
    patched = client.patch(
        f"/api/v1/incidents/{incident['id']}/rca",
        headers=auth_headers,
        json={"body_json": body},
    )
    assert patched.status_code == 200
    confirmed = client.post(
        f"/api/v1/incidents/{incident['id']}/rca/confirm",
        headers=auth_headers,
        json={"reviewer_acknowledgement": True},
    )
    assert confirmed.json()["cause_status"] == "CONFIRMED"
    edited = client.patch(
        f"/api/v1/incidents/{incident['id']}/rca",
        headers=auth_headers,
        json={"body_json": {**body, "incident_summary": "Edited"}},
    )
    assert edited.json()["cause_status"] == "UNCONFIRMED"
    assert edited.json()["reviewer_id"] is None
    summary = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    assert summary["llm"]["calls"] >= 2
    assert summary["ingestion"]["documents_total"] >= 0
    assert "estimated_cost_usd" in summary["llm"]
    assert client.get("/api/v1/metrics/requests", headers=auth_headers).status_code == 200


def test_authenticated_request_metrics_are_attributed_without_bodies(client, auth_headers):
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/documents", headers=auth_headers).status_code == 200

    summary = client.get("/api/v1/metrics/summary", headers=auth_headers).json()
    assert summary["requests"]["total"] > 0

    requests = client.get("/api/v1/metrics/requests", headers=auth_headers).json()["items"]
    request_rows = [item for item in requests if item["type"] == "request"]
    assert request_rows
    assert any(item["route"] == "/api/v1/auth/me" for item in request_rows)
    assert all(not {"prompt", "body", "question"} & item.keys() for item in request_rows)


def test_schema_dimension_validation_and_rate_limit(client, auth_headers):
    from app.core.config import get_settings
    from app.core.database import engine
    from app.core.limits import reset_limits
    from app.main import validate_embedding_schema

    settings = get_settings()
    try:
        validate_embedding_schema(engine, settings.model_copy(update={"embedding_dim": 512}))
    except RuntimeError as error:
        assert "Embedding dimension mismatch" in str(error)
    else:
        raise AssertionError("dimension mismatch should fail startup validation")
    original = settings.rate_limit_per_minute
    settings.rate_limit_per_minute = 1
    reset_limits()
    first = client.post("/api/v1/chat", headers=auth_headers, json={"question": "q"})
    second = client.post("/api/v1/chat", headers=auth_headers, json={"question": "q"})
    settings.rate_limit_per_minute = original
    assert first.status_code == 200
    assert second.status_code == 429


def test_migration_downgrade_and_upgrade():
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
