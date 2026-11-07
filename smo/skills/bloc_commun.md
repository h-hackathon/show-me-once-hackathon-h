## Utiliser les tools (bloc commun SMO)

Pour chaque pièce :
1. Appelle `$precheck` : il vérifie, sans rien modifier, que l'interface n'a pas changé.
2. Si le precheck est OK : ouvre la pièce, lis ses valeurs, puis appelle `$run` avec ces valeurs.
3. `$run` renvoie `draft_saved` : vérifie à l'écran que la pièce est en brouillon avec les bonnes valeurs.
4. `$run` renvoie `duplicate` : la pièce est déjà saisie, ne recommence pas.
5. `$run` renvoie `flagged` : n'enregistre rien et explique pourquoi dans ta réponse.
6. Le precheck échoue, `$run` renvoie `error`, ou l'écran ne correspond pas : fais la tâche toi-même à l'écran
   en suivant cette Skill, puis appelle `report_drift` en décrivant ce qui a changé.
7. Fournisseur inconnu ou douteux : vérifie-le avec `check_supplier` avant de le créer.

Toujours : ne jamais cliquer sur « Valider ». Réponds au format demandé, avec mode = "tool" si le tool a fait la
saisie, "computer_use" si tu l'as faite à l'écran.
