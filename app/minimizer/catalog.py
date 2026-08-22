"""The field catalog: the canonical list of information units SafeContext knows about.

Nothing may appear in an outbound payload unless it is declared here. This is the
allow-list that makes `minimize()` deterministic — the planner can only reason about
field IDs, never about raw values, and unknown IDs are dropped and logged.

Each definition knows how to *extract* its instances from a bundle. An "information
unit" is one instance of one field (two employees on a bundle = two `employee.name`
units), which is what makes `available_units` a computed number rather than a claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from app.minimizer.sensitivity import Sensitivity

Bundle = dict[str, Any]
Extractor = Callable[[Bundle], list[Any]]


@dataclass(frozen=True)
class FieldDef:
    field_id: str
    sensitivity: Sensitivity
    allowed_ops: frozenset[str]
    extract: Extractor
    label: str
    #: Emitted into the payload under this key. Defaults to a flattened field_id.
    out_key: str = ""
    #: True when the field is a single scalar rather than a per-instance list.
    scalar: bool = False
    #: True when the field is semantically a set. A one-element set is still a set —
    #: without this, `["over transaction limit"]` would reach the model as a bare
    #: string and the payload's shape would depend on the data.
    always_list: bool = False

    @property
    def key(self) -> str:
        return self.out_key or self.field_id.replace(".", "_")


# --------------------------------------------------------------------------- #
# extractor helpers
# --------------------------------------------------------------------------- #

def _pluck(collection: str, attr: str) -> Extractor:
    def _ex(b: Bundle) -> list[Any]:
        return [d[attr] for d in b.get(collection, []) or [] if d.get(attr) is not None]
    return _ex


def _one(collection: str, attr: str) -> Extractor:
    """A scalar off a single sub-document (vendor, treasury, fraud_ring)."""
    def _ex(b: Bundle) -> list[Any]:
        doc = b.get(collection)
        if not isinstance(doc, dict):
            return []
        val = doc.get(attr)
        return [] if val is None else [val]
    return _ex


def _hours_until(ts: Any) -> float | None:
    if not isinstance(ts, datetime):
        return None
    now = datetime.now(timezone.utc)
    ref = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return round((ref - now).total_seconds() / 3600.0, 1)


def _days_since(ts: Any) -> int | None:
    if not isinstance(ts, datetime):
        return None
    now = datetime.now(timezone.utc)
    ref = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return max(0, (now - ref).days)


def _vendor_account_changed(b: Bundle) -> list[Any]:
    v = b.get("vendor")
    if not isinstance(v, dict):
        return []
    hist = v.get("account_change_history") or []
    return [bool(hist)]


def _vendor_days_since_change(b: Bundle) -> list[Any]:
    v = b.get("vendor")
    if not isinstance(v, dict):
        return []
    hist = v.get("account_change_history") or []
    if not hist:
        return []
    latest = max(hist, key=lambda h: h.get("changed_at") or datetime.min)
    d = _days_since(latest.get("changed_at"))
    return [] if d is None else [d]


def _vendor_change_channel(b: Bundle) -> list[Any]:
    v = b.get("vendor")
    if not isinstance(v, dict):
        return []
    hist = v.get("account_change_history") or []
    return [hist[-1].get("requested_via")] if hist else []


def _invoice_scheduled_in_hours(b: Bundle) -> list[Any]:
    out = []
    for inv in b.get("invoices", []) or []:
        h = _hours_until(inv.get("scheduled_at"))
        if h is not None:
            out.append(h)
    return out


def _injection_flags(b: Bundle) -> list[Any]:
    # Computed on the box by app.minimizer.injection and stamped onto the invoice.
    return [bool(inv.get("injection_detected")) for inv in b.get("invoices", []) or []]


def _shared_device(b: Bundle) -> list[Any]:
    ids = [t.get("device_id") for t in b.get("transactions", []) or [] if t.get("device_id")]
    return ids


def _txn_count(b: Bundle) -> list[Any]:
    txns = b.get("transactions") or []
    return [len(txns)] if txns else []


def _flags(b: Bundle) -> list[Any]:
    out: list[str] = []
    for t in b.get("transactions", []) or []:
        out.extend(t.get("flags") or [])
    return sorted(set(out))


# --------------------------------------------------------------------------- #
# the catalog
# --------------------------------------------------------------------------- #

_DEFS: list[FieldDef] = [
    # --- people -------------------------------------------------------------
    FieldDef("employee.name", Sensitivity.PII, frozenset({"keep", "drop", "alias"}),
             _pluck("employees", "name"), "Employee name"),
    FieldDef("employee.email", Sensitivity.PII, frozenset({"keep", "drop"}),
             _pluck("employees", "email"), "Employee email"),
    FieldDef("employee.department", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _pluck("employees", "department"), "Department"),

    # --- cards (PCI floor) --------------------------------------------------
    FieldDef("card.pan", Sensitivity.PCI, frozenset({"drop"}),
             _pluck("cards", "pan"), "Card PAN"),
    FieldDef("card.last4", Sensitivity.PCI, frozenset({"drop"}),
             _pluck("cards", "last4"), "Card last four"),

    # --- transactions -------------------------------------------------------
    FieldDef("txn.amount_exact", Sensitivity.FINANCIAL,
             frozenset({"keep", "drop", "amount_band", "category_rollup"}),
             _pluck("transactions", "amount"), "Transaction amount"),
    FieldDef("txn.merchant", Sensitivity.INTERNAL,
             frozenset({"keep", "drop", "category_rollup"}),
             _pluck("transactions", "merchant"), "Merchant"),
    FieldDef("txn.category", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _pluck("transactions", "category"), "Category"),
    FieldDef("txn.timestamp", Sensitivity.INTERNAL,
             frozenset({"keep", "drop", "time_window", "date_bucket", "trend"}),
             _pluck("transactions", "ts"), "Transaction time"),
    FieldDef("txn.count", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _txn_count, "Transaction count", scalar=True),
    FieldDef("txn.flags", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _flags, "Policy violations", out_key="policy_violations", always_list=True),
    FieldDef("device.id", Sensitivity.INTERNAL,
             frozenset({"keep", "drop", "boolean_shared"}),
             _shared_device, "Device identifier"),
    FieldDef("fraud.score", Sensitivity.INTERNAL,
             frozenset({"keep", "drop", "score_band"}),
             _pluck("transactions", "fraud_score"), "Fraud score"),

    # --- vendor -------------------------------------------------------------
    FieldDef("vendor.name", Sensitivity.INTERNAL, frozenset({"keep", "drop", "alias"}),
             _one("vendor", "name"), "Vendor name", scalar=True),
    FieldDef("vendor.bank_account", Sensitivity.HIGHLY_SENSITIVE, frozenset({"drop"}),
             _one("vendor", "bank_account"), "Vendor bank account", scalar=True),
    FieldDef("vendor.routing", Sensitivity.HIGHLY_SENSITIVE, frozenset({"drop"}),
             _one("vendor", "routing"), "Vendor routing number", scalar=True),
    FieldDef("vendor.account_changed", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _vendor_account_changed, "Bank account changed", scalar=True),
    FieldDef("vendor.days_since_account_change", Sensitivity.INTERNAL,
             frozenset({"keep", "drop"}),
             _vendor_days_since_change, "Days since account change", scalar=True),
    FieldDef("vendor.change_requested_via", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _vendor_change_channel, "Change requested via", scalar=True),
    FieldDef("vendor.relationship_months", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _one("vendor", "relationship_months"), "Relationship length", scalar=True),
    FieldDef("vendor.prior_payments_stable", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _one("vendor", "prior_payments_stable"), "Prior payments stable", scalar=True),

    # --- invoices -----------------------------------------------------------
    FieldDef("invoice.body", Sensitivity.HIGHLY_SENSITIVE, frozenset({"drop"}),
             _pluck("invoices", "body"), "Invoice body"),
    FieldDef("invoice.injection_detected", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _injection_flags, "Injection pattern detected"),
    FieldDef("invoice.amount_exact", Sensitivity.FINANCIAL,
             frozenset({"keep", "drop", "amount_band"}),
             _pluck("invoices", "amount"), "Invoice amount"),
    FieldDef("invoice.scheduled_in_hours", Sensitivity.INTERNAL, frozenset({"keep", "drop"}),
             _invoice_scheduled_in_hours, "Hours until payment"),

    # --- confidential -------------------------------------------------------
    FieldDef("notes.body", Sensitivity.CONFIDENTIAL, frozenset({"keep", "drop"}),
             _pluck("notes", "body"), "Internal note"),

    # --- treasury (MNPI) ----------------------------------------------------
    FieldDef("cash.balance_exact", Sensitivity.MNPI,
             frozenset({"keep", "drop", "amount_band"}),
             _one("treasury", "balance_exact"), "Cash balance", scalar=True),
    FieldDef("cash.runway_months", Sensitivity.MNPI, frozenset({"keep", "drop"}),
             _one("treasury", "runway_months"), "Runway (months)", scalar=True),
    FieldDef("cash.monthly_burn", Sensitivity.MNPI,
             frozenset({"keep", "drop", "amount_band"}),
             _one("treasury", "monthly_burn"), "Monthly burn", scalar=True),
]

CATALOG: dict[str, FieldDef] = {d.field_id: d for d in _DEFS}
FIELD_IDS: tuple[str, ...] = tuple(CATALOG)


def get(field_id: str) -> FieldDef | None:
    return CATALOG.get(field_id)


def available_units(bundle: Bundle) -> dict[str, list[Any]]:
    """Every catalog field instance present on this bundle. The denominator."""
    out: dict[str, list[Any]] = {}
    for fid, d in CATALOG.items():
        try:
            vals = d.extract(bundle)
        except Exception:  # a malformed bundle must not take the stream down
            vals = []
        if vals:
            out[fid] = vals
    return out


def catalog_rows() -> list[dict[str, Any]]:
    """Serialisable view, for the UI and for seeding the `field_catalog` collection."""
    return [
        {
            "field_id": d.field_id,
            "sensitivity": d.sensitivity.value,
            "allowed_ops": sorted(d.allowed_ops),
            "label": d.label,
            "scalar": d.scalar,
        }
        for d in _DEFS
    ]
