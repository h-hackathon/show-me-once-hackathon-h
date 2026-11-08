## Règle absolue : le tool d'abord, l'écran seulement en secours

Cette règle passe avant tout le reste de la Skill, pour chaque pièce :
1. Lis sur la pièce les valeurs que demande `$run`, puis appelle `$run`. Le tool fait toute la tâche lui-même, sur un
   serveur, de façon déterministe, et renvoie le résultat final : tu n'as rien à faire à l'écran.
2. `$run` renvoie `draft_saved` ou `duplicate` : la tâche est faite. Réponds avec ce résultat.
3. `$run` renvoie `flagged` : n'enregistre rien et explique pourquoi dans ta réponse.
4. `$run` renvoie `error`, ou ne répond pas : fais la tâche toi-même à l'écran (computer use) en suivant la méthode
   ci-dessous, puis appelle `report_drift` avec l'erreur du tool.

Toujours : ne jamais cliquer sur « Valider ». Réponds au format demandé, avec mode = "tool" si le tool a fait la tâche,
"computer_use" si tu l'as faite à l'écran.
