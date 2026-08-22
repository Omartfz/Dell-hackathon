# CLAUDE.md — contract for Claude Code on the GB10

You are building **SafeContext** on **this Dell GB10**. This machine is the only demo host.

Read and obey, in order:

1. This file
2. [TASKS.md](TASKS.md) — execute top to bottom
3. [docs/prd/05-always-on-spend.md](docs/prd/05-always-on-spend.md) — **the current product**
4. [docs/prd/02-features.md](docs/prd/02-features.md) — mechanism: `minimize()`, catalog, policy, metrics
5. [docs/prd/04-gb10.md](docs/prd/04-gb10.md) — machine contract
6. [docs/prd/01-overview.md](docs/prd/01-overview.md), [03-demo.md](docs/prd/03-demo.md) — **superseded on domain, UI, and interaction model** by PRD 05. The mechanism sections still hold.

## Product (one sentence)

An **always-on** local agent that watches a live stream of spend transactions and documents, reasons about every one of them on this box, and for the small number it cannot resolve locally, emits the **minimum sufficient payload** for an external model — plus an exposure report proving what was withheld.

Everything runs **on this GB10**: install, model download, Mongo, app, demo. No other machine.

## The escalation ladder

| Tier | Handler | Leaves the box? |
|---|---|---|
| 0 | Rules + deterministic scoring | No — 0 bytes |
| 1 | Local Qwen on this GB10 | No — 0 bytes |
| 2 | External model | **Minimized payload only** |

Tiers 0 and 1 must work with the network unplugged. That is a demo requirement, not a nice-to-have.

## The one permitted external call

Tier 2 is the **only** thing that may leave this box, and it is constrained structurally:

- One module: `app/escalate/external.py`. Its entry point accepts the envelope returned by `submit_spec` and **nothing else**.
- The raw bundle must not be in scope at that call site — no `bundle` parameter, no closure over it, no re-read from Mongo inside it.
- The external SDK may be installed **only** for that module.
- Everything else — planner, triage, preview, re-identification — is **localhost only**.
- If the external call is unavailable, **queue the envelope** and surface `N escalations queued — offline`. Never fail the stream.
- Fallback: if the round-trip is unreliable on the day, render the envelope with a Copy button and let a human paste it. The exposure report is the product either way.

## Hard rules

- Planner, triage, and preview inference = **localhost** (Ollama or vLLM installed by NemoClaw). Never the external model.
- **Pull/download models on this GB10** (`ollama pull` or NemoClaw Express). Never fetch weights from another PC.
- **Do not** install LangGraph, vector DBs, embeddings, or PDF parsers.
- **Do not** add tools: `query_mongo`, `http_fetch`, `call_external_llm`, `send_raw`. The planner never calls out.
- Agent proposes KEEP/TRANSFORM/REMOVE **spec JSON**. Python `minimize()` executes. Policy **wins**.
- These **never** appear in an outbound payload, for any role, task, or spec:
  `card.pan`, `card.last4`, `vendor.bank_account`, `vendor.routing`, `invoice.body`
- The `aliases` collection is the re-identification key. It **never** leaves the box. Treat it like a credential.
- Every Tier-2 event is written to `escalations` — payload sent, decisions, metrics, approval. That is the audit trail.
- Metrics are **computed**, never hardcoded (no fake 85%).
- Do not invent NemoClaw/OpenClaw/OpenShell flags. Read `--help` and installed docs on **this** box.
- If OpenClaw skill APIs are unclear: Python tool-loop + local Qwen. Say so. Do not block the demo.
- Arch is `aarch64`. Never pull `linux/amd64` images.
- Smallest code that demos. Wire into the existing console if it is on this box; **Streamlit is the fallback** and is perfectly acceptable.

## Kickoff (human pastes this)

> Execute TASKS.md from T0 to T14 on this GB10. Pull the model on this machine. Gate on local `hello` before product code. Build SafeContext per CLAUDE.md and docs/prd/05-always-on-spend.md. Planner is local only; the sole external call takes `minimize()` output. Do everything on this box. Commit locally when each task's acceptance passes.
