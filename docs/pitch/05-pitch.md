# 05. The Pitch

**Scope:** The argument in the order it should be told. Product contract: [../prd/01-overview.md](../prd/01-overview.md). Demo numbers: [../prd/03-demo.md](../prd/03-demo.md).

---

## The need

The report is due tomorrow. The files that would write it sit in a bank, an insurer, anywhere a leak is a career.

People already want the new tools: Claude Code, Claude Cowork, Copilot. They make the analysis faster. Then security blocks them on day one.

Most institutions do not ship their own frontier model. The internal one, if it exists, is slower and worse. So the report is still manual, on a short deadline, because the tool cannot see the file.

---

## The idea

Prompt the model anyway. Keep the sensitive parts on the box.

GB10 runs a local agent over MongoDB. What leaves the room is a small envelope: enough for the report, not enough to leak the client.

> Give the model what the task needs. Not the file.

---

## The equivalence

Seventeen information units in the seeded record. Six leave the box for the churn report. The write-up still names declining usage, support load, and an upcoming renewal.

| | Whole file | SafeContext |
|---|---|---|
| What Claude sees | Every field | Status, ARR **band**, term, renewal, usage trend, ticket **counts** |
| PII | email, phone | none (this report) |
| Exact figure | $847,291 | $500k-$1M |
| Injection ticket body | present | never outbound |

---

## The mechanism

A **local** agent (OpenClaw + Qwen on the GB10) proposes KEEP / TRANSFORM / REMOVE. Python `minimize()` executes. MongoDB **policy wins**. There is no `call_external_llm` tool. A human copies the envelope into Claude, Copilot, or Cowork.

Unhedged dump: quality maybe high, exposure max. Zero context: 100% reduction, 0% utility. SafeContext is the Pareto point we can show in one run.

---

## The product

Two screens:

| Screen | What it shows |
|---|---|
| **Console** | Task, naive JSON, copy-ready envelope, decision log, live counts |
| **Deck** | The argument, 15 slides |

They never give us an Anthropic key. They keep the cloud tool they already wanted.

---

## What has to be true

The minimized answer must still hit the report rubric (usage down, tickets up, renewal). If it cannot, we sent too little. That is a failed run, not a win on reduction %.

---

## Where it goes

The wedge is "the report on a deadline, without leaking the file." The primitive is **task-conditioned egress** for any external model.
