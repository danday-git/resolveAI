from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AppSetting, AuditEvent


def member_headers(client):
    creds = {"email": "member@example.com", "password": "member-password-123"}
    client.post("/api/v1/auth/register", json=creds)
    token = client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_only_admins_can_read_or_change_ai_settings(client, auth_headers):
    headers = member_headers(client)
    assert client.get("/api/v1/admin/ai", headers=headers).status_code == 403
    body = {"llm_provider": "mock", "llm_model": "m"}
    assert client.put("/api/v1/admin/ai", headers=headers, json=body).status_code == 403
    assert client.post("/api/v1/admin/ai/test", headers=headers).status_code == 403


def test_api_key_is_stored_encrypted_and_never_returned(client, auth_headers):
    secret = "sk-test-abcdefghijklmnop1234"
    saved = client.put(
        "/api/v1/admin/ai",
        headers=auth_headers,
        json={"llm_provider": "openai", "llm_model": "gpt-4o-mini", "openai_api_key": secret},
    )
    assert saved.status_code == 200, saved.text
    view = saved.json()
    assert view["source"] == "admin" and view["llm_provider"] == "openai"
    assert view["openai_api_key"] == {"set": True, "last4": "1234", "source": "admin"}
    assert secret not in saved.text
    assert secret not in client.get("/api/v1/admin/ai", headers=auth_headers).text
    with SessionLocal() as db:
        stored = db.get(AppSetting, 1).openai_api_key
        audit = db.scalars(select(AuditEvent).where(AuditEvent.action.like("admin.ai%"))).one()
    assert stored and secret not in stored
    assert audit.detail["keys_changed"] == ["openai_api_key"] and secret not in str(audit.detail)


def test_switching_to_an_external_provider_requires_consent_again(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert me["llm_consent_required"] is False
    client.put(
        "/api/v1/admin/ai",
        headers=auth_headers,
        json={
            "llm_provider": "anthropic",
            "llm_model": "claude-haiku-4-5",
            "anthropic_api_key": "k",
        },
    )
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert me["external_llm_providers"] == ["anthropic"] and me["llm_consent_required"] is True
    blocked = client.post("/api/v1/chat", headers=auth_headers, json={"question": "hello there"})
    assert blocked.status_code == 403


def test_external_provider_without_a_key_is_refused(client, auth_headers):
    refused = client.put(
        "/api/v1/admin/ai",
        headers=auth_headers,
        json={"llm_provider": "openai", "llm_model": "gpt-4o-mini", "openai_api_key": ""},
    )
    assert refused.status_code == 422
    assert client.get("/api/v1/admin/ai", headers=auth_headers).json()["source"] == "env"


def test_chat_uses_the_model_the_admin_chose(client, auth_headers):
    client.put(
        "/api/v1/admin/ai",
        headers=auth_headers,
        json={"llm_provider": "mock", "llm_model": "mock-picked-by-admin"},
    )
    tested = client.post("/api/v1/admin/ai/test", headers=auth_headers).json()
    assert tested["ok"] is True and tested["model"] == "mock-picked-by-admin"
