# Contrat site compta ↔ SMO

Le site compta (`logiciel-test/`) est le logiciel cible des démos. SMO en a besoin de trois choses : un parcours réaliste, des libellés stables, et une API technique pour vérifier ce qui est vraiment enregistré.
Ce contrat a été envoyé à la session qui construit le site le 7 nov., et elle l'a intégré.

## Où il tourne

- **En ligne** (HTTPS, public) : il est vu par les navigateurs cloud H et par le serveur SMO (Railway).
- **En localhost** sur le PC de Thomas : c'est le cas desktop. L'agent utilise un navigateur `host: "user_device"`, qui voit le localhost.

## Parcours métier

- **Connexion `/login`** : libellés « E-mail » et « Mot de passe », bouton « Se connecter ». Pas de captcha ni de 2FA, cookie persistant.
- **Choix du dossier** : le cabinet gère 14 sociétés ; il faut ouvrir `SITE_DOSSIER` (ex. « 00417 ATELIER DORN SAS »). `smo.runtime.ui.login` sait passer cet écran.
- **« Factures à traiter »** (boîte de réception) : INV-001 à INV-010 depuis `prep/factures/`, chaque PDF à `/inbox/INV-00X.pdf`. Deux pièges :
  - INV-007 : fournisseur allemand → taxe « 20 % autoliquidation UE » ;
  - INV-009 : TTC imprimé faux de +100 €.
- **« Factures fournisseurs » → « Nouvelle facture »** :
  - champs : Fournisseur (autocomplétion + création à la volée), Référence fournisseur, Date de facture ;
  - lignes : Libellé, Quantité, Prix unitaire HT, Taxe (20 %, 10 %, 5,5 %, 0 %, 20 % autoliquidation UE) ;
  - totaux HT / TVA / TTC.
- **Deux états** : « Enregistrer le brouillon » et « Valider ». L'agent ne valide jamais.
- **2e parcours** : édition d'une situation comptable à date, avec un piège (« Destination = Imprimante » par défaut).

## Accessibilité

Chaque champ a un `<label>` visible relié à son input, chaque bouton a un texte. **Pas de `data-testid`** : les scripts compilés visent les rôles et les libellés, comme sur un vrai logiciel.

## API technique (JSON, header `X-Admin-Token: $SITE_ADMIN_TOKEN`)

| Méthode | Chemin | Usage |
|---|---|---|
| GET | `/api/health` (publique) | `{"ok": true, "ui_version": "v1"}` |
| GET | `/api/invoices[?reference=...]` | `[{id, supplier, reference, date, lines:[{label, quantity, unit_price, tax}], total_ht, total_tva, total_ttc, status: "draft"\|"validated", created_at}]` |
| POST | `/api/admin/reset` | vide les factures saisies (garde la boîte de réception), pour le benchmark |
| GET / POST | `/api/admin/ui-version` | `{"version": "v1"\|"v2"}`, bascule à chaud |

## Interface v2 (démo du precheck et de la réparation)

- « Enregistrer le brouillon » devient « Sauvegarder ».
- « Référence fournisseur » passe dans un onglet « Détails ».
- Nouveau champ obligatoire : « Catégorie de dépense ».
- En option : une fenêtre de confirmation avant l'enregistrement.

## Variables à mettre dans `smo/.env`

`SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_DOSSIER`, `SITE_ADMIN_TOKEN`.
