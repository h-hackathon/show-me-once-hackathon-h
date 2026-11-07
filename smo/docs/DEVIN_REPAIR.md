# Mission : réparer le tool `$tool_name`, l'interface du logiciel a changé

Repo : $repo. Le tool est dans `tools/$tool_name/` (lis `tools/README.md`).
Logiciel : $url (identifiants dans tes Secrets Devin, comme pour la création du tool).

## Ce qui a cassé

$details

## Le contrat d'interface actuel (`ui_contract.json`)

```json
$contract
```

## Comment l'agent H a fini la tâche à la main sur la nouvelle interface

$trace

## À livrer : une PR, titre « fix: $tool_name »

- Mets à jour `tool.py` et `ui_contract.json` pour la nouvelle interface ; garde le même `NAME` et les mêmes `Params` si possible.
- Mêmes contraintes qu'à la création : sélecteurs par rôle et libellé, `precheck` sans effet, `run` idempotent, jamais « Valider ».
- `uv run pytest tools/$tool_name` passe sur l'interface actuelle.
