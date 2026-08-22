# Dell Hackathon — SafeContext

Local **context minimizer** for the Dell GB10 / OpenClaw hackathon.

Given a business task and MongoDB enterprise data, SafeContext produces the **minimum sufficient payload** for an external LLM (Claude, Copilot, …) plus an exposure report. The user copies that payload out themselves. The planner runs **on the GB10 only**.

**Commencer ici (GB10 à côté) :** [START.md](START.md) — ordre exact, commandes, gate `hello`, puis le code.

## PRDs

| Doc | Use |
|---|---|
| [docs/prd/01-overview.md](docs/prd/01-overview.md) | Product, principle, locks, success, non-goals |
| [docs/prd/02-features.md](docs/prd/02-features.md) | Features, tools, `minimize()`, catalog, UI |
| [docs/prd/03-demo.md](docs/prd/03-demo.md) | Seed data, four scenarios, build order |
| [docs/prd/04-gb10.md](docs/prd/04-gb10.md) | What the GB10 installs vs what you build on-site |

## Venue rule

Plans and scaffolds are fine. **The agent is built on the GB10 on the day.** Demo runs on that box. No cloud inference for the planner.
