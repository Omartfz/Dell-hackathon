"""Boot check. Runs with or without Mongo and Ollama — it must degrade, not crash.

Useful on the box before the demo: it tells you exactly which dependency is missing
and what still works without it.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.main import app


def main() -> int:
    bad = 0
    with TestClient(app) as c:
        r = c.get("/")
        print(f"  GET /               {r.status_code}")
        bad += r.status_code != 200

        for asset in ("/static/app.js", "/static/styles.css"):
            r = c.get(asset)
            print(f"  GET {asset:<16}{r.status_code}  {len(r.content):>6} bytes")
            bad += r.status_code != 200

        r = c.get("/api/health")
        print(f"  GET /api/health     {r.status_code}")
        bad += r.status_code != 200
        h = r.json()
        rs = h["mongo"]["replica_set"]
        model = h["inference"]["local_model"]
        print(f"     mongo replica set : {rs}")
        if not rs:
            print(f"       -> {h['mongo']['detail']}")
        print(f"     local model       : {model or 'NONE (tier 1 will be skipped)'}")
        print(f"     escalation enabled: {h['escalation']['enabled']}")

        r = c.post("/api/stream/start")
        expect = 200 if rs else 409
        print(f"  POST /api/stream/start {r.status_code} (expected {expect})")
        bad += r.status_code != expect

    print("\n  OK — app boots and reports its own state honestly" if not bad
          else f"\n  {bad} check(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
