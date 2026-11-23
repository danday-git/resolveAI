import os
from pathlib import Path

os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai_test",
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("JWT_SECRET", "test-secret-for-resolveai-at-least-32-chars")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_DIM", "256")
os.environ.setdefault("DEMO_USER_EMAIL", "demo@resolveai.local")
os.environ.setdefault("DEMO_USER_PASSWORD", "demo-password-for-tests")
os.environ.setdefault("UPLOAD_DIR", "/tmp/resolveai-test-uploads")
# A developer .env must not switch on services the tests do not start.
os.environ["CLAMAV_HOST"] = ""
os.environ["OCR_ENABLED"] = "false"

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from app.core.database import SessionLocal, engine
from app.core.limits import reset_limits
from app.core.security import hash_password
from app.main import app
from app.models import User

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrate_database():
    if os.getenv("REQUIRE_TEST_DB") == "1":
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            pytest.exit(
                f"REQUIRE_TEST_DB=1 but the test database is unreachable ({type(error).__name__})",
                returncode=1,
            )
    config = Config(str(API_DIR / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_database(migrate_database):
    reset_limits()
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE feedback, request_logs, llm_requests, rca_reports, analyses, "
                "incidents, messages, conversations, chunks, documents, audit_events, "
                "password_reset_tokens, users CASCADE"
            )
        )
    yield
    reset_limits()


@pytest.fixture
def client(clean_database):
    with SessionLocal() as db:
        db.add(
            User(
                email="demo@resolveai.local",
                password_hash=hash_password("demo-password-for-tests"),
                role="admin",
            )
        )
        db.commit()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@resolveai.local", "password": "demo-password-for-tests"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
