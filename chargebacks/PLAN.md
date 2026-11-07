# Plan : Show me once × chargebacks (projet principal)

> « Chaque contestation de paiement non défendue à temps, c'est de l'argent perdu.
> Léa, aux opérations d'une marketplace, en traite une fois en commentant à voix haute.
> Son agent H défend les 30 suivantes, et le compteur « € récupérés » monte en direct dans Stripe. »

Comptarex (factures) reste le **plan B** : même pipeline SMO, déjà branché et testé hors ligne.

## Pourquoi ce cas

| Question | Réponse |
|---|---|
| La douleur en 10 s ? | Un litige non défendu avant la date limite = argent perdu d'office. ~15 min par litige. |
| Pourquoi du computer use ? | Les preuves qui gagnent sont dans des outils **sans API** : back-office maison, portail transporteur, historique du support. |
| « Ça existe déjà » (Chargeflow, Justt, outils Stripe) ? | Ils ne voient que les données accessibles par API et appliquent **leurs** règles. SMO apprend **les vôtres**, en vous regardant une fois, et va chercher les preuves là où elles sont. |
| Vrais résultats ? | Oui : dans le bac à sable Stripe, des moyens de paiement de test créent de vrais litiges, et la preuve envoyée les fait gagner ou perdre. Le benchmark se mesure en **€ récupérés**. |

## Les règles que Léa dit à voix haute (= la vérité terrain)

| Cas | Décision |
|---|---|
| Livré, avec preuve de signature chez le transporteur | **Contester**, avec le suivi et la signature |
| Client déjà remboursé (vu dans le back-office) | **Accepter** |
| Montant < 15 € | **Accepter** (se défendre coûte plus cher) |
| Carte volée confirmée (le client le dit au support) | **Accepter** et **bloquer le client** |
| Échanges support où le client confirme avoir reçu | **Contester**, avec la capture des échanges |
| Cas non prévu | **S'arrêter et demander à l'humain** |

Toujours : l'agent prépare la réponse puis **s'arrête avant « Soumettre »** ; l'humain valide d'un clic (critère contrôle).

## Ce qu'il faut construire

```
chargebacks/
  PLAN.md                ce fichier
  backoffice/            faux back-office de la marketplace (comme comptarex : web, sans API publique)
  seed_stripe.py         crée les paiements + litiges dans le bac à sable Stripe
  verite_terrain.json    pour chaque litige : la bonne décision et le montant en jeu
```

### 1. Le back-office (Devin, ~2 h) — même recette que comptarex
Un seul site, 3 onglets, les **mêmes clients et montants** que dans Stripe (graine fixe) :
- **Commandes** : n° de commande, client, articles, montant, statut (remboursé ou non), client bloqué ou non.
- **Suivi transporteur** : n° de suivi → historique, preuve de livraison, signature (image).
- **Support** : fil de messages par client (« j'ai bien reçu », « on m'a volé ma carte »…).
- Connexion simple sans captcha ; bouton « Bloquer le client » (seule action d'écriture).
- API technique protégée par jeton (comme comptarex) : `GET /api/customers` (qui est bloqué), `POST /api/admin/reset`.
- Pièges réalistes : deux clients homonymes, un colis livré au point relais sans signature, un remboursement partiel.

### 2. Les litiges Stripe (`seed_stripe.py`, ~1 h)
- Clé `STRIPE_SECRET_KEY=sk_test_...` du compte Stripe créé pour le hackathon.
- 10 paiements avec les moyens de paiement de test qui créent un litige (fraude, colis non reçu…).
  Noms exacts à reprendre de la doc Stripe : docs.stripe.com/testing → section *Disputes*.
- Métadonnées sur chaque paiement : n° de commande du back-office (le lien entre les deux mondes).
- Écrit `verite_terrain.json`.
- Rappel doc Stripe (à revérifier) : en mode test, une preuve contenant `winning_evidence` fait gagner le litige, `losing_evidence` le fait perdre.
  → Le seed fixe donc la preuve gagnante dans le back-office **seulement** pour les litiges qu'on doit contester.

### 3. SMO : brancher la nouvelle tâche (petites modifs, le pipeline ne change pas)
Le pipeline est déjà générique (capture → Skill → agent H → tool Devin → reprise en computer use). Seuls ces points sont propres aux factures :

| Fichier | Aujourd'hui (factures) | Pour les litiges |
|---|---|---|
| `runtime/builtins.py` | `verify_entry` lit `/api/invoices` | `verify_dispute(dispute_id)` lit le litige dans **Stripe par API** : statut, preuve envoyée, montant |
| `runtime/builtins.py` | `check_supplier` (Linkup) | `check_merchant_or_carrier` : Linkup vérifie un transporteur ou une adresse douteuse |
| `pipeline/provision.py` | consignes « pièce en brouillon, ne jamais Valider » | « préparer la réponse, ne jamais Soumettre sans validation » ; règles ci-dessus |
| `config.py` / `.env` | un seul `SITE_*` | `SITE_*` = back-office + `STRIPE_SECRET_KEY` ; connexion Stripe via **vault / browser profile H** |
| `clients/site.py` | factures | clients du back-office |

### 4. Le tableau de bord (front)
- Liste des litiges : décision de l'agent, preuves trouvées (captures), bouton **Valider et soumettre** / **Corriger**.
- **Compteur « € récupérés »** (lu dans Stripe : litiges gagnés) et « € perdus évités ».
- Pause / stop.

## Risques, dans l'ordre

1. **Connexion de l'agent au Dashboard Stripe** (code e-mail « nouvel appareil », captcha).
   Test : `prep/05_test_stripe_access.py`. Parade : vault + browser profile H. Dernière parade : l'agent fait le
   travail d'enquête à l'écran (back-office, transporteur, support) et la **soumission passe par un custom tool qui
   appelle l'API Stripe** — c'est même la bonne architecture : API là où elle existe, computer use là où elle n'existe pas.
2. **Délai de résolution d'un litige en mode test** : à mesurer tout de suite (le compteur doit monter pendant la démo).
3. **Durée d'une session Devin** (> 10 min) : générer le tool en avance, montrer la réparation en accéléré (déjà prévu dans `smo/PLAN.md`).

## Ordre de travail

1. Compte Stripe hackathon + clé `sk_test_` → test de connexion de l'agent (risque 1) et mesure du délai (risque 2).
2. `seed_stripe.py` + `verite_terrain.json`.
3. Back-office (Devin), en ligne sur Railway comme comptarex.
4. Vidéo de démo : Léa traite **un** litige en disant les règles à voix haute.
5. `smo new demo.mov --task "Défendre un litige Stripe" --owner lea --go`.
6. Benchmark : 10 litiges × 3 runs — A : agent seul ; B : agent + Skill ; C : agent + tool. Mesure : **€ récupérés**, bonnes décisions /10, temps.
7. Tableau de bord + compteur, vidéo de secours, pitch.
