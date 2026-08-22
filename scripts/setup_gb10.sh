#!/usr/bin/env bash
# Full box setup. Run this on the GB10, in the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "════ SafeContext · GB10 setup ════"
echo "==> arch: $(uname -m)   $(head -n1 /etc/os-release 2>/dev/null || true)"
if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "arm64" ]; then
  echo "!!  not aarch64 — check you are on the box, not the laptop"
fi
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total \
  --format=csv,noheader 2>/dev/null || echo "    (no nvidia-smi; fine for a dry run)"

echo
echo "==> 1/4 python venv"
python3 -m venv .venv
./.venv/bin/pip install -q -U pip
./.venv/bin/pip install -q -r requirements.txt
echo "    deps installed"

echo
echo "==> 2/4 MongoDB Community"
bash scripts/setup_mongo.sh

echo
echo "==> 3/4 local model"
MODEL="${OLLAMA_MODEL:-nemotron3-nano:30b}"
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${MODEL%%:*}"; then
    echo "    '$MODEL' already present"
  else
    echo "    pulling $MODEL on THIS box (never copy weights from another machine)"
    ollama pull "$MODEL" || {
      echo "!!  pull failed — trying a smaller fallback"
      ollama pull nemotron3-nano:9b || ollama pull qwen3.5:9b || true
    }
  fi
  ollama list || true
else
  cat <<'MSG'
    ollama not on PATH. Install the NVIDIA stack first:
      curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
    Choose Express install with LOCAL inference. Then re-run this script.
    SafeContext still starts without it: tiers 0 and 2 work, tier 1 is skipped.
MSG
fi

echo
echo "==> 4/4 seed"
./.venv/bin/python -m app.db.seed

echo
echo "════ ready ════"
echo "  start:  ./run.sh"
echo "  open:   http://127.0.0.1:8000   (on the box)"
