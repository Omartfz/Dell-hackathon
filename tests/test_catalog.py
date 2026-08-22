"""Catalog invariants — the allow-list has to hold its shape."""
from __future__ import annotations

from app.minimizer import catalog
from app.minimizer.sensitivity import NEVER_OUTBOUND
from app.minimizer.transforms import OPS


def test_every_never_outbound_field_exists_and_only_permits_drop():
    for fid in NEVER_OUTBOUND:
        d = catalog.CATALOG.get(fid)
        assert d is not None, f"{fid} is in NEVER_OUTBOUND but not in the catalog"
        assert d.allowed_ops == {"drop"}, f"{fid} must not permit any emitting op"


def test_every_allowed_op_is_implemented():
    for d in catalog.CATALOG.values():
        for op in d.allowed_ops:
            assert op in OPS, f"{d.field_id} allows unimplemented op '{op}'"


def test_output_keys_are_unique():
    keys = [d.key for d in catalog.CATALOG.values()]
    assert len(keys) == len(set(keys)), "two fields would collide in the payload"


def test_extractors_tolerate_a_junk_bundle():
    """A malformed bundle must not take the stream down."""
    for junk in ({}, {"transactions": None}, {"vendor": "not a dict"},
                 {"invoices": [{}]}, {"employees": [{"name": None}]}):
        assert isinstance(catalog.available_units(junk), dict)


def test_available_units_counts_instances_not_fields(bec_bundle):
    units = catalog.available_units(bec_bundle)
    assert len(units["employee.name"]) == 2      # two people
    assert len(units["txn.amount_exact"]) == 4   # four transactions
    assert len(units["vendor.name"]) == 1        # one scalar
