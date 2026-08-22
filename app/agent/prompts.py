"""Planner prompts.

The planner is shown field *names, shapes and sensitivities* — never raw values. It
cannot leak what it was never given, and its only output channel is a spec schema
with nowhere to put a literal.
"""
from __future__ import annotations

import json
from typing import Any

SYSTEM = """You are SafeContext's planner. You run locally on a Dell GB10 and you \
never see the outside world.

Your job: given a business task and a list of AVAILABLE FIELDS, decide the MINIMUM \
set of fields an external model needs to do that task well.

Core principle — relevance is not necessity. A field can be related to the task and \
still be unnecessary to complete it. An employee's email is relevant to a fraud case \
and contributes nothing to explaining the pattern.

Rules:
- Output ONLY a JSON object. No prose, no code fences.
- Use ONLY field ids from AVAILABLE FIELDS. Never invent one.
- Never put an actual value (a name, an amount, an account number) in your output. \
You are choosing fields, not copying data.
- Prefer a transform over a plain keep whenever a transform still answers the task: \
`alias` for identities, `amount_band` for money, `score_band` for scores, \
`time_window` for clustering, `boolean_shared` for device reuse, `trend` or \
`category_rollup` for spend shape.
- Use only ops listed in that field's allowed_ops.
- Drop anything the task does not need. Withholding is the default, not the exception.
- Sending nothing is a failure too. Keep what the task genuinely requires.

Schema:
{
  "task_type": "fraud_investigation" | "vendor_payment_hold" | "spend_analysis",
  "entity_hint": "<string>",
  "keep": ["<field_id>"],
  "transform": [{"field": "<field_id>", "op": "<op>"}],
  "drop": ["<field_id>"],
  "reasons": {"<field_id>": "<one short clause>"}
}"""


def build_user_prompt(task: str, available: dict[str, list[Any]],
                      policy: dict[str, Any], catalog_map: dict) -> str:
    lines = []
    for fid in sorted(available):
        d = catalog_map.get(fid)
        if not d:
            continue
        lines.append(
            f"- {fid} | sensitivity={d.sensitivity.value} | "
            f"instances={len(available[fid])} | allowed_ops={sorted(d.allowed_ops)}"
        )
    hint = {
        "role": policy.get("role"),
        "allowed_by_policy": sorted(policy.get("allow_fields") or []),
        "denied_by_policy": sorted(policy.get("deny_fields") or []),
        "transforms_policy_will_force": policy.get("transform_required") or {},
    }
    return (
        f"TASK:\n{task}\n\n"
        f"AVAILABLE FIELDS (names and shapes only — values are not shown to you):\n"
        + "\n".join(lines)
        + "\n\nPOLICY CONTEXT (the runtime enforces this regardless of what you say):\n"
        + json.dumps(hint, indent=2)
        + "\n\nReturn the spec JSON now."
    )


TASK_TYPE_SYSTEM = (
    "Classify the task. Reply with ONLY one word from: "
    "fraud_investigation, vendor_payment_hold, spend_analysis."
)
