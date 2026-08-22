"""The egress gate. This is the security argument, so it gets its own file."""
from __future__ import annotations

import inspect

import pytest

from app.escalate import external
from app.escalate.external import EnvelopeViolation, assert_minimized
from app.minimizer.minimize import minimize
from app.minimizer.spec import Spec


def test_a_real_minimize_result_passes_the_gate(bec_bundle, policy_hold_analyst, aliases):
    spec = Spec(task_type="vendor_payment_hold",
                keep=["vendor.account_changed", "invoice.injection_detected"])
    out = minimize(bec_bundle, spec, policy_hold_analyst, aliases)
    assert_minimized(out.envelope("Assess whether this payment should be held."))


@pytest.mark.parametrize("bad", [
    {"task": "t", "instructions_for_external_llm": "i", "context": {}, "bundle": {"x": 1}},
    {"task": "t", "instructions_for_external_llm": "i", "context": {"transactions": []}},
    {"task": "t", "instructions_for_external_llm": "i", "context": {"cards": []}},
    {"task": "t", "instructions_for_external_llm": "i", "context": "not a dict"},
    {"task": "t"},
])
def test_gate_rejects_anything_that_is_not_a_minimized_envelope(bad):
    with pytest.raises(EnvelopeViolation):
        assert_minimized(bad)


def test_escalate_takes_an_envelope_and_nothing_else():
    """Structural guarantee: there is no parameter through which a raw record
    could reach the network, so this cannot regress quietly."""
    params = list(inspect.signature(external.escalate).parameters)
    assert params == ["envelope"]


def test_escalate_module_never_touches_the_database():
    src = inspect.getsource(external)
    for forbidden in ("adb", "sdb", "pymongo", "motor", "get_bundle", "app.db"):
        assert forbidden not in src, f"egress module references {forbidden}"


@pytest.mark.asyncio
async def test_escalation_is_off_by_default():
    result = await external.escalate(
        {"task": "t", "instructions_for_external_llm": "i", "context": {"a": 1}})
    assert result.status == "disabled"
