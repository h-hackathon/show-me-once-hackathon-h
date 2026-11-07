# Mission : compiler la tâche « $task » en tool déterministe

Repo : $repo (h-tools). Lis d'abord son `README.md`, puis crée `tools/$tool_name/` en copiant `tools/_template/`.
Logiciel cible ($kind) : $url. Identifiants de test dans tes Secrets Devin : `SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD` (appli de bureau : `DESKTOP_LOGIN`, `DESKTOP_PASSWORD`).
- Type `web` : Playwright, avec les aides de `h_tools.ui` (`login`, `locate`, `check_contract`).
- Type `desktop` : `KIND = "desktop"`, `precheck(cfg)` et `run(params, cfg)` sans page, en Python avec l'accessibilité macOS (pyobjc : ApplicationServices). Les éléments se trouvent par rôle et nom accessible, comme sur le web. Ta machine ne peut pas lancer l'appli : écris le tool et ses tests, ils seront joués sur le Mac.
- Aucun dossier n'est imposé : s'il faut en choisir un, c'est celui du client indiqué sur la pièce (un champ de `Params`, passé à `login(page, cfg, dossier)`).
- Les fournisseurs se comparent sans casse ni accents.

Pièce traitée pendant la démo : $sample.

## 1. La Skill validée par l'humain (référence métier, prioritaire sur tout le reste)

$skill

## 2. Ce que l'agent H a fait à l'écran en suivant cette Skill (trace condensée)

L'agent a réussi la tâche en computer use, sans tool, sur une pièce suivante de la démo. Chaque ligne : écran (URL, titre) → consigne en cours → actions de l'agent.
Pièces jointes : `trace.json` (trace complète), `trial.json` (ses essais et le verdict de Holo), captures d'écran.

$trace

## 3. Règles vérifiées sur le web (Linkup)

$checks

## 4. Carte du logiciel (relevée par un agent H qui l'a parcouru en lecture seule)

Écrans, chemin pour y arriver, libellés exacts : la base de `ui_contract.json`.

$map

## 5. Documentation publique du logiciel (Linkup)

$docs

## À livrer dans `tools/$tool_name/` (voir le README d'h-tools)

1. `tool.py` : `NAME = "$tool_name"`, `DESCRIPTION`, `Params` (pydantic, un champ par valeur lue sur la pièce, avec une description), `precheck` et `run`.
2. `ui_contract.json` : chaque écran traversé, avec ses éléments attendus (rôle + libellé visible).
3. `test_tool.py` : rejoue une pièce contre le logiciel et vérifie le résultat.
4. `skill.md` : la Skill ci-dessus, corrigée seulement là où la trace montre le vrai chemin (libellés exacts, écran intermédiaire oublié). Garde les règles métier telles quelles. N'y ajoute pas de partie « Utiliser les tools » : SMO l'ajoute lui-même.
5. `env.txt` : les variables dont le tool a besoin, une par ligne (`SITE_URL`, `SITE_LOGIN`, `SITE_PASSWORD`…).

Puis suis la section « Pour Devin : livrer un tool » du README : PR « tool: $tool_name », tests verts, fusion. Le déploiement est automatique et prévient SMO.

## Contraintes

- Sélecteurs par rôle et libellé visible uniquement. Jamais de coordonnées, jamais de sélecteur CSS.
- `precheck` ne modifie rien.
- `run` est idempotent : une pièce déjà saisie renvoie `{"status": "duplicate"}` sans rien créer (le logiciel affiche « Doublon : … »).
- Les règles de la Skill sont codées en dur (ex. HT + TVA = TTC) : en cas d'écart, renvoie `{"status": "flagged", "reason": ...}` sans enregistrer.
- Ne jamais cliquer sur « Valider » : on s'arrête toujours en brouillon.
- Ne modifie rien en dehors de `tools/$tool_name/`.
