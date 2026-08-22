# START — tout se fait sur le GB10

Pas de laptop. Pas de clé USB. Pas de `scp`.  
Clone GitHub → Claude Code → il installe et il build.

## Sur le GB10 uniquement

```bash
git clone --branch master https://github.com/Omartfz/Dell-hackathon.git
cd Dell-hackathon
```

> ⚠️ **`master` est la branche de travail.** La branche `docs/prd` n'a **ni** `CLAUDE.md` **ni** `TASKS.md` — un clone par défaut ne suffit pas.

Ouvre **Claude Code dans ce dossier**. Colle :

```
Execute TASKS.md from T0 to T14 on this GB10. Pull the model on this machine. Gate on local hello before product code. Build SafeContext per CLAUDE.md and docs/prd/05-always-on-spend.md. Planner is local only; the sole external call takes minimize() output. Do everything here.
```

## Ce que Claude Code fait (TASKS.md)

T0–T4 : NemoClaw, **télécharge Qwen ici** (`ollama pull`), `hello` local, Mongo  
T5–T9 : seed spend (Northwind), `minimize()` + tests, five tools, planner local  
T10–T14 : stream + escalation ladder, UI, ré-identification, démo

## La règle réseau

Le planner et le triage tournent **en local uniquement**. La seule sortie du code est
`app/escalate/external.py`, et elle ne reçoit que la sortie de `minimize()` — jamais le bundle brut.
Réseau débranché : Tier 0 et Tier 1 continuent, Tier 2 attend en file.

Fichiers : [CLAUDE.md](CLAUDE.md) · [TASKS.md](TASKS.md) · [PRD 05](docs/prd/05-always-on-spend.md)
