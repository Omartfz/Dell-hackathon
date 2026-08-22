# 08. System design

What the Shopify hackathon called “two screens + a live quote.” Ours is **one minimizer console + a copy envelope**. The live agent is on the GB10; `site/console.html` is a **simulated** twin (chip on the page).

## Boundary

```
┌─────────────────────────────────────────────┐
│  Dell GB10  (trusted)                       │
│                                             │
│  MongoDB     customers · policies · tickets │
│      ↑                                      │
│  OpenClaw    whoami · find · bundle · policy│
│  + local Qwen     proposes spec JSON        │
│      ↓                                      │
│  minimize()  KEEP / TRANSFORM / REMOVE      │
│      ↓                                      │
│  envelope    { task, context }              │
└──────────────────┬──────────────────────────┘
                   │ copy (human)
                   ▼
            Claude / Copilot   (untrusted)
```

Nothing in our process calls Anthropic. Ticket bodies never enter `context`.

## Why this split

| Piece | Sees full Acme | Why |
|---|---|---|
| Qwen planner | yes | Must choose fields |
| `minimize()` | yes, then strips | Exact metrics |
| External LLM | **no** | Product |

## Tools (five)

`whoami` → `find_customer` → `get_customer_bundle` → `get_policy` → `submit_spec`

No `query_mongo`, no `http_fetch`, no `call_external_llm`.

## Data (Mongo is the SoR)

users, customers, contracts, usage_monthly, tickets, internal_notes, projects, documents, policies, field_catalog.

Changing `users.role` or a policy document changes the next outbound spec.

## Stack

NemoClaw installs OpenClaw + OpenShell. Inference: Ollama `qwen3.6:35b` (or `qwen3.5:9b`) **on the GB10**. UI for the real demo: Streamlit on the box. Vitrine: `site/`.

## Honesty

`site/console.html` wears **Simulated**. Counts there are the PRD Acme story, not a live `metrics()` call. When Streamlit is up, that is the source of truth.
