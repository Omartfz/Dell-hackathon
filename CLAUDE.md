# CLAUDE.md — contract for Claude Code on the GB10

You are building **SafeContext** on **this Dell GB10**. This machine is the only demo host.

Read and obey, in order:

1. This file
2. [TASKS.md](TASKS.md) — execute top to bottom
3. [docs/prd/01-overview.md](docs/prd/01-overview.md)
4. [docs/prd/02-features.md](docs/prd/02-features.md)
5. [docs/prd/03-demo.md](docs/prd/03-demo.md)
6. [docs/prd/04-gb10.md](docs/prd/04-gb10.md)

## Product (one sentence)

Local agent: given a task + MongoDB business data, emit the **minimum sufficient JSON payload** for a human to paste into Claude, plus an exposure report. **You never call Claude/Anthropic/OpenAI cloud.**

Everything runs **on this GB10**: install, model download, Mongo, app, demo. No other machine.

## Hard rules

- All planner/preview inference = **localhost** (Ollama or vLLM installed by NemoClaw).
- **Pull/download models on this GB10** (`ollama pull` or NemoClaw Express). Never fetch weights from another PC.
- **Do not** install LangGraph, vector DBs, embeddings, PDF parsers, `anthropic`, cloud OpenAI.
- **Do not** add tools: `query_mongo`, `http_fetch`, `call_external_llm`, `send_raw`.
- Agent proposes KEEP/TRANSFORM/REMOVE **spec JSON**. Python `minimize()` executes. Policy **wins**.
- `tickets.bodies` **never** appear in outbound payload (prompt-injection surface).
- Metrics are **computed**, never hardcoded (no fake 85%).
- Do not invent NemoClaw/OpenClaw/OpenShell flags. Read `--help` and installed docs on **this** box.
- If OpenClaw skill APIs are unclear: Python tool-loop + local Qwen. Say so. Do not block the demo.
- Arch is `aarch64`. Never pull `linux/amd64` images.
- Smallest code that demos. Streamlit UI, not React.

## Kickoff (human pastes this)

> Execute TASKS.md from T0 to T12 on this GB10. Pull the model on this machine. Gate on local `hello` before product code. Build SafeContext per CLAUDE.md and docs/prd. No cloud LLM APIs. Do everything on this box. Commit locally when each task’s acceptance passes.
