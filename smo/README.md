# SMO : Show me once

Capturer, automatiser et maintenir des agents H pour des tâches répétitives. Le principe :
- une capture vidéo + voix d'une tâche faite une fois devient un **agent custom H** ;
- cet agent a sa Skill, un tool déterministe écrit par Devin, et reprend en computer use quand le tool échoue ;
- la trace de chaque reprise renvoie Devin corriger le tool et la Skill.

```
capture → transcribe → frames → read → understand → enrich → skill → review → provision → trial → compile → upgrade
   ├──→ map (agent H, en parallèle : carte des écrans de la tâche) ──┤
   └──→ docs (Linkup, en parallèle : documentation publique du logiciel) ──┘

Un agent H par type de logiciel : `web` (navigateur) ou `desktop` (bureau du Mac), chacun avec sa Skill et ses tools.
Chaque Skill envoyée dans H se termine par le bloc commun `skills/bloc_commun.md` (utiliser les tools).
          Gladia       ffmpeg   Holo   Holo        Linkup            humain   agent H     agent H  Devin     agent H + tool
                                (1 capture par appel, puis synthèse en texte seul)
```

Le plan complet et l'état des API sont dans [`PLAN.md`](PLAN.md).

## Installer

```bash
cd smo
uv sync --extra desktop              # sur le Mac ; --extra desktop = l'agent bureau (appli de bureau)
uv run playwright install chromium   # pour les tools compilés
cp .env.example .env                 # puis remplir
uv run smo doctor                    # ✅ / ⏭️ / ❌ par API
uv run smo doctor --probe all        # vraies sessions H : Skill, agent guidé, tool exécuté par nous
```

## La page d'enregistrement (le plus simple)

```bash
uv run smo serve                     # puis ouvrir http://localhost:8000 dans Chrome
```

La page suit quatre temps :
1. **Préparer** : la tâche, l'adresse du logiciel, la pièce traitée et le prénom.
2. **Enregistrer** : Chrome partage l'écran et le micro. Gladia transcrit en direct pendant qu'on parle.
3. **Comprendre** : à l'arrêt, la vidéo part au serveur et le pipeline tourne. La page montre l'avancement, puis la Skill à relire et à valider.
4. **Agent** : l'agent est créé dans H et teste la tâche à l'écran, puis Devin code le tool. La page donne les liens (session de test, PR).

Quelques précisions :
- **Clé Gladia** : elle reste sur le serveur, qui ouvre la session en direct ; le navigateur ne reçoit qu'une adresse à jeton temporaire.
- **Transcription utilisée par le pipeline** : c'est celle du fichier complet, plus fiable que le direct.
- **Accès** : la capture d'écran exige `localhost` ou HTTPS. Si `SMO_SERVER_TOKEN` est défini, la page demande le jeton. En ligne (Railway), ce jeton est obligatoire (16 caractères minimum) : sans lui, le serveur refuse de démarrer, pour que personne ne dépense nos crédits.
- **Taille** : une vidéo de plus de 500 Mo est refusée.
- **Reprendre un run** : `http://localhost:8000/?run=<run_id>`.

## En ligne de commande

```bash
# 1. Une capture → un run (vidéo, ou audio + images ; un PDF = pièce de référence)
uv run smo new capture.mov --task "Saisir une facture fournisseur"

# 2. Le pipeline : s'arrête à la relecture de la Skill (sauf --auto), puis reprend où il en était
uv run smo run <run_id>
uv run smo approve <run_id>
uv run smo run <run_id> --no-wait    # n'attend pas Devin ; relancer pour suivre
uv run smo status <run_id>

# Tout d'un coup, sans relecture (parcours Catherine)
uv run smo new capture.mov --task "..." --go --auto
```

Chaque étape écrit son fichier dans `runs/<run_id>/` : `map.json` (gardée aussi dans `runs/_maps/`), `transcript.json`, `frames/`, `notes.json`, `procedure.json`, `context.json`, `skill.md`, `agent.json`, `trace.json` (+ `trace/`), `trial.json`, `compile.json`.
Option `--guided` : à l'étape trial, l'agent est guidé phrase par phrase au lieu de suivre seul sa Skill.
On peut refaire une étape : `uv run smo run <id> --only understand --force`.

## Le serveur

