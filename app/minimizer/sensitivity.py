"""Sensitivity taxonomy and the fields that may never leave the box."""
from __future__ import annotations

from enum import Enum


class Sensitivity(str, Enum):
    INTERNAL = "INTERNAL"
    PII = "PII"
    PCI = "PCI"
    FINANCIAL = "FINANCIAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    MNPI = "MNPI"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"


#: Counted as sensitive when computing the exposure report.
SENSITIVE = frozenset(
    {
        Sensitivity.PII,
        Sensitivity.PCI,
        Sensitivity.FINANCIAL,
        Sensitivity.CONFIDENTIAL,
        Sensitivity.MNPI,
        Sensitivity.HIGHLY_SENSITIVE,
    }
)

#: Hard floor. No spec, policy, role, or task can put these in an outbound payload.
#: minimize() enforces this last, after every other rule has had its say.
NEVER_OUTBOUND = frozenset(
    {
        "card.pan",
        "card.last4",
        "vendor.bank_account",
        "vendor.routing",
        "invoice.body",
    }
)


class Decision(str, Enum):
    KEEP = "KEEP"
    TRANSFORM = "TRANSFORM"
    REMOVE = "REMOVE"


class Source(str, Enum):
    """Who made the call — shown in the decision log so the trace is auditable."""

    AGENT = "agent"
    POLICY = "policy"
    CATALOG = "catalog"      # NEVER_OUTBOUND floor
    DEFAULT = "default"      # not mentioned by the agent, dropped conservatively
