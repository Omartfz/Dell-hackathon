"""Populate the inbox on first run.

A console that opens empty is a console nobody can evaluate. This builds the
escalations that the stream *would* produce for the cases already planted in the seed
— the BEC invoice and the three collusion rings — by running the **real** pipeline:
the real bundles, the real policies from the catalog, the real `minimize()`, and the
real exposure metrics.

Nothing here is illustrative. The payloads are byte-for-byte what would leave the box,
and the numbers come from `metrics.compute()`. The only shortcut is that the planner's
field selection is taken from policy rather than from a live model call, which is the
same labelled `fallback` path the stream uses when the model is slow — so the UI marks
these exactly as it would mark any other fallback escalation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import fallback
from app.minimizer import metrics
from app.minimizer.minimize import minimize
from app.minimizer.reidentify import AliasMap
from app.minimizer.spec import fallback_spec

NOW = datetime.now(timezone.utc)


def _aliases() -> AliasMap:
    return AliasMap.from_docs(fallback.data()["aliases"])


def _vendor_bundle(vendor_id: str) -> dict[str, Any]:
    d = fallback.data()
    vendor = next((v for v in d["vendors"] if v["_id"] == vendor_id), None)
    if not vendor:
        return {}
    txns = [t for t in d["transactions"] if t["vendor_id"] == vendor_id][:60]
    emp_ids = {t["employee_id"] for t in txns}
    card_ids = {t["card_id"] for t in txns}
    return {
        "entity": {"id": vendor_id, "type": "vendor", "name": vendor["name"]},
        "vendor": vendor,
        "invoices": [i for i in d["invoices"] if i["vendor_id"] == vendor_id],
        "transactions": txns,
        "employees": [e for e in d["employees"] if e["_id"] in emp_ids],
        "cards": [c for c in d["cards"] if c["_id"] in card_ids],
        "notes": [n for n in d["internal_notes"] if n["subject_employee_id"] in emp_ids],
        "documents": [x for x in d["documents"] if x.get("vendor_id") == vendor_id],
        "treasury": d["treasury"][0],
    }


def _ring_bundle(ring: dict) -> dict[str, Any]:
    d = fallback.data()
    txns = [t for t in d["transactions"] if t["_id"] in set(ring["transaction_ids"])]
    emp_ids = {t["employee_id"] for t in txns}
    vendor = next((v for v in d["vendors"] if v["_id"] == ring["vendor_id"]), None)
    return {
        "entity": {"id": ring["_id"], "type": "fraud_ring", "name": ring["_id"]},
        "vendor": vendor,
        "invoices": [],
        "transactions": txns,
        "employees": [e for e in d["employees"] if e["_id"] in emp_ids],
        "cards": [c for c in d["cards"] if c["_id"] in set(ring["card_ids"])],
        "notes": [n for n in d["internal_notes"] if n["subject_employee_id"] in emp_ids],
        "documents": [],
        "treasury": d["treasury"][0],
    }


def _policy(role: str, task_type: str) -> dict:
    for p in fallback.data()["policies"]:
        if p["role"] == role and p["task_type"] == task_type:
            return p
    return {"role": role, "task_type": task_type, "allow_fields": [],
            "deny_fields": [], "transform_required": {}}


def _run(bundle: dict, task_type: str, task: str, role: str = "ap_analyst") -> dict | None:
    if not bundle:
        return None
    policy = _policy(role, task_type)
    spec = fallback_spec(task_type, policy)
    result = minimize(bundle, spec, policy, _aliases())
    if not result.payload:
        return None
    return {
        "envelope": result.envelope(task),
        "metrics": metrics.compute(bundle, result),
        "decisions": result.decisions_as_dicts(),
        "naive_baseline": metrics.naive_baseline(bundle),
        "policy_id": policy.get("_id"),
        "task": task, "task_type": task_type, "role": role,
    }


def build() -> tuple[list[dict], list[dict]]:
    """Returns (inbox_items, escalation_docs), both in the shape the API serves."""
    d = fallback.data()
    inbox: list[dict] = []
    escalations: list[dict] = []

    cases: list[tuple[str, dict, str, str, str, str, list[str], float]] = []

    bec = next((i for i in d["invoices"] if i.get("injection_detected")), None)
    if bec:
        cases.append((
            bec["_id"], _vendor_bundle(bec["vendor_id"]), "vendor_payment_hold",
            "Assess whether this vendor payment should be held.",
            "critical", "Hold payment — suspected vendor impersonation",
            ["Bank account changed 3 days before a scheduled payment",
             "Change requested inside an invoice body carrying an instruction-injection pattern",
             "14 months of prior stable payments to the original account"],
            bec["amount"],
        ))

    for i, ring in enumerate(d["fraud_rings"]):
        sev = "critical" if i == 0 else "high" if i == 1 else "medium"
        cases.append((
            ring["_id"], _ring_bundle(ring), "fraud_investigation",
            "Explain why this cluster of transactions looks like a fraud ring.",
            sev, f"Collusion cluster {ring['_id']} — {len(ring['card_ids'])} cards, one device",
            [f"{len(ring['transaction_ids'])} transactions on {len(ring['card_ids'])} cards "
             f"sharing a single device",
             "Every transaction over the cardholder limit",
             "Static rules score these individually and miss the cluster"],
            ring["total"],
        ))

    for n, (event_id, bundle, task_type, task, sev, headline, reasons, amount) in enumerate(cases):
        out = _run(bundle, task_type, task)
        if not out:
            continue
        created = NOW - timedelta(minutes=7 * (n + 1))
        env_bytes = len(str(out["envelope"]))
        escalations.append({
            "event_id": event_id, "created_at": created, "status": "queued",
            "task": out["task"], "task_type": out["task_type"],
            "entity_id": bundle["entity"]["id"], "policy_id": out["policy_id"],
            "role": out["role"], "fallback": True,
            "envelope": out["envelope"], "payload_bytes": env_bytes,
            "metrics": out["metrics"], "decisions": out["decisions"],
            "naive_baseline": out["naive_baseline"], "trace": [],
            "external": {"status": "queued"},
            "answer_aliased": "", "answer_reidentified": "", "alias_swaps": 0,
        })
        m = out["metrics"]
        inbox.append({
            "_id": f"seed_{event_id}", "created_at": created, "status": "open",
            "severity": sev, "kind": "invoice" if event_id.startswith("inv") else "transaction",
            "event_id": event_id, "entity_id": bundle["entity"]["id"],
            "headline": headline, "reasons": reasons, "amount": amount,
            "answer": "", "escalation_status": "queued",
            "exposure": {
                "available_units": m["available_units"], "sent_units": m["sent_units"],
                "sensitive_exposed": m["sensitive_exposed"],
                "reduction": m["context_reduction_units"],
            },
        })

    return inbox, escalations


_CACHE: tuple[list[dict], list[dict]] | None = None


def cached() -> tuple[list[dict], list[dict]]:
    global _CACHE
    if _CACHE is None:
        _CACHE = build()
    return _CACHE
