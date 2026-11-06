# Show me once — Hackathon H Company × 42AI (7–8 nov 2026)

> « Vos équipes n'ont pas besoin d'apprendre à automatiser. Elles font la tâche une fois, l'agent fait les 500 suivantes. »

## ⚠️ Règle d'or
Ce dossier = **préparation** (docs, tests de l'API, choix techniques).
Le **code du produit** s'écrit pendant le hackathon (à partir du samedi 10h30), dans un **repo neuf**.
Ne pas arriver avec le projet déjà codé : le jury peut regarder l'historique des commits.

## Thèse
Un agent computer-use ne sait pas comment *toi* tu fais ton travail (règles implicites, exceptions).
Résultat : il hésite, se trompe, consomme des étapes. La solution n'est pas un meilleur prompt :
c'est de **te regarder faire une fois**.

## MVP
Cas : **saisie de factures fournisseurs dans un ERP web (Odoo)**.
1. **Démo** : un humain saisit 1 facture en commentant à voix haute (captures d'écran + voix via Gladia).
2. **Skill** : Holo4 (Models API) transforme captures + transcription en procédure écrite → **Skill H**, affichée et éditable.
3. **Exécution** : l'agent traite 10 factures PDF en parallèle (sessions Agents API, navigateurs cloud), s'arrête avant validation.
4. **Contrôle** : l'humain valide en 1 clic, bouton pause/stop, factures suspectes signalées.

Hors MVP (slide vision) : desktop natif, multi-logiciels, rejouer la Skill comme test de non-régression (angle QA).

## Architecture
```
[Capture]  screenshots + audio ──► Gladia (transcription horodatée)
     │
[Skill builder]  Holo4 / Models API ──► procédure (Skill H) ──► UI d'édition
     │
[Runner]  Agents API (h/web-surfer-pro) × N sessions ──► answer_schema (Pydantic)
     │
[Supervision]  dashboard : progression, pause/stop, validation, logs benchmark
```

## Grille de jugement (référence : brief H pour Eugenia)
| Critère | Poids | Notre réponse |
|---|---|---|
| Usage du computer use | 25 % | Écran central à l'apprentissage ET à l'exécution |
| Fiabilité | 25 % | Benchmark : chaque tâche lancée plusieurs fois |
| Utilité | 20 % | DAF de PME, cabinets comptables |
| Originalité | 15 % | Apprentissage par démonstration |
| UX & contrôle | 10 % | Skill éditable, pause/stop, validation humaine |
| Démo & Q&A | 5 % | Pitch 4 min + vidéo de secours |

## Benchmark (le chiffre qui gagne)
Même lot de 10 factures, 2 conditions × 3 runs :
- **A** : agent seul, prompt classique
- **B** : agent + Skill apprise de la démo

Colonnes de log (format du brief H) : voir `prep/benchmark_log_template.csv`.
Slide cible : « A : x/10 → B : y/10, z× moins d'étapes ».

## Rôles (4 personnes)
1. **Capture** : enregistrement écran + Gladia
2. **Skill builder** : prompt Holo4, format Skill, UI d'édition
3. **Runner** : sessions parallèles, answer_schema, benchmark
4. **Front & pitch** : dashboard supervision (Devin pour coder), vidéo de secours, post LinkedIn

## Planning
- **Sam 10h30–13h** : chacun sa brique en isolé, interfaces fixées dès le départ
- **Sam 18h** : boucle complète sur 1 facture ✅
- **Sam soir** : parallélisation + benchmark A/B
- **Dim 8h–12h** : fiabilisation, gel des fonctionnalités, vidéo de secours
- **Dim 12h–14h** : README final, slides, répétition → **dépôt 14h00**

## Livrables
- Démo live (vidéo de secours si le site lâche), vrais résultats, pas de maquettes
- 1 slide « ce que l'agent a trouvé »
- Pitch 4 min : problème → qui paie → ce qu'on a construit
- Repo + README que quelqu'un d'autre peut suivre

## Prix visés
Podium · Best Use of Gladia (1 000 €) · Best Use of Devin (1 000 €) · Best LinkedIn Post (500 €)

## Démarrage pour l'équipe (préparation)
Tout est dans `prep/`. Le journal `prep/JOURNAL.md` raconte chaque étape et nos découvertes.

1. **Prérequis** : Python 3.10+, Docker Desktop lancé, git.
2. **Installer** (depuis `prep/`) :
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   cp .env.example .env
   ```
3. **Tes clés** (gratuites, une par personne, jamais partagées) dans `prep/.env` :
   H → platform.hcompany.ai/settings/api-keys · Gladia → app.gladia.io > API Keys
4. **Odoo** : `cd odoo && ./setup_odoo.sh` (5 min) → http://localhost:8069
5. **Tests** (depuis `prep/`) :
   ```bash
   .venv/bin/python 01_test_agents_api.py      # l'agent H navigue sur le web
   .venv/bin/python 03_test_gladia.py          # transcription d'un audio de démo
   ```
   Pour `02_test_odoo_access.py` (l'agent H dans Odoo) : lancer le tunnel d'abord (`docker compose up -d tunnel` dans `odoo/`) et copier l'adresse dans `ODOO_URL`.
