import sentry_sdk
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.observability import init_sentry


def test_metrics_endpoint_is_off_without_a_token_and_needs_it_when_set(client, monkeypatch):
    assert client.get("/metrics").status_code == 404
    monkeypatch.setattr(get_settings(), "metrics_token", SecretStr("scrape-token"))
    assert client.get("/metrics").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.get("/metrics", headers=wrong).status_code == 401


def test_metrics_report_requests_queue_and_llm_usage(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "metrics_token", SecretStr("scrape-token"))
    files = {"file": ("runbook.md", b"Restart nginx when the upstream stops answering.")}
    assert client.post("/api/v1/documents", headers=auth_headers, files=files).status_code == 202
    client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    client.get("/wp-login.php?x=1")
    client.get("/another-scanner-path")

    body = client.get("/metrics", headers={"Authorization": "Bearer scrape-token"}).text
    lines = body.splitlines()

    def value(prefix):
        [line] = [line for line in lines if line.startswith(prefix)]
        return float(line.rsplit(" ", 1)[1])

    # The route template is the label, never the raw path with its ids.
    route = 'method="GET",route="/api/v1/incidents/{incident_id}",status="404"'
    assert value(f"resolveai_http_requests_total{{{route}}}") >= 1
    assert "00000000-0000" not in body and "wp-login" not in body
    assert value('resolveai_http_requests_total{method="GET",route="unmatched",status="404"}') >= 2
    assert value('resolveai_documents{status="ready"}') == 1
    assert value('resolveai_documents{status="queued"}') == 0
    assert value("resolveai_ingestion_oldest_queued_seconds") == 0
    llm = (
        'resolveai_llm_requests_last_hour{provider="mock",model="mock-embedding",outcome="success"}'
    )
    assert value(llm[: llm.index("model=")]) >= 1 or value(llm) >= 1


def test_sentry_reports_carry_no_secrets_locals_or_bodies(monkeypatch):
    sent = []
    monkeypatch.setattr(get_settings(), "sentry_dsn", SecretStr("http://key@127.0.0.1:9/1"))
    init_sentry()
    try:
        client = sentry_sdk.get_client()
        monkeypatch.setattr(client.transport, "capture_envelope", sent.append)
        # Built at run time: Sentry quotes the source line of each frame, so a literal written
        # here would show up as code, not as the leaked runtime value this test is about.
        secret = "hunter2" + "secret"

        def fail():
            prompt = "raw prompt " + secret  # noqa: F841
            raise RuntimeError(f"upstream refused password={secret} for ops@" + "example.com")

        try:
            fail()
        except RuntimeError:
            sentry_sdk.capture_exception()
        client.flush()
        [envelope] = sent
        report = str(envelope.items[0].payload.json)
        assert "RuntimeError" in report
        assert secret not in report and "ops@" + "example.com" not in report
        assert "raw prompt " + secret not in report
        frames = envelope.items[0].payload.json["exception"]["values"][0]["stacktrace"]["frames"]
        assert all("vars" not in frame for frame in frames)
    finally:
        sentry_sdk.init()  # back to disabled for the other tests


def test_unhandled_error_is_reported_once_and_hidden_from_the_client(client, monkeypatch):
    seen = []
    monkeypatch.setattr("app.core.errors.sentry_sdk.capture_exception", seen.append)

    def boom():
        raise RuntimeError("database exploded")

    monkeypatch.setattr("app.main.render_metrics", lambda db: boom())
    monkeypatch.setattr(get_settings(), "metrics_token", SecretStr("t"))
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as quiet:
        response = quiet.get("/metrics", headers={"Authorization": "Bearer t"})
    assert response.status_code == 500
    assert "exploded" not in response.text
    assert [type(error) for error in seen] == [RuntimeError]
