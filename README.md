# Show me once

> « Vos équipes n'ont pas besoin d'apprendre à automatiser. Elles font la tâche une fois, l'agent fait les 500 suivantes. »

**Cas de démo** : chaque lundi, une personne de l'équipe CRM lance un notebook Databricks qui calcule les résultats
des campagnes email de la semaine, colle le résultat dans un Google Sheet, et le dashboard se met à jour.
Elle le fait **une fois** en commentant à voix haute ; Show me once en tire une **Skill** (procédure + règles implicites),
elle la relit, puis l'agent H fait la même chose pour les 10 pays en parallèle.
Le score ne vient pas du résumé de l'agent : il vient de **ce qui est réellement écrit dans le Sheet**.

Hackathon H Company × 42AI — 7–8 novembre 2026.

## Architecture

```
1. capture   vidéo commentée ──ffmpeg──► audio ──Gladia──► phrases horodatées (+ 1 capture d'écran par phrase)
2. skill     phrases + captures ──Holo (Models API)──► skills/crm-dashboard.md   (relue par l'humain)
3. run       10 pays × Agents API (h/web-surfer-pro) en parallèle :
             Databricks ▸ notebook rapport_<PAYS> ▸ Run all ▸ copier le résultat ▸ Google Sheet ▸ onglet <PAYS> ▸ Dashboard
4. check     contenu réel du Sheet (API Apps Script) vs vérité terrain ──► score, alertes, affirmations fausses
```

**Données** : base CRM 100 % fictive, 5 tables reliées dans `workspace.decathlon_crm` (clés primaires/étrangères) :
`clients` (≈14 000) ─< `envois` (≈98 000) >─ `campagnes` (179) · `envois` ─< `evenements` (≈37 000) · `commandes` (≈3 000).
Générée par `som/crm_data.py` avec une graine fixe : Databricks et notre vérité terrain sont identiques.

**Les 3 pièges** (semaine du 26 octobre 2026) — c'est ce que la Skill doit apprendre de la démo :

| Pays | Piège | Comportement attendu |
|---|---|---|
| FR | campagne « [TEST] Newsletter Running » envoyée à la liste interne | l'exclure du rapport |
| IT | bug de tracking : taux d'ouverture de 112 % | ne pas publier la ligne, prévenir |
| CH | aucune campagne cette semaine | ne pas toucher l'onglet, prévenir |

| Fichier | Rôle |
|---|---|
| `som/crm_data.py` | génération de la base + calcul du rapport + règles (vérité terrain) |
| `som/notebooks.py` → `databricks/01_setup_crm.py` | notebook de setup à importer dans Databricks |
| `sheets/dashboard.gs` | Apps Script : onglets pays, dashboard + graphiques, API lecture/reset |
| `som/capture.py` | vidéo → phrases Gladia + captures |
| `som/skill_builder.py` | démo → Skill (Holo) |
| `som/runner.py` | sessions Agents API en parallèle, réponse structurée |
| `som/checker.py` | notation contre la vérité terrain |

## Installation (≈ 20 min)

**1. Python**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Remplis `HAI_API_KEY` et `GLADIA_API_KEY` dans `.env`.

**2. Databricks Free Edition** (databricks.com/learn/free-edition, compte dédié au hackathon)
- Workspace ▸ ton dossier ▸ ⋮ ▸ **Import** ▸ fichier `databricks/01_setup_crm.py` ▸ **Run all** (≈ 1–2 min).
- Il crée les 5 tables et les 10 notebooks `rapport_<PAYS>` dans le dossier `show-me-once`.
- Copie l'adresse du workspace dans `DATABRICKS_URL`.

**3. Google Sheet**
- Nouveau Sheet ▸ Extensions ▸ Apps Script ▸ colle `sheets/dashboard.gs` ▸ change `TOKEN` ▸ exécute `setup`.
- Déployer ▸ Nouveau déploiement ▸ Application Web (Exécuter en tant que : Moi · Accès : Tout le monde) ▸ URL `/exec` → `SHEET_WEBAPP_URL`.
- Partager ▸ « Tous les utilisateurs disposant du lien » ▸ **Éditeur** → lien dans `SHEET_URL` (l'agent n'a pas à se connecter à Google).
- `SHEET_TOKEN` = la valeur de `TOKEN`.

**4. Connexion de l'agent à Databricks** (Free Edition envoie un code par e-mail)
- **Option 1, recommandée** : créer un profil navigateur sur la plateforme H, s'y connecter une fois à Databricks → `HAI_BROWSER_PROFILE_ID`.
- **Option 2** : `DATABRICKS_EMAIL` + une boîte mail lue en IMAP (`OTP_IMAP_*`, mot de passe d'application) : l'agent récupère le code tout seul.

**5. Vérifier**
```bash
python -m som sheet-reset
python -m som doctor --online
```

## Premier test

```bash
python -m som skill --transcript data/demo/demo_narration.txt
python -m som run -c B -p FR
python -m som run -c AB -p FR,IT,CH
```
Après la commande `skill` : relis `skills/crm-dashboard.md`, corrige si besoin, passe `reviewed: true`.
`run -c AB -p FR,IT,CH` lance les 2 conditions sur les 3 pays piégés.

Pour voir ce que chaque onglet doit contenir : `python -m som truth -p FR,IT,CH`.

## Avec une vraie démo

```bash
python -m som capture demo_FR.mov
python -m som skill --demo runs/demo/demo_FR/demo.json
```
Le script de la narration (avec les 3 règles à dire à voix haute) est dans `data/demo/demo_narration.txt`.

## Benchmark A/B

```bash
python -m som bench --runs 2 --concurrency 5
```
10 pays × (A, B) × 2 runs = 40 sessions. Le Sheet est remis à la semaine précédente avant chaque lot.
Résultats dans `runs/<date>/` : `log.csv` (format du brief H, avec le lien de replay de chaque session),
`scores.csv` (détail par pays), `answers_*.json`.

## À vérifier sur le premier vrai run
- L'agent arrive-t-il à copier le texte du dernier bloc du notebook ? Sinon : bouton de téléchargement CSV du tableau, puis Fichier ▸ Importer dans Sheets.
- Combien de sessions en parallèle nos crédits et le profil navigateur acceptent (`--concurrency`).
