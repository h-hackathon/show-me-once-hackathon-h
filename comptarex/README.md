# Comptarex : faux logiciel de cabinet comptable

« COMPTAREX Cabinet 6.2 » imite un logiciel de cabinet de 2004 : gris Windows 2000, Tahoma 11 px, codes partout,
menus en arbre, éditions en Courier. Il sert de **cible de test aux agents H** : l'agent n'a aucune API, il doit
passer par l'écran. Le projet a deux versions, branchées sur la **même base SQLite** :

- **web** (Flask) : pour l'agent navigateur (Agents API H, ou un navigateur sur le poste) ;
- **logiciel** (Qt / PySide6, style Windows) : une vraie fenêtre macOS pour l'agent desktop.

Maquette validée : https://claude.ai/artifact/K6YXQ7xbZGyu7RWsXcE4YW

## Lancer

```bash
cd comptarex
uv sync
uv run comptarex-admin init                  # crée .env : identifiants + jeton admin tirés au hasard
uv run comptarex-web                         # site : http://127.0.0.1:8042
uv run --extra desktop comptarex-desktop     # logiciel de bureau (même base)
```

Les identifiants sont dans `.env` (`SITE_LOGIN`, `SITE_PASSWORD`). Au premier lancement, la base
`data/comptarex.db` est créée avec les données fictives (graine fixe : toujours les mêmes chiffres).

## Les deux parcours

**Reporting**, la situation comptable à date :

Connexion → choix du dossier **00417 ATELIER DORN SAS** → menu *Editions* → *Etats de synthèse* →
*Situation intermédiaire* → date « au » en JJ/MM/AAAA → onglet *Destination* = *Ecran* → *Lancer l'édition*.
Ensuite, *Transmettre au client…* envoie la situation dans l'espace client.

**Saisie d'une facture fournisseur** (contrat du pipeline SMO, `smo/docs/CONTRAT_SITE.md`) :

Bureau → *Factures à traiter* (les PDF INV-001…010) → *Saisir*. On peut aussi passer par le menu
*Saisie* → *Factures fournisseurs* → *Nouvelle facture*.

- Champs : *Fournisseur* (autocomplétion, ou *+ Créer le fournisseur*), *Référence fournisseur*, *Date de facture*, puis des lignes *Libellé / Quantité / Prix unitaire HT / Taxe*.
- Boutons : *Enregistrer le brouillon* / *Valider*.

## Pièges volontaires

| Piège | Ce qui se passe |
|---|---|
| Destination par défaut = Imprimante | « Edition envoyée vers \\SRV-CAB01\HP LaserJet… » : rien ne s'affiche. On peut mémoriser *Ecran* comme destination par défaut. |
| Bouton *Aperçu* | Il demande Java 1.4.2. Seul *Lancer l'édition* avec la destination *Ecran* fonctionne. |
| Dates | JJ/MM/AAAA obligatoire, sinon « Erreur 0x2F ». |
| Contre-valeur en francs | Case cochée par défaut. |
| Brouillard | 23 écritures non validées, exclues sauf si on coche la case (le résultat et la trésorerie changent alors). |
| Choix du dossier | 14 dossiers, dont un verrouillé par un collègue et un clôturé (ouverts en consultation seule). |
| INV-007 | Fournisseur allemand absent du fichier : il faut le créer, puis appliquer la taxe « 20 % autoliquidation UE ». Le nom de l'expéditeur est mal décodé (BÃœROTECHNIK). |
| INV-009 | Le TTC imprimé est faux de 100 € (1 366,00 au lieu de 1 266,00). Le prélèvement de 1 266,00 est visible dans le brouillard bancaire. |
| Doublons | Une même référence chez un même fournisseur est refusée. |
| Modules absents | Bilan, Journaux, etc. renvoient « Module non disponible (code 0x41) ». |

## Chiffres de référence (dossier 00417, au 31/10/2026, écritures validées)

| | Montant |
|---|---|
| Chiffre d'affaires | 412 380,00 |
| Résultat net provisoire (avant IS) | 40 337,85 (264 598,95 FRF) |
| Trésorerie | 60 566,37 (BNP 48 213,77 · Crédit Agricole 12 040,10 · caisse 312,50) |
| Clients | 67 450,00, dont 8 900,00 échus à plus de 60 jours |
| Fournisseurs | 23 118,56 |
| TVA à décaisser | 5 494,50 |

- Toutes les variantes (30/09, 31/10 et 04/11, avec et sans brouillard) sont dans `data/verite_terrain_situation.json` (régénérable avec `comptarex-admin verite`).
- Les pièges des factures sont décrits dans `data/verite_terrain_factures.csv`.
- Une facture **validée** génère une écriture et modifie donc la situation. Un brouillon ne la modifie pas.

## API technique (contrôle du banc de test, jamais pour l'agent)

En-tête `X-Admin-Token: <SITE_ADMIN_TOKEN>`, sauf `/api/health`.

| Appel | Effet |
|---|---|
| `GET /api/health` | `{"ok": true, "ui_version": "v1"}` |
| `GET /api/invoices[?reference=PM-2026-0412]` | Factures saisies : `id, numero, dossier, supplier, supplier_code, reference, date (AAAA-MM-JJ), lines[{label, quantity, unit_price, tax}], total_ht, total_tva, total_ttc, status ("draft" ou "validated"), category, piece, created_at, updated_at` |
| `POST /api/admin/reset` | Vide les factures saisies, les fournisseurs créés, les messages envoyés, les éditions et la destination mémorisée. La boîte de réception est gardée. |
| `GET` / `POST /api/admin/ui-version` | `{"version": "v1" ou "v2", "confirm": false}`. Bascule à chaud, sans redémarrage. |

