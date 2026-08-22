# Video script

Spoken script for the recorded pitch video, one line per slide.

Deck: `site/deck.html` — 14 slides, advance with `→`, space, or click. Staging: [06-slide-plan.md](06-slide-plan.md). System: [08-system-design.md](08-system-design.md).

**Runtime:** ~3:30.

**Vocabulary rules.** Do not name the stack — "OpenClaw", "Qwen", "minimize()" — before slide 12. Do not say "CRM". Do not say "the model is blind". No metrics on slides 9–11. No market size on slide 14.

---

**1 · Ask for more. Send less. More safety.**

> SafeContext. You ask the model for more work. You send it less of the file. That trade is what buys you more safety.

**2 · Everyone wants the new tools.**

> Claude Code. Cowork. Codex. Copilot. ChatGPT. Gemini. Every team wants the latest one, because it makes the work faster.

*Names stagger in — pace to the animation, don't finish the list early.*

**3 · Institutions run on privacy.**

> But look at what the regulated world runs on. Client PII. Patient records. Account numbers. Exact balances. Internal memos. Banks, hospitals, insurers — that data *is* the job.

*Slow down. One beat per line.*

**4 · So they never start.**

> So the tool gets blocked on day one. Not because it's bad — because of what would have to leave the building to use it. The report stays manual.

**5 · A layer between you and the model.**

> Here's the fix. One layer, between you and the model. You hand it the whole file — names, accounts, amounts. It runs on the Dell GB10, and it keeps, transforms, or removes every field. What reaches Claude is an envelope with only what the task needs. Nothing else in your workflow changes.

**6 · Names change. Numbers change.**

> Identifiers become tokens. Exact figures become bands. The model still writes the summary — it just never sees the real values. The private view never leaves.

*Emphasise "still". Capability is preserved, not traded away.*

**7 · This is what we do to the document.**

> Concretely, here's a client file. Jane Doe becomes CLIENT_01. The account number becomes ACCT_7. Eight hundred forty-seven thousand becomes "five hundred k to one million." A two-point-four million dollar transfer becomes "seven figures." And the note about the CFO evaluating a competitor — that just goes. Removed entirely.

*Each row strikes through then resolves. Let the animation land; don't outrun it.*

**8 · This is what leaves the box.**

> So this is the whole payload. A token, a band, a trend, a ticket count. Enough to write the summary. Not enough to identify anyone.

**9 · Bob has 20 spreadsheets.**

> Meet Bob. Bank analyst. Twenty Excel files just landed. Meeting's at nine.

*Warmer, faster. The human beat after four concept slides.*

**10 · He wants Claude.**

> He'd paste all twenty in a heartbeat. Policy says no.

*Quick, almost funny. Shortest slide in the deck.*

**11 · The files stay on the GB10.**

> With the layer in place, the files never leave the box. Bob sends an envelope, not the workbooks. And the summary still gets written, on time.

**12 · Mongo holds the record.**

> Under the hood: MongoDB holds the record. OpenClaw, running a local Qwen, proposes keep, transform, remove. A Python function — `minimize()` — executes it. And when the model and the policy disagree, policy wins.

*First mention of the stack. Not before here.*

**13 · The system**

> Here it is with the boundary drawn in. A task comes in, OpenClaw and the local Qwen read what they need from Mongo, and propose a spec. `minimize()` executes it. Out comes the envelope.
>
> Now look at the dashed line. Everything inside it runs on the GB10. The records never cross it. The model that reads the raw data never crosses it. One thing crosses: the envelope. Claude gets that and nothing else.

*The diagram builds node by node — pace the first paragraph to the build, one clause per box. Then stop, let the crossing arrow land, and deliver the second paragraph slower. Point at the dashed fence on "this line." The claim is structural, not a formal privacy guarantee — don't overstate it.*

**14 · SafeContext**

> SafeContext. Ask for more. Send less. More safety.

*Exact echo of slide 1 — same pace, same weight. Let it hang, then stop.*

---

## If you're over time

Cut in this order. Each slide survives on its headline alone.

1. Slide 4, second sentence — "Not because it's bad..."
2. Slide 6, second sentence — "The model still writes the summary..."
3. Slide 13, first paragraph — open straight on "Now look at the dashed line."

---

## Optional cold open

Not in the current cut. Two scenes, hard cut to black between them, ~30s total — runs before slide 1 if you want a hook. Cast: BOB, DANA. One laptop.

**Scene 1 — before**

*(BOB at a laptop, typing.)*

**BOB** *(typing)* "Summarize these accounts—" *(hits Submit)*

*(DANA enters, looks at the screen.)*

**DANA** Bob. Is that client data — on an external model?

**BOB** I just—

**DANA** *(cold)* You're fired.

*(Cut to black.)*

**Scene 2 — after**

*(Lights up. Same BOB, same laptop, typing.)*

**BOB** *(typing)* "Summarize these accounts—" *(hits Submit)*

*(DANA enters, looks at the screen.)*

**DANA** Bob. What's this?

**BOB** SafeContext. Nothing sensitive left the building.

**DANA** *(beat)* ...Good work.

*(Lights fade. Presenter: "SafeContext. Ask for more. Send less. More safety." → slide 1.)*
