#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || { echo "run scripts/setup_gb10.sh first"; exit 1; }
exec ./.venv/bin/python -m app.main
