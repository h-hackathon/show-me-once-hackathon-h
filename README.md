# h-tools : les tools des agents SMO

Devin écrit ici un dossier par tâche apprise (`tools/<nom>/`).
- **Tool web** : il tourne dans son propre conteneur Railway, dans ce projet Railway (séparé de celui de SMO). Le serveur SMO lui transmet les appels des agents H, `precheck_<nom>` et `run_<nom>`, par son adresse publique et avec le mot de passe commun (`SMO_SERVER_TOKEN`).
- **Tool de bureau** (`<nom>_desktop`) : il ne va pas sur Railway. SMO le livre avec la Skill de l'agent bureau, en posant ses fichiers par l'API H. L'agent le lance depuis son shell, dans son propre environnement : c'est la technique de H, et rien n'est installé chez l'utilisateur.

**Aucun identifiant ici, ni dans GitHub, ni sur Railway.** L'utilisateur ne remplit que son vault H. À chaque appel, SMO y lit l'élément du site et envoie le contexte dans le corps de la requête : l'adresse du logiciel, l'identifiant, le mot de passe et le code TOTP du moment. Le tool n'en garde rien et n'en renvoie rien.

```
Devin ─PR─▶ tests hors ligne verts ─▶ Devin fusionne ─▶ deploy.yml : tests ─▶ railway up (web) ─▶ annonce à SMO
     SMO : precheck réel avec le vault de chaque agent ─┬─ OK ─▶ l'agent H reçoit le tool
                                                        └─ KO ─▶ deploy en rouge, l'agent reste à l'écran
```

La méthode de Devin est la skill `.agents/skills/smo-tool/SKILL.md` : procédure, règles du tool, interdits, sortie JSON.

## Un tool

```
tools/<nom>/
  tool.py            NAME, DESCRIPTION, Params, rules(params), precheck(page, cfg), run(page, params, cfg)
  ui_contract.json   les écrans traversés et leurs éléments attendus
  test_tool.py       hors ligne : paramètres de la pièce de la démo, une règle de la Skill par test
  skill.md           la Skill de l'agent (reprise à l'écran), poussée dans H à chaque déploiement
  requirements.txt   (optionnel) dépendances en plus du runtime (tool web)
```

Partir de `tools/_template/` (web) ou de `tools/_template_desktop/` (bureau). Le déploiement ignore les dossiers dont le nom commence par `_`.
Le nom du dossier est `NAME` : lettres minuscules, chiffres et `_`. Un tool de bureau finit par `_desktop`.

### Règles

- **Sélecteurs** : uniquement par rôle et libellé visible, jamais de coordonnées ni de CSS. C'est ce qui rend le precheck fiable.
  - Web : `h_tools.ui.locate`, `page.get_by_role` ou `get_by_label`.
  - Bureau : `h_tools.desk` (`set_value`, `click`, `find`).
- **`precheck`** ne modifie rien. Web : `login(page, cfg)` puis `check_contract(page, CONTRACT, cfg)`. Bureau : `desk.check_contract(CONTRACT)`.
- **`rules(params)`** : les règles de la Skill, codées en dur. Elle renvoie la raison de l'arrêt, ou `None`, sans toucher au logiciel : c'est ce que la CI teste.
- **`run`** :
  - il appelle d'abord `rules` : un écart renvoie `{"status": "flagged", "reason": ...}` sans rien enregistrer ;
  - il vérifie ensuite l'interface, comme `precheck` : si elle a changé, il renvoie `{"status": "error", "reason": "interface changée", "missing": [...]}` sans rien saisir ;
  - il est idempotent, par ce que montre l'écran : une pièce déjà saisie renvoie `{"status": "duplicate"}` ;
  - il s'arrête toujours avant l'action finale (brouillon, réponse préparée) : jamais « Valider », jamais « Soumettre ».
- **Statuts renvoyés par `run`** : `draft_saved`, `duplicate`, `flagged` ou `error`, plus les valeurs saisies.
- **`cfg`**, le contexte de l'appel :
  - il contient `cfg.site_url`, `cfg.username`, `cfg.password`, `cfg.totp` (le code du moment) et `cfg.api_key`, `None` si un champ est absent ;
  - il est en lecture seule ;
  - ne jamais l'écrire dans un résultat, un log ou un fichier (le runtime efface de toute façon les secrets des résultats) ;
  - `login(page, cfg, code="Code")` remplit aussi le champ de double authentification.
- **Logiciel générique** : rien de propre à un client n'est écrit en dur (ni adresse, ni compte, ni dossier). Demain, le même tool doit pouvoir servir sur une autre instance du logiciel.
- **Dossier** : aucun n'est imposé. S'il faut en choisir un, c'est un champ de `Params` (le client indiqué sur la pièce), passé à `login(page, cfg, dossier)`.
- **Appli de bureau** (`KIND = "desktop"`) :
  - on écrit `precheck(cfg)` et `run(params, cfg)` sans page ;
  - l'appli est pilotée par `h_tools.desk`, qui appelle `cua`, le CLI de H, présent dans l'environnement de l'agent bureau ;
  - l'appli est déjà ouverte et connectée par l'agent (avec son vault) : le tool ne voit aucun mot de passe.
