# Saisir une facture fournisseur

## Règle absolue : la tâche à l'écran

Pas encore de tool automatique pour cette tâche : fais-la toi-même à l'écran (computer use), en suivant la méthode
ci-dessous.
- Fournisseur inconnu ou douteux : vérifie-le avec `check_supplier` avant de le créer.

Toujours : ne jamais cliquer sur « Valider ». Réponds au format demandé, avec mode = "computer_use".

## Objectif
Saisir une facture fournisseur dans Comptarex Cabinet 6.2 (https://show-me-once-prep-production.up.railway.app/login), une pièce à la fois, en s'arrêtant en brouillon.

## Prérequis
- Être connecté au logiciel.
- S'il faut choisir un dossier ou une société : celui du client indiqué sur la pièce.

## Étapes
1. Aller sur « Connexion » (Accéder à l'application pour commencer la tâche)
2. Cliquer sur « Se connecter » (Valider la connexion pour accéder au logiciel)

## Règles
- Aucun écran intermédiaire de sélection du dossier après connexion n’est imposé par la réglementation comptable française. Il peut s’agir d’une étape propre au logiciel ou à l’organisation de l’entreprise. La règle comptable consiste à enregistrer la facture dans les comptes de l’entité concernée, avec les justificatifs et imputations appropriés. (corrigé par vérification ; dit pendant la démo : « Écran intermédiaire obligatoire : Sélection du dossier après la connexion »)
- L’autocomplétion est une règle d’interface, pas une exigence réglementaire ou comptable. Les sources fournies n’établissent aucun seuil légal de deux lettres. Pour saisir le fournisseur, recherchez-le dans le référentiel et sélectionnez l’entité correspondant à la facture, en vérifiant son identité et en évitant les doublons ; si le fournisseur est nouveau, créez sa fiche selon la procédure de l’entreprise. Puis contrôlez les données de facture et son imputation comptable. (corrigé par vérification ; dit pendant la démo : « Champ Fournisseur avec autocomplétion : taper au moins 2 lettres puis choisir dans la liste »)
- La validation d’une facture dans le workflow interne n’est pas, à elle seule, une règle légale qui rend toute modification impossible. Il faut distinguer l’approbation interne de la facture et la correction du document comptable : si une facture déjà réglée doit être corrigée ou annulée, elle ne doit pas être modifiée ou remplacée directement ; la correction se fait au moyen d’une facture d’avoir. Pour une facture non réglée, les sources disponibles ne précisent pas une règle générale d’irréversibilité après validation ; en cas d’erreur, il convient de demander au fournisseur une facture corrigée ou, selon le cas, un avoir, et de conserver une trace comptable. (corrigé par vérification ; dit pendant la démo : « Validation irréversible : une fois validée, la facture ne peut plus être modifiée »)
- Session à durée limitée : toute saisie non enregistrée sera perdue à l'expiration
- Lors de la saisie, transcrire la date figurant sur la facture fournisseur, sans la modifier, dans le format requis par le champ ou le logiciel. JJ/MM/AAAA est un format de saisie possible, mais les informations disponibles n’établissent pas qu’il soit imposé par la réglementation française. Vérifier que la date enregistrée correspond à la date portée sur la facture. (corrigé par vérification ; dit pendant la démo : « Date au format JJ/MM/AAAA :respecter le format dans le champ texte »)
- Ne jamais cliquer sur « Valider » ou « Confirmer » : la pièce reste en brouillon.

## S'arrêter et prévenir un humain si
- Quand la facture est enregistrée ou validée
- Quand la session expire

## Carte du logiciel
- Connexion (https://show-me-once-prep-production.up.railway.app/login) : URL de départ du logiciel. Champs : E-mail (type: email), Mot de passe (type: password). Boutons : Se connecter
- Sélection du dossier de travail (https://show-me-once-prep-production.up.railway.app/dossiers) : Écran affiché automatiquement après la connexion. Titre visible : « Sélection du dossier de travail ». Instruction : « Cliquez sur le nom d'un dossier pour l'ouvrir, ou sélectionnez-le puis cliquez sur Ouvrir le dossier. ». Champs : Rechercher (text, placeholder: 'Numéro, nom, SIRET…'), Collaborateur (dropdown, défaut: 'Tous'), Etat (dropdown, défaut: 'Tous'). Boutons : Ouvrir le dossier, Ouvrir en consultation, Créer un dossier…, Actualiser, Page 1/2 (pagination)
- Bureau du dossier (https://show-me-once-prep-production.up.railway.app/bureau) : Écran affiché après l'ouverture d'un dossier. Titre visible : « Bureau du dossier ».. Boutons : Changer de dossier (en haut à droite)
- Factures fournisseur — Nouvelle facture (non enregistrée) (https://show-me-once-prep-production.up.railway.app/factures/nouvelle) : Menu général → Saisie → Factures fournisseur → Nouvelle facture. Titre visible : « Factures fournisseur — Nouvelle facture (non enregistrée) ».. Champs : Journal : AC — ACHATS (libellé fixe, non modifiable), Pièce justificative : aucune (Factures à traiter) — lien « Factures à traiter » pour rattacher une pièce PDF, Fournisseur (text avec autocomplete — « Saisissez au moins 2 lettres puis choisissez dans la liste. »), Référence fournisseur (text), Date de facture (text, format JJ/MM/AAAA), Lignes de facture : Libellé (text), Quantité (number), Prix unitaire HT (number), Taxe (dropdown, défaut 20 %), Montant HT (calculé), Suppr. (bouton x). Boutons : Ajouter une ligne, Enregistrer le brouillon, Valider, Annuler
- Factures fournisseur — liste (https://show-me-once-prep-production.up.railway.app/factures) : Menu général → Saisie → Factures fournisseur → Liste des factures. Titre visible : « Factures fournisseur — liste ».. Boutons : Nouvelle facture, Pagination : <<, <, >, >>
- Factures à traiter — pièces reçus du client (https://show-me-once-prep-production.up.railway.app/inbox) : Menu général → Saisie → Factures à traiter. Titre visible : « Factures à traiter — pièces reçus du client ». Instruction : « Cliquez sur le n° de pièce pour ouvrir le PDF, puis sur « Saisir » pour créer la facture fournisseur correspondante. ». Boutons : Saisir (colonne Action, visible quand une pièce est présente)
- Pièges : PIÈGES ET POINTS D'ATTENTION :\n1. ÉCRAN INTERMÉDIAIRE OBLIGATOIRE — Sélection du dossier : après la connexion, l'agent doit choisir un dossier. Il ne peut pas passer directement à la saisie. Le bouton « Ouvrir le dossier » n'est actif qu'après sélection d'un dossier (cliquer sur son nom). Ne pas confondre avec « Ouvrir en consultation » (mode lecture seule).\n2. CHAMP FOURNISSEUR AVEC AUTOCOMPLÉTION — Il faut taper au moins 2 lettres puis sélectionner dans la liste qui apparaît. Un simple texte libre ne suffira pas : la valeur doit être choisie dans la liste déroulante.\n3. VALIDATION IRRÉVERSIBLE — Le bouton « Valider » est définitif : « Une facture validée ne peut plus être modifiée (contre-passation obligatoire). » Privilégier « Enregistrer le brouillon » si l'agent n'est pas sûr.\n4. SESSION À DURATION LIMITÉE — Le bandeau en bas indique une expiration (ex. « expire dans 14:58 »). Toute saisie non enregistrée sera perdue à l'expiration.\n5. DATE AU FORMAT JJ/MM/AAAA — Le champ Date de facture n'est pas un sélecteur de date mais un champ texte avec placeholder « JJ/MM/AAAA ». Le format doit être respecté.\n6. JOURNAL FIXE — Le journal est pré-rempli à « AC — ACHATS » et n'est pas modifiable depuis ce formulaire.\n7. PIÈCE JUSTIFICATIVE OPTIONNELLE — Le lien « Factures à traiter » dans le formulaire permet de rattacher un PDF déjà reçu. Ce n'est pas obligatoire pour créer la facture.\n8. AUCUNE FENÊTRE DE CONFIRMATION OBSERVÉE — Les boutons « Valider », « Enregistrer le brouillon » et « Annuler » n'ont pas été testés (mode lecture seule). Une fenêtre de confirmation pourrait apparaître à la validation.\n9. « Saisie par journal » — Autre mode de saisie accessible depuis le menu, non exploré ici. Il pourrait être une alternative pour la saisie de factures fournisseur via les journaux comptables.
