import json
from pathlib import Path


def test_end_to_end_upload_chat_incident_rca_export(client, auth_headers):
    root = Path(__file__).resolve().parents[4]
    sop = (root / "evals/fixtures/docs/nginx-502-runbook.md").read_bytes()
    upload = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("nginx-502-runbook.md", sop, "text/markdown")},
    )
    assert upload.status_code == 202
    doc = client.get(f"/api/v1/documents/{upload.json()['id']}", headers=auth_headers).json()
    assert doc["status"] == "ready"
    chat = client.post(
        "/api/v1/chat",
        headers=auth_headers,
        json={"question": "What does connect() failed (111: Connection refused) mean?"},
    )
    assert chat.status_code == 200
    answer = chat.json()
    assert answer["citations"]
    source = client.get(
        f"/api/v1/chunks/{answer['citations'][0]['chunk_id']}", headers=auth_headers
    ).json()
    assert answer["citations"][0]["quote"] in source["text"]

    fixture = json.loads((root / "evals/fixtures/incidents/nginx-502.json").read_text())
    incident = client.post("/api/v1/incidents", headers=auth_headers, json=fixture)
    assert incident.status_code == 201
    incident_id = incident.json()["id"]
    analysis = client.post(
        f"/api/v1/incidents/{incident_id}/analyze", headers=auth_headers, json={}
    )
    assert analysis.status_code == 200
    assert any(
        "refused" in observation["excerpt"].lower()
        for observation in analysis.json()["observations"]
    )
    evidence = analysis.json()["evidence"]
    assert evidence
    assert all(item["filename"] == "nginx-502-runbook.md" for item in evidence)
    assert all(isinstance(item["score"], (int, float)) for item in evidence)
    report = client.post(
        f"/api/v1/incidents/{incident_id}/rca",
        headers=auth_headers,
        json={"analysis_id": analysis.json()["id"]},
    )
    assert report.status_code == 201
    assert report.json()["cause_status"] == "UNCONFIRMED"
    patch = {
        "body_json": {
            **report.json()["body_json"],
            "confirmed_cause": (
                "The upstream process may not be listening, pending human verification."
            ),
            "evidence_appendix": [
                {"ref": analysis.json()["observations"][0]["id"], "excerpt": "Connection refused"}
            ],
        }
    }
    updated = client.patch(f"/api/v1/incidents/{incident_id}/rca", headers=auth_headers, json=patch)
    assert updated.status_code == 200
    confirm = client.post(
        f"/api/v1/incidents/{incident_id}/rca/confirm",
        headers=auth_headers,
        json={
            "reviewer_acknowledgement": True,
            "expected_updated_at": updated.json()["updated_at"],
        },
    )
    assert confirm.status_code == 200
    assert confirm.json()["cause_status"] == "CONFIRMED"
    exported = client.get(f"/api/v1/incidents/{incident_id}/rca/export", headers=auth_headers)
    assert exported.status_code == 200
    assert "Cause status:** CONFIRMED" in exported.text
    assert "AI-assisted draft" not in exported.text
