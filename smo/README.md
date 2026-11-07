# SMO : Show me once

Capturer, automatiser et maintenir des agents H pour des tâches répétitives. Le principe :
- une capture vidéo + voix d'une tâche faite une fois devient un **agent custom H** ;
- cet agent a sa Skill, un tool déterministe écrit par Devin, et reprend en computer use quand le tool échoue ;
- la trace de chaque reprise renvoie Devin corriger le tool et la Skill.

```
capture → transcribe → frames → read → understand → enrich → skill → review → provision → trial → compile → upgrade
   ├──→ map (agent H, en parallèle : carte des écrans de la tâche) ──┤
   └──→ docs (Linkup, en parallèle : documentation publique du logiciel) ──┘

Un agent H par type de logiciel : `web` (navigateur) ou `desktop` (bureau du Mac), chacun avec sa Skill et ses tools.
Chaque Skill envoyée dans H se termine par le bloc commun `skills/bloc_commun.md` (utiliser les tools).
          Gladia       ffmpeg   Holo   Holo        Linkup            humain   agent H     agent H  Devin     agent H + tool
                                (1 capture par appel, puis synthèse en texte seul)
```

Le plan complet et l'état des API sont dans [`PLAN.md`](PLAN.md).

## Installer

```bash
cd smo
uv sync --extra desktop              # sur le Mac ; --extra desktop = l'agent bureau (appli de bureau)
uv run playwright install chromium   # pour les tools compilés
cp .env.example .env                 # puis remplir
uv run smo doctor                    # ✅ / ⏭️ / ❌ par API
uv run smo doctor --probe all        # vraies sessions H : Skill, agent guidé, tool exécuté par nous
```

## La page d'enregistrement (le plus simple)

```bash
uv run smo serve                     # puis ouvrir http://localhost:8000 dans Chrome
```

La page suit quatre temps :
1. **Préparer** : la tâche, l'adresse du logiciel, la pièce traitée et le prénom.
2. **Enregistrer** : Chrome partage l'écran et le micro. Gladia transcrit en direct pendant qu'on parle.
3. **Comprendre** : à l'arrêt, la vidéo part au serveur et le pipeline tourne. La page montre l'avancement, puis la Skill à relire et à valider.
4. **Agent** : l'agent est créé dans H et teste la tâche à l'écran, puis Devin code le tool. La page donne les liens (session de test, PR).

Quelques précisions :
- **Clé Gladia** : elle reste sur le serveur, qui ouvre la session en direct ; le navigateur ne reçoit qu'une adresse à jeton temporaire.
- **Transcription utilisée par le pipeline** : c'est celle du fichier complet, plus fiable que le direct.
- **Accès** : la capture d'écran exige `localhost` ou HTTPS. Si `SMO_SERVER_TOKEN` est défini, la page demande le jeton. En ligne (Railway), ce jeton est obligatoire (16 caractères minimum) : sans lui, le serveur refuse de démarrer, pour que personne ne dépense nos crédits.
- **Taille** : une vidéo de plus de 500 Mo est refusée.
- **Reprendre un run** : `http://localhost:8000/?run=<run_id>`.

## En ligne de commande

```bash
# 1. Une capture → un run (vidéo, ou audio + images ; un PDF = pièce de référence)
uv run smo new capture.mov --task "Saisir une facture fournisseur" --owner catherine --sample INV-001

# 2. Le pipeline : s'arrête à la relecture de la Skill (sauf --auto), puis reprend où il en était
uv run smo run <run_id>
uv run smo approve <run_id>
uv run smo run <run_id> --no-wait    # n'attend pas Devin ; relancer pour suivre
uv run smo status <run_id>

# Tout d'un coup, sans relecture (parcours Catherine)
uv run smo new capture.mov --task "..." --owner catherine --go --auto
```

Chaque étape écrit son fichier dans `runs/<run_id>/` : `map.json` (gardée aussi dans `runs/_maps/`), `transcript.json`, `frames/`, `notes.json`, `procedure.json`, `context.json`, `skill.md`, `agent.json`, `trace.json` (+ `trace/`), `trial.json`, `compile.json`.
Option `--guided` : à l'étape trial, l'agent est guidé phrase par phrase au lieu de suivre seul sa Skill.
On peut refaire une étape : `uv run smo run <id> --only understand --force`.

## Le serveur

