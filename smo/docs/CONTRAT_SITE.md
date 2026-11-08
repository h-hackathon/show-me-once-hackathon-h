# Contrat site compta ↔ SMO

Le logiciel cible des démos est **Qonta** (`comptarex/` du repo, « QONTA Cabinet 6.2 », un faux logiciel de cabinet de 2004). Il existe en deux versions sur la même base SQLite :
- un site web : `uv run comptarex-web` → http://127.0.0.1:8042 ;
- une application de bureau Qt : `uv run --extra desktop comptarex-desktop`.

SMO a besoin de trois choses : un parcours réaliste, des libellés stables, et une API technique pour vérifier ce qui est vraiment enregistré. Le détail du site est dans `comptarex/README.md`.

## Où il tourne

- **Localhost** (aujourd'hui) : le navigateur cloud H ne le voit pas. SMO ouvre alors le navigateur de l'agent sur cette machine (`host: "user_device"`, extra `hai-agents[browser]`). C'est aussi le cas desktop.
- **En ligne** (pas encore fait, à décider) : tunnel `cloudflared tunnel --url http://127.0.0.1:8042`, ou Railway (dossier racine `comptarex/`, la base est recréée à chaque déploiement).

## Parcours « saisir une facture fournisseur » (vérifié en vrai navigateur par la session du site)

- **Connexion `/login`** : « E-mail », « Mot de passe », bouton « Se connecter ». Le formulaire s'affiche même si une session est déjà ouverte.
- **Choix du dossier `/dossiers`** : aucun dossier n'est imposé. L'agent prend celui du client indiqué sur la pièce ; un tool le reçoit en paramètre (`login(page, cfg, dossier)`).
- **Boîte de réception `/inbox`** (« Factures à traiter ») : chaque PDF est à `/inbox/INV-00X.pdf`, avec le bouton « Saisir ».
- **Nouvelle facture `/factures/nouvelle`**. On y arrive aussi par le menu Saisie → Factures fournisseurs → Nouvelle facture.
  - **Champs** (libellés exacts) : « Fournisseur », « Référence fournisseur », « Date de facture » (JJ/MM/AAAA, sinon « Erreur 0x2F »).
  - **Fournisseur** : en autocomplétion, `role=option`, ex. « PAPETERIE MARTIN SARL — 401PAPMA ». Taper le nom exact suffit, sans tenir compte de la casse ni des accents.
  - **Fournisseurs absents** : on les crée avec « + Créer le fournisseur » (champs « Raison sociale », « Pays », « N° TVA intracommunautaire », bouton « Créer »). Deux sont à créer : BÜROTECHNIK WEBER (INV-007) et FORMATION PLUS (INV-008).
  - **Lignes** : « Libellé », « Quantité », « Prix unitaire HT », « Taxe » (`aria-labelledby`, à viser avec `.nth(i)`). Trois lignes vides par défaut ; « Ajouter une ligne » recharge la page.
  - **Taxes** : « 20 % », « 10 % », « 5,5 % », « 0 % », « 20 % autoliquidation UE ».
- **Boutons** : « Enregistrer le brouillon », « Valider » (fenêtre Oui/Non avant), « Annuler ». Les fenêtres sont du HTML (`role=alertdialog`), pas des `confirm()` natifs.
- **Succès** : le message « Brouillon enregistré sous le n° FA-2026-000X ».
- **Doublon** (même fournisseur + même référence) : refusé par le message « Doublon : … ».

## API technique (header `X-Admin-Token: $SITE_ADMIN_TOKEN`, sauf `/api/health`)

| Méthode | Chemin | Usage |
|---|---|---|
| GET | `/api/health` | `{"ok": true, "ui_version": "v1"}` |
| GET | `/api/invoices[?reference=...]` | factures saisies (format ci-dessous) |
| POST | `/api/admin/reset` | vide les factures, les fournisseurs créés, les messages, les éditions et la destination mémorisée ; garde la boîte de réception. **À faire entre deux runs du benchmark.** |
| GET / POST | `/api/admin/ui-version` | `{"version": "v1"\|"v2", "confirm": false}`, bascule à chaud |

Format d'une facture : `id, numero, dossier, supplier, supplier_code, reference, date, lines[{label, quantity, unit_price, tax}], total_ht, total_tva, total_ttc, status ("draft"|"validated"), category, piece, created_at, updated_at`.

- `date` est en ISO `AAAA-MM-JJ` (l'écran, lui, attend JJ/MM/AAAA).
- `supplier` est en **MAJUSCULES SANS ACCENTS** (« BUROTECHNIK WEBER GMBH ») : on compare sans la casse ni les accents.
- `tax` est le libellé affiché (« 20 % autoliquidation UE »), `quantity` un nombre, `unit_price` en euros.
- **INV-007 attendue** : taxe « 20 % autoliquidation UE », `total_tva` 0, `total_ttc` 1240.

## Interface v2 (démo du precheck et de la réparation)

- « Enregistrer le brouillon » devient « Sauvegarder ».
- « Référence fournisseur » passe dans l'onglet (`role=tab`) « Détails ».
- « Catégorie de dépense » devient obligatoire.
- Le titre passe à « Cabinet 6.3 ».
- Avec `"confirm": true`, la fenêtre « Confirmer l'enregistrement ? » s'affiche avant « Sauvegarder ».

**Vérifié le 7 nov.** (`tests/test_site_live.py`) :
- le precheck passe en v1 (0,9 s) ;
- en v2 (6,4 s), il détecte « Référence fournisseur » et « Enregistrer le brouillon » manquants ;
- le nouveau champ obligatoire n'est pas détecté par le precheck (il ne vérifie que la présence des éléments attendus). C'est `run` qui échoue à l'enregistrement, et l'agent reprend à l'écran.

## Autre parcours : la situation comptable

Bureau → Editions → Etats de synthèse → Situation intermédiaire → date → onglet Destination = Ecran → Lancer l'édition. Piège : la destination par défaut est « Imprimante ». Les chiffres attendus sont dans `comptarex/data/verite_terrain_situation.json`.

## Variables dans `smo/.env`

`SITE_URL` (Qonta en ligne : https://show-me-once-prep-production.up.railway.app), `SITE_LOGIN`, `SITE_PASSWORD`. `SITE_ADMIN_TOKEN` est facultatif (relire ce qui est enregistré). Appli de bureau (base locale) : `DESKTOP_LOGIN`, `DESKTOP_PASSWORD`.

Décisions du 7 nov. au soir : on ne vide pas Qonta entre deux essais (chaque essai traite la pièce suivante), et l'interface reste fixe (pas de bascule v1 / v2 en démo).
