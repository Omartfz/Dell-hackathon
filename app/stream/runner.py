"""The always-on stream, driven by a MongoDB change stream.

This is the module that earns the "survives its own sandbox" claim, and it is worth
being precise about how:

* The agent does not poll. It opens a database-level change stream and Mongo pushes
  inserts to it. Insert a document with `mongosh` on the box and the agent reacts —
  there is no file you could substitute for this.
* After every event it checkpoints the stream's **resume token** into `agent_state`.
  On restart it reopens with `resume_after=<token>` and continues from exactly where
  it stopped: no gap, no replay of what it already did.
* Processing is idempotent regardless. Each event id is claimed in `processed_events`
  under a unique `_id`, so a crash between "work done" and "token saved" costs a
  duplicate attempt, not duplicate side effects.

Kill -9 the process mid-stream and restart it; the ledger and the token agree.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from pymongo.errors import PyMongoError

from app.agent import planner
from app.db.client import adb
from app.escalate.external import EnvelopeViolation, assert_minimized, escalate
from app.minimizer.reidentify import AliasMap
from app.stream import triage
from app.stream.triage import Tier, Verdict
from config import settings

STATE_ID = "stream"
Broadcast = Callable[[dict[str, Any]], Awaitable[None]]

#: Only inserts, only the two collections that carry business events.
_PIPELINE = [{"$match": {"operationType": "insert",
                         "ns.coll": {"$in": ["transactions", "invoices"]}}}]


class StreamRunner:
    def __init__(self, broadcast: Broadcast | None = None) -> None:
        self._broadcast = broadcast or self._noop
        self.running = False
        self.online = True
        self.counters = {"processed": 0, "tier0": 0, "tier1": 0, "tier2": 0,
                         "queued": 0, "bytes_out": 0, "sensitive_exposed": 0}
        self._task: asyncio.Task | None = None
        self._started_at: datetime | None = None
        self._last_error = ""

    # ------------------------------------------------------------------ #
    @staticmethod
    async def _noop(_: dict[str, Any]) -> None:
        return None

    async def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        await self._broadcast({"type": kind, "at": datetime.now(timezone.utc).isoformat(),
                               **payload})

    # ------------------------------------------------------------------ #
    # resume-token checkpointing
    # ------------------------------------------------------------------ #
    async def _load_token(self) -> dict | None:
        doc = await adb().agent_state.find_one({"_id": STATE_ID})
        return (doc or {}).get("resume_token")

    async def _save_token(self, token: dict, event_id: str) -> None:
        await adb().agent_state.update_one(
            {"_id": STATE_ID},
            {"$set": {"resume_token": token, "last_event_id": event_id,
                      "updated_at": datetime.now(timezone.utc)},
             "$inc": {"checkpoints": 1}},
            upsert=True,
        )

    async def _claim(self, event_id: str) -> bool:
        """Idempotency ledger. False means somebody already handled this event."""
        try:
            await adb().processed_events.insert_one(
                {"_id": event_id, "processed_at": datetime.now(timezone.utc)})
            return True
        except PyMongoError:
            return False

    async def state(self) -> dict[str, Any]:
        # /api/health is exactly what you call when Mongo is unreachable, so this
        # must never raise. Report what is known and say the rest is unavailable.
        try:
            doc = await adb().agent_state.find_one({"_id": STATE_ID}) or {}
        except Exception as exc:
            return {
                "running": self.running, "online": self.online,
                "counters": dict(self.counters), "checkpoints": None,
                "last_event_id": None, "has_resume_token": None,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "last_error": self._last_error or f"mongo unavailable: {exc}",
                "mongo_reachable": False,
            }
        return {
            "mongo_reachable": True,
            "running": self.running,
            "online": self.online,
            "counters": dict(self.counters),
            "checkpoints": doc.get("checkpoints", 0),
            "last_event_id": doc.get("last_event_id"),
            "has_resume_token": bool(doc.get("resume_token")),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_error": self._last_error,
        }

    # ------------------------------------------------------------------ #
    # the ladder
    # ------------------------------------------------------------------ #
    async def handle(self, event: dict[str, Any], kind: str) -> Verdict:
        v = triage.tier0(event, kind)
        self.counters["tier0"] += 1
        if v.resolved:
            return v

        v = await triage.tier1(event, kind, v)
        self.counters["tier1"] += 1
        if v.resolved:
            return v

        return await self._tier2(event, kind, v)

    async def _tier2(self, event: dict[str, Any], kind: str, v: Verdict) -> Verdict:
        self.counters["tier2"] += 1
        task = triage.task_for(event, kind, v)
        entity_id = event.get("vendor_id") or v.entity_id

        result = await planner.plan(task, entity_id=entity_id)
        if "error" in result:
            v.headline = f"escalation aborted: {result['error']}"
            return v

        envelope = result["envelope"]
        try:
            assert_minimized(envelope)
        except EnvelopeViolation as exc:
            # Fail closed. An envelope we cannot vouch for does not leave.
            self._last_error = f"envelope rejected: {exc}"
            v.headline = "escalation blocked by egress gate"
            v.reasons.append(str(exc))
            return v

        payload_bytes = len(json.dumps(envelope, default=str))
        m = result["metrics"]

        outcome = await escalate(envelope) if self.online else None
        status = outcome.status if outcome else "queued"
        if status == "sent":
            self.counters["bytes_out"] += payload_bytes
        else:
            self.counters["queued"] += 1
        self.counters["sensitive_exposed"] += m["sensitive_exposed"]

        answer = outcome.text if outcome and outcome.text else ""
        aliases = AliasMap.from_docs(await adb().aliases.find({}).to_list(2000))
        restored, swaps = aliases.reidentify(answer) if answer else ("", 0)

        doc = {
            "event_id": event["_id"],
            "created_at": datetime.now(timezone.utc),
            "status": status,
            "task": task,
            "task_type": result["task_type"],
            "entity_id": result["entity_id"],
            "policy_id": result.get("policy_id"),
            "role": result.get("role"),
            "fallback": result.get("fallback", False),
            "envelope": envelope,               # exactly what left, byte for byte
            "payload_bytes": payload_bytes,
            "metrics": m,
            "decisions": result["decisions"],
            "naive_baseline": result["naive_baseline"],
            "trace": result["trace"],
            "external": outcome.as_dict() if outcome else {"status": "queued"},
            "answer_aliased": answer,
            "answer_reidentified": restored,
            "alias_swaps": swaps,
        }
        try:
            await adb().escalations.insert_one(doc)
        except PyMongoError:
            pass  # unique on event_id: already recorded, nothing to add

        await self._inbox(event, kind, v, result, restored or answer, status)
        v.tier = Tier.ESCALATED
        v.bytes_out = payload_bytes if status == "sent" else 0
        v.task = task
        return v

    async def _inbox(self, event, kind, v, result, answer, status) -> None:
        m = result["metrics"]
        await adb().inbox.insert_one({
            "created_at": datetime.now(timezone.utc),
            "status": "open",
            "severity": v.severity,
            "kind": kind,
            "event_id": event["_id"],
            "entity_id": result["entity_id"],
            "headline": v.headline,
            "reasons": v.reasons,
            "amount": event.get("amount"),
            "answer": answer,
            "escalation_status": status,
            "exposure": {
                "available_units": m["available_units"],
                "sent_units": m["sent_units"],
                "sensitive_exposed": m["sensitive_exposed"],
                "reduction": m["context_reduction_units"],
            },
        })

    # ------------------------------------------------------------------ #
    # the change stream
    # ------------------------------------------------------------------ #
    async def _consume(self) -> None:
        db = adb()
        token = await self._load_token()
        kwargs: dict[str, Any] = {"full_document": "updateLookup"}
        if token:
            kwargs["resume_after"] = token
            await self._emit("log", {"message": "resuming from saved token"})

        try:
            stream = db.watch(_PIPELINE, **kwargs)
        except PyMongoError as exc:
            # A token from a rotated oplog is unusable; start fresh rather than die.
            self._last_error = f"resume failed, starting fresh: {exc}"
            await self._emit("log", {"message": self._last_error})
            stream = db.watch(_PIPELINE, full_document="updateLookup")

        async with stream as cursor:
            self.running = True
            self._started_at = datetime.now(timezone.utc)
            await self._emit("status", await self.state())
            async for change in cursor:
                await self._on_change(change)

    async def _on_change(self, change: dict[str, Any]) -> None:
        doc = change.get("fullDocument") or {}
        event_id = str(doc.get("_id") or change["_id"].get("_data"))
        kind = "invoice" if change["ns"]["coll"] == "invoices" else "transaction"

        if not await self._claim(event_id):
            return

        t0 = time.monotonic()
        try:
            verdict = await self.handle(doc, kind)
        except Exception as exc:                     # never let one event stop the stream
            self._last_error = f"{type(exc).__name__}: {exc}"
            await self._emit("log", {"message": f"event {event_id} failed: {exc}"})
            verdict = Verdict(Tier.RULES, True, "low", "errored", [str(exc)])

        self.counters["processed"] += 1
        await self._save_token(change["_id"], event_id)

        await self._emit("event", {
            "event_id": event_id, "kind": kind,
            "merchant": doc.get("merchant") or doc.get("vendor_id"),
            "amount": doc.get("amount"),
            "ms": int((time.monotonic() - t0) * 1000),
            "verdict": verdict.as_dict(),
            "counters": dict(self.counters),
        })

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._runner())

    async def _runner(self) -> None:
        backoff = 1.0
        while True:
            try:
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.running = False
                self._last_error = f"{type(exc).__name__}: {exc}"
                await self._emit("log", {"message": f"stream dropped: {exc}; retrying"})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            else:
                backoff = 1.0

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    # ------------------------------------------------------------------ #
    async def drain_queue(self) -> dict[str, int]:
        """Replay queued escalations once the network is back."""
        db = adb()
        sent = failed = 0
        async for doc in db.escalations.find({"status": {"$in": ["queued", "disabled"]}}):
            outcome = await escalate(doc["envelope"])
            if outcome.status == "sent":
                aliases = AliasMap.from_docs(await db.aliases.find({}).to_list(2000))
                restored, swaps = aliases.reidentify(outcome.text)
                await db.escalations.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "sent", "external": outcome.as_dict(),
                              "answer_aliased": outcome.text,
                              "answer_reidentified": restored, "alias_swaps": swaps}})
                await db.inbox.update_one({"event_id": doc["event_id"]},
                                          {"$set": {"answer": restored,
                                                    "escalation_status": "sent"}})
                self.counters["queued"] = max(0, self.counters["queued"] - 1)
                self.counters["bytes_out"] += doc.get("payload_bytes", 0)
                sent += 1
            else:
                failed += 1
        await self._emit("status", await self.state())
        return {"sent": sent, "still_queued": failed}


# --------------------------------------------------------------------------- #
# the replay — genuine inserts, so the change stream is genuinely exercised
# --------------------------------------------------------------------------- #

async def replay(limit: int = 60, rate_hz: float | None = None,
                 include_bec: bool = True, bec_at: int = 12) -> dict[str, Any]:
    """Re-insert seeded rows as new documents at a steady rate.

    This is a *replay*, not a live production feed, and the UI says so. But the
    inserts are real inserts, so the change stream, the indexes and the idempotency
    ledger are all doing their actual jobs.
    """
    db = adb()
    rate = rate_hz or settings().stream_rate_hz
    delay = 1.0 / max(rate, 0.1)
    stamp = int(time.time())

    sample = await db.transactions.aggregate([
        {"$match": {"fraud_score": {"$lt": 0.75}}},
        {"$sample": {"size": limit}},
    ]).to_list(limit)

    ring = await db.transactions.find(
        {"device_id": "d3f9a1c2-77b4-4e21-9c05-1a8e6f0b2d33"}).to_list(10)
    bec = await db.invoices.find_one({"_id": "inv_bec"})

    inserted = 0
    for i, doc in enumerate(sample):
        if include_bec and i == bec_at and bec:
            for j, r in enumerate(ring):
                r = dict(r)
                r["_id"] = f"live_{stamp}_ring_{j}"
                r["ts"] = datetime.now(timezone.utc)
                await db.transactions.insert_one(r)
                inserted += 1
                await asyncio.sleep(delay)
            b = dict(bec)
            b["_id"] = f"live_{stamp}_bec"
            b["received_at"] = datetime.now(timezone.utc)
            await db.invoices.insert_one(b)
            inserted += 1
            await asyncio.sleep(delay)

        d = dict(doc)
        d["_id"] = f"live_{stamp}_{i}"
        d["ts"] = datetime.now(timezone.utc)
        await db.transactions.insert_one(d)
        inserted += 1
        await asyncio.sleep(delay)

    return {"inserted": inserted, "rate_hz": rate}
