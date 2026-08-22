"""In-memory mirror of the aggregation pipelines.

MongoDB is the system of record and every pipeline in `queries.py` is what actually
runs on the box. This module computes the *same shapes* from the same seeded dataset
in pure Python, and is used only when mongod is unreachable.

It exists for one reason: a demo must never show an empty console because a database
container did not come up. The API tries Mongo first, always, and reports which path
served the request so the distinction is never hidden.
"""
from __future__ import annotations

import functools
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.seed import build


@functools.lru_cache(maxsize=1)
def data() -> dict[str, list[dict]]:
    return build()


def _txns() -> list[dict]:
    return data()["transactions"]


def spend_rollup(months: int = 6) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=30 * months)
    rows = [t for t in _txns() if t["ts"] >= since]
    by_cat: dict[str, list[float]] = defaultdict(list)
    by_month: dict[str, list[float]] = defaultdict(list)
    by_merch: dict[str, float] = defaultdict(float)
    flagged = 0
    for t in rows:
        by_cat[t["category"]].append(t["amount"])
        by_month[t["ts"].strftime("%Y-%m")].append(t["amount"])
        by_merch[t["merchant"]] += t["amount"]
        if t["fraud_score"] >= 0.6:
            flagged += 1
    return {
        "by_category": sorted(
            ({"_id": k, "total": round(sum(v), 2), "count": len(v)} for k, v in by_cat.items()),
            key=lambda r: -r["total"]),
        "by_month": [{"_id": k, "total": round(sum(by_month[k]), 2), "count": len(by_month[k])}
                     for k in sorted(by_month)],
        "top_merchants": sorted(({"_id": k, "total": round(v, 2)} for k, v in by_merch.items()),
                                key=lambda r: -r["total"])[:8],
        "totals": [{"_id": None, "total": round(sum(t["amount"] for t in rows), 2),
                    "count": len(rows), "flagged": flagged}],
    }


def open_rings() -> list[dict]:
    by_dev: dict[str, dict] = {}
    for t in _txns():
        if not t.get("device_id") or t["fraud_score"] < 0.5:
            continue
        d = by_dev.setdefault(t["device_id"], {"_id": t["device_id"], "cards": set(),
                                               "employees": set(), "txns": [], "total": 0.0,
                                               "max_score": 0.0, "first": t["ts"], "last": t["ts"]})
        d["cards"].add(t["card_id"]); d["employees"].add(t["employee_id"])
        d["txns"].append(t["_id"]); d["total"] += t["amount"]
        d["max_score"] = max(d["max_score"], t["fraud_score"])
        d["first"] = min(d["first"], t["ts"]); d["last"] = max(d["last"], t["ts"])
    out = []
    for d in by_dev.values():
        if len(d["cards"]) < 2:
            continue
        out.append({**d, "cards": sorted(d["cards"]), "employees": sorted(d["employees"]),
                    "card_count": len(d["cards"]), "total": round(d["total"], 2),
                    "window_hours": round((d["last"] - d["first"]).total_seconds() / 3600, 1)})
    return sorted(out, key=lambda r: -r["total"])


def vendor_risk() -> list[dict]:
    invs = data()["invoices"]
    out = []
    for v in data()["vendors"]:
        hist = v.get("account_change_history") or []
        if not hist:
            continue
        pending = [i for i in invs if i["vendor_id"] == v["_id"] and i["status"] == "scheduled"]
        if not pending:
            continue
        out.append({
            "_id": v["_id"], "name": v["name"],
            "relationship_months": v["relationship_months"],
            "prior_payments_stable": v["prior_payments_stable"],
            "latest_change": max(h["changed_at"] for h in hist),
            "pending_total": round(sum(i["amount"] for i in pending), 2),
            "pending_count": len(pending),
            "next_payment_at": min(i["scheduled_at"] for i in pending),
            "injection_flagged": any(i.get("injection_detected") for i in pending),
        })
    return sorted(out, key=lambda r: -r["pending_total"])


def cash_forecast(days: int = 90) -> dict[str, Any]:
    """Balance projection with a widening p10–p90 band, from real burn."""
    tre = data()["treasury"][0]
    bal, burn = tre["balance_exact"], tre["monthly_burn"]
    daily = burn / 30.0
    start = datetime.now(timezone.utc) - timedelta(days=days)
    hist, fut = [], []
    for d in range(days, 0, -1):
        ts = start + timedelta(days=days - d)
        hist.append({"t": ts.strftime("%Y-%m-%d"), "v": round(bal + daily * d, 2)})
    for d in range(0, days + 1, 3):
        ts = datetime.now(timezone.utc) + timedelta(days=d)
        mid = bal - daily * d
        spread = daily * d * 0.22
        fut.append({"t": ts.strftime("%Y-%m-%d"), "v": round(mid, 2),
                    "lo": round(mid - spread, 2), "hi": round(mid + spread, 2)})
    return {"history": hist[::3], "forecast": fut, "runway_months": tre["runway_months"],
            "balance": bal, "burn": burn}


def collections() -> dict[str, int]:
    d = data()
    counts = {k: len(v) for k, v in d.items()}
    counts.update({"escalations": 0, "inbox": 0, "processed_events": 0, "agent_state": 0})
    return counts


def flagged(limit: int = 12) -> list[dict]:
    rows = sorted((t for t in _txns() if t["flags"] or t["fraud_score"] >= 0.6),
                  key=lambda t: -t["fraud_score"])[:limit]
    names = {e["_id"]: e["name"] for e in data()["employees"]}
    return [{**t, "employee_name": names.get(t["employee_id"], t["employee_id"])} for t in rows]
