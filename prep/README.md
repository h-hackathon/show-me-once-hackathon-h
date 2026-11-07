# prep — préparation du hackathon

Tout ce qui a été fait **avant** le samedi 7 nov 10h30 : tests des API, factures de test, Odoo.
Ce n'est pas le code du produit (voir `../smo/`). Le journal `JOURNAL.md` raconte chaque étape et nos découvertes.

## Contenu
| Chemin | Rôle |
|---|---|
| `01_test_agents_api.py` | l'agent H navigue sur le web (réponse structurée) |
| `02_test_odoo_access.py` | l'agent H se connecte à notre Odoo |
| `03_test_gladia.py` | transcription horodatée d'un audio de démo |
| `04_test_holo.py` | Holo lit une facture et rédige une Skill |
| `05_test_stripe_access.py` | l'agent H accède au Dashboard Stripe |
| `factures/` | 10 factures fictives (dont 2 pièges), leur générateur et la vérité terrain |
| `audio/` | narration de démo pour tester Gladia |
| `odoo/` | Odoo local (Docker) + tunnel public, plan B comme logiciel cible |
| `ressources/` | documentation des sponsors (H, Gladia, Linkup, Cognition, Stripe) et kit équipe |
| `benchmark_log_template.csv` | colonnes de log du benchmark (format du brief H) |
| `JOURNAL.md`, `QUESTIONS.md`, `CHECKLIST_VENDREDI.md`, `GUIDE_REPETITION.md` | suivi de la préparation |

## Démarrage
Toutes les commandes se lancent **depuis `prep/`**.

1. **Prérequis** : [uv](https://docs.astral.sh/uv/), Docker Desktop lancé (pour Odoo), git.
2. **Installer** :
   ```bash
   uv sync
   cp .env.example .env
   ```
3. **Tes clés** (gratuites, une par personne, jamais partagées) dans `prep/.env` :
   H → platform.hcompany.ai/settings/api-keys · Gladia → app.gladia.io > API Keys
4. **Odoo** : `cd odoo && ./setup_odoo.sh` (5 min) → http://localhost:8069
5. **Tests** :
   ```bash
   uv run python 01_test_agents_api.py      # l'agent H navigue sur le web
   uv run python 03_test_gladia.py          # transcription d'un audio de démo
   ```
   Pour `02_test_odoo_access.py` (l'agent H dans Odoo) : lancer le tunnel d'abord (`docker compose up -d tunnel` dans `odoo/`) et copier l'adresse dans `ODOO_URL`.
