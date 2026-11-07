# Show me once — la cellule litiges qui apprend en regardant

> « Vos équipes n'ont pas besoin d'apprendre à automatiser. Elles font la tâche une fois, l'agent fait les 500 suivantes. »

**Le problème.** Chaque contestation de paiement (chargeback) non défendue à temps, c'est de l'argent perdu.
Une marketplace en reçoit des centaines par jour, à environ 15 minutes chacune : 400 litiges = 100 heures de travail.
Et ce n'est pas automatisable par API : les preuves sont dispersées dans des outils qui n'en ont pas
(back-office, portail transporteur, support), et la décision dépend de règles que seule l'équipe connaît.

**Ce qu'on a construit.** Une analyste traite **un** litige en commentant à voix haute. Show me once en tire une **Skill**
(procédure + règles), elle la relit, puis l'agent H traite toute la file en parallèle, directement dans le Dashboard Stripe.
Le score ne vient pas de ce que l'agent raconte : il vient **des vrais statuts des litiges dans Stripe**.

Hackathon H Company × 42AI — 7–8 novembre 2026.

## Architecture

```
1. capture   vidéo commentée ──ffmpeg──► audio ──Gladia──► phrases horodatées (+ 1 capture d'écran par phrase)
2. skill     phrases + captures ──Holo (Models API)──► skills/litiges.md   (relue et corrigée par l'humain)
3. run       N litiges × Agents API (h/web-surfer-pro) en parallèle :
             Stripe (litige) ▸ Sportiva Admin ▸ Parcelia Pro ▸ Sportiva Care ▸ décision ▸ Stripe (contester / accepter / bloquer)
4. check     API Stripe : statut réel de chaque litige vs vérité terrain ──► € récupérés, erreurs, fraudeurs bloqués
5. watch     écran de démo local « € récupérés » qui se met à jour pendant que les agents travaillent
```

## Les règles de l'équipe (ce que la Skill doit apprendre)

| # | Situation | Où le voir | Décision |
|---|---|---|---|
| 1 | Montant < 15 € | Stripe | accepter (les frais coûtent plus cher) |
| 2 | Le titulaire confirme le vol de sa carte | Sportiva Care | accepter **et bloquer le client** (métadonnée `bloque = oui`) |
| 3 | Client déjà remboursé | Sportiva Admin | **contester** avec le justificatif de remboursement (sinon on paie deux fois) |
| 4 | Livré contre signature | Parcelia Pro | contester avec la preuve de livraison |
| 5 | Sans signature, mais le client a écrit « bien reçu » | Sportiva Care | contester avec l'export du ticket |
| 6 | Aucune preuve | — | accepter |

**24 litiges réels** dans Stripe (mode test), mélangés : 8 livrés signés, 3 réceptions confirmées au support,
3 déjà remboursés, 3 petits montants, 3 cartes volées, 4 sans aucune preuve. `python -m som truth` affiche la décision attendue.

**Pourquoi c'est réel.** Les litiges sont créés par les cartes de test Stripe qui déclenchent un chargeback.
En mode test, Stripe tranche selon la preuve : `winning_evidence` fait gagner, `losing_evidence` fait perdre.
Chaque document des outils affiche sa « référence de preuve » : une preuve qui ne prouve rien fait perdre le litige.

## Résultat attendu du benchmark (simulation)

| | Agent seul (A) | Agent + Skill (B) |
|---|---|---|
| Litiges bien traités | 12 / 24 | **24 / 24** |
| € récupérés | 880 € | **1 182 €** |
| Contestés à tort | 144 € | **0 €** |
| Fraudeurs bloqués | 0 / 3 | **3 / 3** |

(Simulation avec un agent « classique » qui conteste dès qu'il voit une preuve de livraison. Les chiffres réels sortent de `bench`.)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

1. **Clés** : `HAI_API_KEY`, `GLADIA_API_KEY`, et `STRIPE_SECRET_KEY` (clé **de test** `sk_test_…` d'un compte Stripe créé pour le hackathon).
2. **Outils internes** : `python -m som outils` génère `app/data.json`. On déploie le dossier `app/` sur Railway (voir `app/README.md`) → `OUTILS_URL`.
3. **Connexion de l'agent à Stripe** : sur la plateforme H, crée un **profil navigateur**, connecte-toi une fois au Dashboard Stripe dedans
   → `HAI_BROWSER_PROFILE_ID`. (Sinon : `STRIPE_LOGIN` + lecture du code e-mail par IMAP, voir `.env.example`.)
4. **Vérifier** : `python -m som doctor --online`

## Utilisation

```bash
python -m som stripe-seed --batch demo
python -m som skill --transcript data/demo/demo_narration.txt
python -m som watch --batch demo
python -m som run -c B --batch demo -o CMD-10247
python -m som run -c B --batch demo --concurrency 5
python -m som check --batch demo
```

- `stripe-seed` crée les 24 litiges (1–2 min).
- Après `skill` : relis `skills/litiges.md`, corrige, passe `reviewed: true`.
- `watch` ouvre l'écran de démo sur http://localhost:8787, à laisser ouvert dans un 2e terminal.
- `run -o CMD-10247` traite 1 litige (le premier test) ; sans `-o`, toute la file.

**Benchmark A/B** — un litige traité ne se rejoue pas, donc chaque condition a son propre lot :

```bash
python -m som stripe-seed --batch runA
python -m som stripe-seed --batch runB
python -m som bench --batch-a runA --batch-b runB --concurrency 5
```

Résultats dans `runs/<date>/` : `log.csv` (format du brief H, lien de replay de chaque session), `scores.csv`, `answers_*.json`.

**Avec une vraie démo** : enregistre l'écran + la voix en traitant un litige, puis
`python -m som capture demo.mov` et `python -m som skill --demo runs/demo/demo/demo.json`.
Le texte à dire (avec les 6 règles) est dans `data/demo/demo_narration.txt`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `som/scenarios.py` | les 24 litiges, leurs preuves, les règles (vérité terrain) |
| `som/seed.py`, `som/stripe_api.py` | création des litiges dans Stripe (mode test), lecture des statuts |
| `som/tools_site.py` → `app/` | Sportiva Admin, Parcelia Pro, Sportiva Care : app Python sans dépendance, déployable sur Railway |
| `som/capture.py`, `som/skill_builder.py` | démo → phrases Gladia + captures → Skill (Holo) |
| `som/runner.py` | une session agent par litige, en parallèle, réponse structurée |
| `som/checker.py` | notation depuis l'état réel de Stripe |
| `som/watch.py` | écran de démo « € récupérés » |

Toutes les données sont fictives (marketplace « Sportiva »). Aucune clé live Stripe n'est acceptée par le code.
