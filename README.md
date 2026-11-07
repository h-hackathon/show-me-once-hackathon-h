# h-tools : les tools des agents SMO

Devin écrit ici un dossier par tâche apprise (`tools/<nom>/`). Chaque tool tourne dans son propre conteneur Railway.
Le watcher SMO lui transmet les appels des agents H, `precheck_<nom>` et `run_<nom>`.

```
Devin ─PR─▶ tests verts ─▶ Devin fusionne ─▶ deploy.yml : tests ─▶ service absent ? railway add
                                                               └─▶ railway up ─▶ SMO met l'agent H à jour
```

## Un tool

```
tools/<nom>/
  tool.py            NAME, DESCRIPTION, Params, precheck(page, cfg), run(page, params, cfg)
  ui_contract.json   les écrans traversés et leurs éléments attendus
  test_tool.py       rejoue la pièce de la démo contre le logiciel, vérifie par son API technique
  skill.md           la Skill de l'agent (reprise à l'écran), poussée dans H à chaque déploiement
  env.txt            les variables dont il a besoin (SITE_URL…), une par ligne
  requirements.txt   (optionnel) dépendances en plus du runtime
```

Partir de `tools/_template/`, que le déploiement ignore tant que son nom commence par `_`.
Le nom du dossier est `NAME` : lettres minuscules, chiffres et `_`.

### Règles

- **Sélecteurs** : uniquement par rôle et libellé visible, avec `h_tools.ui.locate`, `page.get_by_role` ou `get_by_label`. Jamais de coordonnées ni de CSS : c'est ce qui rend le precheck fiable.
- **`precheck`** ne modifie rien. En général : `login(page, cfg)` puis `check_contract(page, CONTRACT, cfg)`.
- **`run`** :
  - il est idempotent : une pièce déjà saisie renvoie `{"status": "duplicate"}` ;
  - les règles de la Skill sont codées en dur : un écart renvoie `{"status": "flagged", "reason": ...}` sans rien enregistrer ;
  - il s'arrête toujours avant l'action finale (brouillon, réponse préparée) : jamais « Valider », jamais « Soumettre ».
- **Statuts renvoyés par `run`** : `draft_saved`, `duplicate`, `flagged` ou `error`, plus les valeurs saisies.
- **`cfg`** lit les variables d'environnement en attributs : `cfg.site_url` → `SITE_URL`, et `None` si elle est absente.
- **Dossier** : aucun n'est imposé. S'il faut en choisir un, c'est un champ de `Params` (le client indiqué sur la pièce), passé à `login(page, cfg, dossier)`.
- **Appli de bureau** : avec `KIND = "desktop"`, on écrit `precheck(cfg)` et `run(params, cfg)` sans page, en passant par l'accessibilité macOS. Ces tools tournent sur le Mac : le déploiement Railway les saute.
- **Le Docker est déjà écrit** : il est commun à tous les tools, donc ne pas écrire de Dockerfile.
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

## Pour Devin : livrer un tool

1. Une branche et une PR « tool: <nom> », ou « fix: <nom> » pour une réparation.
2. `uv run pytest tests tools/<nom>` passe en local.
3. Attendre que le check `tests` de la PR soit vert : `gh pr checks <n°> --watch`.
4. S'il est vert, fusionner : `gh pr merge <n°> --merge`. S'il est rouge, corriger et repousser, ne jamais fusionner en rouge.

## Déploiement (automatique)

À chaque fusion sur `main`, `.github/workflows/deploy.yml` :
1. trouve les tools modifiés (`scripts/changed_tools.sh`) ; si `h_tools/`, le Dockerfile ou les dépendances ont changé, il les prend tous ;
2. relance leurs tests, car rien n'empêche côté GitHub une fusion en rouge ;
3. lance `scripts/deploy_tool.sh <nom>` pour chacun :
   - il assemble le contexte de build (Dockerfile, `h_tools/`, et `tools/<nom>/` copié en `tool/`) ;
   - si le service `tool-<nom>` n'existe pas, il le crée (`railway add`), avec `PORT=8080` et les variables de `env.txt` en référence aux variables partagées du projet ;
   - il lance `railway up` ;
   - il attend que le watcher voie le nouveau commit ;
   - il prévient SMO (`POST /hooks/tool-deployed`).

L'adresse d'un tool se déduit de son nom : `http://tool-<nom>.railway.internal:8080`, avec `-` à la place de `_`.
Le conteneur n'a pas de domaine public. Seul le watcher le joint, à condition d'être dans le même projet et le même environnement Railway.

Redéployer à la main : Actions → deploy → « Run workflow » (tools séparés par des espaces, vide = tous).

### Mise en place (une fois)

- **Projet Railway** dédié aux tools. Il contient le watcher SMO et les services `tool-*`.
- **Variables partagées** du projet : `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_ADMIN_TOKEN`.
- **Secrets GitHub** du repo (`gh secret set NOM -R Tomoroshimaru/h-tools`) :

| Secret | Rôle |
|---|---|
| `RAILWAY_API_TOKEN` | token de **compte** Railway (un token de projet ne peut pas créer de service) |
| `RAILWAY_PROJECT_ID` | le projet Railway des tools |
| `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_ADMIN_TOKEN` | les tests, contre le logiciel en ligne |
| `SMO_WATCHER_URL`, `SMO_SERVER_TOKEN` | attendre que le watcher voie le nouveau commit (optionnel) |
| `SMO_SERVER_URL` | prévenir SMO pour qu'il mette l'agent H à jour (optionnel) |

Attention : les tests remettent le logiciel à zéro (`/api/admin/reset`). Il vaut mieux une instance de test que celle de la démo.

## En local

```bash
uv sync
uv run playwright install chromium
cp .env.example .env                                    # puis remplir
uv run pytest                                           # runtime + tous les tools
TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080
curl -X POST localhost:8080/precheck
```
