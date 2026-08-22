"""The contract tests. If any of these fail, nothing downstream matters."""
from __future__ import annotations

import json

import pytest

from app.minimizer import metrics as M
from app.minimizer.minimize import minimize
from app.minimizer.sensitivity import Decision, Source
from app.minimizer.spec import Spec
from tests.conftest import INJECTION_SENTENCE


def _json(result) -> str:
    return json.dumps(result.payload, default=str)


# --------------------------------------------------------------------------- #
# the floor: things that may never leave, under any spec
# --------------------------------------------------------------------------- #

def test_never_outbound_survives_an_agent_that_asks_for_everything(
    bec_bundle, policy_hold_analyst, aliases
):
    """Worst case: a planner that has been talked into keeping the crown jewels."""
    hostile = Spec(
        task_type="vendor_payment_hold",
        keep=["card.pan", "card.last4", "vendor.bank_account",
              "vendor.routing", "invoice.body", "employee.email"],
    )
    out = minimize(bec_bundle, hostile, policy_hold_analyst, aliases)
    blob = _json(out)

    for secret in ("000123456789", "021000021", "4147209855128831", "8831", "9014"):
        assert secret not in blob, f"{secret} leaked"
    assert "daniel.green@" not in blob
    assert "eleanor.bennett@" not in blob
    assert INJECTION_SENTENCE not in blob


