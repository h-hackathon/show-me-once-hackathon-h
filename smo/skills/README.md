# Bloc commun des Skills

La règle absolue (le tool d'abord, l'écran en secours puis `report_drift`, ne jamais finaliser, le format de réponse)
est dans les instructions de l'agent (`smo/pipeline/provision.py`) : elles sont toujours lues, une Skill ne l'est que
si H la charge. Ces blocs n'en donnent que le détail, sans la répéter.

SMO insère l'un d'eux en tête de chaque Skill qu'il envoie dans H (création de l'agent, essais, mise à jour) :
- `bloc_commun.md` : l'agent a son tool web. Comment appeler `run_<tâche>`, que faire de chaque statut, quand reprendre
  à l'écran et appeler `report_drift`.
- `bloc_commun_bureau.md` : la même chose pour un tool de bureau, livré dans la Skill et lancé avec `./run.sh`.
- `bloc_commun_sans_tool.md` : le tool n'est pas encore là, l'agent fait la tâche à l'écran.

Le bloc n'apparaît pas à la relecture humaine, et Devin ne l'écrit pas : il est ajouté au moment de l'envoi.
Les noms des tools (`$run`) et le schéma des valeurs (`$schema`) sont remplis automatiquement.
`lire_pieces_jointes.md` est une petite Skill à part, commune à tous les agents SMO.
