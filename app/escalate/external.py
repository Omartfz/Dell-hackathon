"""The only egress in this codebase.

`escalate()` takes the envelope produced by `submit_spec` and nothing else. There is
no `bundle` parameter, no database handle, and no closure over either — so there is
no expression inside this module that could reach a raw record even by mistake. That
is the whole security argument, and it is short enough to read in one sitting.

If the network is gone, or escalation is switched off, the envelope is queued and the
caller carries on. Tiers 0 and 1 never depend on this file.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from config import settings

#: Keys an envelope is allowed to carry. Anything else is a bug upstream, and we
#: fail closed rather than forward it.
_ALLOWED_KEYS = frozenset({"task", "instructions_for_external_llm", "context"})


class EnvelopeViolation(RuntimeError):
    pass


@dataclass
class EscalationResult:
    status: str                 # "sent" | "queued" | "disabled" | "error"
    text: str = ""
    model: str = ""
    ms: int = 0
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "text": self.text, "model": self.model,
                "ms": self.ms, "error": self.error}


def assert_minimized(envelope: dict[str, Any]) -> None:
    """Structural gate. Runs before every send, and in the test suite."""
    if not isinstance(envelope, dict):
        raise EnvelopeViolation("envelope must be a dict")
    extra = set(envelope) - _ALLOWED_KEYS
    if extra:
        raise EnvelopeViolation(f"envelope carries unexpected keys: {sorted(extra)}")
    if not isinstance(envelope.get("context"), dict):
        raise EnvelopeViolation("envelope.context must be a dict")
    for banned in ("bundle", "raw", "_id", "transactions", "cards", "employees"):
        if banned in envelope["context"]:
            raise EnvelopeViolation(f"context contains raw collection '{banned}'")


async def escalate(envelope: dict[str, Any]) -> EscalationResult:
    """Send a minimized envelope to the external model. Queue on any failure."""
    assert_minimized(envelope)
    s = settings()

    if not s.escalation_enabled or not s.escalation_url:
        return EscalationResult(status="disabled")

    prompt = (
        f"{envelope['instructions_for_external_llm']}\n\n"
        f"TASK: {envelope['task']}\n\n"
        f"CONTEXT (deliberately reduced; identities are aliases and amounts are bands):\n"
        f"{envelope['context']}\n\n"
        "Give a short assessment and a recommended action. Refer to entities by the "
        "aliases given. Do not speculate about fields that were withheld."
    )
    headers = {"content-type": "application/json"}
    if s.escalation_api_key:
        headers["authorization"] = f"Bearer {s.escalation_api_key}"

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=s.escalation_timeout_s) as c:
            r = await c.post(
                s.escalation_url,
                headers=headers,
                json={"model": s.escalation_model,
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 500},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return EscalationResult(status="queued", error=str(exc),
                                ms=int((time.monotonic() - t0) * 1000))

    text = _extract_text(data)
    return EscalationResult(status="sent", text=text, model=s.escalation_model,
                            ms=int((time.monotonic() - t0) * 1000))


def _extract_text(data: dict) -> str:
    """Tolerate the two common response shapes without importing a vendor SDK."""
    if isinstance(data.get("content"), list):           # Anthropic-style
        return "".join(b.get("text", "") for b in data["content"])
    choices = data.get("choices")                        # OpenAI-style
    if isinstance(choices, list) and choices:
        return (choices[0].get("message") or {}).get("content", "")
    return data.get("text", "") or ""
