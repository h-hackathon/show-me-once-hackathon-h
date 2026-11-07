# SMO : Show me once

Capturer, automatiser et maintenir des agents H pour des tâches répétitives. Le principe :
- une capture vidéo + voix d'une tâche faite une fois devient un **agent custom H** ;
- cet agent a sa Skill, un tool déterministe écrit par Devin, et reprend en computer use quand le tool échoue ;
- la trace de chaque reprise renvoie Devin corriger le tool et la Skill.

```
capture → transcribe → frames → read → understand → enrich → skill → review → provision → trial → compile → upgrade
   └──→ map (agent H, en parallèle : carte des écrans de la tâche) ──┘
          Gladia       ffmpeg   Holo   Holo        Linkup            humain   agent H     agent H  Devin     agent H + tool
                                (1 capture par appel, puis synthèse en texte seul)
```

Le plan complet et l'état des API sont dans [`PLAN.md`](PLAN.md).

## Installer

```bash
cd smo
uv sync
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

## Serveur (Railway)

```bash
uv run smo serve                     # local : http://localhost:8000/docs
uv run smo webhook                   # abonne SMO_SERVER_URL/webhooks/h aux sessions H → H_WEBHOOK_SECRET
```

- Le serveur répond aux custom tools des agents `smo-*` : `precheck_*`, `run_*`, `report_drift`, `check_supplier`, `verify_entry`.
- Il les sert même quand la session est lancée depuis l'interface H (webhook, et polling en secours).
- Déploiement : le `Dockerfile` (Python 3.12 + Chromium) ; les variables Railway sont celles du `.env`.

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
