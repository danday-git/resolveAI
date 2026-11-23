from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import LLMRequest, User

_entries: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def rate_limit(key: str, request: Request, limit: int | None = None) -> None:
    now = monotonic()
    maximum = limit or get_settings().rate_limit_per_minute
    with _lock:
        recent = [stamp for stamp in _entries[key] if now - stamp < 60]
        if len(recent) >= maximum:
            request.state.retry_after = max(1, int(60 - (now - recent[0])))
            raise ApiError(429, "RATE_LIMITED", "Request rate limit exceeded")
        recent.append(now)
        _entries[key] = recent


def rate_limit_user(user_id: UUID, request: Request) -> None:
    rate_limit(str(user_id), request)


def check_daily_budget(db: Session, user: User) -> None:
    today = datetime.now(UTC).date()
    total = db.scalar(
        select(func.coalesce(func.sum(LLMRequest.cost_estimate_usd), 0)).where(
            LLMRequest.owner_id == user.id,
            LLMRequest.created_at >= datetime.combine(today, datetime.min.time(), UTC),
        )
    )
    if float(total or 0) >= get_settings().daily_budget_usd:
        raise ApiError(429, "BUDGET_EXCEEDED", "Daily model budget has been reached")


def reset_limits() -> None:
    with _lock:
        _entries.clear()
