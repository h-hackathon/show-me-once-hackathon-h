# Tools : ils vivent dans h-tools

Les tools écrits par Devin sont dans le repo **h-tools** (`Tomoroshimaru/h-tools`), un dossier `tools/<nom>/` par tâche apprise.
Son `README.md` est la référence pour leur forme (`tool.py`, `ui_contract.json`, `test_tool.py`, `skill.md`, `env.txt`), pour leurs tests et pour leur déploiement.
Chaque tool web tourne dans son propre service Railway, que SMO joint sur le réseau privé ; les tools de bureau tournent sur le Mac.

Comment SMO trouve un tool (`smo.runtime.tools.find`) :
1. dans un clone local d'h-tools, si `H_TOOLS_DIR` est défini : obligatoire sur le Mac pour les tools de bureau ;
2. sinon, pour un tool web, le service déployé (`smo.runtime.remote`).

Ce dossier ne sert plus qu'aux tests locaux de SMO quand `H_TOOLS_DIR` n'est pas défini. `_template/` est l'ancienne version du modèle : celui d'h-tools fait foi.
