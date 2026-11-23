import json
from pathlib import Path

from app.core.config import get_settings

DEFAULT_PRICING: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "text-embedding-3-small"): (0.02, 0.0),
    ("openai", "text-embedding-3-large"): (0.13, 0.0),
    ("anthropic", "claude-haiku-4-5"): (1.00, 5.00),
    ("anthropic", "claude-sonnet-4-5"): (3.00, 15.00),
    ("ollama", "*"): (0.0, 0.0),
    ("mock", "*"): (0.0, 0.0),
}


def _pricing() -> dict[tuple[str, str], tuple[float, float]]:
    prices = DEFAULT_PRICING.copy()
    path = get_settings().llm_pricing_file
    if path:
        try:
            entries = json.loads(Path(path).read_text())
            for entry in entries:
                prices[(entry["provider"], entry["model"])] = (
                    float(entry["input_per_1m"]),
                    float(entry["output_per_1m"]),
                )
        except (OSError, ValueError, KeyError, TypeError):
            raise ValueError("LLM_PRICING_FILE must contain a JSON pricing list") from None
    return prices


def estimate_cost(provider: str, model: str, in_tok: int, out_tok: int) -> float | None:
    prices = _pricing()
    price = prices.get((provider, model), prices.get((provider, "*")))
    if price is None:
        return None
    return (in_tok * price[0] + out_tok * price[1]) / 1_000_000
