# Show Me Once

> Cette partie vit dans le dossier `chrome_cast/` du repo show-me-once. Elle est indépendante des outils factices (`app/`) et de la gestion des litiges (`som/`) : backend, dépendances et `.env` séparés. Les commandes ci-dessous se lancent depuis la racine du repo.

Enregistre une tâche **une seule fois** (écran, clics, saisies, changements d'onglet et narration vocale), puis transforme-la en procédure exécutable par un agent de computer use (H Company). La suite prévue : génération de script Python avec Devin, et fallback vers H en cas d'échec.

```
extension/   Extension Chrome MV3 : capture de l'écran, du micro et des événements DOM, puis upload
backend/     FastAPI : stockage, transcription Gladia, fusion en timeline, skill.md, envoi à H Company
```

## 1. Lancer le backend

```bash
cd chrome_cast/backend
pip install -r requirements.txt
cp .env.example .env   # renseigner GLADIA_API_KEY et HAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

`GET /health` indique si les clés Gladia et H sont bien chargées.

## 2. Charger l'extension

1. Ouvrir `chrome://extensions` et activer le **Mode développeur**.
2. Cliquer sur **Charger l'extension non empaquetée** et choisir le dossier `chrome_cast/extension/`.
3. Dans la popup Show Me Once, ouvrir **Réglages** et renseigner l'URL du backend (par défaut `http://localhost:8000`).

## 3. Enregistrer

1. Ouvrir la popup, puis cliquer sur **● Nouvel enregistrement**. Un onglet *recorder* épinglé s'ouvre.
2. Cliquer sur **Choisir l'écran et démarrer**, choisir **Écran entier** et autoriser le micro.
3. Faire la tâche en parlant, par exemple : « je regarde le litige… je vérifie le statut de livraison… ».
4. Arrêter avec la popup (**■ Arrêter et envoyer**) ou avec le bouton « Arrêter le partage » de Chrome.
5. Le lien **Ouvrir la timeline** mène à `http://localhost:8000/viewer/<id>`. On y trouve la vidéo, les étapes avec leurs captures et leur narration, `skill.md`, et les boutons pour H Company.

Si l'upload échoue, la vidéo, l'audio et `events.json` sont téléchargés en local. On peut les réimporter avec `POST /recordings/import`.

## 4. Envoyer à ton agent H Company

Dans la timeline, section **Envoyer à H Company** :

- **＋ Créer l'agent dans H** : crée en un clic, dans ton catalogue H, un *skill* (la procédure) et un *agent* qui l'utilise, avec l'URL de départ. Tu le retrouves ensuite sur platform.hcompany.ai, onglet Agents, où tu le lances avec un message comme « Analyse le premier litige et recommande accepter ou contester ».
- **⬇ Fichier agent H (.json)** : le même agent dans un fichier autonome (`show-me-once/h-export@1`, contenant `skill` et `agent` au format exact des API H). Pour l'importer depuis n'importe quelle machine :

```bash
HAI_API_KEY=... python3 chrome_cast/scripts/import_to_h.py mon-agent.h-agent.json --run "Analyse le premier litige"
```

- **⬇ SKILL.md** : la procédure seule, avec frontmatter `name`/`description`, à coller dans H ou dans un autre agent.
- **▶ Lancer maintenant** : lance une session ponctuelle, sans créer d'agent.

Par défaut, l'agent ne fait **aucune action irréversible** (accepter, rembourser, payer, supprimer, envoyer…) sauf si ton message le demande explicitement. Si une page de connexion s'affiche, il s'arrête et le signale.

## 5. Connecter l'agent à Stripe (ou à une autre app)

Le navigateur cloud de H démarre déconnecté. Deux mécanismes, combinables, configurés dans `backend/.env` puis appliqués en recliquant **＋ Créer l'agent dans H** (l'agent existant est mis à jour) :