- **Le Docker est déjà écrit** : il est commun à tous les tools web, donc ne pas écrire de Dockerfile.
- Ne modifier que `tools/<nom>/`. Le runtime `h_tools/` est commun : y toucher redéploie tous les tools.

### Format de `ui_contract.json`

```json
{
  "version": 1,
  "screens": [
    {"name": "Nouvelle facture", "path": "/factures/nouvelle",
     "anchors": [{"label": "Fournisseur"}, {"role": "button", "name": "Enregistrer le brouillon"}]}
  ]
}
```

Un écran s'atteint par `path` (URL relative au logiciel), ou par `via` (une liste de clics, par exemple `[{"role": "link", "name": "Factures"}]`).
Pour un tool de bureau, l'écran porte aussi `window` (titre de la fenêtre ou nom de l'appli), et les rôles sont ceux de `cua state` (`push button`, `text field`…).

## Pour Devin : livrer un tool

Ta session reçoit l'accès au logiciel en **secrets de session** : `SITE_URL`, `SITE_USERNAME`, `SITE_PASSWORD`. SMO les lit dans le vault H, ils n'existent que dans cette session, et `Context.from_env()` les lit. Ne les écris nulle part : pas dans le code, pas dans un commit, pas dans la PR, pas dans un message.

1. Une branche et une PR « tool: <nom> », ou « fix: <nom> » pour une réparation.
2. Mettre au point contre le vrai logiciel, avec tes secrets de session :
   ```bash
   uv run python -m h_tools.cli tools/<nom> precheck
   uv run python -m h_tools.cli tools/<nom> run '{"reference": "...", ...}'    # la pièce de la démo, une fois
   ```
3. `uv run pytest tests tools/<nom>` passe en local. En CI, ces tests sont hors ligne : il n'y a aucun identifiant dans GitHub.
4. Attendre que le check `tests` de la PR soit vert : `gh pr checks <n°> --watch`.
5. S'il est vert, fusionner : `gh pr merge <n°> --merge`. S'il est rouge, corriger et repousser, ne jamais fusionner en rouge.
6. Suivre le déploiement : `gh run watch $(gh run list -w deploy -L 1 --json databaseId -q '.[0].databaseId')`. S'il est rouge (precheck réel en échec), lire le log, corriger, puis reprendre à l'étape 1.

## Déploiement (automatique)

À chaque fusion sur `main`, `.github/workflows/deploy.yml` :
1. trouve les tools modifiés (`scripts/changed_tools.sh`) ; si `h_tools/`, le Dockerfile ou les dépendances ont changé, il les prend tous ;
2. relance leurs tests, car rien n'empêche côté GitHub une fusion en rouge ;
3. lance `scripts/deploy_tool.sh <nom>` pour chacun.

Pour un tool web, `deploy_tool.sh` :
- assemble le contexte de build (Dockerfile, `h_tools/`, et `tools/<nom>/` copié en `tool/`) ;
- crée le service `tool-<nom>` s'il n'existe pas (`railway add`), avec deux variables seulement : `PORT=8080` et `SMO_SERVER_TOKEN` (en référence à la variable partagée) ;
- lance `railway up`, puis donne au service une adresse publique (`railway domain`, port 8080) ;
- l'annonce à SMO (`scripts/announce.py` → `POST /hooks/tool-deployed` avec le nom, le commit et l'adresse), et recommence jusqu'à ce que SMO voie le nouveau commit ;
- SMO fait alors un precheck avec le vault de chaque agent qui attend ce tool. Si c'est OK, l'agent reçoit le tool. Sinon, le déploiement échoue et l'agent garde la version d'avant.

Pour un tool de bureau, `announce.py` envoie ses fichiers à SMO : le tool, le runtime sans Playwright, et `run.sh`. SMO les pose dans la Skill de l'agent bureau (`files` de l'API Skills de H), et l'agent lance `./run.sh run '{...}'`.

Le tool n'accepte que les appels portant le mot de passe commun avec SMO (en-tête `X-SMO-Token`), sauf `/health`. Le contexte ne passe que dans le corps des requêtes, en HTTPS.

Redéployer à la main : Actions → deploy → « Run workflow » (tools séparés par des espaces, vide = tous).

### Mise en place (une fois)

- **Projet Railway** dédié aux tools : il ne contient que les services `tool-*`, créés au premier déploiement de chacun.
- **Variable partagée** du projet (Settings › Shared Variables) : `SMO_SERVER_TOKEN`, le mot de passe commun avec SMO. Aucune variable de site.
- **Secrets GitHub** du repo (`gh secret set NOM -R Tomoroshimaru/h-tools`) :

| Secret | Rôle |
|---|---|
| `RAILWAY_API_TOKEN` | token de **compte** Railway (un token de projet ne peut pas créer de service) |
| `RAILWAY_PROJECT_ID` | le projet Railway des tools |
| `SMO_SERVER_URL` | l'adresse publique du serveur SMO, à qui chaque tool est annoncé |
| `SMO_SERVER_TOKEN` | le mot de passe commun avec SMO (le même que la variable partagée) |

## En local

```bash
uv sync
uv run playwright install chromium
cp .env.example .env                                    # un compte de test, jamais commité
uv run pytest                                           # hors ligne, + le precheck réel si SITE_URL est rempli
uv run python -m h_tools.cli tools/<nom> precheck
TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080
```
