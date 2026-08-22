# START — tu as le GB10 à côté. Fais ça, dans l’ordre.

**Ne code pas l’agent maintenant.**  
Les 60–90 premières minutes = **installer la box** jusqu’à ce qu’elle réponde `hello` en local.  
Ensuite seulement on écrit SafeContext (seed → minimize → tools → UI).

Produit : [docs/prd/01-overview.md](docs/prd/01-overview.md)  
Contrat machine : [docs/prd/04-gb10.md](docs/prd/04-gb10.md)

---

## 0. Les deux machines

| Machine | Rôle maintenant |
|---|---|
| **GB10** (Linux, le petit Dell / Spark) | C’est **là** que le demo doit tourner. Tu t’assois dessus (écran + clavier du stand, ou SSH depuis le laptop). |
| **Laptop Windows** (celui-ci, Cursor) | Cache du modèle `qwen3.6:35b` (~23 GB dans `C:\Users\Bureau\.ollama\models`). Clavier / copie de fichiers. **Pas** le demo. |

Si vous êtes deux : **A** reste sur le GB10 (stack + hello). **B** prépare Mongo + clone git dès que le réseau de la box marche.

---

## 1. Maintenant — sur le GB10 (terminal Linux)

Ouvre un terminal **sur le GB10**. Pas PowerShell, pas WSL.

### 1.1 Sanity (2 min)

```bash
head -n 2 /etc/os-release
uname -m
nvidia-smi
docker info --format '{{.ServerVersion}}'
df -h
hostname -I
whoami
```

Coche :

- [ ] `uname -m` = `aarch64` (sinon stop : mauvaises images)
- [ ] `nvidia-smi` montre un GPU (GB10 / Spark)
- [ ] `df -h` : **au moins ~40 GB libres** sur `/` (modèle ~23 GB + Docker)
- [ ] tu as noté l’**IP** (`hostname -I`) → `GB10_IP=…`
- [ ] tu as noté le **user** (`whoami`) → souvent `nvidia`

Si Docker n’existe pas : dis-le, n’invente pas d’install. Les boxes venue l’ont en général.

### 1.2 Copier le modèle depuis le laptop (le plus long)

Le modèle est **déjà** sur le laptop. Il ne rentre pas sur une clé 16 GB. Câble USB-C / Ethernet **ou** même Wi‑Fi.

**Sur le GB10**, crée le dossier d’arrivée :

```bash
mkdir -p ~/ollama-models-from-laptop
```

**Sur le laptop**, PowerShell (remplace `nvidia` et l’IP) :

```powershell
scp -r $env:USERPROFILE\.ollama\models nvidia@<GB10_IP>:~/ollama-models-from-laptop
```

Ça peut prendre 10–40 min. Laisse tourner. **Ne lance pas l’inférence depuis une clé USB.**

Si `scp` demande un mot de passe / refuse :

- même réseau que le GB10
- `ssh nvidia@<GB10_IP>` marche d’abord
- sinon partage de fichiers / clé USB **uniquement pour copier**, puis `cp` vers `~/` **sur le disque interne**

**Fallback si la copie 23 GB est trop lente :** on installera Ollama via NemoClaw puis :

```bash
ollama pull qwen3.5:9b
```

Moins fort, mais **local**. On n’attend pas Claude.

### 1.3 Installer NemoClaw + OpenClaw + OpenShell (sur le GB10)

Toujours **sur le GB10** :

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

Questions typiques :

1. Notice third-party → **yes**
2. **Express install?** → **Y** si ça choisit une inférence **locale** (vLLM ou Ollama).  
   Si ça propose un cloud / API NVIDIA hosted → **n**, puis onboard local (étape 1.4).

Si le Wi‑Fi venue est mort et que tu as `nemoclaw.sh` sur une clé :

```bash
bash /media/$USER/*/nemoclaw.sh
# ou le chemin réel du script
```

```bash
source ~/.bashrc
which nemoclaw
nemoclaw --help | head
```

**Ne pas inventer des flags.** Si les noms ci‑dessous ne marchent pas : `nemoclaw onboard --help` et `nemoclaw --help` **sur cette box**.

### 1.4 Pointer l’inférence en local (si Express n’a pas suffi)

```bash
nemoclaw onboard --help
```

Schéma **probable** (à confirmer sur la box) :

```bash
export NEMOCLAW_PROVIDER=install-ollama
export NEMOCLAW_MODEL=qwen3.6:35b
nemoclaw onboard
```

Puis coller les blobs copiés là où Ollama les lit **vraiment** (un des deux, teste avec `ollama list`) :

```bash
# user-local
mkdir -p ~/.ollama/models
cp -a ~/ollama-models-from-laptop/. ~/.ollama/models/

# parfois service system
# sudo mkdir -p /usr/share/ollama/.ollama/models
# sudo cp -a ~/ollama-models-from-laptop/. /usr/share/ollama/.ollama/models/

ollama list
```

Tu dois voir `qwen3.6:35b` (~22–23 GB) **sans** un pull de 30 min.  
Sinon `qwen3.5:9b` en fallback.

