# Journal de bord — préparation

Ce qui a été fait, pourquoi, et ce qu'on en retient. À relire avant le pitch.

## Jeudi 5 nov — Prise en main de l'Agents API H

**Installation**
- Environnement Python isolé dans `prep/.venv` (n'abîme pas le Python de l'ordi).
- Paquets : `hai-agents` (SDK officiel H), `pydantic` (format de réponse imposé), `python-dotenv` (lecture de la clé).

**Clé API**
- Rangée dans `prep/.env`, fichier privé, ignoré par git (`.gitignore`).
- Le script la lit automatiquement (`load_dotenv()`), plus besoin de `export`.
- Règle : la clé ne va jamais dans un fichier de doc, un commit ou un message.

**Le test (`01_test_agents_api.py`)**
- Envoie une tâche en langage naturel à l'agent `h/web-surfer-pro`, qui pilote un vrai navigateur dans le cloud de H.
- Tâche : « va sur Hacker News, donne le titre du 1er article, signale les blocages ».
- `answer_schema` oblige l'agent à répondre dans un format fixe : `success`, `summary`, `blockers`.
  C'est ce qu'on utilisera pour les factures : une réponse exploitable par le code, pas du texte libre.

**Résultats (3 runs)**

| Run | Succès | Temps | Événements |
|---|---|---|---|
| 1 | ✅ | 21,8 s | 15 |
| 2 | ✅ | 19,0 s | 15 |
| 3 | ✅ | 19,3 s | 15 |

**Ce qu'on en retient**
- 3/3 réussites, ~20 s par session pour une tâche simple.
- ⚠️ Le titre est toujours juste, mais le petit texte varie d'un run à l'autre
  (nom de domaine lu `sshole.com`, `ss-hole.com`, `sshhole.com`).
  → Sur des factures (montants, n° TVA), ce genre d'écart est critique.
  → Argument pour le pitch : c'est pour ça qu'on mesure la fiabilité sur plusieurs runs, et que la Skill + la validation humaine comptent.

## Jeudi 5 nov — Les 10 factures de test

**Fichiers** (`prep/factures/`)
- `INV-001.pdf` à `INV-010.pdf` : 10 factures fournisseurs fictives, au format français classique.
- `verite_terrain.csv` : les bonnes réponses pour chaque facture (fournisseur, n°, date, HT, TVA, TTC, comportement attendu).
- `generer_factures.py` : le script qui les crée. On le relance pour les régénérer à l'identique.

**Pourquoi une vérité terrain ?** Pour le benchmark, on compare ce que l'agent saisit dans Odoo
avec ces valeurs. Sans elle, on ne pourrait pas dire « 9/10 correctes ».

