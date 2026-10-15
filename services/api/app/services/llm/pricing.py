"""Rough list prices (USD per million tokens) for cost estimates shown in usage reports.

These are estimates for budgeting, not billing. Unknown models are costed at zero.
"""

from __future__ import annotations

PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICES_PER_MILLION.get(model)
    if price is None:
        # Providers sometimes return dated variants such as "gpt-4.1-mini-2025-04-14".
        price = next((p for name, p in PRICES_PER_MILLION.items() if model.startswith(name)), None)
    if price is None:
        return 0.0
    return round((input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 6)
