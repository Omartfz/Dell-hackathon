"""The escalation ladder.

Tier 0  deterministic rules + the ensemble score            0 bytes leave
Tier 1  local model reasoning, on this box                  0 bytes leave
Tier 2  minimized escalation to an external model           minimized payload only

Tiers 0 and 1 have no network dependency of any kind. Unplug the box and they keep
running, which is both a demo beat and the honest operating posture: an outage should
degrade this system, not stop it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from app.agent import llm
from app.minimizer.injection import scan
from config import settings


class Tier(IntEnum):
    RULES = 0
    LOCAL_LLM = 1
    ESCALATED = 2


@dataclass
class Verdict:
    tier: Tier
    resolved: bool
    severity: str            # "low" | "medium" | "high" | "critical"
    headline: str
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0
    bytes_out: int = 0
    entity_id: str = ""
    task: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"tier": int(self.tier), "resolved": self.resolved,
                "severity": self.severity, "headline": self.headline,
                "reasons": self.reasons, "score": round(self.score, 3),
                "bytes_out": self.bytes_out, "entity_id": self.entity_id,
                "task": self.task}


def _hours_until(ts: Any) -> float:
    if not isinstance(ts, datetime):
        return 1e9
    ref = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return (ref - datetime.now(timezone.utc)).total_seconds() / 3600.0


def tier0(event: dict[str, Any], kind: str) -> Verdict:
    """Deterministic. No model, no network, microseconds."""
    s = settings()
    reasons: list[str] = []
    score = float(event.get("fraud_score") or 0.0)

    if kind == "invoice":
        finding = scan(event.get("body") or "")
        if finding.detected:
            score = max(score, 0.55) + finding.risk_delta
            reasons.append(
                "invoice body contains an instruction-injection pattern "
                f"({', '.join(finding.categories)}) — legitimate vendors do not write this"
            )
        hrs = _hours_until(event.get("scheduled_at"))
        if hrs < 24:
            score += 0.10
            reasons.append(f"payment scheduled in {hrs:.0f}h")
    else:
        for f in event.get("flags") or []:
            score += 0.05
            reasons.append(f)

    amount = float(event.get("amount") or 0.0)
    if amount >= s.tier2_min_amount:
        reasons.append(f"value at or above the escalation floor")

    score = min(score, 0.99)
    if score < s.tier1_score_low:
        return Verdict(Tier.RULES, True, "low", "cleared by rules", reasons, score,
                       entity_id=event.get("vendor_id", ""))
    return Verdict(Tier.RULES, False, "medium", "needs reasoning", reasons, score,
                   entity_id=event.get("vendor_id", ""))


async def tier1(event: dict[str, Any], kind: str, v0: Verdict) -> Verdict:
    """Local reasoning on the raw event. The record never leaves the machine."""
    s = settings()
    facts = {
        "kind": kind,
        "amount": event.get("amount"),
        "merchant": event.get("merchant"),
        "category": event.get("category"),
        "flags": event.get("flags"),
        "ensemble_score": round(v0.score, 3),
        "rule_findings": v0.reasons,
    }
    system = (
        "You triage corporate spend events for a finance team. Reply with ONLY JSON: "
        '{"resolved": true|false, "severity": "low"|"medium"|"high"|"critical", '
        '"headline": "<max 12 words>", "why": "<one clause>"}. '
        "resolved=true means it needs no human and no further analysis."
    )
    try:
        reply = await llm.chat(system, str(facts), json_mode=True)
        data = llm.extract_json(reply.text) or {}
    except Exception as exc:
        # No local model? Do not silently pass the event — hand it up the ladder.
        return Verdict(Tier.LOCAL_LLM, False, "high",
                       "local model unavailable; escalating on rules alone",
                       v0.reasons + [str(exc)], v0.score,
                       entity_id=v0.entity_id)

    resolved = bool(data.get("resolved"))
    severity = str(data.get("severity", "medium")).lower()
    if severity not in ("low", "medium", "high", "critical"):
        severity = "medium"
    reasons = v0.reasons + ([str(data["why"])] if data.get("why") else [])
    headline = str(data.get("headline") or "reviewed locally")[:120]

    amount = float(event.get("amount") or 0.0)
    high_value = amount >= s.tier2_min_amount
    if resolved or not (high_value and (v0.score >= s.tier1_score_high
                                        or severity in ("high", "critical"))):
        return Verdict(Tier.LOCAL_LLM, True, severity, headline, reasons,
                       v0.score, entity_id=v0.entity_id)

    return Verdict(Tier.LOCAL_LLM, False, severity, headline, reasons,
                   v0.score, entity_id=v0.entity_id)


def task_for(event: dict[str, Any], kind: str, verdict: Verdict) -> str:
    if kind == "invoice":
        return "Assess whether this vendor payment should be held."
    return "Explain why this cluster of transactions looks like a fraud ring."
