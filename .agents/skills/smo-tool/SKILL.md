---
name: smo-tool
description: Créer ou réparer un tool déterministe dans h-tools à partir d'un brief SMO (une tâche apprise d'une démonstration humaine, puis réussie à l'écran par un agent H). À utiliser pour tout brief « Tâche SMO : créer le tool … » ou « Tâche SMO : réparer le tool … ».
---

# SMO : créer ou réparer un tool dans h-tools

## Vue d'ensemble

Un brief SMO te donne une tâche qu'un humain a montrée une fois et qu'un agent H a ensuite réussie à l'écran. Tu en fais un tool déterministe qui fait toute la tâche sur un serveur, ou tu répares un tool existant. Ton travail est fini quand la PR est fusionnée avec les tests verts et que le déploiement est vert : le déploiement sur Railway, le precheck réel par SMO (avec le vault H de l'agent) et la mise à jour de l'agent se font tout seuls, mais un precheck en échec met le déploiement en rouge.

## Les identifiants

Ta session reçoit l'accès au logiciel en **secrets de session** : `SITE_URL`, `SITE_USERNAME`, `SITE_PASSWORD` (variables d'environnement). SMO les lit dans le vault H de l'utilisateur au moment de lancer ta session ; ils n'existent que dans cette session. Le tool, lui, les reçoit à chaque appel dans `cfg` (`cfg.site_url`, `cfg.username`, `cfg.password`, `cfg.totp`) : en local, `Context.from_env()` les lit dans tes secrets.
- Ne les écris jamais : ni dans le code, ni dans un fichier, ni dans un commit, une PR, un message ou ta sortie structurée.
- Si le site demande une double authentification, tu n'as pas le code (le vault ne révèle jamais la graine TOTP) : écris le tool avec `login(page, cfg, code="<libellé du champ>")`, il sera vérifié par le precheck réel après le déploiement.

## Ce que fournit le brief

- Le nom du tool (`<nom>`, qui est aussi le nom du dossier), la tâche, le type de logiciel (web ou bureau), l'adresse du logiciel, la demande que l'agent a reçue pendant son essai réussi (en conversation, avec des pièces jointes : « Saisis la facture jointe dans Qonta »). En usage réel, l'agent lit chaque pièce jointe et appelle le tool une fois par pièce, avec les valeurs lues.
- La Skill validée par l'humain : c'est la référence métier, prioritaire sur tout le reste.
- La trace condensée de l'essai réussi, les règles vérifiées sur le web, la carte du logiciel (écrans, chemins, libellés exacts) et sa documentation.
- En pièces jointes : les sorties JSON complètes de chaque étape (`trace.json`, `trial.json`, `procedure.json`, `notes.json`, `map.json`, `docs.json`) et des captures d'écran.
- Pour une réparation : ce qui a cassé, le contrat et la Skill actuels, et la trace de l'agent qui a fini la tâche à l'écran sur la nouvelle interface.

## Procédure

1. Lis le `README.md` du repo. Ne travaille que dans `tools/<nom>/`.
2. Création : copie `tools/_template/` (web) ou `tools/_template_desktop/` (bureau, nom en `_desktop`). Réparation : pars du tool existant, et garde le même `NAME` et les mêmes `Params` si possible.
3. Écris `tool.py`, `ui_contract.json`, `test_tool.py` et `skill.md`.
4. Une fois : `uv sync && uv run playwright install --with-deps chromium`. Mets au point contre le vrai logiciel avec tes secrets de session :
   ```bash
   uv run python -m h_tools.cli tools/<nom> precheck
   uv run python -m h_tools.cli tools/<nom> run '{"reference": "...", ...}'    # les valeurs saisies dans la trace, une fois
   ```
   Le second appel doit renvoyer `duplicate` : c'est l'idempotence.
5. `uv run pytest tests tools/<nom>` doit passer. Les tests sont **hors ligne** (paramètres de la pièce, une règle de la Skill par test, `run(None, params, cfg)` → `flagged`) : en CI, il n'y a aucun identifiant. Le precheck réel tourne en plus chez toi, parce que `SITE_URL` y est défini.
6. Crée une branche, puis une PR « tool: <nom> » (« fix: <nom> » pour une réparation). Attends la vérification `tests` : `gh pr checks <n°> --watch`.
7. Si c'est vert : `gh pr merge <n°> --merge`. Si c'est rouge : corrige et repousse.
8. Suis le déploiement : `gh run watch $(gh run list -w deploy -L 1 --json databaseId -q '.[0].databaseId')`. S'il est rouge (le precheck réel de SMO a échoué, le log dit quels éléments manquent), corrige dans une nouvelle PR.
9. Renseigne ta sortie structurée (voir plus bas).

## Spécifications du tool

- **`run` fait toute la tâche, de bout en bout, et renvoie le résultat final.** Quand il réussit, l'agent H n'a rien à faire à l'écran.
  1. Règles métier de la Skill codées en dur dans `rules(params)` (ex. HT + TVA = TTC), sans toucher au logiciel. En cas d'écart : `{"status": "flagged", "reason": ...}`, sans rien enregistrer.
  2. Il se connecte (`login(page, cfg)`), puis vérifie l'interface (son `ui_contract.json`, comme `precheck`). Si elle a changé : `{"status": "error", "reason": "interface changée", "missing": [...]}`, sans rien saisir.
  3. Pièce déjà saisie, d'après ce que montre l'écran : `{"status": "duplicate"}`.
  4. Sinon il saisit, s'arrête en brouillon, et renvoie `{"status": "draft_saved", ...}` avec les valeurs saisies.
  5. Toute autre panne : `{"status": "error", "reason": ...}`. L'agent reprendra alors à l'écran.
