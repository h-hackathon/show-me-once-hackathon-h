# h-tools

> **TL;DR (EN)** — Deterministic automation tools for H Company agents, written by Devin.
> A human shows a task once (e.g. entering a supplier invoice in an accounting web app), an H agent succeeds at it
> on screen, then Devin turns it into a `tools/<name>/` folder: a typed Playwright script that does the whole task
> server-side, stops at a draft (never “Validate”), and is idempotent. Each web tool ships as its own Railway
> container behind a shared token; credentials never live in this repo — they come from the user's H vault on every call.
> CI is fully offline; a real UI precheck runs after each deploy, and a failed precheck turns the deploy red.

Les tools des agents SMO : Devin écrit ici un dossier par tâche apprise (`tools/<nom>/`). L'agent H appelle le tool
au lieu de refaire la tâche à l'écran ; si le tool échoue ou si l'interface a changé, l'agent reprend la main à
l'écran et Devin répare le tool.

## Architecture

```
            brief SMO (démo humaine + essai réussi de l'agent H)
                                │
Devin ─PR─▶ tests hors ligne verts ─▶ fusion ─▶ deploy.yml ─▶ railway up (un service par tool web) ─▶ annonce à SMO
                                                                                                        │
                       SMO : precheck réel avec le vault de chaque agent ─┬─ OK ─▶ l'agent H reçoit le tool
                                                                          └─ KO ─▶ deploy en rouge, l'agent reste à l'écran

À l'usage :   agent H ─▶ SMO ─(X-SMO-Token, contexte du vault)─▶ tool-<nom> sur Railway ─▶ logiciel cible (Playwright)
```

- **Tool web** : un conteneur Railway par tool, dans un projet Railway dédié (séparé de SMO). SMO lui transmet les
  appels `precheck_<nom>` et `run_<nom>` des agents H, par son adresse publique et avec le mot de passe commun
  (`SMO_SERVER_TOKEN`).
- **Tool de bureau** (`<nom>_desktop`) : pas de Railway. SMO le livre avec la Skill de l'agent bureau (fichiers posés
  par l'API H) ; l'agent le lance depuis son shell, et l'appli est pilotée par son arbre d'accessibilité (`cua`).
- **Aucun identifiant ici, ni dans GitHub, ni sur Railway.** À chaque appel, SMO lit le vault H de l'utilisateur et
  envoie le contexte dans le corps de la requête (adresse du logiciel, identifiant, mot de passe, code TOTP du
  moment). Le tool n'en garde rien et n'en renvoie rien.

## Le repo

```
h_tools/              runtime commun (y toucher redéploie tous les tools)
  server.py             le conteneur : GET /health, GET /describe, POST /precheck, POST /run
  loader.py             charge tools/<nom>/tool.py, un navigateur neuf par appel, erreurs → résultats
  config.py             Context : le contexte d'un appel, en lecture seule, secrets masqués et effacés
  ui.py                 helpers Playwright : login, ancres par rôle/libellé, contrat d'interface
  desk.py               helpers des tools de bureau (cua)
  formats.py            formats d'un écran français (montants, dates) et comparaison de noms
  steps.py, cli.py      étapes nommées ; lancer un tool en ligne de commande
tools/
  _template/            modèle de tool web
  _template_desktop/    modèle de tool de bureau
  <nom>/                un tool (ex. saisir_une_facture_fournisseur_web)
tests/                runtime + forme de chaque tool (hors ligne)
scripts/              déploiement : changed_tools.sh, deploy_tool.sh, announce.py, run.sh (tool de bureau)
.agents/skills/smo-tool/SKILL.md   la méthode de Devin pour créer ou réparer un tool
Dockerfile, railway.json           le conteneur commun à tous les tools web
```

## Un tool

```
tools/<nom>/
  tool.py            NAME, DESCRIPTION, Params, rules(params), precheck(page, cfg), run(page, params, cfg)
  ui_contract.json   les écrans traversés et leurs éléments attendus
  test_tool.py       hors ligne : paramètres de la pièce de la démo, une règle de la Skill par test
  skill.md           la Skill de l'agent (reprise à l'écran), poussée dans H à chaque déploiement
  requirements.txt   (optionnel) dépendances en plus du runtime (tool web)
```

Le nom du dossier est `NAME` : lettres minuscules, chiffres et `_`. Un tool de bureau finit par `_desktop` et déclare
`KIND = "desktop"` (`precheck(cfg)` et `run(params, cfg)`, sans page). Les dossiers commençant par `_` ne sont pas
déployés.

- **`rules(params)`** : les règles métier de la Skill, codées en dur, sans toucher au logiciel ; c'est ce que la CI
  teste.
