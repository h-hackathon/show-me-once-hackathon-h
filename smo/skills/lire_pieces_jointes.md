# Lire les pièces jointes d'une demande

Les fichiers joints à la demande sont dans `files/` de ta workstation (`/workspace/files/`) : lis-les depuis son
shell, une pièce à la fois. H en pose aussi une copie dans `~/Downloads` du navigateur : si la workstation ne répond
pas, ouvre la pièce dans le navigateur, et sers-toi de cette copie quand le logiciel demande la pièce justificative.

1. Liste les pièces : `ls -la /workspace/files/`.
2. Pour chaque PDF : `pdftotext -layout "/workspace/files/<nom>.pdf" -`. Si le texte sort vide (scan), dis-le dans ta
   réponse pour cette pièce et passe à la suivante : ne devine aucune valeur.
3. Une image jointe au message, tu la vois directement : lis les valeurs dessus.
4. Recopie les valeurs exactement (montants, dates, numéros, taux de TVA), au format attendu par le logiciel ou par
   le tool. Une valeur absente ou illisible : signale-la, ne l'invente pas.
5. Traite la pièce jusqu'au bout (tool, ou écran en secours) avant de lire la suivante. Dans ta réponse finale,
   donne pour chaque pièce son nom de fichier, les valeurs lues et ce qui a été fait.
