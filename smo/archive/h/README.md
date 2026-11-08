# Archives de la plateforme H

Agents et Skills supprimés de H, gardés ici tels qu'ils étaient au moment de la suppression.
- `agent.<nom>.json` : la définition complète de l'agent (instructions, Skills, tools, environnements) ; `_revisions`
  ne liste que les dates des révisions, H ne rend pas leur contenu.
- `skill.<nom>.md` : le corps de la Skill ; `skill.<nom>.json` : sa description et ses fichiers.

Pour en recréer un : `h.upsert_skill` / `h.upsert_agent` (`smo/clients/h.py`) avec ces valeurs.

- `2026-11-08/` : les agents et Skills des tests (`smotest-…`, `…-demo-…`), remplacés par `smo-<tâche>-<web|desktop>`.
