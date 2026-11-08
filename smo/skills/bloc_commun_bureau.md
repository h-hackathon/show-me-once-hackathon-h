## Règle absolue : le tool d'abord, l'écran seulement en secours

Cette règle passe avant tout le reste de la Skill, pour chaque pièce. Le tool est livré avec cette Skill : ses
fichiers (`run.sh`, `tool/`, `h_tools/`) sont dans le dossier de la Skill, dans ton environnement.
1. L'application ouverte (et connectée si elle le demande), lis sur la pièce les valeurs que demande le tool, puis
   lance dans ton shell, depuis le dossier de cette Skill :
   `./run.sh run '<les valeurs, en JSON>'`
   Le tool fait toute la saisie lui-même, de façon déterministe, et affiche le résultat final en JSON : tu n'as rien
   à faire à l'écran. Les valeurs attendues (schéma JSON) : `$schema`
2. `status` vaut `draft_saved` ou `duplicate` : la tâche est faite. Réponds avec ce résultat.
3. `status` vaut `flagged` : n'enregistre rien et explique pourquoi dans ta réponse.
4. `status` vaut `error`, ou la commande échoue : fais la tâche toi-même à l'écran (computer use) en suivant la
   méthode ci-dessous, puis appelle `report_drift` avec l'erreur du tool (`./run.sh precheck` dit, sans rien
   modifier, ce qui a changé dans l'interface).

Toujours : ne jamais cliquer sur « Valider ». Réponds au format demandé, avec mode = "tool" si le tool a fait la tâche,
"computer_use" si tu l'as faite à l'écran.