`uv run smo serve` lance un seul programme qui fait trois choses :
1. **La page d'enregistrement** (`/`) et son API (`/api/...`) : reçoit la vidéo, fait tourner le pipeline, montre l'avancement.
2. **Le worker des tools** : quand un agent `smo-*` appelle un tool, sa session H attend. Le serveur le voit en interrogeant H toutes les 5 s, se rattache à la session et exécute le tool (`precheck_*`, `run_*`, `report_drift`, `check_supplier`…), même si la session a été lancée depuis l'interface H. Le webhook H (`/webhooks/h`) est facultatif : plus rapide, mais il demande une adresse publique et un secret.
3. **Le relais vers h-tools** : les tools écrits par Devin vivent dans le repo h-tools, et chacun tourne dans son propre service Railway, dans le projet Railway d'h-tools. À chaque déploiement, h-tools annonce le tool à SMO (`POST /hooks/tool-deployed` : nom, commit, adresse publique). SMO retient l'adresse, appelle le tool (`/describe`, `/precheck`, `/run`) avec le mot de passe commun `SMO_SERVER_TOKEN`, et remet à jour les agents H qui l'attendent, avec la Skill du repo et le bloc commun.

Où il tourne : **un seul serveur SMO, sur Railway, gère tout**. Sur la page, on choisit l'agent :
- **web** : l'agent H travaille dans son navigateur cloud, sur le site en ligne ;
- **bureau** : l'agent H travaille dans l'**environnement desktop de test configuré dans H**, dont on donne l'identifiant dans `H_DESKTOP_ENV`. Sans lui, SMO prend le bureau de la machine où il tourne, ce qui ne sert qu'en local.

Les tools déterministes de bureau (accessibilité macOS) doivent tourner là où tourne l'appli : h-tools ne les déploie pas sur Railway. En attendant, l'agent bureau travaille en computer use.

## Déployer sur Railway

Trois projets Railway séparés : Qonta (le logiciel de test), SMO (ce serveur), h-tools (les tools de Devin).

1. **Service SMO**, dans son propre projet : New › GitHub Repo › `show-me-once-prep`.
   - Settings › Source : **Root Directory = `smo`** ; branche `main` une fois la PR fusionnée, ou `feat/smo` pour tester avant.
   - Le reste vient de `railway.toml` : construction par le `Dockerfile`, vérification de santé sur `/health`, redémarrage en cas d'échec.
2. **Volume** : clic droit sur le service › Attach Volume, monté sur **`/data`**. Sans lui, les runs et les cartes sont effacés à chaque redéploiement.
3. **Variables** (Raw Editor : coller le `.env`, puis ajuster) :
   - toutes les clés et les `SITE_*` du `.env` ;
   - **`SMO_RUNS_DIR=/data/runs`** ;
   - **`SMO_SERVER_TOKEN`** : 16 caractères minimum, par exemple `openssl rand -hex 24`. Sans lui, le serveur refuse de démarrer en ligne.
   - **`H_DESKTOP_ENV`** : l'identifiant de l'environnement desktop de test configuré dans H (agent bureau) ;
   - `DESKTOP_LOGIN` / `DESKTOP_PASSWORD` : les identifiants de l'appli dans cet environnement ;
   - inutile sur Railway : `H_TOOLS_DIR`.
4. **Adresse** : Settings › Networking › Generate Domain. La mettre dans `SMO_SERVER_URL`, sur Railway et dans le `.env` du Mac.
5. **h-tools**, pour la liaison : dans le projet Railway d'h-tools, la variable partagée `SMO_SERVER_TOKEN` (le même jeton) ; dans les secrets GitHub du repo h-tools, `SMO_SERVER_URL` (cette adresse) et `SMO_SERVER_TOKEN`. Chaque déploiement de tool l'annonce alors à SMO.
6. **Vérifier** : `uv run smo doctor` (ligne « Serveur SMO »), puis ouvrir l'adresse dans Chrome ; la page demande le jeton.

En local, pour essayer un tool d'h-tools sans le déployer : `gh repo clone Tomoroshimaru/h-tools ~/h-tools`, puis `H_TOOLS_DIR=~/h-tools` dans le `.env`.

## Autres commandes

```bash
uv run smo trace <session_id>        # trace de n'importe quelle session H
uv run smo tools --precheck          # tools compilés + precheck
uv run smo repair <tool> --session <id> --details "bouton renommé"
uv run pytest                        # tests hors ligne
```

## Structure

```
smo/
  smo/clients/     gladia, holo (Models API), h (Agents API), linkup, devin, site
  smo/pipeline/    une étape par fichier + orchestrator.py (le driver)
  smo/runtime/     serveur FastAPI, worker des tools H, chargement des tools, helpers Playwright
  tools/           les tools compilés par Devin (un dossier par tâche) + _template
  docs/            brief Devin (création, réparation), contrat du site compta
```

Repris de `prep/` : la transcription Gladia (`03`), la lecture d'écran Holo (`04`), l'usage de l'Agents API (`01`, `02`).
