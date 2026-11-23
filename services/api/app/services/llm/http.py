import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.services.llm.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)


def post_json(
    client: httpx.Client,
    url: str,
    json: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    max_retries: int,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any], int]:
    retries = 0
    while True:
        try:
            response = client.post(url, json=json, headers=headers, timeout=timeout)
            if response.status_code in (401, 403):
                raise ProviderAuthError("Provider authentication failed")
            if response.status_code == 429:
                if retries < max_retries:
                    sleep(0.5 * (2**retries) + random.uniform(0, 0.1))
                    retries += 1
                    continue
                raise ProviderRateLimited("Provider rate limit exceeded")
            if response.status_code >= 500:
                if retries < max_retries:
                    sleep(0.5 * (2**retries) + random.uniform(0, 0.1))
                    retries += 1
                    continue
                raise ProviderError("Provider server error")
            if response.is_error:
                raise ProviderError(f"Provider request failed ({response.status_code})")
            try:
                payload = response.json()
            except ValueError:
                raise ProviderError("Provider returned invalid JSON") from None
            if not isinstance(payload, dict):
                raise ProviderError("Provider returned an invalid response")
            return payload, retries
        except (httpx.TimeoutException, httpx.ConnectError):
            if retries >= max_retries:
                raise ProviderTimeout("Provider request timed out") from None
            sleep(0.5 * (2**retries) + random.uniform(0, 0.1))
            retries += 1
