---
name: smo-tool
description: Créer ou réparer un tool déterministe dans h-tools à partir d'un brief SMO (une tâche apprise d'une démonstration humaine, puis réussie à l'écran par un agent H). À utiliser pour tout brief « Tâche SMO : créer le tool … » ou « Tâche SMO : réparer le tool … ».
---

# SMO : créer ou réparer un tool dans h-tools

## Vue d'ensemble

Un brief SMO te donne une tâche qu'un humain a montrée une fois et qu'un agent H a ensuite réussie à l'écran. Tu en fais un tool déterministe qui fait toute la tâche sur un serveur, ou tu répares un tool existant. Ton travail est fini quand la PR est fusionnée avec les tests verts : le déploiement sur Railway et l'annonce à SMO se font ensuite tout seuls.

## Ce que fournit le brief

- Le nom du tool (`<nom>`, qui est aussi le nom du dossier), la tâche, le type de logiciel (web ou bureau), l'adresse du logiciel, la pièce de la démonstration.
- La Skill validée par l'humain : c'est la référence métier, prioritaire sur tout le reste.
- La trace condensée de l'essai réussi, les règles vérifiées sur le web, la carte du logiciel (écrans, chemins, libellés exacts) et sa documentation.
- En pièces jointes : les sorties JSON complètes de chaque étape (`trace.json`, `trial.json`, `procedure.json`, `notes.json`, `map.json`, `docs.json`) et des captures d'écran.
- Pour une réparation : ce qui a cassé, le contrat et la Skill actuels, et la trace de l'agent qui a fini la tâche à l'écran sur la nouvelle interface.

## Procédure

1. Lis le `README.md` du repo. Ne travaille que dans `tools/<nom>/`.
2. Création : copie `tools/_template/`. Réparation : pars du tool existant, et garde le même `NAME` et les mêmes `Params` si possible.
3. Écris `tool.py`, `ui_contract.json`, `test_tool.py`, `skill.md` et `env.txt`.
4. Une fois : `uv sync && uv run playwright install --with-deps chromium`. Puis `uv run pytest tests tools/<nom>` doit passer contre le logiciel de test (tes Secrets `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_ADMIN_TOKEN`).
5. Crée une branche, puis une PR « tool: <nom> » (« fix: <nom> » pour une réparation). Attends la vérification `tests` : `gh pr checks <n°> --watch`.
6. Si c'est vert : `gh pr merge <n°> --merge`. Si c'est rouge : corrige et repousse.
7. Renseigne ta sortie structurée (voir plus bas).

## Spécifications du tool

- **`run` fait toute la tâche, de bout en bout, et renvoie le résultat final.** Quand il réussit, l'agent H n'a rien à faire à l'écran.
  1. Il vérifie d'abord l'interface (son `ui_contract.json`, comme `precheck`). Si elle a changé : `{"status": "error", "reason": "interface changée", "missing": [...]}`, sans rien saisir.
  2. Pièce déjà saisie : `{"status": "duplicate"}`.
  3. Règles métier de la Skill codées en dur (ex. HT + TVA = TTC). En cas d'écart : `{"status": "flagged", "reason": ...}`, sans rien enregistrer.
  4. Sinon il saisit, s'arrête en brouillon, et renvoie `{"status": "draft_saved", ...}` avec les valeurs saisies.
  5. Toute autre panne : `{"status": "error", "reason": ...}`. L'agent reprendra alors à l'écran.
- `precheck` ne modifie rien.
- `Params` : un champ par valeur à lire sur la pièce, chacun avec sa description. C'est l'agent qui les remplit en lisant la pièce.
- Dossier : s'il faut en choisir un, c'est un champ de `Params` (le client indiqué sur la pièce), passé à `login(page, cfg, dossier)`.
- `skill.md` : la Skill du brief, corrigée seulement là où la trace montre le vrai chemin. Garde les règles métier.
- Appli de bureau (`KIND = "desktop"`) : `precheck(cfg)` et `run(params, cfg)` sans page, avec l'accessibilité macOS (pyobjc). Ta machine ne peut pas lancer l'appli : écris le code et les tests, ils seront joués ailleurs.

## Conseils

- Prends les libellés exacts dans la carte et la trace, et reprends-les tels quels dans `ui_contract.json`.
- Sélecteurs : `h_tools.ui.locate`, `page.get_by_role` ou `page.get_by_label`.
- Qonta (le logiciel de test) refuse un doublon avec le message « Doublon : … » : c'est le filet de sécurité de l'idempotence quand `SITE_ADMIN_TOKEN` est absent.

## Interdits

- Cliquer sur « Valider » ou « Soumettre ».
- Des coordonnées ou des sélecteurs CSS.
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
