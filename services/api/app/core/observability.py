"""Prometheus metrics in the text exposition format, and optional Sentry error reports."""

import threading
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

import sentry_sdk
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security_text import redact
from app.models import Document, DocumentStatus, LLMRequest

# shortcut: counters live in this process, so each API replica reports its own and they restart
# at zero; scrape every replica (Prometheus sums them), and move to prometheus_client's
# multiprocess mode if one container ever runs several uvicorn workers.
_lock = threading.Lock()
_requests: Counter[tuple[str, str, int]] = Counter()
_seconds: defaultdict[tuple[str, str], float] = defaultdict(float)


def observe_request(method: str, route: str, status: int, seconds: float) -> None:
    with _lock:
        _requests[method, route, status] += 1
        _seconds[method, route] += seconds


def _line(name: str, value: float, **labels: object) -> str:
    def escaped(text: object) -> str:
        return str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    inner = ",".join(f'{key}="{escaped(label)}"' for key, label in labels.items())
    return f"{name}{{{inner}}} {value}" if inner else f"{name} {value}"


def render_metrics(db: Session) -> str:
    with _lock:
        requests, seconds = dict(_requests), dict(_seconds)
    now = datetime.now(UTC)
    lines = [
        "# HELP resolveai_http_requests_total Requests handled by this API process.",
        "# TYPE resolveai_http_requests_total counter",
        *(
            _line("resolveai_http_requests_total", count, method=m, route=r, status=s)
            for (m, r, s), count in sorted(requests.items())
        ),
        "# HELP resolveai_http_request_duration_seconds_sum Time spent handling requests.",
        "# TYPE resolveai_http_request_duration_seconds_sum counter",
        *(
            _line("resolveai_http_request_duration_seconds_sum", round(total, 3), method=m, route=r)
            for (m, r), total in sorted(seconds.items())
        ),
        "# HELP resolveai_documents Documents by ingestion status, all users.",
        "# TYPE resolveai_documents gauge",
    ]
    counts = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
    lines += [
        _line("resolveai_documents", counts.get(s, 0), status=s.value) for s in DocumentStatus
    ]
    oldest = db.scalar(
        select(func.min(Document.created_at)).where(Document.status == DocumentStatus.QUEUED)
    )
    lines += [
        "# HELP resolveai_ingestion_oldest_queued_seconds Age of the oldest queued document.",
        "# TYPE resolveai_ingestion_oldest_queued_seconds gauge",
        _line(
            "resolveai_ingestion_oldest_queued_seconds",
            round((now - oldest).total_seconds()) if oldest else 0,
        ),
        "# HELP resolveai_llm_requests_last_hour LLM and embedding calls in the last hour.",
        "# TYPE resolveai_llm_requests_last_hour gauge",
    ]
    calls = db.execute(
        select(LLMRequest.provider, LLMRequest.model, LLMRequest.outcome, func.count())
        .where(LLMRequest.created_at >= now - timedelta(hours=1))
        .group_by(LLMRequest.provider, LLMRequest.model, LLMRequest.outcome)
        .order_by(LLMRequest.provider, LLMRequest.model, LLMRequest.outcome)
    )
    lines += [
        _line("resolveai_llm_requests_last_hour", count, provider=p, model=m, outcome=o)
        for p, m, o, count in calls
    ]
    cost = db.scalar(
        select(func.coalesce(func.sum(LLMRequest.cost_estimate_usd), 0)).where(
            LLMRequest.created_at >= now - timedelta(days=1)
        )
    )
    lines += [
        "# HELP resolveai_llm_cost_usd_last_day Estimated LLM spend in the last 24 hours.",
        "# TYPE resolveai_llm_cost_usd_last_day gauge",
        _line("resolveai_llm_cost_usd_last_day", float(cost or 0)),
    ]
    return "\n".join(lines) + "\n"


def _scrub(event, hint):
    """Exception text can quote a log line or a document; it gets the same redaction as our logs."""
    for item in (event.get("exception") or {}).get("values") or []:
        if item.get("value"):
            item["value"] = redact(item["value"])[0]
    return event


def init_sentry() -> None:
    """Error reports go to Sentry only when SENTRY_DSN is set. No request bodies, local
    variables, cookies or user details leave the process."""
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn.get_secret_value(),
            environment=settings.sentry_environment,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            traces_sample_rate=0,
            before_send=_scrub,
        )
