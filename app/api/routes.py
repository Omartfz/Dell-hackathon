"""HTTP + WebSocket surface."""
from __future__ import annotations

import asyncio
from typing import Any

from bson import json_util
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from app.agent import llm, planner
from app.db import indexes, queries
from app.db.client import adb, replica_set_ready
from app.db.seed import seed_sync
from app.stream.runner import StreamRunner, replay
from config import settings

router = APIRouter(prefix="/api")
RUNNER = StreamRunner()


def _clean(obj: Any) -> Any:
    """BSON -> JSON without dragging ObjectId/datetime into the encoder."""
    return json_util._json_convert(obj, json_options=json_util.RELAXED_JSON_OPTIONS)


def ok(payload: Any) -> JSONResponse:
    return JSONResponse(content=_clean(payload))


# --------------------------------------------------------------------------- #
# health & agent state
# --------------------------------------------------------------------------- #

@router.get("/health")
async def health():
    rs_ok, rs_msg = await replica_set_ready()
    model = await llm.resolve_model()
    s = settings()
    return ok({
        "mongo": {"replica_set": rs_ok, "detail": rs_msg, "uri": s.mongo_uri,
                  "db": s.mongo_db},
        "inference": {"local_model": model, "configured": s.ollama_model,
                      "url": s.ollama_url, "available": await llm.available_models()},
        "escalation": {"enabled": s.escalation_enabled,
                       "configured": bool(s.escalation_url)},
        "agent": await RUNNER.state(),
    })


@router.get("/state")
async def state():
    return ok(await RUNNER.state())


@router.post("/stream/start")
async def stream_start():
    rs_ok, msg = await replica_set_ready()
    if not rs_ok:
        raise HTTPException(status_code=409, detail=msg)
    await RUNNER.start()
    await asyncio.sleep(0.4)
    return ok(await RUNNER.state())


@router.post("/stream/stop")
async def stream_stop():
    await RUNNER.stop()
    return ok(await RUNNER.state())


@router.post("/stream/replay")
async def stream_replay(limit: int = Body(40, embed=True),
                        rate_hz: float | None = Body(None, embed=True)):
    asyncio.create_task(replay(limit=limit, rate_hz=rate_hz))
    return ok({"started": True, "limit": limit})


@router.post("/network/{mode}")
async def network(mode: str):
    """The air-gap toggle. 'offline' makes Tier 2 queue; Tiers 0-1 are untouched."""
    if mode not in ("online", "offline"):
        raise HTTPException(400, "mode must be online or offline")
    RUNNER.online = mode == "online"
    return ok({"online": RUNNER.online})


@router.post("/drain")
async def drain():
    return ok(await RUNNER.drain_queue())


# --------------------------------------------------------------------------- #
# the product
# --------------------------------------------------------------------------- #

@router.post("/ask")
async def ask(task: str = Body(..., embed=True),
              entity_hint: str = Body("", embed=True),
              user_id: str = Body("avery", embed=True)):
    result = await planner.plan(task, user_id=user_id, entity_hint=entity_hint)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@router.get("/inbox")
async def inbox(limit: int = 25):
    rows = await adb().inbox.find({}).sort("created_at", -1).to_list(limit)
    return ok(rows)


@router.get("/escalations")
async def escalations(limit: int = 25):
    rows = await adb().escalations.find({}).sort("created_at", -1).to_list(limit)
    return ok(rows)


@router.get("/escalations/{event_id}")
async def escalation(event_id: str):
    doc = await adb().escalations.find_one({"event_id": event_id})
    if not doc:
        raise HTTPException(404, "no such escalation")
    return ok(doc)


@router.post("/inbox/{item_id}/{action}")
async def act(item_id: str, action: str):
    """Approve or dismiss. Written in a transaction so the inbox, the invoice and
    the audit trail cannot disagree with each other."""
    if action not in ("hold", "release", "dismiss"):
        raise HTTPException(400, "action must be hold, release or dismiss")
    from bson import ObjectId

    db = adb()
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "bad item id")

    item = await db.inbox.find_one({"_id": oid})
    if not item:
        raise HTTPException(404, "no such item")

    async with await db.client.start_session() as session:
        async with session.start_transaction():
            await db.inbox.update_one({"_id": oid},
                                      {"$set": {"status": action}}, session=session)
            if item.get("kind") == "invoice" and action in ("hold", "release"):
                await db.invoices.update_many(
                    {"_id": item["event_id"]},
                    {"$set": {"status": "held" if action == "hold" else "scheduled"}},
                    session=session)
            await db.escalations.update_one(
                {"event_id": item["event_id"]},
                {"$set": {"human_action": action}}, session=session)
    return ok({"item": item_id, "action": action, "atomic": True})


@router.post("/role/{role}")
async def flip_role(role: str, user_id: str = "avery"):
    """Retrieval that changes behaviour: one document write, different payloads."""
    if role not in ("ap_analyst", "controller"):
        raise HTTPException(400, "role must be ap_analyst or controller")
    await adb().users.update_one({"_id": user_id}, {"$set": {"role": role}})
    return ok({"user": user_id, "role": role})


@router.get("/policies")
async def policies():
    return ok(await adb().policies.find({}).to_list(50))


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, patch: dict = Body(...)):
    """Edit a policy and the very next escalation behaves differently. No redeploy."""
    patch.pop("_id", None)
    res = await adb().policies.update_one({"_id": policy_id}, {"$set": patch})
    if not res.matched_count:
        raise HTTPException(404, "no such policy")
    return ok(await adb().policies.find_one({"_id": policy_id}))


