import base64
import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Annotated
from urllib.parse import quote, urlencode

import httpx
import jwt
from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.api.deps import get_current_user, missing_llm_consent
from app.core.ai_settings import effective_settings
from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.limits import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Document, DocumentStatus, PasswordResetToken, User
from app.services.ingestion.pipeline import ingest_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        local, separator, domain = value.rpartition("@")
        local_domain = domain.lower().endswith(".local")
        candidate = f"{local}@{domain[:-6]}.example" if separator and local_domain else value
        try:
            normalized = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError:
            raise ValueError("Invalid email address") from None
        if local_domain:
            return f"{normalized.local_part}@{domain.lower()}".lower()
        return normalized.normalized.lower()


def _valid_password(value: SecretStr) -> SecretStr:
    size = len(value.get_secret_value().encode())
    # bcrypt reads at most 72 bytes; a longer password would be silently cut short.
    if len(value.get_secret_value()) < 12 or size > 72:
        raise ValueError("Password must be 12 to 72 characters")
    return value


class RegisterRequest(LoginRequest):
    _password = field_validator("password")(_valid_password)


class EmailRequest(LoginRequest):
    password: SecretStr = SecretStr("")


class ChangePasswordRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr
    _password = field_validator("new_password")(_valid_password)


class ResetConfirmRequest(BaseModel):
    token: str
    new_password: SecretStr
    _password = field_validator("new_password")(_valid_password)


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


def _public(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "external_llm_providers": effective_settings().external_llm_providers,
        "llm_consent_required": bool(missing_llm_consent(user)),
        "llm_consent_at": user.llm_consent_at,
    }


def _start_session(response: Response, user: User) -> dict:
    token, expires_at = create_access_token(user.id)
    response.set_cookie(
        "resolveai_session",
        token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/",
        expires=expires_at,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": _public(user),
    }


