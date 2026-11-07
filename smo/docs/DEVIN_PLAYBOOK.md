# Playbook SMO : créer ou réparer un tool dans h-tools

Tu reçois un brief SMO : une tâche apprise d'une démonstration humaine, puis réussie à l'écran par un agent H. Tu en fais un tool déterministe, ou tu répares un tool existant.

## Méthode

1. Repo `Tomoroshimaru/h-tools`. Lis son `README.md`. Ne travaille que dans `tools/<nom>/` (le nom est donné par le brief).
2. Création : copie `tools/_template/`. Réparation : pars du tool existant.
3. Écris `tool.py`, `ui_contract.json`, `test_tool.py`, `skill.md` et `env.txt`.
4. Une fois : `uv sync && uv run playwright install --with-deps chromium`. Puis `uv run pytest tests tools/<nom>` doit passer contre le logiciel de test (tes Secrets `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_ADMIN_TOKEN`).
5. Une branche, puis une PR « tool: <nom> » (ou « fix: <nom> » pour une réparation). Attends la vérification `tests` : `gh pr checks <n°> --watch`.
6. Si c'est vert : `gh pr merge <n°> --merge`. Si c'est rouge : corrige et repousse. Ne fusionne jamais en rouge.
7. Après la fusion, le déploiement et l'annonce à SMO sont automatiques. Ne touche ni à `h_tools/`, ni au Dockerfile, ni aux workflows.

## Règles du tool

- **`run` fait toute la tâche, de bout en bout, et renvoie le résultat final.** Quand il réussit, l'agent H n'a rien à faire à l'écran.
  1. Il vérifie d'abord l'interface (son `ui_contract.json`, comme `precheck`). Si elle a changé : `{"status": "error", "reason": "interface changée", "missing": [...]}`, sans rien saisir.
  2. Pièce déjà saisie : `{"status": "duplicate"}` (le logiciel affiche « Doublon : … »).
  3. Règles métier de la Skill codées en dur (ex. HT + TVA = TTC). En cas d'écart : `{"status": "flagged", "reason": ...}`, sans rien enregistrer.
  4. Sinon il saisit, s'arrête en brouillon, et renvoie `{"status": "draft_saved", ...}` avec les valeurs saisies.
  5. Toute autre panne : `{"status": "error", "reason": ...}`. L'agent reprendra alors à l'écran.
- `precheck` ne modifie rien.
- Sélecteurs par rôle et libellé visible uniquement. Jamais de coordonnées, jamais de sélecteur CSS.
- Ne jamais cliquer sur « Valider ».
- Aucun dossier n'est imposé : s'il faut en choisir un, c'est un champ de `Params` (le client indiqué sur la pièce).
- `Params` : un champ par valeur à lire sur la pièce, chacun avec sa description. C'est l'agent qui les remplit en lisant la pièce.
- `skill.md` : la Skill du brief, corrigée seulement là où la trace montre le vrai chemin. Garde les règles métier. N'y ajoute pas la règle « le tool d'abord » : SMO l'insère lui-même.
- Appli de bureau (`KIND = "desktop"`) : `precheck(cfg)` et `run(params, cfg)` sans page, avec l'accessibilité macOS (pyobjc). Ta machine ne peut pas lancer l'appli : écris le code et les tests, ils seront joués ailleurs.

## Ta sortie (obligatoire)

À la fin, renseigne ta sortie structurée (structured output) avec exactement ce JSON :

```json
{"tool": "<nom>", "pr_url": "<adresse de la PR>", "tests_passed": true, "merged": true, "issues": ["<problème restant>"]}
```

`tests_passed` et `merged` valent `true` ou `false` ; `issues` est vide si tout va bien.
