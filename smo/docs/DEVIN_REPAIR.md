# Tâche SMO : réparer le tool `$tool_name` (l'interface du logiciel a changé)

$method

## La tâche

- Tool : `tools/$tool_name/`, dans $repo. Logiciel : $url.
- PR « fix: $tool_name ». Garde le même `NAME` et les mêmes `Params` si possible.
- Accès au logiciel : tes secrets de session `SITE_URL`, `SITE_USERNAME`, `SITE_PASSWORD`, lus dans le vault H de l'utilisateur. Ils ne sont pas dans ce brief : ne les écris nulle part (code, commit, PR, message).
- Mets aussi à jour `skill.md` si le chemin à l'écran a changé (nouvel onglet, bouton renommé, champ obligatoire). Ne touche pas aux règles métier.

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

Pièce jointe : `trace.json`, la trace complète de cette reprise.
