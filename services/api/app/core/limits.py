import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import ApiError
from app.models import LLMRequest, User


def rate_limit(key: str, request: Request, limit: int | None = None) -> None:
    """Counts one hit for the key in the current minute, shared by every API instance."""
    maximum = limit or get_settings().rate_limit_per_minute
    # Its own short transaction: the count must survive a failed request, and the row lock
    # must not be held while the request waits on a model.
    # shortcut: fixed one-minute windows allow up to 2x the limit across a window boundary;
    # move to a sliding window if the limit ever has to be exact.
    with engine.begin() as connection:
        count, wait = connection.execute(
            text(
                "INSERT INTO rate_limits (key, window_start, count) "
                "VALUES (:key, date_trunc('minute', now()), 1) "
                "ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limits.count + 1 "
                "RETURNING count, 60 - extract(second from now())"
            ),
            # Hashed: keys carry emails and client addresses.
            {"key": hashlib.sha256(key.encode()).hexdigest()},
        ).one()
    if count > maximum:
        request.state.retry_after = max(1, int(wait))
        raise ApiError(429, "RATE_LIMITED", "Request rate limit exceeded")


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


def purge_rate_limits() -> None:
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM rate_limits WHERE window_start < now() - interval '5 minutes'")
        )


def reset_limits() -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM rate_limits"))