def test_catalog_floor_is_attributed_to_the_catalog_not_the_policy(
    bec_bundle, policy_hold_analyst, aliases
):
    spec = Spec(task_type="vendor_payment_hold", keep=["vendor.bank_account"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    d = next(x for x in out.decisions if x.field == "vendor.bank_account")
    assert d.decision is Decision.REMOVE
    assert d.source is Source.CATALOG


def test_injection_body_withheld_but_the_signal_travels(
    bec_bundle, policy_hold_analyst, aliases
):
    """The whole injection-as-evidence mechanic, in one assertion pair."""
    spec = Spec(
        task_type="vendor_payment_hold",
        keep=["invoice.injection_detected", "vendor.account_changed"],
        drop=["invoice.body"],
    )
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)

    assert INJECTION_SENTENCE not in _json(out)
    assert out.payload["invoice_injection_detected"] is True


# --------------------------------------------------------------------------- #
# precedence
# --------------------------------------------------------------------------- #

def test_policy_deny_beats_agent_keep(bec_bundle, policy_hold_analyst, aliases):
    spec = Spec(task_type="vendor_payment_hold", keep=["notes.body"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    d = next(x for x in out.decisions if x.field == "notes.body")
    assert d.decision is Decision.REMOVE
    assert d.source is Source.POLICY
    assert "Blocked by policy (ap_analyst, vendor_payment_hold)" == d.reason
    assert "do not disclose" not in _json(out)


def test_required_transform_applies_even_when_agent_said_keep_raw(
    bec_bundle, policy_hold_analyst, aliases
):
    spec = Spec(task_type="vendor_payment_hold", keep=["invoice.amount_exact", "vendor.name"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)

    assert out.payload["invoice_amount_exact"] == "$25k–$50k"
    assert "27000" not in _json(out)
    assert out.payload["vendor_name"] == "Vendor_A"
    assert "Industrious" not in _json(out)


def test_agent_may_be_more_conservative_than_policy(bec_bundle, policy_hold_analyst, aliases):
    spec = Spec(task_type="vendor_payment_hold", drop=["vendor.relationship_months"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    d = next(x for x in out.decisions if x.field == "vendor.relationship_months")
    assert d.decision is Decision.REMOVE and d.source is Source.AGENT


def test_unmentioned_fields_are_removed_not_kept(bec_bundle, policy_hold_analyst, aliases):
    out = minimize(bec_bundle, Spec(task_type="vendor_payment_hold"), policy_hold_analyst, aliases)
    assert out.payload == {}
    assert all(d.decision is Decision.REMOVE for d in out.decisions)


def test_unknown_field_ids_are_ignored_and_surfaced(bec_bundle, policy_hold_analyst, aliases):
    spec = Spec(task_type="vendor_payment_hold", keep=["vendor.secret_sauce", "made.up"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    assert out.ignored_fields == ["made.up", "vendor.secret_sauce"]


def test_disallowed_op_removes_rather_than_guesses(bec_bundle, policy_fraud_analyst, aliases):
    """`card.last4` only permits drop. Asking for an alias must not silently fall back."""
    spec = Spec(task_type="fraud_investigation",
                transform=[{"field": "card.last4", "op": "alias"}])
    out = minimize(bec_bundle, spec, policy_fraud_analyst, aliases)
    d = next(x for x in out.decisions if x.field == "card.last4")
    assert d.decision is Decision.REMOVE


# --------------------------------------------------------------------------- #
# task-awareness: the answer to "isn't this just redaction?"
# --------------------------------------------------------------------------- #

def test_same_bundle_different_task_yields_different_payload(
    bec_bundle, policy_hold_analyst, policy_fraud_analyst, aliases
):
    hold = minimize(
        bec_bundle,
        Spec(task_type="vendor_payment_hold",
             keep=["vendor.account_changed", "invoice.injection_detected"]),
        policy_hold_analyst, aliases,
    )
    fraud = minimize(
        bec_bundle,
        Spec(task_type="fraud_investigation",
             keep=["txn.merchant", "txn.count"],
             transform=[{"field": "device.id", "op": "boolean_shared"}]),
        policy_fraud_analyst, aliases,
    )

    assert "vendor_account_changed" in hold.payload
    assert "vendor_account_changed" not in fraud.payload
    assert "device_id" in fraud.payload
    assert hold.payload.keys() != fraud.payload.keys()


def test_fraud_transforms_produce_the_shape_of_the_attack(
    bec_bundle, policy_fraud_analyst, aliases
):
    spec = Spec(task_type="fraud_investigation",
                keep=["txn.merchant", "txn.category", "txn.count", "txn.flags",
                      "employee.name", "device.id", "fraud.score",
                      "txn.amount_exact", "txn.timestamp"])
    out = minimize(bec_bundle, spec, policy_fraud_analyst, aliases)

    assert out.payload["device_id"] == {
        "shared": True, "distinct_devices": 1, "cards_involved": 2}
    assert out.payload["txn_timestamp"]["event_count"] == 4
    assert out.payload["fraud_score"] == "0.80–0.90"
    assert out.payload["txn_amount_exact"] == "$10k–$25k"
    assert out.payload["employee_name"] == ["Employee_7", "Employee_12"]
    assert out.payload["policy_violations"] == ["over transaction limit"]


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #

def test_metrics_are_computed_and_expose_nothing_sensitive(
    bec_bundle, policy_hold_analyst, aliases
):
    spec = Spec(
        task_type="vendor_payment_hold",
        keep=["vendor.account_changed", "vendor.days_since_account_change",
              "vendor.relationship_months", "vendor.prior_payments_stable",
              "invoice.injection_detected", "invoice.scheduled_in_hours", "txn.count"],
        transform=[{"field": "vendor.name", "op": "alias"},
                   {"field": "invoice.amount_exact", "op": "amount_band"}],
    )
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    m = M.compute(bec_bundle, out)

    assert m["available_units"] > m["sent_units"] > 0
    assert m["context_reduction_units"] > 0.5
    assert m["context_reduction_bytes"] > 0.5
    assert m["sensitive_available"] > 0
    assert m["sensitive_exposed"] == 0, f"exposed: {m['exposed_fields']}"
    assert m["estimated_exposure"] == 0.0


def test_a_raw_sensitive_keep_registers_as_exposed(bec_bundle, aliases):
    """Sanity check on the metric itself: it must be able to report a non-zero."""
    permissive = {"role": "controller", "task_type": "fraud_investigation",
                  "allow_fields": [], "deny_fields": [], "transform_required": {}}
    out = minimize(bec_bundle, Spec(task_type="fraud_investigation",
                                    keep=["employee.email"]), permissive, aliases)
    m = M.compute(bec_bundle, out)
    assert m["sensitive_exposed"] == 2
    assert m["exposed_fields"] == ["employee.email"]


def test_alias_is_not_counted_as_exposure(bec_bundle, policy_fraud_analyst, aliases):
    spec = Spec(task_type="fraud_investigation", keep=["employee.name"])
    out = minimize(bec_bundle, spec, policy_fraud_analyst, aliases)
    m = M.compute(bec_bundle, out)
    names = [d for d in out.decisions if d.field == "employee.name"]
    assert names[0].decision is Decision.TRANSFORM
    assert "employee.name" not in m["exposed_fields"]


def test_max_chars_sheds_fields_and_flags_truncation(bec_bundle, aliases):
    tight = {"role": "ap_analyst", "task_type": "spend_analysis",
             "allow_fields": [], "deny_fields": [], "transform_required": {}, "max_chars": 60}
    spec = Spec(task_type="spend_analysis",
                keep=["txn.merchant", "txn.category", "txn.count", "vendor.name"])
    out = minimize(bec_bundle, spec, tight, aliases)
    assert out.truncated
    assert len(json.dumps(out.payload, default=str)) <= 60


# --------------------------------------------------------------------------- #
# re-identification round trip
# --------------------------------------------------------------------------- #

def test_reidentification_round_trip(aliases):
    external_answer = (
        "Vendor_A shows an account change 3 days before payment. "
        "Employee_7 and Employee_12 both transacted on a shared device."
    )
    restored, n = aliases.reidentify(external_answer)
    assert n == 3
    assert "Industrious" in restored
    assert "Eleanor Bennett" in restored and "Daniel Green" in restored
    assert "Employee_1" not in restored  # Employee_12 must not be clipped


def test_required_transform_does_not_conscript_an_unrequested_field(
    bec_bundle, policy_hold_analyst, aliases
):
    """`transform_required` constrains how a field may travel, not whether it does.

    Regression guard: an earlier version treated a required transform as a mandate
    to emit, which quietly widened every payload beyond what the planner asked for.
    """
    spec = Spec(task_type="vendor_payment_hold", keep=["vendor.account_changed"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)

    assert "vendor.name" in policy_hold_analyst["transform_required"]
    assert "vendor_name" not in out.payload
    assert out.payload == {"vendor_account_changed": True}


def test_single_element_collections_keep_their_shape(
    bec_bundle, policy_fraud_analyst, aliases
):
    """A one-item set is still a set. Payload shape must not depend on the data."""
    spec = Spec(task_type="fraud_investigation", keep=["txn.flags"])
    out = minimize(bec_bundle, spec, policy_fraud_analyst, aliases)
    assert out.payload["policy_violations"] == ["over transaction limit"]
