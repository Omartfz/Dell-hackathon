"""Instruction-injection detection over free-text document bodies.

Two jobs, and the second one is the interesting one:

1. Defensive — `invoice.body` is in NEVER_OUTBOUND, so an injected instruction can
   never reach an external model through us. That is handled by the catalog floor,
   not here.
2. Evidential — a legitimate vendor does not write "ignore previous instructions"
   on an invoice. The presence of an injection pattern is *itself* a fraud signal,
   so we detect it, raise the risk score, and let the boolean travel outbound while
   the body stays home. The signal travels; the payload does not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override",   re.compile(r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?\b", re.I)),
    ("override",   re.compile(r"\bdisregard\s+(all\s+)?(previous|prior|the\s+above)\b", re.I)),
    ("persona",    re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(admin|administrator|system)\b", re.I)),
    ("exfil",      re.compile(r"\bsend\s+(the\s+)?(entire|full|complete|all)\b.{0,40}\b(record|data|database|file)s?\b", re.I)),
    ("exfil",      re.compile(r"\b(forward|email|post|upload)\b.{0,30}\b(to\s+)?(an?\s+)?external\b", re.I)),
    ("authority",  re.compile(r"\b(system|admin|developer)\s*(:|prompt\b|override\b)", re.I)),
    ("confirm",    re.compile(r"\bconfirm\s+the\s+(updated|new|revised)\s+bank\s+account\b", re.I)),
    ("urgency",    re.compile(r"\b(do\s+not|don'?t)\s+(verify|confirm|call|contact)\b", re.I)),
]


@dataclass(frozen=True)
class InjectionFinding:
    detected: bool
    categories: tuple[str, ...]
    match_count: int
    #: Bounded contribution to the risk score. Evidence, not a verdict.
    risk_delta: float

    def as_dict(self) -> dict:
        return {
            "detected": self.detected,
            "categories": list(self.categories),
            "match_count": self.match_count,
            "risk_delta": self.risk_delta,
        }


def scan(text: str | None) -> InjectionFinding:
    if not text or not isinstance(text, str):
        return InjectionFinding(False, (), 0, 0.0)

    cats: list[str] = []
    count = 0
    for name, pat in _PATTERNS:
        found = pat.findall(text)
        if found:
            count += len(found)
            cats.append(name)

    if not count:
        return InjectionFinding(False, (), 0, 0.0)

    ordered = tuple(sorted(set(cats)))
    # Distinct categories matter more than repetition: three different tricks in one
    # document is a stronger signal than the same phrase six times. The two terms are
    # capped *separately* — a single shared ceiling let pure repetition saturate the
    # score and drew level with genuine variety.
    variety = min(0.30, 0.10 * len(ordered))
    repetition = min(0.05, 0.01 * (count - len(ordered)))
    return InjectionFinding(True, ordered, count, round(variety + repetition, 3))


def redact_preview(text: str, width: int = 160) -> str:
    """A short, safe excerpt for the UI. Never leaves the box — display only."""
    if not text:
        return ""
    for _, pat in _PATTERNS:
        m = pat.search(text)
        if m:
            start = max(0, m.start() - width // 3)
            return ("…" if start else "") + text[start:m.end() + width // 3].strip() + "…"
    return text[:width].strip() + ("…" if len(text) > width else "")