**Variété volontaire** (pour tester l'agent)
- De 1 à 3 lignes par facture.
- Plusieurs taux de TVA : 20 % et 5,5 % (le café, INV-003).
- Montants de 189 € à 1 366 €.

**Les 2 pièges**

| Facture | Piège | Ce que l'agent doit faire |
|---|---|---|
| INV-007 | Fournisseur allemand, TVA 0 % (autoliquidation) | Saisir avec TVA 0 % et prévenir l'humain |
| INV-009 | Total TTC imprimé faux : 1 366 € au lieu de 1 266 € (+100 €) | Ne pas valider, signaler l'écart |

**Argument pitch :** un agent « prompt seul » recopie le total imprimé. Un agent qui a appris
de la démo (« je vérifie toujours HT + TVA = TTC ») le repère. C'est ce que le benchmark A/B doit montrer.

## Jeudi 5 nov — Odoo en local avec Docker

**Pourquoi Docker** : on contrôle tout (on peut remettre la base à zéro entre deux runs du benchmark).
**Le hic** : l'agent H tourne dans le cloud de H, il ne voit pas `localhost`. Il faut un **tunnel**
qui donne à notre Odoo une adresse publique temporaire (`https://xxx.trycloudflare.com`).

**Fichiers** (`prep/odoo/`)
- `docker-compose.yml` : 3 conteneurs → `db` (PostgreSQL, les données), `odoo` (l'appli), `tunnel` (Cloudflare, l'adresse publique).
- `odoo.conf` : réglages Odoo. Privé (ignoré par git), contient un mot de passe maître aléatoire.

**Ce qui est en place**
- Base `hackathon`, appli Facturation, société « Atelier Dorn SAS » à Paris.
- Plan comptable **français** : TVA 0 %, 5,5 %, 10 %, 20 % disponibles (utile pour INV-003 et INV-007).
- Compte admin renommé et mot de passe aléatoire fort (rangés dans `.env`), car l'Odoo sera visible sur internet.
- Gestionnaire de bases caché sur l'adresse publique (`list_db = False`).
- Odoo tourne sur http://localhost:8069 ✅

**Commandes utiles** (depuis `prep/odoo/`)
- Démarrer : `docker compose up -d`
- Voir l'adresse publique : `docker compose logs tunnel | grep trycloudflare`
- Arrêter : `docker compose down` (les données sont conservées)

⚠️ L'adresse publique change à chaque redémarrage du tunnel → mettre à jour `ODOO_URL` dans `.env`.

**Tunnel : bloqué par le réseau (jeudi 5 nov)**
- Le tunnel Cloudflare a besoin du port **7844** pour sortir. Le wifi actuel le bloque (testé : 7844 fermé, 443 ouvert).
- Essayé : protocole QUIC (UDP) ❌, puis HTTP/2 (TCP 7844) ❌.
- ⚠️ Risque pour le week-end : le wifi du hackathon peut bloquer pareil. Il faut une solution qui passe par le port 443 (le web normal), ou un partage de connexion 4G.

## Vendredi 6 nov — L'agent H atteint Odoo ✅

- Nouveau réseau : port 7844 ouvert → tunnel Cloudflare OK (protocole http2).
- Test `02_test_odoo_access.py` : l'agent se connecte et ouvre **Facturation > Fournisseurs > Factures fournisseur**.
  58 s, 51 événements, aucun blocage. Il ne crée rien (consigne de lecture seule).

**🔎 Découverte importante : l'agent a inventé un détail.**
- Il affirme avoir vu « 10 factures REF0001–REF0010 ».
- Vérification directe dans la base Odoo : **0 facture**. C'est faux.
- Conséquence pour le projet : **on ne croit jamais l'agent sur parole.**
  Le benchmark doit vérifier l'état réel d'Odoo (ce qui est vraiment saisi) et le comparer à `verite_terrain.csv`,
  pas se fier au résumé que l'agent renvoie.
- Argument pitch : « Notre contrôle ne repose pas sur ce que l'agent dit avoir fait, mais sur ce qui est réellement dans l'ERP. »

**Rappel** : l'adresse publique change à chaque redémarrage du tunnel → mettre à jour `ODOO_URL` dans `.env`.

## Vendredi 6 nov — Préparation Gladia + questions pour H

**Gladia** (transcription de la voix pendant la démo)
- `03_test_gladia.py` : envoie un audio à Gladia et affiche le texte avec les horodatages (début → fin de chaque phrase).
  Les horodatages servent à relier ce que l'humain dit à ce qu'il fait à l'écran au même moment.
- `audio/demo_narration.wav` : 1 min de voix de synthèse qui commente la saisie d'INV-001.
  Elle contient volontairement les **règles implicites** que la Skill doit apprendre :
  « je vérifie toujours HT + TVA = TTC », « fournisseur étranger → TVA 0 % et je signale », « je laisse en brouillon ».
  `audio/demo_narration.txt` contient le texte exact, pour comparer avec la transcription de Gladia.

**Questions pour H** : 5 nouvelles questions ajoutées à `QUESTIONS.md`, tirées de nos tests
(coût des 60 sessions du benchmark, tunnels, wifi, envoi de PDF, détail inventé par l'agent).

## Vendredi 6 nov — Projet regroupé dans `Bureau/Hackathon H`

- Tout le projet est maintenant dans **`~/Desktop/Hackathon H`** (avant : `~/Projet perso/hackathon-h-show-me-once`).
- L'environnement Python `.venv` a été recréé : il contient des chemins absolus et ne supporte pas d'être déplacé.
- Odoo : les données sont dans des volumes Docker, indépendants du dossier → rien de perdu (société + plan comptable FR vérifiés).
- Le tunnel est arrêté. Pour le relancer : `cd ~/Desktop/"Hackathon H"/prep/odoo && docker compose up -d tunnel`,
  puis copier la nouvelle adresse dans `ODOO_URL` du `.env`.
- Le fichier `.env` est dans `prep/`. Il est caché dans le Finder (Cmd + Maj + . pour l'afficher).

## Vendredi 6 nov — Gladia fonctionne ✅

- Clé Gladia en place dans `.env`. Transcription d'1 min d'audio en **~5 s**.
- 1er essai (voix de synthèse « Eddy ») : transcription très mauvaise, et 30 s du milieu **perdues**,
  justement le passage avec les règles implicites.
- 2e essai (voix « Thomas ») : quasi parfait. Les 3 règles sont transcrites mot pour mot,
  les montants arrivent en chiffres (« 24,90 euros », « 298,80€ »), avec un horodatage par phrase.
  Petites erreurs restantes : « Papetri Martin », « ramède de papier ».
- `audio/demo_narration.wav` = maintenant la version « Thomas ».

**Ce qu'on en retient**
- La qualité de la voix compte énormément → pendant la démo : **micro proche, pièce calme, phrases courtes**.
- Les noms propres sont fragiles (« Papetri ») → la Skill doit croiser la voix avec les **captures d'écran**,
  où le nom est écrit correctement. C'est l'intérêt de combiner voix + écran.
- Les règles implicites passent bien à l'oral → c'est exactement la matière dont la Skill a besoin.

## Vendredi 6 nov — Guide de répétition + correction INV-007

- `GUIDE_REPETITION.md` : guide pas à pas pour découvrir Odoo, saisir INV-001 à la main, puis l'enregistrer
  en commentant (QuickTime, écran + micro). Les noms de menus et de champs ont été relevés dans **notre** Odoo.
- **Correction métier (INV-007, fournisseur allemand)** : dans Odoo, la bonne saisie n'est pas « TVA 0 % »
  mais la taxe **« 20% EU G »** (autoliquidation intra-UE). L'entreprise déclare elle-même 20 % de TVA due
  et 20 % de TVA déductible, donc net 0 € : on paie bien 1 240 €. `verite_terrain.csv` est mis à jour.
  → Bel exemple de règle métier qu'un agent ne devine pas seul, mais qu'un comptable montre en 2 secondes.
- **ffmpeg** (outil qui extrait le son et les images d'une vidéo) : installé via le paquet Python `imageio-ffmpeg`,
  dans `.venv`. Homebrew ne marchait pas : version Intel sur un Mac M5, incompatible avec macOS 26.

## Vendredi 6 nov — Partage avec l'équipe

- **Dépôt git** créé dans `Bureau/Hackathon H` (préparation uniquement, pas le code produit).
  Les secrets en sont exclus : `.env` et `odoo/odoo.conf` sont dans `.gitignore`, et j'ai vérifié qu'aucune clé n'est commitée.
  Les vidéos (`.mov`, `.mp4`) sont exclues aussi, trop lourdes : à partager par Drive.
- **`odoo/setup_odoo.sh`** : installe en une commande le même Odoo chez chaque membre
  (compta française, société fictive, compte sécurisé écrit dans `.env`). Testé sur une copie isolée ✅.
- **README** : section « Démarrage pour l'équipe ».
- **Kit équipe** (document en ligne partageable) : projet en 1 page, état des tests, découvertes,
  installation, mission par rôle, plan de tournage, planning.

## Vendredi 6 nov — Holo (Models API) : le cœur du projet fonctionne ✅

- `04_test_holo.py` : 2 tests, appel en format compatible OpenAI (`api.hcompany.ai/v1/chat/completions`).
- **Accès** : `holo4-27b` et `holo4-35b-a3b` → erreur 402, ils demandent des crédits payants.
  `holo3-1-35b-a3b` est **gratuit** et suffit pour nos tests (modèle par défaut du script).
- **Test 1 — lire une facture (image d'INV-009)** : 2,8 s. Tous les champs sont justes, et il **repère le piège** :
  « HT + TVA = 1 266 € ≠ TTC affiché 1 366 € ».
- **Test 2 — écrire une Skill** (transcription de la démo + image d'INV-001) : 3,6 s.
  Résultat propre en 3 parties : ÉTAPES (menus Odoo exacts), RÈGLES (contrôle du total, brouillon), ARRÊT (quand prévenir l'humain).

**Ce qu'on en retient**
- La chaîne « démo commentée → Skill » marche dès maintenant, en quelques secondes.
- ⚠️ **La Skill recopie aussi les erreurs de l'humain.** La narration disait « TVA à zéro » pour un fournisseur étranger,
  et la Skill l'a reprise, alors que la bonne saisie est « 20% EU G ».
  → C'est exactement pour ça que la Skill doit être **relue et éditable** avant de lancer l'agent (critère UX & contrôle).
  → Phrase pitch : « L'agent apprend votre méthode, et vous gardez la main sur ce qu'il a appris. »
- Question pour H (Discord) : Holo4 sera-t-il accessible pendant le hackathon avec les crédits fournis ?

## Samedi 7 nov, 10h40 — Pivot : Stripe à la place d'Odoo, cas d'usage finance

**Pourquoi** : Stripe est partenaire du hackathon et présent sur place (aide + jury sensible). Le brief H (doc de Nolwenn)
pousse la finance/assurance et note surtout le computer use (25 %) et la fiabilité (25 %).

**Cas d'usage proposé** : une personne de l'équipe finance/support montre **une fois** comment traiter une
**demande de remboursement** dans le Dashboard Stripe (sandbox), en commentant ses règles à voix haute :
« moins de 30 jours → je rembourse ; plus de 30 jours → je refuse et je préviens ; client avec un litige ouvert → je ne touche à rien ».
L'agent traite ensuite 10 demandes, s'arrête **avant** chaque remboursement et l'humain valide.
- Pièges : demande hors délai, montant demandé ≠ montant payé, paiement introuvable, litige (chargeback) en cours.
- Données de test : créées via l'API Stripe avec la clé sandbox (`sk_test_`) ; l'agent, lui, ne passe que par l'écran.

**Risque n°1 à tester tout de suite** : la connexion de l'agent au Dashboard (code par e-mail sur « nouvel appareil », captcha).
→ `05_test_stripe_access.py`. Si ça bloque : demander à l'équipe Stripe sur place, sinon Odoo reste le plan B (déjà prêt).

**Question jury attendue** : « Stripe a une API, pourquoi un agent qui clique ? »
→ Parce que la valeur, ce sont les **règles de la personne**, pas l'appel API ; et la même méthode marche
sur n'importe quel outil sans API (back-office maison, portail fournisseur…). Stripe n'est que la vitrine.

## Samedi 7 nov, 11h — Ce que disent les ressources sponsors (poussées par Thomas)

- **Aucune track ni grille de jugement** dans les ressources. Prix (page Luma) : podium 5 000 / 3 000 / 2 000 €,
  Best Use of Gladia 1 000 €, Best Use of Devin 1 000 €. **Pas de prix Stripe** : Stripe offre seulement 250 $ de crédits par participant.
- **Nouveau sponsor : Linkup** (API de recherche web) → utile pour vérifier un fournisseur ou un client sur le web.
- **Plateforme H** : « browser profiles » et « vaults » → l'agent peut garder une session connectée
  et des identifiants sans les écrire dans la consigne (règle le risque de connexion Stripe/Odoo).
- **H a ses propres « Skills »** (hub.hcompany.ai/agents-api/skills/overview) → notre Skill doit être une vraie Skill H.