- `precheck` ne modifie rien.
- `Params` : un champ par valeur à lire sur la pièce, chacun avec sa description. C'est l'agent qui les remplit en lisant la pièce.
- Dossier : s'il faut en choisir un, c'est un champ de `Params` (le client indiqué sur la pièce), passé à `login(page, cfg, dossier)`.
- `skill.md` : la Skill du brief, corrigée seulement là où la trace montre le vrai chemin. Garde les règles métier.
- Logiciel générique : rien de propre à un client en dur (adresse, compte, dossier). Tout vient de `cfg` et de `Params`.
- Appli de bureau (`KIND = "desktop"`, nom en `_desktop`) : `precheck(cfg)` et `run(params, cfg)` sans page. L'appli est pilotée par son arbre d'accessibilité avec `h_tools.desk` (`set_value`, `click`, `check_contract`), qui appelle `cua`, le CLI de H. Le tool ne va pas sur Railway : SMO le pose dans la Skill de l'agent bureau, qui le lance depuis son shell (`./run.sh run '{...}'`), l'appli déjà ouverte et connectée. Ta machine ne peut pas lancer l'appli : écris le code et les tests hors ligne. Les rôles du contrat sont ceux de `cua state` (`push button`, `text field`…).

## Règles de code (Python, Playwright sync)

Le runtime (`h_tools/`) fournit déjà le navigateur : un Chrome d'utilisateur français ordinaire (fr-FR, Europe/Paris), 10 s par action, 30 s par chargement de page, un navigateur neuf par appel. Ton code ne lance ni ne configure de navigateur.

1. **Aucune pause fixe.** Ni `time.sleep`, ni `page.wait_for_timeout`. Attends un état : les locators de Playwright attendent seuls, sinon `expect(locator).to_be_visible()`, `page.wait_for_url(...)`, ou le texte de confirmation du logiciel.
2. **Sélecteurs humains seulement** : `locate(page, ancre)`, `page.get_by_role`, `page.get_by_label`, `page.get_by_text`, avec les libellés exacts de la carte et de la trace. Ni CSS, ni XPath, ni coordonnées, ni `nth()` sans raison écrite.
3. **Chaque étape est nommée et vérifie son effet.** Enveloppe-la dans `with step("saisie du fournisseur"):` (de `h_tools.ui`). Une panne remonte alors avec le nom de l'étape, ce qui sert à l'agent et à une réparation. Après une saisie, vérifie la valeur (`expect(champ).to_have_value(...)`). Après « Enregistrer le brouillon », attends le message de confirmation du logiciel et renvoie ce qu'il affiche (n° attribué, statut).
4. **Champs à autocomplétion** (ex. fournisseur) : `press_sequentially(texte, delay=50)` comme une frappe humaine, puis attends la liste et choisis l'option par son texte. Ne remplis jamais un tel champ d'un coup avec `fill`.
5. **Session expirée en cours d'appel** : juste avant d'enregistrer, appelle `stay_logged_in(page, cfg, dossier)`. S'il renvoie `True`, reprends la saisie depuis le début : la vérification de doublon évite la double saisie.
6. **Valeurs** : `Params` typés (montants en `Decimal`, dates en `date`) avec leur description. Un seul helper par format pour l'écran du logiciel (ex. `fr_amount(Decimal("312.6")) → "312,60"`, `fr_date(date) → "10/10/2026"`), testé hors ligne.
7. **Un clic qui enregistre est fait une seule fois**, puis attendu. Jamais de boucle de nouvelle tentative autour d'un enregistrement : en cas de doute, renvoie une `error` et laisse l'agent vérifier à l'écran.
8. **Sorties** : uniquement les statuts listés plus haut, avec les valeurs saisies. Jamais d'identifiant, de cookie ou de jeton dans un résultat ou un log.
9. **Tests hors ligne** dans `test_tool.py` : une règle de la Skill par test, les helpers de format, `Params` sur les valeurs de la trace, `run(None, params, cfg)` → `flagged`.

## Conseils

- Prends les libellés exacts dans la carte et la trace, et reprends-les tels quels dans `ui_contract.json`.
- Qonta (le logiciel de test) refuse un doublon avec le message « Doublon : … » : c'est l'idempotence par l'écran. Sa session expire au bout de 15 minutes d'inactivité.
- Si le logiciel affiche un captcha ou bloque l'automatisation, ne cherche pas à le contourner : le tool renvoie `{"status": "error", "reason": "accès automatique bloqué"}` et l'agent H reprend à l'écran.

## Interdits

- Écrire un identifiant (adresse de compte, mot de passe, code) où que ce soit.
- Cliquer sur « Valider » ou « Soumettre ».
- Des coordonnées ou des sélecteurs CSS.
- `time.sleep`, `wait_for_timeout`, ou une boucle de nouvelle tentative autour d'un enregistrement.
- Contourner une protection du logiciel : plugin « stealth », résolution de captcha, proxy, empreinte de navigateur modifiée.
- Imposer un dossier.
- Ajouter à `skill.md` la règle « le tool d'abord » : SMO l'insère lui-même.
- Toucher à `h_tools/`, au Dockerfile ou aux workflows.
- Fusionner une PR dont les tests sont rouges.

## Sortie structurée (obligatoire)

À la fin, renseigne ta sortie structurée (structured output) avec exactement ce JSON :

```json
{"tool": "<nom>", "pr_url": "<adresse de la PR>", "tests_passed": true, "merged": true, "issues": ["<problème restant>"]}
```

`tests_passed` et `merged` valent `true` ou `false` ; `issues` est vide si tout va bien.
