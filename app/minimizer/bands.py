"""Deterministic band tables. No LLM ever rewrites a value — these do the work."""
from __future__ import annotations

from bisect import bisect_right

_AMOUNT_EDGES = [0, 100, 500, 1_000, 5_000, 10_000, 25_000, 50_000,
                 100_000, 250_000, 500_000, 1_000_000]
_AMOUNT_LABELS = [
    "<$100", "$100–$500", "$500–$1k", "$1k–$5k", "$5k–$10k", "$10k–$25k",
    "$25k–$50k", "$50k–$100k", "$100k–$250k", "$250k–$500k", "$500k–$1M", ">$1M",
]

_SCORE_EDGES = [0.0, 0.20, 0.40, 0.60, 0.70, 0.80, 0.90, 0.95]
_SCORE_LABELS = [
    "0.00–0.20", "0.20–0.40", "0.40–0.60", "0.60–0.70",
    "0.70–0.80", "0.80–0.90", "0.90–0.95", "0.95–1.00",
]


def amount_band(value: float | int | None) -> str | None:
    """847_291 -> '$500k–$1M'. Magnitude survives; the digits do not."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    idx = max(0, bisect_right(_AMOUNT_EDGES, v) - 1)
    return _AMOUNT_LABELS[min(idx, len(_AMOUNT_LABELS) - 1)]


def score_band(value: float | int | None) -> str | None:
    """0.87 -> '0.80–0.90'."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    idx = max(0, bisect_right(_SCORE_EDGES, v) - 1)
    return _SCORE_LABELS[min(idx, len(_SCORE_LABELS) - 1)]


def amount_range_band(values: list[float]) -> str | None:
    """A band that covers a set of amounts, e.g. four ring transactions."""
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    lo, hi = amount_band(min(nums)), amount_band(max(nums))
    return lo if lo == hi else f"{lo} … {hi}"
