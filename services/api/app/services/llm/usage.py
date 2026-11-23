import json
import logging
from uuid import UUID

from app.core.database import SessionLocal
from app.core.logging import request_id_var
from app.models import LLMRequest
from app.services.llm.pricing import estimate_cost

logger = logging.getLogger("resolveai.llm")


def record_llm_call(
    *,
    operation: str,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    retries: int = 0,
    prompt_version: str | None = None,
    owner_id: UUID | None = None,
    error_category: str | None = None,
    request_id: str | None = None,
) -> float | None:
    request_id = request_id or request_id_var.get() or "unknown"
    outcome = "error" if error_category else "success"
    cost = estimate_cost(provider, model, input_tokens, output_tokens)
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "operation": operation,
                "provider": provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "retries": retries,
                "cost_estimate_usd": cost,
                "outcome": outcome,
                "error_category": error_category,
            }
        )
    )
    try:
        with SessionLocal() as db:
            db.add(
                LLMRequest(
                    owner_id=owner_id,
                    request_id=request_id,
                    operation=operation,
                    provider=provider,
                    model=model,
                    prompt_version=prompt_version,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    retries=retries,
                    cost_estimate_usd=cost,
                    outcome=outcome,
                    error_category=error_category,
                )
            )
            db.commit()
    except Exception:
        logger.warning("Unable to persist model usage record")
    return cost
