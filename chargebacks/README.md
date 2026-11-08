# Sportiva — outils factices et litiges Stripe de démonstration

Environnement de démonstration indépendant, développé pour un hackathon. Marques et données 100 % fictives.

Le repo contient trois parties, chacune dans son dossier :

| Dossier | Contenu |
|---|---|
| [`app/`](app/) | les 3 outils internes factices (déployés sur Railway) |
| [`som/`](som/) | la gestion des litiges : données des outils + création des litiges dans Stripe |
| [`chrome_cast/`](chrome_cast/) | l'enregistreur Chrome « Show Me Once » : extension + backend (voir [`chrome_cast/README.md`](chrome_cast/README.md)) |

1. **`app/` : trois outils internes factices**, déployés sur Railway, avec des données reliées entre elles
   (commande ↔ colis ↔ ticket ↔ client).
   - **Sportiva Admin** (`/admin`) : back-office e-commerce — commandes, clients, remboursements, produits, analyses.
   - **Parcelia Pro** (`/parcelia`) : portail transporteur — suivi, étiquette, preuve de livraison (POD).
   - **Sportiva Care** (`/care`) : support client — tickets et conversations.
2. **`som/` : la gestion des litiges** — génère les données des outils et crée de vrais litiges dans un compte
   Stripe **en mode test**, rattachés aux commandes des outils (numéro `CMD-…` dans la description du paiement).
3. **`chrome_cast/` : l'enregistreur Chrome**, indépendant du reste (il a son propre backend, ses propres
   dépendances et son propre `.env`). Il enregistre l'écran, la voix et les clics, puis produit la timeline et
   le `skill.md`. Code repris du repo [noahsgds/chrome_cast](https://github.com/noahsgds/chrome_cast).

## Les données

| | Nombre |
|---|---|
| Litiges (commandes contestées) | 400 |
| Commandes au total (90 jours + historique client) | ≈ 2 460 |
| Colis Parcelia | ≈ 2 360 |
| Tickets support | ≈ 1 010 |
| Clients | ≈ 1 520 |

Les 400 litiges suivent 6 règles, appliquées dans cet ordre (la première qui s'applique décide) :

| Ordre | Condition | Où la vérifier | Décision |
|---|---|---|---|
| 1 | Montant < 15 € | Stripe | Accepter |
| 2 | Carte volée signalée par le titulaire | Sportiva Care | Accepter + bloquer le client (métadonnée `bloque = oui`) |
| 3 | Commande déjà remboursée | Sportiva Admin | Contester (justificatif de remboursement) |
| 4 | Livré contre signature | Parcelia Pro | Contester (preuve de livraison) |
| 5 | Réception confirmée par écrit au support | Sportiva Care | Contester (export de la conversation) |
| 6 | Aucune preuve | — | Accepter |

Résultat attendu : 237 litiges à contester, 36 à accepter en bloquant le client, 127 à accepter.
`python -m som truth` affiche la décision attendue pour chaque commande. Les pages des outils ne l'affichent jamais.

Chaque preuve affiche une « référence de preuve à transmettre ». En mode test, Stripe fait gagner un litige dont la
preuve contient `winning_evidence` et perdre celui dont la preuve contient `losing_evidence`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis colle ta clé Stripe sk_test_…
python -m som doctor
```

## Commandes

```bash
python -m som outils                               # régénère app/data.json
python -m som stripe-seed --batch demo             # crée les 400 litiges dans Stripe (5 à 10 min)
python -m som stripe-seed --batch plus --offset 60 # seulement les litiges 61 à 400 (si les 60 premiers existent déjà)
python -m som stripe-seed --batch video --limit 13 # un petit lot à part
python -m som stripe-sync --batch demo             # récupère les litiges que Stripe n'avait pas encore créés
python -m som truth                                # décision attendue par litige
```

Un litige traité ne se remet pas à zéro : utilise un nom de lot différent pour chaque usage. La liste des litiges
créés est enregistrée dans `runs/stripe/<lot>.json` (ignoré par git).

## Déploiement des outils

Voir `app/README.md` (Railway, Root Directory = `app`, variable `SECRET_KEY`). Après `python -m som outils`,
un `git push` suffit pour que Railway redéploie.

## Fichiers

| Fichier | Rôle |
|---|---|
| `app/server.py` | les 3 outils (Python standard, aucune dépendance) |
| `app/data.json` | les données affichées par les outils |
| `som/scenarios.py` | les 400 litiges, leurs preuves et la règle de décision |
| `som/tools_site.py` | génère `app/data.json` (litiges + commandes ordinaires + historique) |
| `som/seed.py`, `som/stripe_api.py` | création des litiges dans Stripe (refuse toute clé qui n'est pas de test) |
| `chrome_cast/extension/` | extension Chrome MV3 (à charger dans `chrome://extensions`) |
| `chrome_cast/backend/` | backend FastAPI de l'enregistreur (`cd chrome_cast/backend`, voir son README) |