def set_password(user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    user.password_changed_at = datetime.now(UTC)
    # A reset link issued before this change must not be able to undo it.
    if db := object_session(user):
        db.query(PasswordResetToken).filter_by(user_id=user.id).delete()


def create_reset_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    return f"{get_settings().app_url}/reset?token={token}"


@router.get("/config")
def auth_config():
    settings = get_settings()
    return {
        "registration": settings.allow_registration,
        "oidc": settings.oidc_enabled,
        "retention_days": settings.retention,
    }


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    rate_limit(f"login:{body.email}:{_client(request)}", request, 10)
    user = db.scalar(select(User).where(User.email == body.email))
    if (
        user is None
        or not verify_password(body.password.get_secret_value(), user.password_hash)
        or not user.is_active
    ):
        audit(db, request, user, "auth.login_failed")
        db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    audit(db, request, user, "auth.login")
    db.commit()
    return _start_session(response, user)


@router.post("/register", status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    if not get_settings().allow_registration:
        raise ApiError(403, "REGISTRATION_CLOSED", "Registration is closed; ask an administrator")
    rate_limit(f"register:{_client(request)}", request, 5)
    # The administrator's address is the seed's: signed up for first, it would leave the
    # install without an administrator, or hand that person the account.
    reserved = body.email == get_settings().demo_user_email.lower()
    if reserved or db.scalar(select(User.id).where(User.email == body.email)):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists")
    # Never an administrator: on a public install anyone could sign up first.
    # The administrator is created by `python -m app.seed`.
    user = User(email=body.email, password_hash=hash_password(body.password.get_secret_value()))
    db.add(user)
    db.flush()
    audit(db, request, user, "auth.register", "user", user.id)
    db.commit()
    return _start_session(response, user)


@router.post("/password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rate_limit(f"password:{user.id}", request, 5)
    if not verify_password(body.current_password.get_secret_value(), user.password_hash):
        raise ApiError(400, "INVALID_CREDENTIALS", "Current password is incorrect")
    set_password(user, body.new_password.get_secret_value())
    audit(db, request, user, "auth.password_changed", "user", user.id)
    db.commit()
    return _start_session(response, user)


def _send_reset_email(to: str, url: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = "Reset your ResolveAI password"
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(
        f"Open this link within 30 minutes to choose a new password:\n\n{url}\n\n"
        "If you did not ask for it, ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port, timeout=10) as smtp:
        # The link is a credential: never send it in the clear, with or without a login.
        # shortcut: no opt-out for a relay without STARTTLS, add one if a local relay needs it.
        smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def _deliver_reset_email(to: str, url: str) -> None:
    try:
        _send_reset_email(to, url)
    except (OSError, smtplib.SMTPException):
        logger.warning("password reset email could not be sent")


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    body: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """Always 202, so the response does not reveal whether the email has an account."""
    rate_limit(f"reset:{_client(request)}", request, 5)
    user = db.scalar(select(User).where(User.email == body.email, User.is_active))
    # Without SMTP there is no safe way to deliver a link; an administrator issues one instead.
    if user is not None and get_settings().smtp_host:
        url = create_reset_token(db, user)
        audit(db, request, user, "auth.password_reset_requested", "user", user.id)
        db.commit()
        # After the response: waiting on the relay would tell real accounts from unknown ones.
        background.add_task(_deliver_reset_email, user.email, url)
    return {"status": "accepted"}


@router.post("/password-reset/confirm")
def confirm_password_reset(
    body: ResetConfirmRequest, request: Request, db: Annotated[Session, Depends(get_db)]
):
    rate_limit(f"reset-confirm:{_client(request)}", request, 10)
    row = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hashlib.sha256(body.token.encode()).hexdigest(),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    user = db.get(User, row.user_id) if row else None
    if row is None or user is None or not user.is_active:
        raise ApiError(400, "INVALID_TOKEN", "This reset link is invalid or has expired")
    set_password(user, body.new_password.get_secret_value())  # also deletes the link
    audit(db, request, user, "auth.password_reset", "user", user.id)
    db.commit()
    return {"status": "ok"}


def _oidc_get(url: str) -> dict:
    return httpx.get(url, timeout=10).raise_for_status().json()


def _oidc_post(url: str, data: dict, auth: tuple[str, str] | None = None) -> dict:
    return httpx.post(url, data=data, auth=auth, timeout=10).raise_for_status().json()


def _oidc_discovery() -> dict:
    issuer = (get_settings().oidc_issuer or "").rstrip("/")
    return _oidc_get(f"{issuer}/.well-known/openid-configuration")


def _oidc_redirect_uri() -> str:
    return f"{get_settings().app_url}/api/v1/auth/oidc/callback"


@router.get("/oidc/login")
def oidc_login():
    settings = get_settings()
    if not settings.oidc_enabled:
        raise ApiError(404, "NOT_FOUND", "Single sign-on is not configured")
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": _oidc_redirect_uri(),
            "scope": "openid email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"{_oidc_discovery()['authorization_endpoint']}?{query}", 302)
    response.set_cookie(
        "resolveai_oidc",
        jwt.encode(
            {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "exp": datetime.now(UTC) + timedelta(minutes=10),
            },
            settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        ),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # the identity provider sends the browser back from another site
        path="/api/v1/auth/oidc",
        max_age=600,
    )
    return response


def _oidc_user(db: Session, request: Request, claims: dict) -> User | None:
    email = str(claims.get("email", "")).lower()
    if not email or claims.get("email_verified") is not True:
        return None
    # SSO creates accounts even with registration closed, so a public provider needs a limit.
    allowed = {d.strip() for d in get_settings().oidc_allowed_domains.lower().split(",")} - {""}
    if allowed and email.rpartition("@")[2] not in allowed:
        return None
    subject = f"{claims['iss']}|{claims['sub']}"
    user = db.scalar(select(User).where(User.oidc_subject == subject))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            if email == get_settings().demo_user_email.lower():
                return None  # reserved for the seed, as in register
            user = User(email=email, password_hash="!")
            db.add(user)
        elif user.oidc_subject is None:
            # Whoever set this account's password may not own the mailbox: end their access.
            set_password(user, secrets.token_urlsafe(32))
        else:
            return None
        user.oidc_subject = subject
        db.flush()
    if not user.is_active:
        return None
    audit(db, request, user, "auth.sso_login", "user", user.id)
    db.commit()
    return user


@router.get("/oidc/callback")
def oidc_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: str = "",
    state: str = "",
    resolveai_oidc: str | None = Cookie(default=None),
):
    settings = get_settings()
    failed = RedirectResponse(f"{settings.app_url}/login?reason=sso", 302)
    failed.delete_cookie("resolveai_oidc", path="/api/v1/auth/oidc")
    secret = settings.oidc_client_secret
    if not settings.oidc_enabled or secret is None or not code or not resolveai_oidc:
        return failed
    try:
        saved = jwt.decode(
            resolveai_oidc, settings.jwt_secret.get_secret_value(), algorithms=["HS256"]
        )
        if not hmac.compare_digest(str(saved["state"]), state):
            return failed
        discovery = _oidc_discovery()
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _oidc_redirect_uri(),
            "code_verifier": saved["verifier"],
        }
        credentials = (settings.oidc_client_id or "", secret.get_secret_value())
        # A provider that does not list client_secret_post only takes HTTP Basic, the OIDC default.
        if "client_secret_post" in discovery.get("token_endpoint_auth_methods_supported", []):
            form |= dict(zip(("client_id", "client_secret"), credentials, strict=True))
            tokens = _oidc_post(discovery["token_endpoint"], form)
        else:
            basic = (quote(credentials[0], safe=""), quote(credentials[1], safe=""))
            tokens = _oidc_post(discovery["token_endpoint"], form, basic)
        id_token = tokens["id_token"]
        keys = jwt.PyJWKSet.from_dict(_oidc_get(discovery["jwks_uri"]))
        kid = jwt.get_unverified_header(id_token).get("kid")
        key = next(k for k in keys.keys if kid is None or k.key_id == kid)
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_client_id,
            issuer=discovery["issuer"],
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        if not hmac.compare_digest(str(claims.get("nonce", "")), str(saved["nonce"])):
            return failed
    except (jwt.PyJWTError, httpx.HTTPError, KeyError, StopIteration, ValueError):
        logger.warning("single sign-on callback rejected")
        return failed
    user = _oidc_user(db, request, claims)
    if user is None:
        return failed
    response = RedirectResponse(f"{settings.app_url}/", 302)
    response.delete_cookie("resolveai_oidc", path="/api/v1/auth/oidc")
    _start_session(response, user)
    return response


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("resolveai_session", path="/", httponly=True, samesite="strict")


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return _public(user)


class ConsentRequest(BaseModel):
    granted: bool


@router.put("/llm-consent")
def set_llm_consent(
    body: ConsentRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Records the user's own decision to send their data to the external model providers."""
    providers = effective_settings(db).external_llm_providers
    if body.granted and not providers:
        raise ApiError(409, "NO_EXTERNAL_PROVIDER", "No external model provider is configured")
    user.llm_consent_at = datetime.now(UTC) if body.granted else None
    user.llm_consent_providers = ",".join(providers) if body.granted else None
    action = "consent.llm_granted" if body.granted else "consent.llm_withdrawn"
    audit(db, request, user, action, "user", user.id, providers=providers)
    # Documents that failed only for want of this consent go back into the queue: the same
    # file cannot be uploaded twice, so nothing else would index them.
    waiting = (
        db.scalars(
            select(Document).where(
                Document.owner_id == user.id,
                Document.status == DocumentStatus.FAILED,
                Document.error_code == "CONSENT_REQUIRED",
            )
        ).all()
        if body.granted
        else []
    )
    for document in waiting:
        document.status = DocumentStatus.QUEUED
        document.attempts = 0
        document.next_attempt_at = None
        document.error_code = document.error_message = None
    db.commit()
    if get_settings().ingest_inline:
        for document in waiting:
            background.add_task(ingest_document, document.id)
    return _public(user)
