from io import BytesIO
from pathlib import Path
from uuid import UUID

import jwt
from pypdf import PdfWriter

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Chunk, Document, User
from app.services.llm.base import ChatResult, ProviderTimeout

RUNBOOK = (
    "Nginx upstream troubleshooting. When connect() failed (111: Connection refused), "
    "the upstream service is not listening. Check ss -ltnp grep 3000 and "
    "systemctl status app-backend before drawing a conclusion."
)


def upload(client, headers, contents: str = RUNBOOK, filename: str = "runbook.md"):
    return client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": (filename, contents.encode(), "text/markdown")},
    )


def test_health_auth_and_expired_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/api/v1/documents").status_code == 401
    assert (
        client.get("/api/v1/documents", headers={"Authorization": "Bearer bad"}).status_code == 401
    )
    expired = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000001", "iat": 1, "exp": 2},
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    response = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_upload_ingests_citations_duplicates_and_delete(client, auth_headers):
    response = upload(client, auth_headers)
    assert response.status_code == 202
    document = client.get(f"/api/v1/documents/{response.json()['id']}", headers=auth_headers).json()
    assert document["status"] == "ready"
    chunks = client.get(f"/api/v1/documents/{document['id']}/chunks", headers=auth_headers).json()
    assert chunks["total"] >= 1
    chat = client.post(
        "/api/v1/chat",
        headers=auth_headers,
        json={"question": "What does connection refused mean for the upstream?"},
    )
    assert chat.status_code == 200
    result = chat.json()
    assert not result["abstained"]
    citation = result["citations"][0]
    assert citation["document_id"] == document["id"]
    source = client.get(f"/api/v1/chunks/{citation['chunk_id']}", headers=auth_headers).json()
    assert citation["quote"] in source["text"]
    assert upload(client, auth_headers).json()["error"]["code"] == "DUPLICATE_DOCUMENT"
    with SessionLocal() as db:
        stored_path = db.get(Document, UUID(document["id"])).storage_path
    assert (
        client.delete(f"/api/v1/documents/{document['id']}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/chunks/{citation['chunk_id']}", headers=auth_headers).status_code
        == 404
    )
    assert not Path(stored_path).exists()
    with SessionLocal() as db:
        assert db.query(Chunk).filter(Chunk.document_id == UUID(document["id"])).count() == 0


def test_upload_rejects_type_size_and_no_text_pdf(client, auth_headers):
    unsupported = client.post(
        "/api/v1/documents", headers=auth_headers, files={"file": ("runbook.exe", b"x")}
    )
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    settings = get_settings()
    old_max = settings.max_upload_mb
    settings.max_upload_mb = 1
    oversized = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("big.txt", b"x" * (1024 * 1024 + 1))},
    )
    settings.max_upload_mb = old_max
    assert oversized.status_code == 413

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    failed = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("blank.pdf", output.getvalue(), "application/pdf")},
    )
    assert failed.status_code == 202
    document = client.get(f"/api/v1/documents/{failed.json()['id']}", headers=auth_headers).json()
    assert document["status"] == "failed"
    assert document["error_code"] == "NO_EXTRACTABLE_TEXT"


def test_upload_sniffing_and_filename_traversal(client, auth_headers):
    invalid = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("bad.pdf", b"not a PDF", "application/pdf")},
    )
    assert invalid.status_code == 400
    response = upload(client, auth_headers, filename="../../etc/passwd.md")
    assert response.status_code == 202
    assert response.json()["filename"] == "passwd.md"


def test_no_retrieval_abstains_without_chat_call(client, auth_headers):
    class NoCall:
        name = "stub"
        model = "stub"

        def chat(self, *args, **kwargs):
            raise AssertionError("chat provider should not be called")

    client.app.state.chat_provider = NoCall()
    response = client.post(
        "/api/v1/chat", headers=auth_headers, json={"question": "unrelated astronomy"}
    )
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["usage"]["input_tokens"] == 0


def test_chat_timeout_and_fabricated_citation_abstain(client, auth_headers):
    upload_response = upload(client, auth_headers)
    document = client.get(
        f"/api/v1/documents/{upload_response.json()['id']}", headers=auth_headers
    ).json()
    assert document["status"] == "ready"

    class Timeout:
        name = "stub"
        model = "stub"

        def chat(self, *args, **kwargs):
            raise ProviderTimeout("timeout")

    client.app.state.chat_provider = Timeout()
    timeout = client.post(
        "/api/v1/chat",
        headers=auth_headers,
        json={"question": "What does connection refused mean for the upstream?"},
    )
    assert timeout.status_code == 504
    assert timeout.json()["error"]["code"] == "LLM_TIMEOUT"

    class Fabricated:
        name = "stub"
        model = "stub"

        def chat(self, *args, **kwargs):
            return ChatResult(
                '{"answer":"Unsupported assertion","abstain":false,'
                '"citations":[{"chunk_id":"fake","quote":"fabricated evidence"}]}',
                5,
                5,
                1,
                0,
                "stub",
                "stub",
            )

    client.app.state.chat_provider = Fabricated()
    response = client.post(
        "/api/v1/chat",
        headers=auth_headers,
        json={"question": "What does connection refused mean for the upstream?"},
    )
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["retrieval"]["citations_rejected"] == 1


def test_cross_user_document_and_chunk_access(client, auth_headers):
    document = upload(client, auth_headers).json()
    chunk_id = client.get(
        f"/api/v1/documents/{document['id']}/chunks", headers=auth_headers
    ).json()["items"][0]["id"]
    with SessionLocal() as db:
        db.add(User(email="other@resolveai.local", password_hash=hash_password("other-password")))
        db.commit()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "other@resolveai.local", "password": "other-password"},
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/documents/{document['id']}", headers=other).status_code == 403
    assert client.get(f"/api/v1/chunks/{chunk_id}", headers=other).status_code == 403


def test_cross_user_incident_and_conversation_access(client, auth_headers):
    chat = client.post(
        "/api/v1/chat", headers=auth_headers, json={"question": "no matching evidence"}
    ).json()
    incident = client.post(
        "/api/v1/incidents",
        headers=auth_headers,
        json={
            "title": "Access scope",
            "severity": "SEV3",
            "service": "api",
            "symptoms": "Test owner scoping",
        },
    ).json()
    with SessionLocal() as db:
        db.add(User(email="second@resolveai.local", password_hash=hash_password("second-password")))
        db.commit()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "second@resolveai.local", "password": "second-password"},
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert (
        client.get(
            f"/api/v1/conversations/{chat['conversation_id']}/messages", headers=other
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/incidents/{incident['id']}", headers=other).status_code == 403
