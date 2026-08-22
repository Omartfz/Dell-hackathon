"""The exposure report.

Every number here is derived from the bundle and the decision log. Nothing is
asserted, nothing is rounded into a nicer story, and there is no constant anywhere
in this file that could be mistaken for a result.

The headline number — `estimated_exposure` — is deliberately named. It is the share
of sensitive units that left in identifying form. It is *not* a probability of
breach, and it must never be labelled as risk.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.minimizer import catalog
from app.minimizer.minimize import MinimizeResult
from app.minimizer.sensitivity import SENSITIVE, Decision, Sensitivity
from app.minimizer.transforms import DEIDENTIFYING


def _size(obj: Any) -> int:
    return len(json.dumps(obj, default=str, ensure_ascii=False))


def compute(bundle: dict[str, Any], result: MinimizeResult) -> dict[str, Any]:
    available = catalog.available_units(bundle)

    available_units = sum(len(v) for v in available.values())
    sent_units = 0
    sensitive_available = 0
    sensitive_exposed = 0

    per_sensitivity: dict[str, dict[str, int]] = defaultdict(
        lambda: {"available": 0, "sent": 0, "exposed": 0}
    )
    exposed_fields: list[str] = []

    for d in result.decisions:
        bucket = per_sensitivity[d.sensitivity.value]
        bucket["available"] += d.units
        if d.sensitivity in SENSITIVE:
            sensitive_available += d.units

        if d.decision is Decision.REMOVE:
            continue

        sent_units += d.units
        bucket["sent"] += d.units

        # A unit counts as exposed only if it left *in identifying form*: an alias or
        # a band is sent, but it is no longer the sensitive value.
        deidentified = d.decision is Decision.TRANSFORM and (d.op in DEIDENTIFYING)
        if d.sensitivity in SENSITIVE and not deidentified:
            sensitive_exposed += d.units
            bucket["exposed"] += d.units
            exposed_fields.append(d.field)

    available_bytes = _size(bundle)
    sent_bytes = _size(result.payload)

    def _ratio(part: int, whole: int) -> float:
        return round(1.0 - (part / whole), 4) if whole else 0.0

    return {
        "available_units": available_units,
        "sent_units": sent_units,
        "withheld_units": available_units - sent_units,
        "available_bytes": available_bytes,
        "sent_bytes": sent_bytes,
        "context_reduction_units": _ratio(sent_units, available_units),
        "context_reduction_bytes": _ratio(sent_bytes, available_bytes),
        "sensitive_available": sensitive_available,
        "sensitive_exposed": sensitive_exposed,
        "estimated_exposure": round(sensitive_exposed / max(sensitive_available, 1), 4),
        "exposed_fields": sorted(set(exposed_fields)),
        "by_sensitivity": {k: dict(v) for k, v in sorted(per_sensitivity.items())},
        "ignored_spec_fields": result.ignored_fields,
        "truncated": result.truncated,
    }


def naive_baseline(bundle: dict[str, Any]) -> dict[str, Any]:
    """What a full dump would have cost. The honest comparison for the UI."""
    available = catalog.available_units(bundle)
    return {
        "units": sum(len(v) for v in available.values()),
        "bytes": _size(bundle),
        "sensitive_units": sum(
            len(v) for fid, v in available.items()
            if catalog.CATALOG[fid].sensitivity in SENSITIVE
        ),
    }


def summarise(metrics: dict[str, Any]) -> str:
    """One line for the nav bar. Reads correctly at the back of a room."""
    return (
        f"{metrics['available_units']} units available · "
        f"{metrics['sent_units']} sent · "
        f"{metrics['sensitive_exposed']} sensitive exposed"
    )