La **v2** change trois choses :
- « Enregistrer le brouillon » devient « Sauvegarder » ;
- « Référence fournisseur » passe dans l'onglet « Détails » ;
- « Catégorie de dépense » devient un champ obligatoire.

Avec `"confirm": true`, une fenêtre « Confirmer l'enregistrement ? » s'affiche en plus avant la sauvegarde.

Les noms de fournisseurs sont stockés comme dans un vieux logiciel : en majuscules sans accents
(« BUROTECHNIK WEBER GMBH »). Il faut les comparer sans tenir compte de la casse ni des accents.

En ligne de commande, les mêmes actions : `uv run comptarex-admin reset | rebuild | ui v2 [--confirm] | verite`.

## Mettre la version web en ligne (Railway)

Les navigateurs cloud de l'Agents API H ne voient pas `localhost` : il faut une adresse HTTPS publique.
Seule la version web se déploie. L'application de bureau reste locale.

Tout est prêt dans `comptarex/` :
- `Dockerfile` : Python 3.12, uv, gunicorn avec 1 processus et 8 fils (SQLite n'accepte qu'un processus) ;
- `railway.json` : build Docker, vérification de santé sur `/api/health`, 1 seule instance ;
- un mode production, activé tout seul sur Railway : cookies `Secure`, HTTPS derrière le proxy, `robots.txt` qui interdit l'indexation.

**En production, le site refuse de démarrer** si `SITE_PASSWORD`, `SECRET_KEY` ou `SITE_ADMIN_TOKEN` manquent ou reprennent une valeur visible dans le dépôt (valeur par défaut du code ou de `.env.example`), ou sont trop courts (8 caractères au minimum pour le mot de passe, 16 pour la clé et le jeton). Le journal de déploiement indique alors lesquelles régler.

### Étapes (tableau de bord Railway)

1. **New Project → Deploy from GitHub repo** → dépôt `show-me-once-prep` (branche `main`).
2. Dans le service, **Settings** :
   - **Root Directory** = `comptarex` ;
   - **Config file path** = `/comptarex/railway.json`. Le chemin est absolu : Railway ne cherche pas ce fichier dans le Root Directory.
3. **Variables**. Tire de nouvelles valeurs au hasard avec `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` et ne réutilise pas celles du `.env` local.

   | Variable | Valeur |
   |---|---|
   | `SITE_LOGIN` | `c.moreau@fiduciaire-moreau.test` |
   | `SITE_PASSWORD` | un mot de passe tiré au hasard |
   | `SITE_ADMIN_TOKEN` | un jeton tiré au hasard |
   | `SECRET_KEY` | une clé tirée au hasard |
   | `COMPTAREX_DB` | `/data/comptarex.db` (seulement avec le volume de l'étape 4) |

4. **Volume** (recommandé) : clic droit sur le service → **Attach volume**, point de montage `/data`. Sans volume, la base repart des données d'origine à chaque déploiement et les saisies sont perdues.
5. **Settings → Networking → Generate Domain**, puis le port proposé par Railway (le site écoute sur `$PORT`).
6. **Deploy**, puis vérifier :
   ```bash
   curl https://<domaine>.up.railway.app/api/health
   # {"ok":true,"ui_version":"v1"}
   curl -H "X-Admin-Token: <SITE_ADMIN_TOKEN>" https://<domaine>.up.railway.app/api/invoices
   # []
   ```
   Ouvrir aussi `https://<domaine>.up.railway.app/login` et se connecter avec `SITE_LOGIN` / `SITE_PASSWORD`.
7. Donner à l'équipe SMO (dans `smo/.env`) : `SITE_URL=https://<domaine>.up.railway.app`, `SITE_PASSWORD` et `SITE_ADMIN_TOKEN`. `SITE_LOGIN` et `SITE_DOSSIER=00417 ATELIER DORN SAS` ne changent pas.

Avec la CLI, c'est la même chose : `railway login`, `railway init` puis `railway up` depuis `comptarex/`. Les variables, le volume et le domaine se règlent ensuite comme ci-dessus.

Garder **une seule instance** : la base SQLite n'est pas partagée entre plusieurs répliques. Pour remettre le site à zéro entre deux runs du benchmark, appeler `POST /api/admin/reset`.

**Tester l'image en local** :
```bash
docker build -t comptarex .
docker run -p 8042:8042 -e COMPTAREX_PROD=1 -e SITE_PASSWORD=… -e SECRET_KEY=… -e SITE_ADMIN_TOKEN=… comptarex
```

**Sans Railway** (dépannage rapide, sans compte) : `cloudflared tunnel --url http://127.0.0.1:8042` donne une URL
`https://….trycloudflare.com` qui pointe sur le site local.

## Structure

```
comptarex/
  Dockerfile   railway.json   .env.example
  comptarex/
    config.py   db.py   seed.py (données fictives)   compta.py (règles métier partagées)   admin.py
    web/        app.py, templates/, static/
    desktop/    app.py, fenetres.py, situation.py, theme.py
  data/         inbox/INV-001…010.pdf, verite_terrain_*.json|csv, comptarex.db (non versionnée)
```
