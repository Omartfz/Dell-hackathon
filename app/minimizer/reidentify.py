"""The alias map — the re-identification key.

Aliases are how a real identity survives a trip off the box: the external model is
shown `Vendor_A`, reasons about `Vendor_A`, and answers about `Vendor_A`. We swap the
real names back in *here*, locally, so the analyst reads `Industrious`.

The map itself never leaves this machine. Treat it like a credential.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def _stable_index(ref_id: str, modulo: int = 90) -> int:
    """Deterministic small integer from an id. No RNG, so the demo is repeatable."""
    h = 0
    for ch in ref_id:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return (h % modulo) + 1


_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def derive_alias(ref_id: str, kind: str) -> str:
    if kind == "vendor":
        return f"Vendor_{_LETTERS[_stable_index(ref_id, len(_LETTERS)) - 1]}"
    if kind == "employee":
        return f"Employee_{_stable_index(ref_id)}"
    if kind == "merchant":
        return f"Merchant_{_LETTERS[_stable_index(ref_id, len(_LETTERS)) - 1]}"
    return f"Entity_{_stable_index(ref_id)}"


@dataclass
class AliasMap:
    """Bidirectional. `forward` is used on the way out, `reverse` on the way back."""

    forward: dict[str, str] = field(default_factory=dict)   # real value or id -> alias
    reverse: dict[str, str] = field(default_factory=dict)   # alias -> display name

    @classmethod
    def from_docs(cls, docs: list[dict]) -> "AliasMap":
        m = cls()
        for d in docs:
            alias = d.get("alias")
            if not alias:
                continue
            display = d.get("display") or d.get("ref_id") or alias
            for key in (d.get("ref_id"), d.get("display")):
                if key:
                    m.forward[str(key)] = alias
            m.reverse[alias] = display
        return m

    def register(self, ref_id: str, display: str, kind: str) -> str:
        """Idempotent. Used when the stream meets an entity the seed didn't alias."""
        if ref_id in self.forward:
            return self.forward[ref_id]
        alias = derive_alias(ref_id, kind)
        # Collision-safe: widen with the stable index if the short form is taken.
        if alias in self.reverse and self.reverse[alias] != display:
            alias = f"{alias}_{_stable_index(ref_id, 999)}"
        self.forward[ref_id] = alias
        self.forward[display] = alias
        self.reverse[alias] = display
        return alias

    def to_alias(self, value: str) -> str:
        return self.forward.get(str(value), str(value))

    def is_aliased(self, value: str) -> bool:
        return str(value) in self.forward

    def reidentify(self, text: str) -> tuple[str, int]:
        """Swap aliases back to real names in a model response. Returns (text, n_swapped)."""
        if not text or not self.reverse:
            return text, 0
        # Longest first so Employee_12 is not clobbered by Employee_1.
        keys = sorted(self.reverse, key=len, reverse=True)
        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b")
        count = 0

        def _sub(m: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return self.reverse[m.group(1)]

        return pattern.sub(_sub, text), count

    def as_docs(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for alias, display in self.reverse.items():
            seen[alias] = {"alias": alias, "display": display}
        return list(seen.values())