- **`precheck`** ne modifie rien : connexion puis `check_contract` (l'interface a-t-elle changé ?).
- **`run`** fait toute la tâche et renvoie l'un de ces statuts, avec les valeurs saisies :
  `flagged` (règle enfreinte, rien n'est enregistré), `duplicate` (pièce déjà saisie, d'après l'écran),
  `draft_saved` (enregistré en brouillon, jamais validé) ou `error` (dont `interface changée`, avec ce qui manque).
- **`cfg`** : `cfg.site_url`, `cfg.username`, `cfg.password`, `cfg.totp`, `cfg.api_key` (`None` si absent), en
  lecture seule ; le runtime efface les secrets de tout résultat.
- **Générique** : rien de propre à un client en dur. Le dossier comptable, s'il faut en choisir un, est un champ de
  `Params`.

Les règles d'écriture (sélecteurs par rôle et libellé uniquement, pas de pause fixe, étapes nommées, interdits) et la
procédure de livraison sont dans la Skill [`smo-tool`](.agents/skills/smo-tool/SKILL.md).

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

Un écran s'atteint par `path` (URL relative au logiciel) ou par `via` (une liste de clics, ex.
`[{"role": "link", "name": "Factures"}]`). Une ancre est `{"role", "name"}`, `{"label"}` ou `{"text"}`, avec
`"exact": false` en option. Pour un tool de bureau, l'écran porte aussi `window`, et les rôles sont ceux de
`cua state` (`push button`, `text field`…). Le runtime ignore les autres clés : un tool peut y ajouter les siennes
(ex. `dossier_ouvert` pour séparer les écrans vus avant et après l'ouverture d'un dossier).

## En local

```bash
uv sync
uv run playwright install chromium
cp .env.example .env                                    # un compte de TEST du logiciel, jamais commité
uv run ruff check .
uv run pytest                                           # hors ligne, + le precheck réel si SITE_URL est rempli
uv run python -m h_tools.cli tools/<nom> precheck
uv run python -m h_tools.cli tools/<nom> run '{"reference": "...", ...}'
TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080
```

## Déploiement (automatique)

À chaque fusion sur `main`, `.github/workflows/deploy.yml` :
1. trouve les tools modifiés (`scripts/changed_tools.sh`) ; si `h_tools/`, le Dockerfile ou les dépendances ont
   changé, il les prend tous ;
2. relance les tests du runtime et de ces tools ;
3. lance `scripts/deploy_tool.sh <nom>` pour chacun :
   - **tool web** : contexte de build (Dockerfile, `h_tools/`, `tools/<nom>/` copié en `tool/`), service
     `tool-<nom>` créé au besoin, ses deux seules variables reposées à chaque fois (`PORT=8080`, `SMO_SERVER_TOKEN`
     pris dans le secret GitHub), `railway up`, adresse publique, puis annonce à SMO (`scripts/announce.py` →
     `POST /hooks/tool-deployed`) jusqu'à ce que SMO voie le nouveau commit et rende son precheck ;
   - **tool de bureau** : `announce.py` envoie à SMO le tool, le runtime sans Playwright et `run.sh`.

Le conteneur n'accepte que les appels portant `X-SMO-Token` (sauf `/health`) ; sans `SMO_SERVER_TOKEN`, il les refuse
tous. Le contexte ne passe que dans le corps des requêtes, en HTTPS.

Redéployer à la main : Actions → deploy → « Run workflow » (tools séparés par des espaces, vide = tous).

### Mise en place (une fois)

- **Projet Railway** dédié aux tools : il ne contient que les services `tool-*`, créés au premier déploiement.
- Rien à régler sur Railway : aucune variable de site, et le jeton SMO vient du secret GitHub.
- **Ne pas relier le dépôt GitHub au projet Railway** (New › GitHub Repo) : le service créé construirait tout le repo
  avec le Dockerfile, qui attend le `tool/` que seul `deploy_tool.sh` prépare, et échouerait à chaque push. Les tools
  arrivent par le CLI (`railway up`), chacun dans son service `tool-*`.
- **Secrets GitHub** du repo (`gh secret set NOM -R Tomoroshimaru/h-tools`) :

| Secret | Rôle |
|---|---|
| `RAILWAY_API_TOKEN` | jeton de **compte** Railway (Account Settings › Tokens, « No workspace ») : un jeton de projet ne crée pas de service, et le CLI refuse un jeton d'équipe (workspace) |
| `RAILWAY_PROJECT_ID` | le projet Railway des tools |
| `SMO_SERVER_URL` | l'adresse publique du serveur SMO, à qui chaque tool est annoncé |
| `SMO_SERVER_TOKEN` | le mot de passe commun avec SMO : le même que la variable `SMO_SERVER_TOKEN` du SMO sur Railway |

## Licence

Propriétaire, tous droits réservés : voir [LICENSE](LICENSE).
