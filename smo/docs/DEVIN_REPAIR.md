# Mission : réparer le tool `$tool_name`, l'interface du logiciel a changé

Repo : $repo (h-tools). Le tool est dans `tools/$tool_name/` ; suis le `README.md` du repo.
Logiciel : $url (identifiants dans tes Secrets Devin, comme pour la création du tool).

## Ce qui a cassé

$details

## Le contrat d'interface actuel (`ui_contract.json`)

```json
$contract
```

## La Skill actuelle de l'agent (`skill.md`)

$skill

## Comment l'agent H a fini la tâche en computer use sur la nouvelle interface (reprise)

$trace

## À livrer : une PR « fix: $tool_name », tests verts, puis fusion (README d'h-tools)

- Mets à jour `tool.py` et `ui_contract.json` pour la nouvelle interface ; garde le même `NAME` et les mêmes `Params` si possible.
- Mets à jour `skill.md` si le chemin à l'écran a changé (nouvel onglet, bouton renommé, champ obligatoire), pour que la reprise à l'écran reste juste. Ne touche pas aux règles métier, et n'ajoute pas de partie « Utiliser les tools » (SMO l'ajoute).
- Mêmes contraintes qu'à la création : sélecteurs par rôle et libellé, `precheck` sans effet, `run` idempotent, jamais « Valider ».
- Le déploiement est automatique après la fusion, et prévient SMO, qui remet l'agent H à jour.
