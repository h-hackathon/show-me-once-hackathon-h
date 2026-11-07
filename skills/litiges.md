---
name: litiges
description: Procédure apprise d'une démonstration humaine (demo_narration.txt), relue et corrigée.
generated: 2026-11-07 19:35 · holo3-1-35b-a3b · 23.2s · 0 captures
reviewed: true   # relue : arrêt après carte volée, cas « déjà remboursé », « livré contre signature »
---

## ETAPES
1. Ouvrir le litige dans le Dashboard Stripe. Noter le montant et le numéro de commande (CMD-…) dans la description du paiement.
2. Si le montant est inférieur à 15 € : accepter le litige. FIN.
3. Ouvrir Sportiva Care et rechercher les tickets de la commande (numéro CMD-…).
4. Si le titulaire de la carte écrit que sa carte a été volée : accepter le litige, puis sur la fiche client Stripe ajouter la métadonnée `bloque` = `oui`. FIN (ne pas contester, même si le colis a été livré).
5. Ouvrir Sportiva Admin et ouvrir la commande.
6. Si la commande a déjà été remboursée : contester le litige avec le justificatif de remboursement (étape 9). FIN.
7. Ouvrir Parcelia Pro et rechercher l'envoi avec le numéro de commande.
8. Si le colis a été livré contre signature : contester avec la preuve de livraison (étape 9). FIN.
   Sinon, si dans Sportiva Care le client a écrit qu'il a bien reçu son colis : contester avec l'export de la conversation (étape 9). FIN.
   Sinon (colis perdu, ou déposé sans signature et aucune confirmation du client) : accepter le litige. FIN.
9. Contester dans Stripe : cliquer sur « Contester », renseigner le transporteur (Parcelia) et le numéro de suivi si c'est une preuve de livraison,
   puis dans le champ d'informations complémentaires coller la « référence de preuve » affichée sur le document utilisé, avec une phrase qui explique la preuve. Soumettre.

## REGLES
Montant inférieur à 15 € : toujours accepter, sans enquêter.
Carte volée confirmée par le titulaire : accepter ET bloquer le client (métadonnée `bloque` = `oui`), ne jamais contester.
Client déjà remboursé : ne jamais accepter (on paierait deux fois) — contester avec le justificatif de remboursement.
Livré contre signature : contester avec la preuve de livraison Parcelia.
Réception confirmée par écrit au support : contester avec l'export de la conversation.
Aucune preuve : accepter.
La preuve à transmettre est la « référence de preuve » affichée sur le document (remboursement, livraison ou conversation). Ne jamais l'inventer.
Ne jamais laisser un litige sans réponse.

## ARRET
Si la commande est introuvable dans les outils, ou si les informations se contredisent : ne rien soumettre dans Stripe et prévenir un humain en expliquant pourquoi.
