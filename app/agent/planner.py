"""The planner loop: whoami -> find_entity -> get_bundle -> get_policy -> spec.

The spec is *chosen* by the local model. There is no `if "fraud" in task` shortcut on
the happy path — that would make the whole demo a lie. When the model will not
produce valid JSON after one retry we fall back to a policy-derived spec, which is
still driven by MongoDB rather than by Python, and we label it `fallback` everywhere
it surfaces so nobody mistakes it for planning.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.agent import llm, prompts, tools
from app.minimizer import catalog
from app.minimizer.spec import Spec, fallback_spec
from pydantic import ValidationError

_TASK_TYPES = ("fraud_investigation", "vendor_payment_hold", "spend_analysis")


@dataclass
class Trace:
    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, tool: str, detail: str, ms: int = 0, **extra: Any) -> None:
        self.steps.append({"tool": tool, "detail": detail, "ms": ms,
                           "n": len(self.steps) + 1, **extra})


def classify_locally(task: str) -> str:
    """Cheap keyword prior. Only a *hint* to the model, never the decision itself."""
    t = task.lower()
    if any(k in t for k in ("hold", "pay this", "should we pay", "impersonat", "bec")):
        return "vendor_payment_hold"
    if any(k in t for k in ("fraud", "ring", "collusion", "unusual", "suspicious")):
        return "fraud_investigation"
    return "spend_analysis"


async def classify(task: str) -> str:
    try:
        reply = await llm.chat(prompts.TASK_TYPE_SYSTEM, task)
        word = reply.text.strip().strip('"').split()[0].lower()
        if word in _TASK_TYPES:
            return word
    except Exception:
        pass
    return classify_locally(task)


async def propose_spec(task: str, bundle: dict, policy: dict,
                       task_type: str, trace: Trace) -> Spec:
    available = catalog.available_units(bundle)
    user = prompts.build_user_prompt(task, available, policy, catalog.CATALOG)

    for attempt in (1, 2):
        try:
            reply = await llm.chat(prompts.SYSTEM, user, json_mode=True)
            raw = llm.extract_json(reply.text)
            if raw is None:
                trace.add("planner", f"attempt {attempt}: no JSON in reply", reply.ms)
                continue
            raw.setdefault("task_type", task_type)
            spec = Spec.model_validate(raw)
            trace.add("planner", f"spec accepted on attempt {attempt} "
                                 f"({len(spec.keep)} keep, {len(spec.transform)} transform, "
                                 f"{len(spec.drop)} drop)", reply.ms, model=reply.model)
            return spec
        except (ValidationError, ValueError) as exc:
            trace.add("planner", f"attempt {attempt}: invalid spec — {type(exc).__name__}")
        except Exception as exc:
            trace.add("planner", f"attempt {attempt}: local model unavailable — {exc}")
            break

    trace.add("planner", "falling back to policy defaults (labelled 'fallback')")
    return fallback_spec(task_type, policy)


async def plan(task: str, *, user_id: str = "avery",
               entity_hint: str = "", entity_id: str = "") -> dict[str, Any]:
    t0 = time.monotonic()
    trace = Trace()

    user = await tools.whoami(user_id)
    role = user.get("role", "ap_analyst")
    trace.add("whoami", f"{user.get('name', user_id)} · role={role}")

    if not entity_id:
        matches = await tools.find_entity(entity_hint or task)
        if not matches:
            for token in (entity_hint or task).split():
                if len(token) > 3:
                    matches = await tools.find_entity(token)
                    if matches:
                        break
        if not matches:
            trace.add("find_entity", "no entity resolved")
            return {"error": "no entity resolved", "trace": trace.steps}
        entity_id = matches[0]["_id"]
        trace.add("find_entity", f"{len(matches)} match(es) → {entity_id}")

    bundle = await tools.get_bundle(entity_id)
    if not bundle:
        trace.add("get_bundle", f"{entity_id} not found")
        return {"error": f"entity {entity_id} not found", "trace": trace.steps}
    available = catalog.available_units(bundle)
    trace.add("get_bundle", f"{sum(len(v) for v in available.values())} information units "
                            f"across {len(available)} fields")

    task_type = await classify(task)
    policy = await tools.get_policy(role, task_type)
    trace.add("get_policy", f"{policy.get('_id', 'default')} · task_type={task_type}"
                            + (" (MISSING — deny-heavy default)" if policy.get("missing") else ""))

    spec = await propose_spec(task, bundle, policy, task_type, trace)
    aliases = await tools.load_aliases()
    out = await tools.submit_spec(spec, bundle, policy, task, aliases)
    trace.add("submit_spec", out["summary"])

    out["trace"] = trace.steps
    out["entity_id"] = entity_id
    out["role"] = role
    out["task_type"] = task_type
    out["total_ms"] = int((time.monotonic() - t0) * 1000)
    return out
