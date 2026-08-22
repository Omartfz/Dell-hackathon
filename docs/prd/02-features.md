# SafeContext — PRD 02 Features & functional spec

Companion to [01-overview.md](./01-overview.md). This is the build contract.

---

## 1. User journey (v1)

```
Enter task  →  Agent retrieves Mongo context  →  Agent proposes spec
    →  minimize() + policy  →  Exposure report + copy-ready payload
    →  User pastes payload into Claude (out of band)
```

Optional (recommended on stage): a **local preview** — second Qwen call that receives **only** the minimized payload, labeled “Preview (local), not Claude.” Does not replace Copy.

## 2. Features

### F1 — Task intake

- Single text field for the user request.
- Optional `user_id` (defaults to seeded sales rep `jordan`).
- No file upload in v1.

**Acceptance:** Submitting “Analyze why Acme is likely to churn.” starts a run and shows progress.

### F2 — MongoDB as system of record

Collections (all required):

| Collection | Role |
|---|---|
| `users` | Identity + `role` (`sales_rep` / `sales_manager`) |
| `customers` | Account, status, PII contact, `owner_user_id` |
| `contracts` | Exact ARR, term, renewal date |
| `usage_monthly` | Seat counts over months |
| `tickets` | Severity + bodies (one body is prompt injection) |
| `internal_notes` | Confidential commentary |
| `projects` | `classification` (e.g. confidential) |
| `documents` | Seeded “files” (contract excerpt, usage export as text) |
| `policies` | Per `role` + `task_type`: allow / deny / transform defaults, `max_chars` |
| `field_catalog` | Canonical field IDs, sensitivity, allowed ops |

Relationships: `user → role → owns customer → contracts / usage / tickets / notes / documents / project`.

**Acceptance:** Editing `users.role` or a `policies` document and re-running the same task changes the outbound payload. Mongo is not a log.

### F3 — Agentic retrieval (not RAG)

The planner (local Qwen via OpenClaw) **chooses tools**. It must not receive a hardcoded field list in Python keyed on task name.

**Tools (only these five):**

| Tool | Returns | Why |
|---|---|---|
| `whoami(user_id)` | user + role | Policy is per-role |
| `find_customer(query)` | `id`, `name`, `status` only | Resolve “Acme” without dumping the record |
| `get_customer_bundle(customer_id)` | Full related docs for the planner | Candidate context = **100% available** for that customer |
| `get_policy(role, task_type)` | allow / deny / max_chars | Mongo changes what may leave |
| `submit_spec(spec)` | minimized payload + exposure report (+ optional local preview) | **Only** output path. No raw bundle egress |

**Forbidden tools:** `query_mongo`, `run_aggregation`, `http_fetch`, `call_external_llm`, `send_raw`.

**Acceptance:** Traces show tool calls. Changing Mongo changes subsequent `get_policy` / bundle contents and the spec.

### F4 — Task understanding

Planner outputs **only** JSON:

```json
{
  "task_type": "churn_analysis | renewal_outreach | other",
  "customer_hint": "Acme",
  "keep": ["customer.status", "contract.term_months"],
  "transform": [
    { "field": "contract.arr_exact", "op": "arr_band" }
  ],
  "drop": ["contact.email", "contact.phone"],
  "reasons": {
    "contact.email": "Not necessary for churn analysis",
    "contract.arr_exact": "Magnitude is enough; exact ARR is not"
  }
}
```

`analyze_task_requirements` / `classify_information` are **prompts**, not tools.

**Acceptance:** Churn vs renewal-email on the same bundle produce different `keep` / `transform` / `drop` sets (see [03-demo.md](./03-demo.md)).

### F5 — Deterministic minimization

`minimize(bundle, spec, policy, catalog) → { payload, decisions, metrics }`

Rules (policy wins over the agent):

1. Only **catalog field IDs** may appear in the payload.
2. Unknown field IDs in the spec are ignored (logged).
3. `deny` in policy → REMOVE even if the agent said KEEP.
4. `tickets.bodies` is **never** outbound (injection surface).
5. Allowed ops: `keep`, `drop`, `arr_band`, `alias`, `trend`, `severity_counts`.
6. Each decision stores `{ field, decision, reason, sensitivity, source }`.
7. Agent reasons are kept if the decision stands; if policy overrides, reason = `"Blocked by policy ({role}, {task_type})"`.

**Transforms:**

| Op | Example |
|---|---|
| `arr_band` | `847291` → `"$500k–$1M"` (fixed band table in code) |
| `alias` | stable alias per entity id, stored in Mongo `aliases` **or** derived `Customer_A` / `Person_12` from id (deterministic, no LLM) |
| `trend` | monthly seats → `{ start, end, pct_change, direction }` |
| `severity_counts` | tickets → `{ sev1: 4, sev2: 1 }` without bodies |

**Acceptance:** Unit tests on the Acme bundle: email never in payload for churn + `sales_rep`; ARR exact never in payload when `arr_band` applied; ticket body with injection never in payload.

### F6 — Exposure report

**Information unit** = one catalog field instance on the customer bundle (e.g. `contact.email`, `contract.arr_exact`, one `internal_notes.body`).