1. **Profil navigateur par défaut** (`HAI_USE_DEFAULT_PROFILE=true`, activé par défaut). Lance une première session, ouvre l'Agent View, connecte-toi à Stripe toi-même (2FA comprise). Les cookies sont sauvegardés à la fin de la session : les runs suivants démarrent déjà connectés. C'est le plus fiable pour Stripe.
2. **Vault** (`HAI_VAULT_ID=...`). Un vault ne sert à rien tant qu'il n'est pas **lié au navigateur de l'agent**, ce que fait maintenant le backend. L'item doit avoir `urls` contenant `dashboard.stripe.com` (ou `stripe.com`), `username`/`email`, `password`, et **`totp`** (le secret base32 de l'appli d'authentification), sinon la 2FA bloque. Les codes envoyés par SMS ou par e-mail ne sont pas gérés par un vault seul.

Pour un profil construit hors de H (cookies existants), voir la doc « Browser profiles » de H, puis `HAI_BROWSER_PROFILE_ID=...`.

## Ce qui est capturé

| Événement | Données |
|---|---|
| `click` | texte, aria-label, label, href, sélecteur CSS, XPath, bounding box, x/y, **capture d'écran** (prise sur `pointerdown`, avant la navigation) |
| `input` | champ et valeur finale. Les mots de passe et les champs CB, token ou OTP sont **masqués** côté navigateur. contenteditable géré |
| `key` | Entrée, Échap, Tab |
| `submit` | formulaire |
| `navigation` | changement d'URL, y compris les SPA (pushState, comme Stripe ou Shopify admin) |
| `tab_switch` / `tab_opened` / `tab_closed` | passages d'un onglet à l'autre (avec une capture d'écran) |
| audio | micro et, en option, son système. Piste séparée envoyée à Gladia |

Tous les événements sont horodatés sur l'horloge de la vidéo (`t` en secondes), ce qui permet de cliquer sur une étape dans le viewer pour aller au bon moment de la vidéo.

## Format de sortie (`data/recordings/<id>/`)

- `video.webm`, `audio.webm`, `screenshots/*.jpg`
- `events.json` : les événements bruts
- `transcript.json` : la réponse brute de Gladia (utterances horodatées et résumé)
- **`session.json`** (`show-me-once/session@1`) : le contrat stable pour H, Devin et le fallback. Il contient `goal`, `apps`, `start_url`, `transcript` et `steps[]`. Chaque étape a `t`, `action`, `url`, `app`, `target`, `target_label`, `value`, `result_url`, `screenshot` et `narration`.
- **`skill.md`** : la procédure lisible par un agent

## API

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/recordings` | upload depuis l'extension (multipart) |
| POST | `/recordings/import` | réimport d'un bundle local |
| GET | `/recordings`, `/recordings/{id}`, `/recordings/{id}/skill.md` | lecture |
| PATCH | `/recordings/{id}` | corriger `title` et `goal`, puis régénérer |
| POST | `/recordings/{id}/reprocess?retranscribe=true` | relancer le pipeline |
| POST | `/recordings/{id}/hcompany/run` | lancer une session d'agent H (`instructions`, `start_url`, `agent`, `max_steps`) |
| POST | `/recordings/{id}/hcompany/skill` | créer un **Skill** H réutilisable |
| GET | `/hcompany/sessions/{session_id}` | statut et `latest_answer` |

## Notes et limites

- **H Company et la vidéo** : l'API Sessions accepte du texte, des `images` (base64) et des `files` (7 Mo maximum au total). Elle n'accepte pas de vidéo en entrée. On envoie donc `skill.md` et jusqu'à 8 captures clés. La vidéo reste dans le bundle pour un humain ou pour un modèle vidéo plus tard.
- **Connexion aux apps** : le navigateur cloud de H n'est pas connecté à Stripe ou à Shopify. Il faut utiliser les *Browser Profiles* ou l'environnement *Your browser* de H pour les vraies apps.
- **Clics hors de Chrome** : la vidéo les enregistre (écran entier), mais aucun événement structuré n'est produit, car seul le DOM de Chrome est instrumenté.
- **Iframes cross-origin** (par exemple Stripe Elements) : capturées grâce à `all_frames`, mais les sélecteurs sont relatifs à l'iframe.
- **Sécurité** : définir `SHOWMEONCE_API_KEY` en production. Les routes d'écriture exigent alors le header `X-ShowMeOnce-Key`. Le viewer accepte `?key=` dans l'URL. Les routes de lecture et `/files` ne sont pas protégées dans ce MVP : à mettre derrière l'authentification du serveur principal.
