"""Flip the operator's role. One document write; the next escalation differs."""
from __future__ import annotations

import sys

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import sdb

ROLES = ("ap_analyst", "controller")

if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else None
    db = sdb()
    user = db.users.find_one({"_id": "avery"}) or {}
    if role not in ROLES:
        role = "controller" if user.get("role") == "ap_analyst" else "ap_analyst"
    db.users.update_one({"_id": "avery"}, {"$set": {"role": role}}, upsert=True)
    print(f"avery: {user.get('role', '?')} -> {role}")
    pol = db.policies.find_one({"role": role, "task_type": "fraud_investigation"})
    if pol:
        print(f"  next fraud escalation uses {pol['_id']}")
        print(f"  notes.body allowed: {'notes.body' in (pol.get('allow_fields') or [])}")
