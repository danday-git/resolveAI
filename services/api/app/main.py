import hmac
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, auth, chat, documents, incidents, metrics
from app.core.config import Settings, get_settings
from app.core.database import engine, get_db
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    internal_error_handler,
    llm_error_handler,
    validation_error_handler,
)
from app.core.logging import RequestLoggingMiddleware
from app.core.observability import init_sentry, render_metrics
from app.services.llm.base import LLMError
from app.services.llm.factory import get_chat_provider, get_embedding_provider

logger = logging.getLogger(__name__)


def validate_embedding_schema(database_engine, settings: Settings) -> None:
    try:
        with database_engine.connect() as connection:
            typmod = connection.execute(
                text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                )
            ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        if "chunks" in str(exc).lower() or "regclass" in str(exc).lower():
            raise RuntimeError("chunks table missing: run `alembic upgrade head`") from None
        raise
    if typmod is None:
        raise RuntimeError("chunks table missing: run `alembic upgrade head`")
    column_dimension = int(typmod)
    if column_dimension != settings.embedding_dim:
        raise RuntimeError(
            f"Embedding dimension mismatch: EMBEDDING_DIM={settings.embedding_dim} but "
            f"chunks.embedding is vector({column_dimension}). Re-run migrations on a fresh DB "
            "with matching EMBEDDING_DIM or change EMBEDDING_MODEL."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.chat_provider = get_chat_provider(settings)
    app.state.embedding_provider = get_embedding_provider(settings)
    validate_embedding_schema(engine, settings)
    yield


def create_app() -> FastAPI:
    init_sentry()
    app = FastAPI(title="ResolveAI API", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(LLMError, llm_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(incidents.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    def prometheus(request: Request, db: Annotated[Session, Depends(get_db)]):
        """Prometheus scrape target. Off until METRICS_TOKEN is set; it reports all users."""
        token = get_settings().metrics_token
        if token is None or not token.get_secret_value():
            raise ApiError(404, "NOT_FOUND", "Not found")
        expected = f"Bearer {token.get_secret_value()}"
        if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
            raise ApiError(401, "UNAUTHORIZED", "A valid metrics token is required")
        return PlainTextResponse(render_metrics(db), media_type="text/plain; version=0.0.4")

    @app.get("/ready")
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    return app


app = create_app()
