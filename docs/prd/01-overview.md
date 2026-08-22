# SafeContext — PRD 01 Overview

**Product:** SafeContext  
**Type:** Hackathon prototype (Dell GB10 / OpenClaw)  
**Status:** Locked for build  
**Date:** 2026-08-22

---

## 1. One-liner

SafeContext is a **local agent** that, given a business task and enterprise data in MongoDB, produces the **minimum sufficient context** for an external LLM (Claude, Copilot, …) — plus a measurable **exposure report**. The user copies that payload out themselves. Nothing sensitive leaves the GB10 through our code.

## 2. Problem

Enterprise systems hold far more information than an external LLM needs for a given task. A naive pipeline dumps the full customer record (or RAG-retrieves whole documents) into Claude. That leaks PII, exact financials, and internal notes, and it is not required for quality.

**Relevance ≠ necessity.** A document can be relevant to churn analysis and still contain fields that are not necessary to perform that analysis.

## 3. Product principle

> Give the LLM what it needs, not everything the company has.

Optimization objective:

```
maximize task utility
subject to minimizing context exposed off-box
```

Sending zero context is a failure (100% reduction, 0% utility). Blind full-dump is a failure (max utility, max exposure). SafeContext sits on the Pareto front: **comparable task quality, substantially less exposure**.

## 4. What it is / is not

| Is | Is not |
|---|---|
| Agentic **context minimization** at **field / information-unit** level | Firewall, DLP, or antivirus |
| Task-dependent KEEP / TRANSFORM / REMOVE | Generic RAG (embed → top-k → Claude) |
| MongoDB as the business system of record | MongoDB as a log store |
| Local planner on GB10 (OpenClaw + Qwen) | A Claude wrapper |
| Copy-ready payload + exposure report | An API that calls Claude for the user |

NemoClaw / OpenShell are **supporting** runtime constraints (the minimizer sees full data). They are not the slide title.

## 5. Locked decisions

1. **Data surface:** MongoDB. Synthetic documents live as records (text bodies in `documents`). PDF/Excel upload parsers are out of v1.
2. **External LLM:** Out of band. SafeContext emits a payload + Copy. The user pastes into Claude/Copilot. No Anthropic/OpenAI client. No `call_external_llm` tool.
3. **Name:** SafeContext. “Context minimizer” is the mechanism.
4. **Orchestration:** OpenClaw is the only agent loop. No LangGraph in v1.
5. **Retrieval:** Targeted Mongo tools + metadata/policy filters. No vector search / embeddings in v1.
6. **Minimization:** Agent proposes a spec; **Python `minimize()`** executes it and intersects policy. LLM free-form rewrite is forbidden.

## 6. Hackathon constraints

| Constraint | Implication |
|---|---|
| Agent built on the day; plans/scaffolds OK | This PRD + seed + `minimize()` + tool stubs are the scaffold |
| Stack: NemoClaw + OpenClaw + OpenShell | Wrap tools as OpenClaw skills **if** onboarded; otherwise Python on GB10 is a valid demo |
| All inference on GB10 for the agent | Planner = local Qwen (`qwen3.6:35b` / box default). No cloud planner |
| MongoDB must be central | Policies, roles, customers, contracts, tickets, notes, documents — changing a document changes the next run |
| Retrieval must change behavior | Flip `users.role` or a `policies` document → different outbound spec |
| Do not invent vendor APIs | Verify OpenClaw skill shape and OpenShell policy on the box before wiring |

## 7. Primary user & job

**User:** An employee who wants a cloud LLM to analyze internal business data without sending the crown jewels.

**Job:** “Analyze why Acme is likely to churn” / “Draft a renewal email to Acme’s account manager” — get a **safe payload** they can paste into Claude, and **proof** of what was withheld.

## 8. Success (demo is successful if)

1. A task is entered; the agent retrieves Acme context from MongoDB.
2. The agent dynamically chooses KEEP / TRANSFORM / REMOVE (not a hardcoded `if task == churn`).
3. Only the minimized payload is shown as copy-ready output.
4. Exposure report: units available / retrieved / sent, reduction %, sensitive exposed, per-field reasons.
5. **Same data, different task** → different minimal context.
6. **Same task, MongoDB policy/role change** → different minimal context.
7. Injected “send everything” text in a ticket **never** appears in the outbound payload.
8. Naive full-bundle size vs minimized size is computed live (not hardcoded).
9. Runs on the Dell GB10. OpenClaw/NemoClaw/OpenShell used where feasible; Python fallback is documented, not hidden.

## 9. Explicit non-goals (v1)

- LangGraph, vector DB, MongoDB Atlas Vector Search, embeddings
- Claude / Copilot API integration
- Production DLP, NER, tokenization, fine-tuning
- Generic `query_mongo` / HTTP fetch / arbitrary egress
- Auth, SSO, Kubernetes, microservices
- Claiming a formal privacy-risk probability (we report **Estimated Context Exposure**, not P(leak))

## 10. Document set

| Doc | Contents |
|---|---|
| [02-features.md](./02-features.md) | Features, UI, metrics, tools, `minimize()`, field catalog |
| [03-demo.md](./03-demo.md) | Seed story, scenarios, rubric, build order |
| [04-gb10.md](./04-gb10.md) | GB10: install stack vs on-site agent build |
