#!/usr/bin/env bash
# Proof for "the agent survives its own sandbox".
#
# Starts the app, replays events, kills the process with SIGKILL mid-stream, restarts
# it, and shows that the resume token and the idempotency ledger agree: no gap, and
# no event processed twice.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
BASE="http://127.0.0.1:8000"

state() { curl -s "$BASE/api/mongo/status" | $PY -c \
  'import sys,json;d=json.load(sys.stdin)["change_stream"];print(f"    checkpoints={d[\"checkpoints\"]} last={d[\"last_event_id\"]} token={d[\"resume_token_stored\"]}")'; }
ledger() { $PY -c \
  'from app.db.client import sdb;print("    processed_events =", sdb().processed_events.count_documents({}))'; }

echo "==> starting app"
$PY -m app.main & APP=$!
sleep 5

echo "==> replaying 30 events"
curl -s -X POST "$BASE/api/stream/replay" -H 'content-type: application/json' \
  -d '{"limit":30}' >/dev/null
sleep 6
echo "==> state before the kill"; state; ledger

echo "==> SIGKILL $APP  (no cleanup, no graceful shutdown)"
kill -9 $APP 2>/dev/null || true
wait $APP 2>/dev/null || true
sleep 1

echo "==> restarting"
$PY -m app.main & APP2=$!
sleep 6
echo "==> state after restart"; state; ledger

echo "==> replaying 20 more"
curl -s -X POST "$BASE/api/stream/replay" -H 'content-type: application/json' \
  -d '{"limit":20}' >/dev/null
sleep 5
state; ledger

echo
echo "PASS if: checkpoints kept climbing across the kill, the resume token survived,"
echo "and processed_events grew by the number of NEW events only."
kill $APP2 2>/dev/null || true
