# 05. The Pitch

**Scope:** The argument in the order it should be told. Product contract: [../prd/01-overview.md](../prd/01-overview.md). Demo numbers: [../prd/03-demo.md](../prd/03-demo.md).

---

## The hook

SafeContext. Ask for more. Send less. More safety.

The jury should know the topic in one beat: more of the frontier model, less of the file, more safety.

---

## The need

Everyone wants the new tools: Claude Code, Cowork, Codex, Copilot, ChatGPT, Gemini.

Banks, hospitals, insurers run on constraints: client PII, patient records, account numbers, exact balances, internal memos. New tools land blocked on day one. Most firms never start.

---

## The idea

A filter between you and the model. It strips sensitive fields and shrinks context so the report still works.

Names become tokens. Exact figures become bands. The model still writes the summary. It does not see Jane Doe or the raw spreadsheet. The private view never leaves the box.

---

## Bob

Bob is a bank analyst. Twenty spreadsheets. Meeting at 9. He wants Claude. Policy says no.

With SafeContext the files stay on the GB10. He pastes an envelope, not the workbooks. The summary still gets written.

On the demo box, Bob's spreadsheets are a customer record in Mongo. Same idea.

---

## The stack

MongoDB holds the record. OpenClaw + local Qwen propose KEEP / TRANSFORM / REMOVE. Python `minimize()` executes. Policy wins. A human copies the envelope into Claude.

There is no `call_external_llm` tool. They never give us an Anthropic key.

---

## What has to be true

The minimized answer must still do the job (the summary, the report). If it cannot, we sent too little. That is a failed run, not a win on reduction.
