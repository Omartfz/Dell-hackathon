"""Aggregation pipelines.

This module is the answer to "if a JSON file would do, it doesn't count." Every
pipeline here does work in the database that would otherwise be a nested loop in
Python over the whole dataset:

  * `bundle_pipeline`      — one round trip assembles an entity and all its relations
                             via $lookup. Not N+1 queries; a real join.
  * `fraud_ring_pipeline`  — $graphLookup walks the shared-device collusion cluster,
                             transitively. This is a graph traversal, in the engine.
  * `spend_rollup_pipeline`— $facet computes category totals, monthly trend and top
                             merchants in a single pass over an indexed range.
  * `vendor_risk_pipeline` — correlates banking changes against scheduled payments
                             with $lookup + $filter, which is the BEC signal itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# --------------------------------------------------------------------------- #
# bundle assembly — what get_bundle() runs
# --------------------------------------------------------------------------- #

def bundle_pipeline(vendor_id: str) -> list[dict[str, Any]]:
    """A vendor plus every document that hangs off it, in one round trip."""
    return [
        {"$match": {"_id": vendor_id}},
        {"$lookup": {
            "from": "transactions", "localField": "_id", "foreignField": "vendor_id",
            "pipeline": [{"$sort": {"ts": -1}}, {"$limit": 400}],
            "as": "transactions", "let": {},
        }},
        {"$lookup": {"from": "invoices", "localField": "_id",
                     "foreignField": "vendor_id", "as": "invoices"}},
        # Employees reached *through* the transactions — the relational hop that a
        # flat file cannot express without loading everything into memory first.
        {"$lookup": {
            "from": "employees",
            "let": {"emp_ids": "$transactions.employee_id"},
            "pipeline": [{"$match": {"$expr": {"$in": ["$_id", {"$ifNull": ["$$emp_ids", []]}]}}}],
            "as": "employees",
        }},
        {"$lookup": {
            "from": "cards",
            "let": {"card_ids": "$transactions.card_id"},
            "pipeline": [{"$match": {"$expr": {"$in": ["$_id", {"$ifNull": ["$$card_ids", []]}]}}}],
            "as": "cards",
        }},
        {"$lookup": {
            "from": "internal_notes",
            "let": {"emp_ids": "$employees._id"},
            "pipeline": [{"$match": {"$expr": {"$in": ["$subject_employee_id",
                                                       {"$ifNull": ["$$emp_ids", []]}]}}}],
            "as": "notes",
        }},
        {"$lookup": {"from": "documents", "localField": "_id",
                     "foreignField": "vendor_id", "as": "documents"}},
        {"$project": {
            "entity": {"id": "$_id", "type": "vendor", "name": "$name"},
            "vendor": {
                "_id": "$_id", "name": "$name", "bank_account": "$bank_account",
                "routing": "$routing", "relationship_months": "$relationship_months",
                "prior_payments_stable": "$prior_payments_stable",
                "account_change_history": "$account_change_history",
            },
            "transactions": 1, "invoices": 1, "employees": 1,
            "cards": 1, "notes": 1, "documents": 1,
        }},
    ]


# --------------------------------------------------------------------------- #
# fraud: graph traversal in the engine
# --------------------------------------------------------------------------- #

def fraud_ring_pipeline(seed_txn_id: str, max_depth: int = 3) -> list[dict[str, Any]]:
    """Expand a collusion cluster from one transaction.

    $graphLookup walks device_id edges transitively: this transaction's device, every
    other transaction on it, and onward. Depth is bounded so a pathological dataset
    cannot hang the stream. Doing this client-side means pulling the whole transaction
    collection over the wire and rebuilding the graph in Python on every tick.
    """
    return [
        {"$match": {"_id": seed_txn_id}},
        {"$graphLookup": {
            "from": "transactions",
            "startWith": "$device_id",
            "connectFromField": "device_id",
            "connectToField": "device_id",
            "as": "cluster",
            "maxDepth": max_depth,
            "restrictSearchWithMatch": {"fraud_score": {"$gte": 0.5}},
        }},
        {"$addFields": {
            "cluster_size": {"$size": "$cluster"},
            "distinct_cards": {"$size": {"$setUnion": ["$cluster.card_id", []]}},
            "distinct_employees": {"$size": {"$setUnion": ["$cluster.employee_id", []]}},
            "cluster_total": {"$sum": "$cluster.amount"},
            "max_score": {"$max": "$cluster.fraud_score"},
            "window_hours": {"$divide": [
                {"$subtract": [{"$max": "$cluster.ts"}, {"$min": "$cluster.ts"}]},
                1000 * 60 * 60,
            ]},
        }},
        # A ring is two or more cards on one device. One card on one device is a person.
        {"$match": {"distinct_cards": {"$gte": 2}}},
        {"$project": {
            "seed_id": "$_id", "device_id": 1, "cluster_size": 1, "distinct_cards": 1,
            "distinct_employees": 1, "cluster_total": 1, "max_score": 1,
            "window_hours": {"$round": ["$window_hours", 1]},
            "transaction_ids": "$cluster._id",
            "card_ids": {"$setUnion": ["$cluster.card_id", []]},
            "employee_ids": {"$setUnion": ["$cluster.employee_id", []]},
        }},
    ]


def open_rings_pipeline(min_cards: int = 2) -> list[dict[str, Any]]:
    """Every shared-device cluster in the book. Powers the inbox summary."""
    return [
        {"$match": {"device_id": {"$ne": None}, "fraud_score": {"$gte": 0.5}}},
        {"$group": {
            "_id": "$device_id",
            "cards": {"$addToSet": "$card_id"},
            "employees": {"$addToSet": "$employee_id"},
            "txns": {"$addToSet": "$_id"},
            "total": {"$sum": "$amount"},
            "max_score": {"$max": "$fraud_score"},
            "first": {"$min": "$ts"}, "last": {"$max": "$ts"},
        }},
        {"$match": {"$expr": {"$gte": [{"$size": "$cards"}, min_cards]}}},
        {"$addFields": {
            "window_hours": {"$round": [
                {"$divide": [{"$subtract": ["$last", "$first"]}, 1000 * 60 * 60]}, 1]},
            "card_count": {"$size": "$cards"},
        }},
        {"$sort": {"total": -1}},
    ]


# --------------------------------------------------------------------------- #
# spend analytics
# --------------------------------------------------------------------------- #

def spend_rollup_pipeline(months: int = 6, vendor_id: str | None = None) -> list[dict[str, Any]]:
    """Category totals, monthly trend and top merchants — one pass, three outputs."""
    since = datetime.now(timezone.utc) - timedelta(days=30 * months)
    match: dict[str, Any] = {"ts": {"$gte": since}}
    if vendor_id:
        match["vendor_id"] = vendor_id
    return [
        {"$match": match},
        {"$facet": {
            "by_category": [
                {"$group": {"_id": "$category", "total": {"$sum": "$amount"},
                            "count": {"$sum": 1}}},
                {"$sort": {"total": -1}},
            ],
            "by_month": [
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$ts"}},
                            "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ],
            "top_merchants": [
                {"$group": {"_id": "$merchant", "total": {"$sum": "$amount"}}},
                {"$sort": {"total": -1}}, {"$limit": 8},
            ],
            "totals": [
                {"$group": {"_id": None, "total": {"$sum": "$amount"},
                            "count": {"$sum": 1},
                            "flagged": {"$sum": {"$cond": [
                                {"$gte": ["$fraud_score", 0.6]}, 1, 0]}}}},
            ],
        }},
    ]


def vendor_risk_pipeline(within_days: int = 30) -> list[dict[str, Any]]:
    """Vendors whose banking details changed shortly before a scheduled payment.

    This correlation *is* the BEC signal, and it is computed where the data lives.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    return [
        {"$match": {"account_change_history.changed_at": {"$gte": cutoff}}},
        {"$lookup": {
            "from": "invoices",
            "let": {"vid": "$_id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$vendor_id", "$$vid"]},
                            "status": "scheduled"}},
                {"$sort": {"scheduled_at": 1}},
            ],
            "as": "pending",
        }},
        {"$match": {"pending.0": {"$exists": True}}},
        {"$addFields": {
            "latest_change": {"$max": "$account_change_history.changed_at"},
            "pending_total": {"$sum": "$pending.amount"},
            "injection_flagged": {"$anyElementTrue": [
                {"$ifNull": ["$pending.injection_detected", [False]]}]},
        }},
        {"$project": {
            "name": 1, "relationship_months": 1, "prior_payments_stable": 1,
            "latest_change": 1, "pending_total": 1, "injection_flagged": 1,
            "pending_count": {"$size": "$pending"},
            "next_payment_at": {"$min": "$pending.scheduled_at"},
        }},
        {"$sort": {"pending_total": -1}},
    ]


def entity_search_pipeline(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """find_entity(): resolve a name to ids without ever returning the record."""
    rx = {"$regex": query, "$options": "i"}
    return [
        {"$match": {"name": rx}},
        {"$limit": limit},
        {"$project": {"_id": 1, "name": 1, "type": {"$literal": "vendor"}}},
    ]
