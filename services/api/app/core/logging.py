import contextvars
import json
import logging
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ApiError, api_error_handler
from app.core.observability import observe_request
from app.models import RequestLog

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
logger = logging.getLogger("resolveai.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-request-id")
        try:
            request_id = str(UUID(supplied)) if supplied else str(uuid4())
        except ValueError:
            request_id = str(uuid4())
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response | None = None
        try:
            content_length = request.headers.get("content-length")
            if (
                request.method == "POST"
                and request.url.path.rstrip("/") == "/api/v1/documents"
                and content_length is not None
            ):
                try:
                    declared_length = int(content_length)
                except ValueError:
                    declared_length = 0
                max_request_size = get_settings().max_upload_mb * 1024 * 1024 + 64 * 1024
                if declared_length > max_request_size:
                    response = await api_error_handler(
                        request,
                        ApiError(
                            413,
                            "FILE_TOO_LARGE",
                            "File exceeds the configured upload limit",
                        ),
                    )
            if response is None:
                response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration = int((time.perf_counter() - started) * 1000)
            request_path = request.url.path
            route_path = getattr(request.scope.get("route"), "path", None)
            route = route_path if isinstance(route_path, str) else request_path
            if request_path.startswith("/api/v1") and not route.startswith("/api/v1"):
                route = f"/api/v1{route}"
            status = response.status_code if response is not None else 500
            # Unmatched paths share one label, so scanners cannot grow the metric without bound.
            observe_request(
                request.method,
                route if isinstance(route_path, str) else "unmatched",
                status,
                time.perf_counter() - started,
            )
            logger.info(
                json.dumps(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "level": "info",
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": duration,
                        "user_id": (
                            str(request.state.user_id)
                            if getattr(request.state, "user_id", None)
                            else None
                        ),
                    }
                )
            )
            if request_path.startswith("/api/v1"):
                try:
                    with SessionLocal() as db:
                        db.add(
                            RequestLog(
                                request_id=request_id,
                                owner_id=getattr(request.state, "user_id", None),
                                method=request.method,
                                route=route,
                                status_code=status,
                                duration_ms=duration,
                                error_code=f"HTTP_{status}" if status >= 400 else None,
                            )
                        )
                        db.commit()
                except Exception:
                    logger.warning("Unable to persist request log")
            request_id_var.reset(token)