### 1.5 GATE — `hello` local (obligatoire avant de coder)

```bash
source ~/.bashrc
nemoclaw my-assistant status
```

Ensuite **une** de ces commandes — celle qui existe chez toi :

```bash
nemoclaw my-assistant connect
# ou
nemoclaw my-assistant dashboard-url --quiet
# ou
openclaw tui
```

Tape : `hello`

- [ ] Ça répond **sans** clé OpenAI / Anthropic / cloud
- [ ] Tu es **sur le GB10**

**STOP ici si ça ne répond pas.** On ne commence pas SafeContext. On debug le stack (provider Ollama/vLLM, modèle présent, `nvidia-smi` encore OK).

Option laptop : tunnel (port = celui que `dashboard-url` affiche, pas forcément 18790) :

```bash
ssh -L 18790:127.0.0.1:18790 nvidia@<GB10_IP>
```

Utilise `127.0.0.1`, pas `localhost`.

### 1.6 MongoDB (toujours GB10)

```bash
docker run -d --name safecontext-mongo --restart unless-stopped -p 27017:27017 mongo:7
docker ps
docker logs safecontext-mongo 2>&1 | tail
```

Si `mongo:7` ne pull pas en ARM64 :

```bash
docker pull --platform linux/arm64 mongo:7
# ou image community ARM64 dispo sur la box
```

Ping :

```bash
docker exec -it safecontext-mongo mongosh --eval 'db.runCommand({ ping: 1 })'
```

- [ ] `ok: 1`

### 1.7 Ce repo sur le GB10

```bash
cd ~
git clone --branch master https://github.com/Omartfz/Dell-hackathon.git
cd Dell-hackathon
git status
```

Si GitHub est lent : `git clone` depuis le laptop via `scp -r` du dossier, ou branche `docs/prd` (même contenu PRD pour l’instant).

Python (après clone ; le `requirements.txt` arrivera avec le code — pour l’instant crée le venv) :

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 --version
```

---

## 2. Quand le GATE est vert — on BUILD quoi (code)

Toujours **sur le GB10**, dans `~/Dell-hackathon`.  
Cursor sur le laptop peut éditer si le dossier est partagé / tu ouvres le clone distant. Le **run** = GB10.

| # | On code | Fichiers | C’est fini quand |
|---|---|---|---|
| **B1** | Seed Mongo | `app/mongodb/seed.py` | Collections Acme / Globex / Umbrella + ticket d’injection |
| **B2** | Minimizer | `app/minimizer/catalog.py`, `minimize.py`, `metrics.py` | `pytest` : pas d’email, ARR en bande, body d’injection absent |
| **B3** | 5 tools | `app/agent/tools.py` | `whoami`, `find_customer`, `get_customer_bundle`, `get_policy`, `submit_spec` |
| **B4** | Planner | `app/agent/prompts.py` + appel Qwen **localhost** | Spec JSON ; **pas** `if task == "churn"` |
| **B5** | UI | `app/ui/app.py` (Streamlit) | Run, payload, Copy, métriques, log ; browser **GB10** |
| **B6** | Scénario 3 | `app/mongodb/flip_role.py` | `sales_rep` → `sales_manager`, rerun churn |
| **B7** | OpenClaw wrap | skills selon **docs installées** | Même tools ; si API floue → on garde Python et on le dit |

Détail data / demo : [docs/prd/03-demo.md](docs/prd/03-demo.md)  
Détail features : [docs/prd/02-features.md](docs/prd/02-features.md)

**Prochain fichier de code = B1 + B2.** On ne fait pas B4–B7 tant que `hello` et Mongo ping ne sont pas verts.

---

## 3. Ce que tu ne fais PAS dans la prochaine heure

- Écrire un agent OpenClaw “fini” sur le laptop
- LangGraph, embeddings, RAG, parser PDF
- `pip install anthropic` / appeler Claude depuis le code
- Lancer le modèle depuis une clé USB
- Pull d’images `linux/amd64`

---

## 4. Checklist unique (coche en descendant)

**Box**

- [ ] 1.1 Sanity OK (`aarch64`, GPU, disque, IP notée)
- [ ] 1.2 Modèle copié sur le **disque interne** (ou fallback 9b)
- [ ] 1.3 `nemoclaw` installé
- [ ] 1.4 `ollama list` (ou vLLM Express) = modèle local
- [ ] 1.5 **`hello` local**
- [ ] 1.6 Mongo ping
- [ ] 1.7 Repo cloné + venv

**Produit** (après le GATE)

- [ ] B1 seed
- [ ] B2 pytest minimize
- [ ] B3 tools
- [ ] B4 planner local
- [ ] B5 UI + Copy
- [ ] B6 flip rôle
- [ ] Scénarios 1–3 répétés dans le browser GB10

---

## 5. Où tu en es → dis-le dans le chat

Envoie **une** ligne, on enchaîne le code :

- `sanity ok, je copie le modele`
- `hello ok, mongo ok` → on code B1+B2 dans ce repo
- `hello casse: …` (colle l’erreur) → on debug le stack, pas le produit
