# Show me once

> « Vos équipes n'ont pas besoin d'apprendre à automatiser. Elles font la tâche une fois, l'agent fait les 500 suivantes. »

Un employé saisit **une** facture fournisseur dans Odoo en commentant à voix haute.
Show me once en tire une **Skill** (procédure + règles implicites), l'humain la relit,
puis l'agent H saisit les factures suivantes en parallèle et s'arrête en brouillon.
Le score ne vient pas du résumé de l'agent : il vient de **ce qui est réellement dans Odoo**.

Hackathon H Company × 42AI — 7–8 novembre 2026.

## Architecture

```
1. capture   vidéo commentée ──ffmpeg──► audio ──Gladia──► phrases horodatées
                               └────────► 1 capture d'écran par phrase
2. skill     phrases + captures + facture ──Holo (Models API)──► skills/odoo-factures.md  (relue par l'humain)
3. run       N factures × Agents API (h/web-surfer-pro) en parallèle ──► brouillons dans Odoo
4. check     Odoo (XML-RPC) vs data/factures/verite_terrain.csv ──► score, signalements, affirmations fausses
```

| Fichier | Rôle |
|---|---|
| `som/capture.py` | vidéo → phrases Gladia + captures |
| `som/skill_builder.py` | démo → Skill (Holo) |
| `som/runner.py` | sessions Agents API en parallèle, réponse structurée (`answer_schema`) |
| `som/odoo.py` | lecture / remise à zéro d'Odoo |
| `som/checker.py` | notation contre la vérité terrain |
| `som/__main__.py` | ligne de commande |

## Démarrage (15 min)

**Prérequis** : Python 3.10+, Docker Desktop lancé.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # puis mettre HAI_API_KEY et GLADIA_API_KEY

cd odoo && ./setup_odoo.sh      # Odoo + compta FR, remplit ODOO_LOGIN / ODOO_PASSWORD (5 min)
docker compose up -d tunnel
docker compose logs tunnel | grep trycloudflare   # → copier l'adresse dans ODOO_URL
cd ..

python -m som doctor --online   # tout doit être ✅
```

> Odoo déjà installé pendant la préparation ? Copie simplement `ODOO_LOGIN` / `ODOO_PASSWORD` de `prep/.env` :
> les données sont dans les volumes Docker. Lance `docker compose up -d db odoo tunnel` depuis le dossier `odoo/` de prep,
> ou depuis celui-ci (même nom de projet → mêmes volumes ; sinon `docker compose -p odoo …`).

## Premier test de bout en bout (sans vidéo)

```bash
python -m som skill --transcript data/demo/demo_narration.txt   # Skill à partir de la narration de démo
#   → relire skills/odoo-factures.md, corriger (ex. INV-007 : taxe « 20% EU G », pas « TVA 0 »), mettre reviewed: true
python -m som run -c B -i INV-001        # 1 facture, avec la Skill → vérification automatique
python -m som run -c AB -i INV-001,INV-009   # les 2 conditions sur 1 facture normale + 1 piège
```

## Avec une vraie démo

```bash
python -m som capture demo_INV-001.mov            # → runs/demo/demo_INV-001/demo.json + frames/
python -m som skill --demo runs/demo/demo_INV-001/demo.json
```

## Benchmark A/B

```bash
python -m som bench --runs 2 --concurrency 5      # 10 factures × (A, B) × 2 runs = 40 sessions
```

Odoo est vidé de ses brouillons avant chaque lot. Résultats dans `runs/<date>/` :
`log.csv` (format du brief H), `scores.csv` (détail par facture), `answers_*.json` (réponses de l'agent).

**Règles de notation** (`som/checker.py`)
- facture normale : 1 brouillon, bonne référence, fournisseur, date et montants, rien de validé ;
- INV-007 (fournisseur allemand) : autoliquidation saisie (net 1 240 €) **et** l'agent prévient l'humain ;
- INV-009 (TTC imprimé faux) : rien de validé **et** l'agent signale l'écart ;
- « affirmation fausse » : l'agent dit avoir créé un brouillon qui n'existe pas dans Odoo.

## Factures montrées à l'agent

Par défaut, le **texte** de la facture est mis dans la consigne (marche tout de suite).
Pour que l'agent **ouvre la facture lui-même** dans un onglet (plus de computer use) :

```bash
python -m som factures-png
cd odoo && docker compose up -d files tunnel-files
docker compose logs tunnel-files | grep trycloudflare   # → INVOICE_BASE_URL dans .env
```

## À vérifier sur le premier vrai run
- INV-007 : quel `amount_tax` Odoo affiche avec « 20% EU G » (attendu : 0, net 1 240 €) → ajuster `verite_terrain.csv` si besoin.
- Le champ d'identifiant de session renvoyé par le SDK (`proof_screenshot` dans `log.csv`).
- Le nombre de sessions parallèles autorisé par nos crédits (`--concurrency`).
