"""Transform operations. Every one is deterministic Python — no model in the loop.

A transform is how a field survives the trip in reduced form: an exact amount becomes
a band, a name becomes an alias, a pile of timestamps becomes a window. The unit is
still *sent* (it counts against exposure), but it is no longer the sensitive value.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.minimizer import bands
from app.minimizer.reidentify import AliasMap


@dataclass
class TransformCtx:
    bundle: dict[str, Any]
    aliases: AliasMap
    field_id: str


TransformFn = Callable[[list[Any], TransformCtx], Any]


def _as_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


# --------------------------------------------------------------------------- #

def op_keep(values: list[Any], ctx: TransformCtx) -> Any:
    if not values:
        return None
    from app.minimizer import catalog  # local import keeps the module import-cycle free

    fdef = catalog.CATALOG.get(ctx.field_id)
    if fdef is not None and fdef.always_list:
        return values
    return values[0] if len(values) == 1 else values


def op_alias(values: list[Any], ctx: TransformCtx) -> Any:
    out = [ctx.aliases.to_alias(v) for v in values]
    return out[0] if len(out) == 1 else out


def op_amount_band(values: list[Any], ctx: TransformCtx) -> Any:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    if len(nums) == 1:
        return bands.amount_band(nums[0])
    return bands.amount_range_band(nums)


def op_score_band(values: list[Any], ctx: TransformCtx) -> Any:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    if len(nums) == 1:
        return bands.score_band(nums[0])
    lo, hi = bands.score_band(min(nums)), bands.score_band(max(nums))
    return lo if lo == hi else f"{lo} … {hi}"


def op_boolean_shared(values: list[Any], ctx: TransformCtx) -> Any:
    """Device UUIDs -> the fact of sharing, never the identifier."""
    ids = [v for v in values if v]
    if not ids:
        return None
    distinct = set(ids)
    cards = {t.get("card_id") for t in ctx.bundle.get("transactions", []) or [] if t.get("card_id")}
    return {
        "shared": len(distinct) < len(ids),
        "distinct_devices": len(distinct),
        "cards_involved": len(cards),
    }


def op_time_window(values: list[Any], ctx: TransformCtx) -> Any:
    ts = sorted(d for d in (_as_dt(v) for v in values) if d)
    if not ts:
        return None
    span_h = round((ts[-1] - ts[0]).total_seconds() / 3600.0, 1)
    return {"window_hours": span_h, "event_count": len(ts)}


def op_date_bucket(values: list[Any], ctx: TransformCtx) -> Any:
    ts = [d for d in (_as_dt(v) for v in values) if d]
    if not ts:
        return None
    weeks = sorted({f"week of {d.strftime('%Y-%m-%d')}" for d in
                    (t - __import__("datetime").timedelta(days=t.weekday()) for t in ts)})
    return weeks[0] if len(weeks) == 1 else weeks


def op_trend(values: list[Any], ctx: TransformCtx) -> Any:
    """Monthly totals -> shape only. Reads amounts+timestamps off the bundle."""
    txns = ctx.bundle.get("transactions") or []
    monthly: dict[str, float] = defaultdict(float)
    for t in txns:
        d = _as_dt(t.get("ts"))
        amt = t.get("amount")
        if d and isinstance(amt, (int, float)):
            monthly[d.strftime("%Y-%m")] += float(amt)
    if len(monthly) < 2:
        return None
    keys = sorted(monthly)
    start, end = monthly[keys[0]], monthly[keys[-1]]
    pct = round(((end - start) / start) * 100.0, 1) if start else None
    return {
        "months": len(keys),
        "start_band": bands.amount_band(start),
        "end_band": bands.amount_band(end),
        "pct_change": pct,
        "direction": "up" if end > start else "down" if end < start else "flat",
    }


def op_category_rollup(values: list[Any], ctx: TransformCtx) -> Any:
    """Individual merchants/amounts -> per-category banded totals."""
    totals: dict[str, float] = defaultdict(float)
    for t in ctx.bundle.get("transactions", []) or []:
        cat = t.get("category") or "uncategorised"
        amt = t.get("amount")
        if isinstance(amt, (int, float)):
            totals[cat] += float(amt)
    if not totals:
        return None
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    return {cat: bands.amount_band(v) for cat, v in top}


def op_count(values: list[Any], ctx: TransformCtx) -> Any:
    return len(values)


def op_drop(values: list[Any], ctx: TransformCtx) -> Any:  # pragma: no cover - never emitted
    return None


OPS: dict[str, TransformFn] = {
    "keep": op_keep,
    "drop": op_drop,
    "alias": op_alias,
    "amount_band": op_amount_band,
    "score_band": op_score_band,
    "boolean_shared": op_boolean_shared,
    "time_window": op_time_window,
    "date_bucket": op_date_bucket,
    "trend": op_trend,
    "category_rollup": op_category_rollup,
    "count": op_count,
}

#: Ops that reduce sensitivity enough that the unit is no longer "exposed".
DEIDENTIFYING = frozenset(
    {"alias", "amount_band", "score_band", "boolean_shared",
     "time_window", "date_bucket", "trend", "category_rollup", "count"}
)