| Metric | Definition |
|---|---|
| `available_units` | Count of catalog fields present on the bundle |
| `retrieved_units` | Same as available in v1 (bundle is the retrieval). If later tools fetch subsets, count only fetched fields |
| `sent_units` | Fields present in minimized payload (a transform still counts as 1 unit sent, with `decision=TRANSFORM`) |
| `context_reduction` | `1 - sent_units / available_units` and `1 - sent_bytes / available_bytes` (`len(json.dumps(...))`) |
| `sensitive_available` | Units with sensitivity in `{PII, FINANCIAL, CONFIDENTIAL, HIGHLY_SENSITIVE}` |
| `sensitive_exposed` | Those still present in payload **after** transform (PII kept as raw = exposed; ARR after `arr_band` = not exact-financial exposed) |
| `estimated_exposure` | `sensitive_exposed / max(sensitive_available, 1)` — label **Estimated Context Exposure**, not a risk probability |
| `task_success` | Rubric in [03-demo.md](./03-demo.md), not vibes |

Optional: token counts if a tokenizer is already on the box; otherwise bytes are enough. Do not fake tokens.

**Acceptance:** UI numbers match `metrics()` output for the run. Never hardcoded 83 / 12 / 85%.

### F7 — Copy-ready payload

Outbound object:

```json
{
  "task": "Analyze why Acme is likely to churn.",
  "instructions_for_external_llm": "Use only this context. Do not assume withheld fields.",
  "context": { }
}
```

UI: Copy button. This is the product handoff to Claude.

**Acceptance:** Payload contains no `contact.email`, `contact.phone`, raw `arr_exact`, `tickets.bodies`, or `sales_rep`-denied notes on Scenario 1.

### F8 — Naive baseline (not RAG)

Two computed columns for the same task:

| Mode | What is “sent” (for metrics only) |
|---|---|
| Naive full | Entire `get_customer_bundle` JSON |
| SafeContext | `minimize()` payload |

v1 does **not** build vector RAG. If a third column is added later: “raw related documents as text, no field strip” — still not embeddings.

**Acceptance:** Table shows live unit/byte counts for both modes.

### F9 — Decision trace

For every catalog field on the bundle: KEEP / REMOVE / TRANSFORM, reason, sensitivity.

**Acceptance:** Demo can be walked field-by-field (“email removed because …”).

### F10 — Local preview (optional, recommended)

Second local model call: `{ task, context }` **minimized only**. Label: Preview (local). If Qwen is down, skip; Copy still works.

## 3. UI (one page)

Prefer Streamlit or a single FastAPI + HTML page. Not React unless spare time.

Must show:

1. Task input + Run
2. Agent progress / tool trace (compact)
3. Copy-ready payload
4. Exposure stats: available, sent, reduction, sensitive exposed / available, task success
5. Decision log (F9)
6. Naive vs SafeContext counts (F8)
7. Optional local preview text

Value must be obvious in 10 seconds: **BEFORE n units → AFTER m units**.

## 4. Agent runtime

- **Planner:** OpenClaw + local Qwen. System prompt: propose spec from field **names/shapes** + policy allow-list; do not copy raw secrets into the spec values.
- **Spine (inspectable, not LangGraph):** `understand → retrieve → plan_spec → execute_minimize → report`. Agentic choices live inside retrieve + plan_spec.
- **OpenShell / NemoClaw:** If onboarded, run the app as the sandbox workload; egress allowlist should not include arbitrary HTTP. **Unverified until docs on the box are read.** Do not block Scenario 1 on sandbox YAML.
- **Fallback:** Same Python app on GB10 without OpenClaw wrap. Say so honestly.

## 5. Field catalog (v1)

| Field ID | Sensitivity | Churn default | Renewal-email default |
|---|---|---|---|
| `customer.name` | INTERNAL | REMOVE or `alias` | KEEP (company) |
| `customer.status` | INTERNAL | KEEP | KEEP |
| `contact.email` | PII | REMOVE | KEEP if needed for “email the AM” **account manager** — customer email still REMOVE unless task needs it |
| `contact.phone` | PII | REMOVE | REMOVE |
| `account_manager.name` | INTERNAL | REMOVE | KEEP |
| `account_manager.email` | PII | REMOVE | KEEP |
| `contract.arr_exact` | FINANCIAL | `arr_band` | `arr_band` |
| `contract.term_months` | INTERNAL | KEEP | KEEP |
| `contract.renewal_date` | INTERNAL | KEEP | KEEP |
| `usage.trend` | INTERNAL | `trend` | optional |
| `tickets.severity_counts` | INTERNAL | `severity_counts` | optional |
| `tickets.bodies` | HIGHLY_SENSITIVE | never outbound | never outbound |
| `notes.body` | CONFIDENTIAL | deny `sales_rep`; allow `sales_manager` | deny `sales_rep` |

These defaults are **hints in the planner prompt**, not `if task ==` in Python. Policy documents can override.

## 6. Policy document shape

```json
{
  "role": "sales_rep",
  "task_type": "churn_analysis",
  "external": true,
  "allow_fields": ["customer.status", "contract.term_months", "contract.renewal_date", "usage.trend", "tickets.severity_counts"],
  "deny_fields": ["contact.email", "contact.phone", "notes.body", "tickets.bodies"],
  "transform_required": { "contract.arr_exact": "arr_band" },
  "max_chars": 4000
}
```

A second policy for `sales_manager` + `churn_analysis` allows `notes.body`. A third for `sales_rep` + `renewal_outreach` allows `account_manager.name` and `account_manager.email`.

## 7. Quality bar

Do not optimize reduction blindly. Task success is defined in [03-demo.md](./03-demo.md). A run with 90% reduction that omits usage trend + ticket load + renewal horizon **fails**.
