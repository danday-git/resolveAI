from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.requests import Request

from app.core.errors import ApiError
from app.core.limits import rate_limit


def request() -> Request:
    return Request({"type": "http", "headers": []})


def test_rate_limit_is_shared_and_exact_under_concurrency(clean_database):
    def hit(_):
        try:
            rate_limit("shared-key", request(), 5)
            return True
        except ApiError as error:
            assert error.status == 429
            return False

    # Threads stand in for API instances: the count lives in the database, not in a process.
    with ThreadPoolExecutor(8) as pool:
        allowed = sum(pool.map(hit, range(20)))
    assert allowed == 5
    rate_limit("another-key", request(), 5)


def test_rate_limited_request_reports_when_to_retry(clean_database):
    blocked = request()
    rate_limit("k", blocked, 1)
    with pytest.raises(ApiError):
        rate_limit("k", blocked, 1)
    assert 1 <= blocked.state.retry_after <= 60


def test_login_is_rate_limited_per_email(client):
    body = {"email": "demo@resolveai.local", "password": "wrong-password"}
    codes = [client.post("/api/v1/auth/login", json=body).status_code for _ in range(11)]
    assert codes == [401] * 10 + [429]


def incident(client, headers, title, service="checkout-web", severity="SEV3"):
    body = {"title": title, "service": service, "severity": severity, "symptoms": "x"}
    assert client.post("/api/v1/incidents", headers=headers, json=body).status_code == 201


def test_incident_search_filter_and_paging_run_on_the_server(client, auth_headers):
    for index in range(5):
        incident(client, auth_headers, f"Checkout 502 #{index}")
    incident(client, auth_headers, "Disk full", service="db-primary", severity="SEV1")
    incident(client, auth_headers, "100%_literal")

    def listing(**params):
        return client.get("/api/v1/incidents", headers=auth_headers, params=params).json()

    page = listing(q="checkout 502", limit=2, offset=4)
    assert (page["total"], len(page["items"])) == (5, 1)
    assert listing(q="DB-PRIMARY")["items"][0]["title"] == "Disk full"
    assert listing(severity="SEV1")["total"] == 1
    assert listing(severity="SEV1", q="checkout")["total"] == 0
    # Wildcards in the search are text, not patterns.
    assert listing(q="%")["total"] == 1
    assert listing(q="_")["total"] == 1
    seen = [i["id"] for offset in (0, 3, 6) for i in listing(limit=3, offset=offset)["items"]]
    assert len(seen) == len(set(seen)) == 7


def test_document_search_and_status_counts(client, auth_headers):
    for name, text in (
        (
            "nginx-runbook.md",
            "When nginx returns 502, check that the upstream service is listening.",
        ),
        ("postgres.md", "Vacuum the orders table weekly and watch for long-running transactions."),
    ):
        files = {"file": (name, text.encode(), "text/markdown")}
        assert (
            client.post("/api/v1/documents", headers=auth_headers, files=files).status_code == 202
        )

    def listing(params):
        return client.get("/api/v1/documents", headers=auth_headers, params=params).json()

    found = listing({"q": "NGINX"})
    assert [d["filename"] for d in found["items"]] == ["nginx-runbook.md"]
    assert found["total"] == 1
    # Counts describe the whole knowledge base, not the filtered page.
    assert found["status_counts"] == {"ready": 2}
    assert listing({"status": ["queued", "processing"]})["total"] == 0
    assert listing({"status": "failed", "q": "nginx"})["total"] == 0
    assert listing({"status": "nonsense"}).get("items") is None
