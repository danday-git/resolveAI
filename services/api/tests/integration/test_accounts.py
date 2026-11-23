import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.api import auth
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import AuditEvent, User

PASSWORD = "a-long-enough-password"


def register(client, email, password=PASSWORD):
    client.cookies.clear()
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_register_makes_members(client, auth_headers):
    response = register(client, "New.Person@Example.com")
    assert response.status_code == 201
    user = response.json()["user"]
    assert (user["email"], user["role"]) == ("new.person@example.com", "member")
    assert register(client, "new.person@example.com").status_code == 409
    assert register(client, "short@example.com", "too-short").status_code == 422
    # A member cannot reach the admin API or another account's data.
    assert client.get("/api/v1/admin/users", headers=bearer(response)).status_code == 403
    assert client.get("/api/v1/admin/users", headers=auth_headers).json()["total"] == 2


def test_first_account_on_an_empty_install_is_not_admin(clean_database, client):
    # Between `up` and the seed, a public install would hand the first visitor the admin role.
    with SessionLocal() as db:
        db.query(User).delete()
        db.commit()
    assert register(client, "first@example.com").json()["user"]["role"] == "member"


def test_registration_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_registration", False)
    assert register(client, "x@example.com").status_code == 403
    config = client.get("/api/v1/auth/config").json()
    assert (config["registration"], config["oidc"]) == (False, False)


