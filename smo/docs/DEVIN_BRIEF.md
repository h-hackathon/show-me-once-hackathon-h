# Mission : compiler la tâche « $task » en tool déterministe

Repo : $repo. Crée le dossier `tools/$tool_name/` en copiant `tools/_template/`, et lis d'abord `tools/README.md`.
Logiciel cible : $url. Identifiants de test dans tes Secrets Devin : `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`, `SITE_DOSSIER`, `SITE_ADMIN_TOKEN`.
Pièce traitée pendant la démo : $sample.
Détails du logiciel (écrans, libellés exacts, API technique, formats) : `docs/CONTRAT_SITE.md`. Les fournisseurs se comparent sans casse ni accents.

## 1. La Skill validée par l'humain (référence métier, prioritaire sur tout le reste)

$skill

## 2. Ce que l'agent H a fait à l'écran en suivant cette Skill (trace condensée)

L'agent custom a traité la pièce de la démo une fois en computer use, sans tool. Chaque ligne : écran (URL, titre) → consigne en cours → actions de l'agent.
Pièces jointes : `trace.json` (trace complète), `trial.json` (réponse de l'agent et ce qui est réellement enregistré dans le logiciel), captures d'écran.

$trace

## 3. Règles vérifiées sur le web (Linkup)

$checks

## 4. Carte du logiciel (relevée par un agent H qui l'a parcouru en lecture seule)

Écrans, chemin pour y arriver, libellés exacts : la base de `ui_contract.json`.

$map

## À livrer : une seule PR, titre « tool: $tool_name »

1. `tools/$tool_name/tool.py` : `NAME = "$tool_name"`, `DESCRIPTION`, `Params` (pydantic, un champ par valeur lue sur la pièce, avec une description), `precheck(page, cfg)`, `run(page, params, cfg)`.
2. `tools/$tool_name/ui_contract.json` : chaque écran traversé, avec ses éléments attendus (rôle + libellé visible).
3. `tools/$tool_name/test_tool.py` : rejoue la pièce de la démo contre le site (interface v1) et vérifie le résultat par l'API technique (`GET /api/invoices?reference=...`).
4. `tools/$tool_name/skill.md` : la Skill ci-dessus, corrigée seulement là où la trace montre le vrai chemin (libellés exacts, écran intermédiaire oublié). C'est elle que l'agent utilisera en reprise à l'écran : garde les règles métier telles quelles.

## Contraintes

- Sélecteurs par rôle et libellé visible uniquement (`get_by_role`, `get_by_label`, helpers de `smo.runtime.ui`). Jamais de coordonnées, jamais de sélecteur CSS.
- `precheck` ne modifie rien.
- `run` est idempotent : si la référence existe déjà, renvoie `{"status": "duplicate"}` sans rien créer.
- Les règles de la Skill sont codées en dur (ex. HT + TVA = TTC) : en cas d'écart, renvoie `{"status": "flagged", "reason": ...}` sans enregistrer.
- Ne jamais cliquer sur « Valider » : on s'arrête toujours en brouillon.
- `uv run pytest tools/$tool_name` passe. Ne modifie rien en dehors de `tools/$tool_name/`.
