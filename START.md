# START — tout se fait sur le GB10

Pas de laptop. Pas de clé USB. Pas de `scp`.  
Clone GitHub → Claude Code → il installe et il build.

## Sur le GB10 uniquement

```bash
git clone --branch docs/prd https://github.com/Omartfz/Dell-hackathon.git
cd Dell-hackathon
```

Ouvre **Claude Code dans ce dossier**. Colle :

```
Execute TASKS.md from T0 to T12 on this GB10. Pull the model on this machine. Gate on local hello before product code. Follow CLAUDE.md and docs/prd. No cloud LLM APIs. Do everything here.
```

## Ce que Claude Code fait (TASKS.md)

T0–T4 : NemoClaw, **télécharge Qwen ici** (`ollama pull`), `hello` local, Mongo  
T5–T12 : seed, minimize, tools, planner, Streamlit, démo

Fichiers : [CLAUDE.md](CLAUDE.md) · [TASKS.md](TASKS.md)
