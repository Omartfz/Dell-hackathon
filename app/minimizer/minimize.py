"""`minimize()` — the deterministic core.

The planner proposes; this function disposes. Precedence, strongest first:

    1. catalog floor      NEVER_OUTBOUND can never be emitted, for any role or task
    2. policy deny        a denied field is removed even if the agent asked to keep it
    3. agent drop         the agent may always be *more* conservative than policy
    4. policy transform   a required transform is applied even if the agent said keep
    5. agent transform    validated against the field's allowed_ops
    6. agent keep         subject to the policy allow-list, if the policy has one
    7. default            anything unmentioned is removed, not kept

No step in that ladder can put a value in the payload that the catalog did not
declare, and no LLM output is ever copied into the payload verbatim.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.minimizer import catalog
from app.minimizer.reidentify import AliasMap
from app.minimizer.sensitivity import NEVER_OUTBOUND, Decision, Sensitivity, Source
from app.minimizer.spec import Spec
from app.minimizer.transforms import DEIDENTIFYING, OPS, TransformCtx

_ENVELOPE_INSTRUCTION = "Use only this context. Do not assume withheld fields."


@dataclass
class FieldDecision:
    field: str
    decision: Decision
    reason: str
    sensitivity: Sensitivity
    source: Source
    op: str | None = None
    units: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "decision": self.decision.value,
            "reason": self.reason,
            "sensitivity": self.sensitivity.value,
            "source": self.source.value,
            "op": self.op,
            "units": self.units,
        }


@dataclass
class MinimizeResult:
    payload: dict[str, Any]
    decisions: list[FieldDecision]
    ignored_fields: list[str] = field(default_factory=list)
    truncated: bool = False

    def envelope(self, task: str) -> dict[str, Any]:
        return {
            "task": task,
            "instructions_for_external_llm": _ENVELOPE_INSTRUCTION,
            "context": self.payload,
        }

    def decisions_as_dicts(self) -> list[dict[str, Any]]:
        return [d.as_dict() for d in self.decisions]


def _policy_reason(policy: dict) -> str:
    return f"Blocked by policy ({policy.get('role', '?')}, {policy.get('task_type', '?')})"


def minimize(
    bundle: dict[str, Any],
    spec: Spec,
    policy: dict[str, Any],
    aliases: AliasMap | None = None,
) -> MinimizeResult:
    aliases = aliases or AliasMap()
    available = catalog.available_units(bundle)

    deny = set(policy.get("deny_fields") or [])
    allow = set(policy.get("allow_fields") or [])
    required = dict(policy.get("transform_required") or {})
    spec_transforms = spec.transform_map()
    spec_keep, spec_drop = set(spec.keep), set(spec.drop)

    # Spec entries that name fields the catalog has never heard of. Dropped, but
    # surfaced — a planner inventing field IDs is worth seeing in the trace.
    mentioned = spec_keep | spec_drop | set(spec_transforms)
    ignored = sorted(f for f in mentioned if f not in catalog.CATALOG)

    payload: dict[str, Any] = {}
    decisions: list[FieldDecision] = []

    for fid, values in sorted(available.items()):
        fdef = catalog.CATALOG[fid]
        n = len(values)
        agent_reason = spec.reasons.get(fid, "")

        def _record(dec: Decision, reason: str, src: Source, op: str | None = None) -> None:
            decisions.append(FieldDecision(fid, dec, reason, fdef.sensitivity, src, op, n))

        # 1 — catalog floor. Unconditional.
        if fid in NEVER_OUTBOUND:
            _record(Decision.REMOVE, "Never leaves the box (catalog floor)", Source.CATALOG)
            continue

        # 2 — policy deny beats an agent KEEP.
        if fid in deny:
            _record(Decision.REMOVE, _policy_reason(policy), Source.POLICY)
            continue

        # 3 — the agent may always be more conservative.
        if fid in spec_drop:
            _record(Decision.REMOVE, agent_reason or "Not necessary for this task", Source.AGENT)
            continue

        # 4 — silence means no. A field the agent never asked for is not a candidate,
        #     and a policy `transform_required` entry does not conscript it: that entry
        #     constrains *how* a field may travel, it does not decide *that* it travels.
        if fid not in spec_keep and fid not in spec_transforms:
            _record(Decision.REMOVE, "Not requested for this task", Source.DEFAULT)
            continue

        # 5 — the allow-list. Required transforms are implicitly permitted, since a
        #     policy that dictates a field's shape has already accepted the field.
        if allow and fid not in allow and fid not in required:
            _record(Decision.REMOVE, _policy_reason(policy), Source.POLICY)
            continue

        # 6 — pick the op. A policy requirement outranks the agent's proposal.
        op: str | None = None
        src = Source.AGENT
        if fid in required:
            op, src = required[fid], Source.POLICY
        elif fid in spec_transforms:
            op, src = spec_transforms[fid], Source.AGENT

        if op is None:
            value = OPS["keep"](values, TransformCtx(bundle, aliases, fid))
            if value is None:
                _record(Decision.REMOVE, "No value present", Source.CATALOG)
                continue
            payload[fdef.key] = value
            _record(Decision.KEEP, agent_reason or "Necessary for this task", Source.AGENT)
            continue

        if op not in fdef.allowed_ops:
            _record(Decision.REMOVE,
                    f"Op '{op}' not permitted on this field; removed rather than guessed",
                    Source.CATALOG)
            continue

        value = OPS[op](values, TransformCtx(bundle, aliases, fid))
        if value is None:
            _record(Decision.REMOVE, f"Transform '{op}' produced nothing", Source.CATALOG, op)
            continue
        payload[fdef.key] = value
        reason = agent_reason or (
            f"Required transform '{op}'" if src is Source.POLICY else f"Reduced via '{op}'"
        )
        _record(Decision.TRANSFORM, reason, src, op)

    result = MinimizeResult(payload=payload, decisions=decisions, ignored_fields=ignored)

    max_chars = policy.get("max_chars")
    if isinstance(max_chars, int) and max_chars > 0:
        result.truncated = _enforce_max_chars(result, max_chars)

    return result


def _enforce_max_chars(result: MinimizeResult, max_chars: int) -> bool:
    """Shed the least-informative kept fields until the payload fits. Never truncates
    mid-value — a half-serialised payload is worse than a smaller honest one."""
    if len(json.dumps(result.payload, default=str)) <= max_chars:
        return False

    by_key = {catalog.CATALOG[d.field].key: d for d in result.decisions
              if d.decision is not Decision.REMOVE and d.field in catalog.CATALOG}
    # Drop plain KEEPs before TRANSFORMs: a transformed field is already cheap and
    # carries deliberate signal, whereas a raw keep is the bulkier, blunter thing.
    order = sorted(
        by_key.items(),
        key=lambda kv: (kv[1].decision is Decision.TRANSFORM,
                        -len(json.dumps(result.payload.get(kv[0]), default=str))),
    )
    for key, dec in order:
        if len(json.dumps(result.payload, default=str)) <= max_chars:
            break
        result.payload.pop(key, None)
        dec.decision = Decision.REMOVE
        dec.reason = f"Dropped to fit policy max_chars={max_chars}"
        dec.source = Source.POLICY
    return True