# --------------------------------------------------------------------------- #
# the MongoDB panel — the work the database is actually doing
# --------------------------------------------------------------------------- #

@router.get("/mongo/status")
async def mongo_status():
    db = adb()
    rs_ok, rs_msg = await replica_set_ready()
    try:
        names = await db.list_collection_names()
        counts = {n: await db[n].estimated_document_count() for n in sorted(names)}
        state = await db.agent_state.find_one({"_id": "stream"}) or {}
    except Exception as exc:
        return ok({"replica_set": {"ready": False, "detail": f"{rs_msg} ({exc})"},
                   "collections": {}, "total_documents": 0,
                   "change_stream": {"watching": ["transactions", "invoices"],
                                     "checkpoints": 0, "last_event_id": None,
                                     "resume_token_stored": False}})
    return ok({
        "replica_set": {"ready": rs_ok, "detail": rs_msg},
        "collections": counts,
        "total_documents": sum(counts.values()),
        "change_stream": {
            "watching": ["transactions", "invoices"],
            "checkpoints": state.get("checkpoints", 0),
            "last_event_id": state.get("last_event_id"),
            "resume_token_stored": bool(state.get("resume_token")),
        },
    })


@router.get("/mongo/indexes")
async def mongo_indexes():
    db = adb()
    out = []
    for coll, models, why in indexes.INDEX_PLAN:
        try:
            live = await db[coll].index_information()
        except Exception:
            live = {}
        out.append({"collection": coll, "rationale": why,
                    "planned": len(models), "live": sorted(live)})
    return ok(out)


@router.get("/mongo/rings")
async def mongo_rings():
    """$graphLookup, live. The collusion graph is walked in the engine."""
    rows = await adb().transactions.aggregate(queries.open_rings_pipeline()).to_list(20)
    return ok({"pipeline": "open_rings_pipeline ($group + $expr)", "rings": rows})


@router.get("/mongo/ring/{txn_id}")
async def mongo_ring(txn_id: str):
    rows = await adb().transactions.aggregate(
        queries.fraud_ring_pipeline(txn_id)).to_list(5)
    return ok({"pipeline": "fraud_ring_pipeline ($graphLookup, maxDepth=3)",
               "stages": [list(s)[0] for s in queries.fraud_ring_pipeline(txn_id)],
               "result": rows})


@router.get("/mongo/spend")
async def mongo_spend(months: int = 6):
    rows = await adb().transactions.aggregate(
        queries.spend_rollup_pipeline(months)).to_list(1)
    return ok({"pipeline": "spend_rollup_pipeline ($facet x4)",
               "result": rows[0] if rows else {}})


@router.get("/mongo/vendor-risk")
async def mongo_vendor_risk():
    rows = await adb().vendors.aggregate(queries.vendor_risk_pipeline()).to_list(20)
    return ok({"pipeline": "vendor_risk_pipeline ($lookup + correlation)",
               "result": rows})


@router.get("/mongo/explain")
async def mongo_explain(collection: str = "transactions"):
    """Proof the indexes are used rather than merely declared."""
    db = adb()
    try:
        plan = await db.command({
            "explain": {"aggregate": collection,
                        "pipeline": queries.open_rings_pipeline(),
                        "cursor": {}},
            "verbosity": "queryPlanner"})
    except Exception as exc:
        raise HTTPException(500, f"explain failed: {exc}")
    return ok(plan)


@router.post("/seed")
async def reseed():
    from app.db.client import sdb
    counts = seed_sync(sdb())
    indexes.ensure_sync(sdb())
    return ok({"seeded": counts, "total": sum(counts.values())})


# --------------------------------------------------------------------------- #
# console screens
# --------------------------------------------------------------------------- #

@router.get("/treasury")
async def treasury():
    doc = await adb().treasury.find_one({"_id": "tre_current"})
    if not doc:
        raise HTTPException(404, "no treasury snapshot")
    return ok(doc)


@router.get("/catalog")
async def catalog_rows():
    rows = await adb().field_catalog.find({}).to_list(200)
    return ok(sorted(rows, key=lambda r: r.get("field_id", "")))


@router.get("/payables")
async def payables(limit: int = 30):
    db = adb()
    rows = await db.invoices.aggregate([
        {"$lookup": {"from": "vendors", "localField": "vendor_id",
                     "foreignField": "_id", "as": "v"}},
        {"$addFields": {"vendor_name": {"$first": "$v.name"}}},
        {"$project": {"v": 0, "body": 0}},      # bodies never reach the browser either
        {"$sort": {"scheduled_at": 1}}, {"$limit": limit},
    ]).to_list(limit)
    return ok(rows)


@router.get("/transactions")
async def transactions(limit: int = 80):
    rows = await adb().transactions.find({}).sort("ts", -1).to_list(limit)
    return ok(rows)


@router.get("/cards")
async def cards():
    """PANs are stripped server-side — the console never receives one."""
    rows = await adb().cards.aggregate([
        {"$lookup": {"from": "employees", "localField": "holder_id",
                     "foreignField": "_id", "as": "e"}},
        {"$addFields": {"holder_name": {"$first": "$e.name"}}},
        {"$project": {"pan": 0, "e": 0}},
    ]).to_list(50)
    return ok(rows)
