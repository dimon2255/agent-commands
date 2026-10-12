"""Per-model prices (USD per million tokens) used to derive cost from recorded usage.

Cost is always computed from the tokens the API reported for the model that actually
served the request. Where a cache rate is not published in the table we use the
standard ratios (reads at 0.1x input, writes at 1.25x input) and say so in the summary.
"""

from __future__ import annotations

PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
    "claude-fable-5-1": {"input": 10.00, "output": 50.00, "cache_read": 0.25, "cache_write": 12.50},
}

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def price_for(model: str | None) -> dict[str, float] | None:
    if not model:
        return None
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    # Tolerate dated snapshots such as claude-opus-5-5-20260401
    for known, price in PRICES_PER_MTOK.items():
        if model.startswith(known):
            return price
    return None


def cost_usd(model: str | None, usage: dict | None) -> float | None:
    """Return the cost of one call, or None when the model has no known price."""
    price = price_for(model)
    if price is None or not usage:
        return None
    inp = float(usage.get("input_tokens") or 0)
    out = float(usage.get("output_tokens") or 0)
    cr = float(usage.get("cache_read_input_tokens") or 0)
    cw = float(usage.get("cache_creation_input_tokens") or 0)
    return (
        inp * price["input"] + out * price["output"] + cr * price["cache_read"] + cw * price["cache_write"]
    ) / 1_000_000.0


def empty_usage() -> dict[str, int]:
    return {k: 0 for k in USAGE_KEYS}


def add_usage(total: dict, part: dict | None) -> dict:
    for k in USAGE_KEYS:
        total[k] = int(total.get(k) or 0) + int((part or {}).get(k) or 0)
    return total
