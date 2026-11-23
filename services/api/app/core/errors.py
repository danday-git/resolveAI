from typing import Any

import sentry_sdk
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.llm.base import LLMError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def _response(request: Request, status: int, code: str, message: str, details: Any = None):
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status)


async def api_error_handler(request: Request, exc: Exception):
    assert isinstance(exc, ApiError)
    response = _response(request, exc.status, exc.code, exc.message, exc.details)
    retry_after = getattr(request.state, "retry_after", None)
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


async def http_error_handler(request: Request, exc: Exception):
    assert isinstance(exc, StarletteHTTPException)
    code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(
        exc.status_code, "HTTP_ERROR"
    )
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _response(request, exc.status_code, code, message)


async def validation_error_handler(request: Request, exc: Exception):
    assert isinstance(exc, RequestValidationError)
    details = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
    return _response(request, 422, "VALIDATION_ERROR", "Request validation failed", details)


async def llm_error_handler(request: Request, exc: Exception):
    assert isinstance(exc, LLMError)
    status, code, message = {
        "timeout": (504, "LLM_TIMEOUT", "The model request timed out"),
        "rate_limited": (429, "LLM_RATE_LIMITED", "The model provider is rate limited"),
        "auth": (503, "LLM_UNAVAILABLE", "The model provider is unavailable"),
        "config": (503, "LLM_UNAVAILABLE", "The model provider is unavailable"),
        "invalid_output": (502, "LLM_INVALID_OUTPUT", "The model returned an invalid response"),
        "provider_error": (502, "LLM_PROVIDER_ERROR", "The model provider request failed"),
    }[exc.category]
    return _response(request, status, code, message)


async def internal_error_handler(request: Request, exc: Exception):
    sentry_sdk.capture_exception(exc)  # does nothing unless SENTRY_DSN is configured
    return _response(request, 500, "INTERNAL_ERROR", "An internal error occurred")
