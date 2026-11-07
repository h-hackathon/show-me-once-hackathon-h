# Guide — Ta première répétition (≈ 30 min)

Objectif : vivre toi-même l'étape 1 du produit (« je montre une fois ») sur une vraie facture,
pour pouvoir l'expliquer au jury et voir ce qui manque.

On fait ça en 3 temps : **découvrir Odoo** → **s'entraîner sans enregistrer** → **enregistrer**.

---

## Temps 1 — Découvrir Odoo (10 min)

**Odoo, c'est quoi ?** Un logiciel de gestion d'entreprise (ERP) utilisé par des milliers de PME.
On utilise seulement son appli **Facturation**. Une « facture fournisseur » = une facture que l'entreprise
**reçoit** et doit payer (l'inverse d'une facture client).

**Se connecter**
1. Ouvre **http://localhost:8069** dans ton navigateur (Odoo doit tourner, voir en bas).
2. E-mail : ligne `ODOO_LOGIN` de ton `.env` · Mot de passe : ligne `ODOO_PASSWORD`.

**Les 3 mots à connaître**

| Mot Odoo | Ce que ça veut dire |
|---|---|
| **Brouillon** | Facture saisie mais pas encore validée. On peut tout modifier. **On s'arrête toujours là.** |
| **Confirmer** | Valider la facture : elle entre dans la comptabilité. **On ne clique jamais dessus.** |
| **Partenaire / Fournisseur** | L'entreprise qui envoie la facture. |

**Faire le tour (sans rien créer)**
1. En haut à gauche, l'icône en grille (4 carrés) → **Facturation**.
2. Menu du haut **Fournisseurs** → **Factures fournisseurs** : la liste est vide, c'est normal.
3. Menu **Fournisseurs** → **Fournisseurs** : la liste des entreprises, vide aussi.

---

## Temps 2 — Saisir INV-001 une fois sans enregistrer (10 min)

Ouvre la facture à côté de ton navigateur :
```bash
open factures/INV-001.pdf          # depuis prep/
```

**Les clics, dans l'ordre**
1. **Facturation → Fournisseurs → Factures fournisseurs** → bouton **Nouveau** (en haut à gauche).
2. **Fournisseur** : tape `Papeterie Martin SARL` → dans la liste qui apparaît, clique **Créer « Papeterie Martin SARL »**.
   (Le fournisseur n'existe pas encore, Odoo le crée au passage.)
3. **Référence de la facture** : `PM-2026-0412` (le n° imprimé sur la facture).
4. **Date de facturation** : `02/10/2026`.
5. Onglet **Lignes de facture** → **Ajouter une ligne** :
   - **Libellé** : `Ramettes papier A4 80 g (carton de 5)`
   - **Quantité** : `10`
   - **Prix** : `24,90`
   - **Taxes** : vérifie qu'il y a **20% G** (G = biens ; S = services).
6. **Contrôle** : en bas à droite, le total doit afficher **298,80 €**, comme sur le PDF.
7. **Ne clique PAS sur « Confirmer ».** La facture reste en **Brouillon** (en haut à droite). C'est enregistré automatiquement.

Si tu bloques sur un clic, envoie-moi une capture.

Ensuite, supprime ce brouillon pour repartir propre : coche-le dans la liste → **Actions** → **Supprimer**.
(Le fournisseur créé peut rester, ce n'est pas grave.)

---

## Temps 3 — Enregistrer ta démo (10 min)

**Préparer**
- Pièce calme, micro proche. Ferme les notifications (mode Concentration).
- Le PDF d'INV-001 et Odoo ouverts côte à côte.

**Lancer l'enregistrement (QuickTime)**
1. Ouvre **QuickTime Player** → menu **Fichier** → **Nouvel enregistrement de l'écran**.
2. Dans la barre qui apparaît : **Options** → Microphone : **MacBook Pro (micro intégré)** → Enregistrer dans : **Autre emplacement…** → `Bureau/Hackathon H/prep`.
3. Choisis **Enregistrer tout l'écran** → **Enregistrer**.

**Pendant l'enregistrement : refais le Temps 2 en parlant à voix haute.**
Dis ce que tu fais **et pourquoi**, surtout tes règles. Exemple de phrases :
- « J'ouvre Facturation, Fournisseurs, Factures fournisseurs, et je clique sur Nouveau. »
- « Je mets le fournisseur, Papeterie Martin. »
- « La référence, c'est le numéro de facture en haut à droite du PDF. »
- « Avant de valider, je vérifie toujours que hors taxe plus TVA égale le total TTC. »
- « Si le fournisseur est étranger, je mets la taxe d'autoliquidation et je préviens la comptable. »
- « Je ne confirme jamais moi-même, je laisse en brouillon. »

👉 Les phrases « **je vérifie toujours…** », « **si… alors…** », « **je ne… jamais** » sont les plus précieuses :
c'est ton savoir-faire implicite, celui que l'agent ne peut pas deviner.

**Arrêter** : icône ⏹ dans la barre des menus en haut (ou Cmd + Ctrl + Échap).
Renomme la vidéo `demo_INV-001.mov`, puis dis-moi que c'est fait.

**Ce que je ferai avec ta vidéo**
1. Extraire le son → Gladia → tes phrases avec leurs horodatages.
2. Prendre une capture d'écran de la vidéo à chaque phrase.
3. Envoyer phrases + captures à Holo4 → premier brouillon de **Skill** (la procédure écrite).
4. Te montrer le résultat : on verra ensemble ce qui marche et ce qui manque.

---

## Si Odoo ne répond pas
```bash
cd odoo && docker compose up -d db odoo   # depuis prep/
```
(Docker Desktop doit être ouvert : icône de baleine dans la barre des menus.)
