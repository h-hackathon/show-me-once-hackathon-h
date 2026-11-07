# SMO : Show me once

Une capture vidéo + voix d'une tâche faite une fois devient un **agent custom H** : sa Skill, un tool déterministe écrit par Devin, et la reprise en computer use quand l'interface change.
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

## Utiliser

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

Chaque étape écrit son fichier dans `runs/<run_id>/` : `transcript.json`, `frames/`, `procedure.json`, `context.json`, `skill.md`, `trace.json` (+ `trace/`), `agent.json`, `compile.json`.
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