`uv run smo serve` lance un seul programme qui fait trois choses :
1. **La page d'enregistrement** (`/`) et son API (`/api/...`) : reçoit la vidéo, fait tourner le pipeline, montre l'avancement.
2. **Le worker des tools** : quand un agent `smo-*` appelle un tool, sa session H attend. Le serveur le voit en interrogeant H toutes les 5 s, se rattache à la session et exécute le tool (`precheck_*`, `run_*`, `report_drift`), même si la session a été lancée depuis l'interface H. Le webhook H (`/webhooks/h`) est facultatif : plus rapide, mais il demande une adresse publique et un secret.
3. **Le relais vers h-tools** : les tools écrits par Devin vivent dans le repo h-tools, et chacun tourne dans son propre service Railway, dans le projet Railway d'h-tools. À chaque déploiement, h-tools annonce le tool à SMO (`POST /hooks/tool-deployed` : nom, commit, adresse publique). SMO retient l'adresse, appelle le tool (`/describe`, `/precheck`, `/run`) avec le mot de passe commun `SMO_SERVER_TOKEN`, et remet à jour les agents H qui l'attendent, avec la Skill du repo et le bloc commun.

Où il tourne : **un seul serveur SMO, sur Railway, gère tout**. Sur la page, on choisit l'agent :
- **web** : l'agent H travaille dans son navigateur cloud, sur le site en ligne ;
- **bureau** : l'agent H travaille sur le **PC du live**, par son relais (`H_DESKTOP_BRIDGE`, voir ci-dessous), ou dans un environnement desktop configuré dans H (`H_DESKTOP_ENV`, prioritaire). Sans l'un ni l'autre, SMO prend le bureau de la machine où il tourne, ce qui ne sert qu'en local.

### Agent bureau sur le PC du live

SMO, sur Railway, n'a pas d'écran. Il donne à l'agent bureau l'environnement `{"kind": "desktop", "host": "user_device", "session_id": H_DESKTOP_BRIDGE}`, et H envoie les clics au relais qui sert cet identifiant : `holo local desktop`, lancé sur le PC du live.

1. Installer holo sur le PC du live : `uv tool install "hai-agents[cli,desktop]==1.4.3"`. Il lit `HAI_API_KEY` (le script la prend dans `smo/.env`), sinon `holo login`.
2. Autorisations macOS, dans Réglages › Confidentialité et sécurité, pour l'app qui lance le script (Terminal, iTerm, VS Code…) : **Enregistrement de l'écran**, **Accessibilité** et **Surveillance de l'entrée**. Puis quitter et rouvrir cette app : une autorisation ne vaut que pour un nouveau processus.
3. Lancer `scripts/desktop_bridge.sh`. Sans `H_DESKTOP_BRIDGE`, il en génère un et l'affiche : le mettre dans les variables Railway de SMO (et dans `.env`). Le relais s'arrête à la fin de chaque session H ; le script le relance en boucle. Ctrl-C arrête tout.
4. Un seul agent à la fois pilote la machine : les essais passent l'un après l'autre, et on ne touche pas à la souris pendant une session.

Les tools déterministes de bureau (accessibilité macOS) doivent tourner là où tourne l'appli : h-tools ne les déploie pas sur Railway. En attendant, l'agent bureau travaille en computer use.

## Déployer sur Railway

Trois projets Railway séparés : Qonta (le logiciel de test), SMO (ce serveur), h-tools (les tools de Devin).

1. **Service SMO**, dans son propre projet : New › GitHub Repo › `show-me-once-prep`.
   - Settings › Source : **Root Directory = `smo`** ; branche `main` une fois la PR fusionnée, ou `feat/smo` pour tester avant.
   - Le reste vient de `railway.toml` : construction par le `Dockerfile`, vérification de santé sur `/health`, redémarrage en cas d'échec.
