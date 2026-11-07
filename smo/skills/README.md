# Bloc commun des Skills

SMO ajoute l'un de ces deux blocs à la fin de chaque Skill qu'il envoie dans H (création de l'agent, essais, mise à jour) :
- `bloc_commun.md` : l'agent a son tool. Ce bloc dit comment utiliser `precheck_<tâche>` et `run_<tâche>`, quand reprendre à l'écran et quand appeler `report_drift`.
- `bloc_commun_sans_tool.md` : le tool n'est pas encore là, l'agent fait la tâche à l'écran.

Le bloc n'apparaît pas à la relecture humaine, et Devin ne l'écrit pas : il est ajouté au moment de l'envoi.
Les noms des tools (`$precheck`, `$run`) sont remplis automatiquement.
C'est une version de départ, à revoir et adapter.
