"""The five tools. There is no sixth.

No tool performs HTTP, runs arbitrary queries, or returns a raw bundle to the caller
of `submit_spec`. The bundle exists only inside the planner's process, and the only
thing that comes out the other side is a minimized envelope plus its exposure report.
"""
from __future__ import annotations

from typing import Any

from app.db import queries
from app.db.client import adb
from app.minimizer import catalog, metrics
from app.minimizer.minimize import MinimizeResult, minimize
from app.minimizer.reidentify import AliasMap
from app.minimizer.spec import Spec

DEFAULT_POLICY: dict[str, Any] = {
    "role": "unknown", "task_type": "unknown",
    "allow_fields": [], "deny_fields": [], "transform_required": {}, "max_chars": 2000,
}


async def whoami(user_id: str = "avery") -> dict[str, Any]:
    doc = await adb().users.find_one({"_id": user_id})
    if not doc:
        return {"_id": user_id, "role": "ap_analyst", "unknown_user": True}
    return doc


async def find_entity(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Resolve a name to ids. Deliberately returns id/name/type and nothing else —
    resolving 'Industrious' must not hand back the vendor record."""
    if not query:
        return []
    rows = await adb().vendors.aggregate(
        queries.entity_search_pipeline(query, limit)).to_list(limit)
    if rows:
        return rows
    emps = await adb().employees.find(
        {"name": {"$regex": query, "$options": "i"}},
        {"_id": 1, "name": 1},
    ).to_list(limit)
    return [{"_id": e["_id"], "name": e["name"], "type": "employee"} for e in emps]


async def get_bundle(entity_id: str) -> dict[str, Any]:
    """The full raw record. 100% available context — the denominator for exposure."""
    db = adb()
    rows = await db.vendors.aggregate(queries.bundle_pipeline(entity_id)).to_list(1)
    if not rows:
        return {}
    bundle = rows[0]
    bundle.pop("_id", None)
    tre = await db.treasury.find_one({"_id": "tre_current"})
    if tre:
        bundle["treasury"] = tre
    return bundle


async def get_policy(role: str, task_type: str) -> dict[str, Any]:
    doc = await adb().policies.find_one({"role": role, "task_type": task_type})
    if not doc:
        # Deny-heavy default: an unrecognised role gets nothing, loudly.
        return {**DEFAULT_POLICY, "role": role, "task_type": task_type,
                "missing": True}
    return doc


async def load_aliases() -> AliasMap:
    docs = await adb().aliases.find({}).to_list(2000)
    return AliasMap.from_docs(docs)


async def submit_spec(spec: Spec, bundle: dict[str, Any], policy: dict[str, Any],
                      task: str, aliases: AliasMap | None = None) -> dict[str, Any]:
    """The only output path. Returns the envelope and the report — never the bundle."""
    aliases = aliases or await load_aliases()
    result: MinimizeResult = minimize(bundle, spec, policy, aliases)
    m = metrics.compute(bundle, result)
    return {
        "envelope": result.envelope(task),
        "metrics": m,
        "decisions": result.decisions_as_dicts(),
        "naive_baseline": metrics.naive_baseline(bundle),
        "summary": metrics.summarise(m),
        "spec": spec.model_dump(),
        "policy_id": policy.get("_id"),
        "fallback": spec.fallback,
    }


TOOLS = {
    "whoami": whoami,
    "find_entity": find_entity,
    "get_bundle": get_bundle,
    "get_policy": get_policy,
    "submit_spec": submit_spec,
}