def test_admin_manages_roles_but_never_removes_the_last_admin(client, auth_headers):
    member = register(client, "member@example.com")
    member_id = member.json()["user"]["id"]
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()["id"]
    for change in ({"role": "member"}, {"is_active": False}):
        response = client.patch(f"/api/v1/admin/users/{me}", headers=auth_headers, json=change)
        assert response.status_code == 409
    promoted = client.patch(
        f"/api/v1/admin/users/{member_id}", headers=auth_headers, json={"role": "admin"}
    )
    assert promoted.json()["role"] == "admin"
    # With two admins the first may now step down.
    assert (
        client.patch(
            f"/api/v1/admin/users/{me}", headers=auth_headers, json={"role": "member"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/admin/users", headers=auth_headers).status_code == 403
    audit = client.get("/api/v1/admin/audit", headers=bearer(member)).json()["items"]
    assert [e["action"] for e in audit][:2] == ["admin.user_updated", "admin.user_updated"]
    assert audit[1]["detail"] == {"role": "admin"}


def test_deactivated_account_loses_its_session_and_cannot_sign_in(client, auth_headers):
    member = register(client, "member@example.com")
    member_id = member.json()["user"]["id"]
    client.patch(
        f"/api/v1/admin/users/{member_id}", headers=auth_headers, json={"is_active": False}
    )
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers=bearer(member)).status_code == 401
    login = client.post(
        "/api/v1/auth/login", json={"email": "member@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401


def test_admin_reset_link_works_once_and_ends_old_sessions(client, auth_headers):
    member = register(client, "member@example.com")
    member_id = member.json()["user"]["id"]
    with SessionLocal() as db:  # make the old session a second older than the reset
        user = db.get(User, member_id)
        old = jwt.encode(
            {
                "sub": member_id,
                "iat": datetime.now(UTC) - timedelta(seconds=5),
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            get_settings().jwt_secret.get_secret_value(),
            algorithm="HS256",
        )
        assert user is not None
    client.cookies.clear()
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 200
    )
    link = client.post(f"/api/v1/admin/users/{member_id}/reset-link", headers=auth_headers).json()
    token = parse_qs(urlparse(link["url"]).query)["token"][0]
    body = {"token": token, "new_password": "another-long-password"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=body).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json=body).status_code == 400
    client.cookies.clear()
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    )
    creds = {"email": "member@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=creds).status_code == 401
    creds["password"] = "another-long-password"
    assert client.post("/api/v1/auth/login", json=creds).status_code == 200


def test_reset_request_never_reveals_accounts_and_emails_only_real_ones(client, monkeypatch):
    sent = []
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.test")
    monkeypatch.setattr(auth, "_send_reset_email", lambda to, url: sent.append((to, url)))
    for email in ("demo@resolveai.local", "nobody@example.com"):
        response = client.post("/api/v1/auth/password-reset/request", json={"email": email})
        assert response.status_code == 202
    assert [to for to, _ in sent] == ["demo@resolveai.local"]
    with SessionLocal() as db:  # the link itself is never written to the audit trail
        events = db.scalars(select(AuditEvent)).all()
        assert "token" not in json.dumps([e.detail for e in events])


def test_change_password_needs_the_current_one(client, auth_headers):
    wrong = {"current_password": "not-the-password", "new_password": "another-long-password"}
    assert client.post("/api/v1/auth/password", headers=auth_headers, json=wrong).status_code == 400
    right = {"current_password": "demo-password-for-tests", "new_password": "another-long-password"}
    changed = client.post("/api/v1/auth/password", headers=auth_headers, json=right)
    assert changed.status_code == 200
    client.cookies.clear()
    # The session that made the change is seconds old at most, and still ends; the new one works.
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(changed)).status_code == 200


@pytest.fixture
def idp(monkeypatch):
    """A fake identity provider whose token endpoint signs whatever claims the test sets."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())) | {"kid": "k1"}
    issuer = "https://idp.test"
    settings = get_settings()
    monkeypatch.setattr(settings, "oidc_issuer", issuer)
    monkeypatch.setattr(settings, "oidc_client_id", "resolveai")
    monkeypatch.setattr(settings, "oidc_client_secret", settings.jwt_secret)
    state = {"claims": {}, "key": key}

    def get(url):
        if url.endswith("/.well-known/openid-configuration"):
            return {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/authorize",
                "token_endpoint": f"{issuer}/token",
                "jwks_uri": f"{issuer}/jwks",
            }
        return {"keys": [jwk]}

    def post(url, data):
        now = datetime.now(UTC)
        claims = {
            "iss": issuer,
            "aud": "resolveai",
            "sub": "subject-1",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "nonce": state["nonce"],
            "email_verified": True,
        } | state["claims"]
        return {"id_token": jwt.encode(claims, state["key"], "RS256", headers={"kid": "k1"})}

    monkeypatch.setattr(auth, "_oidc_get", get)
    monkeypatch.setattr(auth, "_oidc_post", post)
    return state


def sso(client, idp, **claims):
    client.cookies.clear()
    start = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    idp["nonce"], idp["claims"] = query["nonce"][0], claims
    assert query["code_challenge_method"] == ["S256"]
    return client.get(
        "/api/v1/auth/oidc/callback",
        params={"code": "c", "state": claims.pop("state", query["state"][0])},
        follow_redirects=False,
    )


def test_sso_only_admits_allowed_email_domains(client, idp, monkeypatch):
    monkeypatch.setattr(get_settings(), "oidc_allowed_domains", "Example.com, corp.test")
    assert sso(client, idp, email="a@evil.test").headers["location"].endswith("reason=sso")
    assert sso(client, idp, email="a@example.com.evil.test").headers["location"].endswith("sso")
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email.like("a@%"))) is None
    assert sso(client, idp, email="a@example.com").headers["location"].endswith("/")


def test_sso_creates_a_member_and_signs_in(client, idp):
    response = sso(client, idp, email="Sso.User@Example.com")
    assert response.headers["location"] == "http://localhost:3000/"
    assert client.get("/api/v1/auth/me").json()["email"] == "sso.user@example.com"
    # The same subject signs in again even if the provider reports a new address.
    assert sso(client, idp, email="renamed@example.com").headers["location"].endswith("/")
    assert client.get("/api/v1/auth/me").json()["email"] == "sso.user@example.com"


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "a@example.com", "email_verified": False},
        {"email": "a@example.com", "nonce": "wrong"},
        {"email": "a@example.com", "aud": "someone-else"},
        {"email": "a@example.com", "iss": "https://evil.test"},
        {"email": "a@example.com", "state": "wrong"},
        {"email": "a@example.com", "exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_sso_rejects_tokens_it_cannot_trust(client, idp, claims):
    response = sso(client, idp, **claims)
    assert response.headers["location"].endswith("/login?reason=sso")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_sso_rejects_a_token_signed_by_another_key(client, idp):
    idp["key"] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert sso(client, idp, email="a@example.com").headers["location"].endswith("reason=sso")


def test_sso_takes_over_a_password_account_registered_with_the_same_email(client, idp):
    squatter = register(client, "victim@example.com")
    assert sso(client, idp, email="victim@example.com").headers["location"].endswith("/")
    client.cookies.clear()
    # The password set by whoever registered first no longer opens the account.
    creds = {"email": "victim@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=creds).status_code == 401
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "victim@example.com"))
        assert user is not None and user.oidc_subject == "https://idp.test|subject-1"
        assert user.password_changed_at is not None
    assert squatter.status_code == 201
