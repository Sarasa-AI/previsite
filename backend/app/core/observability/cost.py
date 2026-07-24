"""Static OpenRouter $/1M-token price map for estimated cost telemetry."""

from __future__ import annotations

# Prices are USD per 1M tokens (prompt, completion). Unknown models → None.
_MODEL_PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "openai/gpt-4.1": (2.00, 8.00),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "anthropic/claude-3-haiku": (0.25, 1.25),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "google/gemini-flash-1.5": (0.075, 0.30),
    "meta-llama/llama-3.1-70b-instruct": (0.35, 0.40),
    "qwen/qwen-2.5-72b-instruct": (0.35, 0.40),
}


def estimate_cost_usd(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    if not model:
        return None
    prices = _MODEL_PRICES_PER_MILLION.get(model)
    if prices is None:
        return None
    prompt_per_m, completion_per_m = prices
    inp = input_tokens or 0
    out = output_tokens or 0
    if inp == 0 and out == 0:
        return 0.0
    return (inp / 1_000_000.0) * prompt_per_m + (out / 1_000_000.0) * completion_per_m
