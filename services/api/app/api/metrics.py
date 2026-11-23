from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Document, LLMRequest, RequestLog, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _parse_date(value: str | None, default: date) -> date:
    if value is None:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(422, "VALIDATION_ERROR", "Dates must use ISO format YYYY-MM-DD") from None


def _window(from_date: str | None, to_date: str | None):
    today = datetime.now(UTC).date()
    start = _parse_date(from_date, today - timedelta(days=6))
    end = _parse_date(to_date, today)
    if start > end:
        raise ApiError(422, "VALIDATION_ERROR", "from must not be after to")
    return (
        start,
        end,
        datetime.combine(start, time.min, UTC),
        datetime.combine(end + timedelta(days=1), time.min, UTC),
    )


@router.get("/summary")
def summary(
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start, end, start_at, end_at = _window(from_, to)
    request_condition = (
        RequestLog.owner_id == user.id,
        RequestLog.created_at >= start_at,
        RequestLog.created_at < end_at,
    )
    req_total, req_errors, p50, p95 = db.execute(
        select(
            func.count(RequestLog.id),
            func.count(case((RequestLog.status_code >= 400, 1))),
            func.percentile_cont(0.5).within_group(RequestLog.duration_ms),
            func.percentile_cont(0.95).within_group(RequestLog.duration_ms),
        ).where(*request_condition)
    ).one()
    error_rows = db.execute(
        select(RequestLog.status_code, func.count())
        .where(*request_condition, RequestLog.status_code >= 400)
        .group_by(RequestLog.status_code)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    llm_condition = (
        LLMRequest.owner_id == user.id,
        LLMRequest.created_at >= start_at,
        LLMRequest.created_at < end_at,
    )
    llm_total, llm_errors, llm_p50, llm_p95, input_tokens, output_tokens, cost = db.execute(
        select(
            func.count(LLMRequest.id),
            func.count(case((LLMRequest.outcome == "error", 1))),
            func.percentile_cont(0.5).within_group(LLMRequest.latency_ms),
            func.percentile_cont(0.95).within_group(LLMRequest.latency_ms),
            func.coalesce(func.sum(LLMRequest.input_tokens), 0),
            func.coalesce(func.sum(LLMRequest.output_tokens), 0),
            func.sum(LLMRequest.cost_estimate_usd),
        ).where(*llm_condition)
    ).one()
    by_model = db.execute(
        select(
            LLMRequest.provider,
            LLMRequest.model,
            func.count(),
            func.coalesce(func.sum(LLMRequest.input_tokens), 0),
            func.coalesce(func.sum(LLMRequest.output_tokens), 0),
            func.sum(LLMRequest.cost_estimate_usd),
        )
        .where(*llm_condition)
        .group_by(LLMRequest.provider, LLMRequest.model)
        .order_by(LLMRequest.provider, LLMRequest.model)
    ).all()
    by_day_rows = db.execute(
        select(
            func.date(LLMRequest.created_at),
            func.count(),
            func.coalesce(func.sum(LLMRequest.input_tokens + LLMRequest.output_tokens), 0),
            func.sum(LLMRequest.cost_estimate_usd),
        )
        .where(*llm_condition)
        .group_by(func.date(LLMRequest.created_at))
        .order_by(func.date(LLMRequest.created_at))
    ).all()
    docs_condition = (
        Document.owner_id == user.id,
        Document.created_at >= start_at,
        Document.created_at < end_at,
    )
    documents_total, failed = db.execute(
        select(
            func.count(Document.id),
            func.count(case((Document.status == "failed", 1))),
        ).where(*docs_condition)
    ).one()
    failures = db.execute(
        select(Document.error_code, func.count())
        .where(*docs_condition, Document.status == "failed")
        .group_by(Document.error_code)
    ).all()
    last20 = (
        db.execute(
            select(RequestLog.status_code)
            .where(RequestLog.owner_id == user.id)
            .order_by(RequestLog.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    daily_start = datetime.combine(datetime.now(UTC).date(), time.min, UTC)
    daily_cost = db.scalar(
        select(func.sum(LLMRequest.cost_estimate_usd)).where(
            LLMRequest.owner_id == user.id, LLMRequest.created_at >= daily_start
        )
    )
    budget = get_settings().daily_budget_usd
    return {
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "requests": {
            "total": req_total,
            "errors": req_errors,
            "error_rate": req_errors / req_total if req_total else 0.0,
            "p50_ms": float(p50 or 0),
            "p95_ms": float(p95 or 0),
            "top_errors": [{"code": str(code), "count": count} for code, count in error_rows],
        },
        "llm": {
            "calls": llm_total,
            "errors": llm_errors,
            "p50_ms": float(llm_p50 or 0),
            "p95_ms": float(llm_p95 or 0),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": float(cost) if cost is not None else None,
            "by_provider_model": [
                {
                    "provider": provider,
                    "model": model,
                    "calls": calls,
                    "input_tokens": incoming,
                    "output_tokens": outgoing,
                    "estimated_cost_usd": float(model_cost) if model_cost is not None else None,
                }
                for provider, model, calls, incoming, outgoing, model_cost in by_model
            ],
            "by_day": [
                {
                    "date": day.isoformat(),
                    "calls": calls,
                    "tokens": tokens,
                    "estimated_cost_usd": float(day_cost) if day_cost is not None else None,
                }
                for day, calls, tokens, day_cost in by_day_rows
            ],
        },
        "ingestion": {
            "documents_total": documents_total,
            "failed": failed,
            "by_error_code": [
                {"code": code or "unknown", "count": count} for code, count in failures
            ],
        },
        "alerts": {
            "error_rate_over_5pct_last_20": len(last20) == 20
            and sum(status >= 400 for status in last20) / len(last20) > 0.05,
            "p95_over_10s": float(p95 or 0) > 10000,
            "daily_budget_exceeded": float(daily_cost or 0) >= budget,
            "daily_budget_usd": budget,
        },
    }


@router.get("/requests")
def requests(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not 1 <= limit <= 100:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be between 1 and 100")
    http_rows = db.scalars(
        select(RequestLog)
        .where(RequestLog.owner_id == user.id)
        .order_by(RequestLog.created_at.desc())
        .limit(limit)
    ).all()
    llm_rows = db.scalars(
        select(LLMRequest)
        .where(LLMRequest.owner_id == user.id)
        .order_by(LLMRequest.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "type": "request",
                "request_id": row.request_id,
                "method": row.method,
                "route": row.route,
                "status_code": row.status_code,
                "duration_ms": row.duration_ms,
                "created_at": row.created_at,
            }
            for row in http_rows
        ]
        + [
            {
                "type": "llm",
                "request_id": row.request_id,
                "operation": row.operation,
                "provider": row.provider,
                "model": row.model,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "latency_ms": row.latency_ms,
                "estimated_cost_usd": float(row.cost_estimate_usd)
                if row.cost_estimate_usd is not None
                else None,
                "outcome": row.outcome,
                "created_at": row.created_at,
            }
            for row in llm_rows
        ],
    }
