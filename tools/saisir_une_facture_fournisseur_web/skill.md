# Saisir une facture fournisseur

## Objectif
Saisir une facture fournisseur dans Qonta (logiciel COMPTAREX Cabinet), une pièce à la fois, sans jamais finaliser.

## Prérequis
- Être connecté au logiciel.
- S'il faut choisir un dossier ou une société : celui du client indiqué sur la pièce.

## Étapes
1. Aller sur la page de connexion de Qonta.
2. Se connecter avec les identifiants du vault (« E-mail », « Mot de passe »), puis cliquer sur « Se connecter ».
3. Écran « Sélection du dossier de travail » : chercher le client indiqué sur la pièce (champ « Rechercher : », puis « OK »),
   puis cliquer sur le nom du dossier (ex. « 00417 ATELIER DORN SAS ») : le « Bureau du dossier » s'ouvre.
   Ne pas utiliser « Ouvrir en consultation » (lecture seule).
4. Menu « Saisie » → « Factures fournisseurs » → « Nouvelle facture ».
5. « Fournisseur » : taper au moins 2 lettres du nom lu sur la pièce, puis le choisir dans la liste
   (ex. « NETCLOUD SERVICES — 401NETCL »). Ne pas choisir « + Créer le fournisseur … » : s'il est absent de la liste,
   s'arrêter et prévenir un humain.
6. « Référence fournisseur » : le n° de facture lu sur la pièce.
7. « Date de facture » : la date de la pièce, au format JJ/MM/AAAA.
8. Pour chaque ligne de la pièce (« Ajouter une ligne » si besoin) : « Libellé », « Quantité », « Prix unitaire HT », « Taxe ».
   Le formulaire propose plusieurs lignes vides : celles qui restent vides ne sont pas enregistrées.
9. Vérifier que le total TTC affiché (« Totaux de la facture ») est égal au total TTC de la pièce ; sinon, s'arrêter
   et expliquer l'écart.
10. Cliquer sur « Enregistrer le brouillon », puis lire le n° attribué (FA-…) dans le bandeau.
    Si Qonta répond « Doublon : la facture … existe déjà (n° FA-…) », la pièce est déjà saisie : ne rien refaire.

## Règles
- Le bouton Valider est irréversible, une fois validée la facture ne peut plus être modifiée
- Le champ Fournisseur doit identifier le fournisseur réel et être rattaché au compte auxiliaire correspondant ; utilisez l'autocomplétion si elle est disponible, mais le seuil de deux lettres et le choix dans une liste ne sont pas des exigences réglementaires ou comptables établies ici. (corrigé par vérification ; dit pendant la démo : « Le champ Fournisseur nécessite une autocomplétion, il faut taper au moins 2 lettres puis choisir dans la liste »)
- La date doit être saisie au format JJ/MM/AAAA
- Ne jamais finaliser (valider, confirmer, envoyer, payer, supprimer) : enregistrer sans finaliser, un humain s'en charge.

## S'arrêter et prévenir un humain si
- La facture est validée et comptabilisée
- Une erreur de validation empêche la saisie

## À lire sur la pièce
- Client (« Facturé à ») : le dossier à ouvrir
- Fournisseur
- Référence fournisseur
- Date de la facture
- Libellé
- Quantité
- Prix unitaire HT
- Taxe
- Montant HT
- Montant TTC