2. **Volume** : clic droit sur le service › Attach Volume, monté sur **`/data`**. Sans lui, les runs et les cartes sont effacés à chaque redéploiement.
3. **Variables** (Raw Editor : coller le `.env`, puis ajuster) :
   - toutes les clés et `SITE_URL` du `.env`. Pas d'identifiant du site : ils sont dans le **vault H** (un élément avec l'adresse du site, l'identifiant et le mot de passe), que SMO retrouve par l'adresse (`smo doctor`, ligne « Vault H ») ;
   - **`SMO_RUNS_DIR=/data/runs`** ;
   - **`SMO_SERVER_TOKEN`** : 16 caractères minimum, par exemple `openssl rand -hex 24`. Sans lui, le serveur refuse de démarrer en ligne.
   - agent bureau : **`H_DESKTOP_BRIDGE`**, l'identifiant du relais du PC du live (voir « Agent bureau sur le PC du live »), ou `H_DESKTOP_ENV`, un environnement desktop configuré dans H ;
   - `DESKTOP_LOGIN` / `DESKTOP_PASSWORD` : les identifiants de l'appli de bureau ;
   - inutile sur Railway : `H_TOOLS_DIR`.
4. **Adresse** : Settings › Networking › Generate Domain. La mettre dans `SMO_SERVER_URL`, sur Railway et dans le `.env` du Mac.
5. **h-tools**, pour la liaison : dans le projet Railway d'h-tools, la variable partagée `SMO_SERVER_TOKEN` (le même jeton) ; dans les secrets GitHub du repo h-tools, `SMO_SERVER_URL` (cette adresse) et `SMO_SERVER_TOKEN`. Chaque déploiement de tool l'annonce alors à SMO.
6. **Vérifier** : `uv run smo doctor` (ligne « Serveur SMO »), puis ouvrir l'adresse dans Chrome ; la page demande le jeton.

En local, pour essayer un tool d'h-tools sans le déployer : `gh repo clone Tomoroshimaru/h-tools ~/h-tools`, puis `H_TOOLS_DIR=~/h-tools` dans le `.env`.

## Identifiants : le vault H, et nulle part ailleurs

L'utilisateur range le site dans son vault H : un élément avec son adresse, l'identifiant, le mot de passe et, si besoin, le TOTP. SMO retrouve cet élément par l'hôte de l'adresse (`clients/vault.py`) et ne garde rien, ni sur disque ni dans un prompt.

```
vault H ─┬─ vault_id sur le navigateur cloud de l'agent ─▶ H remplit la connexion, le modèle ne voit pas les valeurs
         ├─ lu à chaque appel de tool ─▶ corps HTTPS de /run ─▶ tool (Railway) ; résultat nettoyé avant l'agent
         └─ lu au lancement de Devin ─▶ session_secrets SITE_URL, SITE_USERNAME, SITE_PASSWORD (pas dans le brief)
```

- Pas d'élément pour le site : la cartographie et les essais s'arrêtent, avec un message qui demande de l'ajouter. En localhost seulement (développement), `SITE_LOGIN` et `SITE_PASSWORD` passent encore dans les consignes, car H ne rattache pas de vault à un navigateur local.
- Un tool de bureau ne passe pas par Railway. h-tools envoie ses fichiers au hook. SMO les pose dans la Skill de l'agent bureau (`files` de l'API Skills), et l'agent le lance depuis son shell : `./run.sh run '{...}'`. `smo doctor --probe desktop-tool` vérifie qu'un agent bureau trouve et lance un fichier de sa Skill.
- Après chaque déploiement d'un tool, le hook fait un precheck avec le vault de chaque agent qui attend ce tool. Si c'est OK, l'agent reçoit le tool. Sinon, il reste à l'écran et le déploiement d'h-tools passe au rouge.

## Autres commandes

```bash
uv run smo trace <session_id>        # trace de n'importe quelle session H
uv run smo tools --precheck          # tools compilés + precheck
uv run smo repair <tool> --session <id> --details "bouton renommé"
uv run pytest                        # tests hors ligne
```

## Structure

```
smo/
  smo/clients/     gladia, holo (Models API), h (Agents API), linkup, devin, site
  smo/pipeline/    une étape par fichier + orchestrator.py (le driver)
  smo/runtime/     serveur FastAPI, worker des tools H, chargement des tools, helpers Playwright
  tools/           les tools compilés par Devin (un dossier par tâche) + _template
  docs/            brief Devin (création, réparation), contrat du site compta
  scripts/         desktop_bridge.sh : le relais bureau du PC du live
```

Repris de `prep/` : la transcription Gladia (`03`), la lecture d'écran Holo (`04`), l'usage de l'Agents API (`01`, `02`).
