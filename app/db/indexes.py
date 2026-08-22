"""Index definitions, each with the query it exists to serve.

Indexes are part of the design here, not an afterthought: the stream does a lookup
per event, and the fraud pipeline walks a graph. Without these the demo degrades
into a collection scan on every tick.
"""
from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

#: (collection, [IndexModel], rationale shown in the UI's MongoDB panel)
INDEX_PLAN: list[tuple[str, list[IndexModel], str]] = [
    ("transactions", [
        IndexModel([("ts", DESCENDING)], name="ts_desc"),
        IndexModel([("vendor_id", ASCENDING), ("ts", DESCENDING)], name="vendor_ts"),
        IndexModel([("device_id", ASCENDING), ("ts", DESCENDING)], name="device_ts"),
        IndexModel([("card_id", ASCENDING)], name="card"),
        IndexModel([("fraud_score", DESCENDING)], name="score_desc"),
        IndexModel([("category", ASCENDING), ("ts", DESCENDING)], name="category_ts"),
    ], "Stream reads by time; triage looks up by vendor, card and device; "
       "the ring pipeline seeks on device_id."),

    ("invoices", [
        IndexModel([("vendor_id", ASCENDING)], name="vendor"),
        IndexModel([("status", ASCENDING), ("scheduled_at", ASCENDING)], name="status_sched"),
        IndexModel([("injection_detected", ASCENDING)], name="injection",
                   partialFilterExpression={"injection_detected": True}),
    ], "Partial index on injection_detected: the flagged set is tiny, so the index "
       "only stores the rows anyone actually queries."),

    ("employees", [IndexModel([("name", TEXT), ("email", TEXT)], name="people_text")],
     "find_entity() resolves free-text names to ids without scanning."),

    ("vendors", [
        IndexModel([("name", TEXT)], name="vendor_text"),
        IndexModel([("account_change_history.changed_at", DESCENDING)], name="acct_change"),
    ], "Vendor lookup by name, and 'who changed banking details recently'."),

    ("policies", [IndexModel([("role", ASCENDING), ("task_type", ASCENDING)],
                             name="role_task", unique=True)],
     "Every escalation reads exactly one policy. Unique keeps roles unambiguous."),

    ("field_catalog", [IndexModel([("field_id", ASCENDING)], name="field_id", unique=True)],
     "The allow-list, read on every minimize()."),

    ("aliases", [
        IndexModel([("alias", ASCENDING)], name="alias", unique=True),
        IndexModel([("ref_id", ASCENDING)], name="ref", unique=True),
    ], "Bidirectional re-identification. Both directions must be unique or the "
       "swap-back is ambiguous."),

    ("escalations", [
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
        IndexModel([("event_id", ASCENDING)], name="event", unique=True),
    ], "The audit trail. Unique on event_id makes escalation idempotent — a "
       "restart mid-flight cannot double-send."),

    ("inbox", [
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
        IndexModel([("status", ASCENDING), ("severity", ASCENDING)], name="status_sev"),
    ], "The action inbox, ordered for the operator."),

    ("processed_events", [
        IndexModel([("_id", ASCENDING)], name="_id_"),
        IndexModel([("processed_at", ASCENDING)], name="ttl",
                   expireAfterSeconds=60 * 60 * 24),
    ], "Idempotency ledger. A TTL index expires it after a day so the collection "
       "cannot grow without bound — Mongo reclaims it, not a cron job we forgot."),

    ("agent_state", [IndexModel([("_id", ASCENDING)], name="_id_")],
     "Holds the change-stream resume token. This is what lets the agent survive "
     "being killed."),
]


async def ensure(db) -> list[dict]:
    out = []
    for coll, models, why in INDEX_PLAN:
        try:
            names = await db[coll].create_indexes(models)
        except Exception as exc:  # an existing conflicting index must not abort startup
            out.append({"collection": coll, "error": str(exc), "rationale": why})
            continue
        out.append({"collection": coll, "created": names, "rationale": why})
    return out


def ensure_sync(db) -> list[dict]:
    out = []
    for coll, models, why in INDEX_PLAN:
        try:
            names = db[coll].create_indexes(models)
        except Exception as exc:
            out.append({"collection": coll, "error": str(exc), "rationale": why})
            continue
        out.append({"collection": coll, "created": names, "rationale": why})
    return out
