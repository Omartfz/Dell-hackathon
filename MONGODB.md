# Explaining the MongoDB work to a mentor

Three criteria. One live command each. Under four minutes total.

Open the **MongoDB** screen in the app before you start — every claim below is visible there.

---

## Criterion 1 — "The agent survives its own sandbox"

**Say this:**

> Our agent isn't polling the database on a timer. It holds an open **change stream**, so MongoDB
> *pushes* every new transaction to it. The problem with that is state: if the process dies, where
> does it pick up? So after every single event we checkpoint the change stream's **resume token**
> into an `agent_state` document. On restart we reopen with `resume_after` that token and continue
> at the exact position — no gap, nothing replayed.
>
> And because a crash can land between "work done" and "token saved", every event id is also
> claimed in `processed_events` under a unique `_id`. So the worst a crash can cost is a duplicate
> *attempt*, never a duplicate side effect.

**Then prove it — on the MongoDB screen, click "Simulate crash & resume".** Checkpoints keep
climbing, the resume token survives, and nothing is reprocessed.

**Or from a terminal, for the stronger version:**
```bash
bash scripts/kill_test.sh
```
That SIGKILLs the agent mid-stream — no graceful shutdown — restarts it, and prints the checkpoint
count and ledger size on both sides of the kill.

**If they push further:** *"a JSON file can't push you anything, and it has no resume token. This is
the difference between a database and a file."*

---

## Criterion 2 — "Retrieval that changes behavior"

**Say this:**

> Everything that governs what may leave the box lives in MongoDB as documents — the `policies`
> collection, the `field_catalog`, and the user's role. None of it is in code. So the agent's
> behaviour is *retrieved*, not compiled.

**Then prove it, live, in about fifteen seconds:**

1. Open **Automation**, click an escalation, and show the payload — the internal Controls note is absent.
2. Go **Home** and click **Role: ap_analyst** so it flips to `controller`.
3. Re-run the same question on the **Home** page.
4. Show the new payload — the note is now included, and the exposure numbers changed.

**Say:**

> We didn't ship a new model, restart a service, or deploy anything. We changed one field on one
> document, and the very next decision the agent made was different.

Also worth showing: the **Controls** screen lists every policy with its allow list, deny list and
forced transforms, all straight out of the collection.

---

## Criterion 3 — "Real business data" (and *"if a JSON file would do, it doesn't count"*)

**Say this:**

> There are **1,334 transactions across 180 days**, plus employees, cards, vendors, invoices,
> internal notes and treasury — properly relational. And we do the analysis *in* the database, not
> by pulling it all into Python.

Walk the MongoDB screen top to bottom:

**`$graphLookup` — collusion clusters.**
> Fraud rings hide in shared devices. This walks the device graph **transitively** inside the
> engine — from one transaction to every card that touched the same device, and onward. Doing that
> client-side means pulling the whole transaction collection over the wire and rebuilding the graph
> in memory on every tick.

**`$lookup` — banking change vs scheduled payment.**
> This joins vendors to their pending invoices and correlates *when banking details changed*
> against *when payment is due*. That correlation isn't a report — **it is the fraud signal**.
> That's what caught the $27,000 vendor-impersonation attempt.

**`$facet` — spend rollup.**
> Category totals, the monthly trend and top merchants, all in a **single pass** over an indexed
> range. Three answers, one scan.

**`bundle_pipeline` — six `$lookup` stages.**
> When the agent needs an entity's full record, it's one round trip, not an N+1 loop.

**Indexes.** Scroll the index table: **24 indexes, each with the query it exists to serve.**
Point at two specifically:
- a **partial index** on `injection_detected` — "the flagged set is tiny, so the index only stores rows anyone actually queries"
- a **TTL index** on `processed_events` — "the idempotency ledger expires itself; MongoDB reclaims it, not a cron job we forgot to write"

**Multi-document transactions.** When a human clicks *Hold & verify*, the inbox item, the invoice
status and the audit trail update **atomically in a transaction** — so those three can never
disagree about whether a payment was stopped.

---

## The 30-second version, if they're in a hurry

> MongoDB does three jobs here that a file cannot. It **wakes the agent up** — change streams push
> events, and the resume token in `agent_state` is what lets the agent be killed and come back
> exactly where it was. It **decides the agent's behaviour** — policies and roles are documents, so
> editing one changes the next decision with no redeploy. And it **does the analysis** —
> `$graphLookup` walks the fraud graph in the engine, `$facet` rolls up spend in one pass, and a
> `$lookup` correlation is literally what detects the vendor-impersonation attack.

---

## If something isn't up

Check the badge in the header: **`MongoDB · rs0 live`** means everything above is real.

If it says `setup pending`:
```bash
bash scripts/setup_mongo.sh    # ~2 min: starts MongoDB Community as a single-node replica set
python -m app.db.seed          # ~10s: 1,334 transactions
```

The replica set is **not** optional — change streams and multi-document transactions both need an
oplog, and a standalone `mongod` has none. That is worth saying out loud if a mentor asks why you
bothered with `rs.initiate()`.
