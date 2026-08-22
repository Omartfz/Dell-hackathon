"""The minimization spec — the only thing the planner is allowed to produce.

The model proposes field *decisions*, never field *values*. That distinction is what
keeps a compromised or confused planner from smuggling a raw account number into the
payload: there is nowhere in this schema to put one.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

TaskType = Literal["fraud_investigation", "vendor_payment_hold", "spend_analysis"]


class TransformReq(BaseModel):
    field: str
    op: str


class Spec(BaseModel):
    task_type: TaskType
    entity_hint: str = ""
    keep: list[str] = Field(default_factory=list)
    transform: list[TransformReq] = Field(default_factory=list)
    drop: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)
    #: Set when the planner failed validation twice and policy defaults were used.
    fallback: bool = False

    @field_validator("keep", "drop", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("transform", mode="before")
    @classmethod
    def _coerce_transform(cls, v):
        """Accept both [{field,op}] and {field: op} — small models emit either."""
        if v is None:
            return []
        if isinstance(v, dict):
            return [{"field": k, "op": o} for k, o in v.items()]
        out = []
        for item in v or []:
            if isinstance(item, dict) and "field" in item:
                out.append({"field": item["field"], "op": item.get("op", "keep")})
        return out

    def transform_map(self) -> dict[str, str]:
        return {t.field: t.op for t in self.transform}


def fallback_spec(task_type: str, policy: dict) -> Spec:
    """Policy-derived spec, used when the planner will not produce valid JSON.

    Still policy-driven — not a hardcoded `if task == "fraud"` — and it is labelled
    `fallback` everywhere it surfaces so the demo never overstates what happened.
    """
    tmap = policy.get("transform_required") or {}
    return Spec(
        task_type=task_type,  # type: ignore[arg-type]
        keep=list(policy.get("allow_fields") or []),
        transform=[{"field": f, "op": o} for f, o in tmap.items()],  # type: ignore[list-item]
        drop=list(policy.get("deny_fields") or []),
        reasons={f: "Policy default (planner fallback)" for f in (policy.get("allow_fields") or [])},
        fallback=True,
    )
