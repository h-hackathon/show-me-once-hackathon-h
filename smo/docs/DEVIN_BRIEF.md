# Tâche SMO : créer le tool `$tool_name`

$method

## La tâche

- Tâche : « $task ». Type de logiciel : $kind. Logiciel : $url.
- Demande que l'agent a reçue pendant l'essai réussi : « $request ». Le tool traite une pièce par appel : ses paramètres sont les valeurs lues sur la pièce, jamais un numéro de pièce à aller chercher.
- Nom du tool et du dossier : `tools/$tool_name/`, dans $repo.
- Accès au logiciel : tes secrets de session `SITE_URL`, `SITE_USERNAME`, `SITE_PASSWORD`, lus dans le vault H de l'utilisateur. Ils ne sont pas dans ce brief : ne les écris nulle part (code, commit, PR, message).

## 1. La Skill validée par l'humain (référence métier, prioritaire sur tout le reste)

$skill

## 2. Ce que l'agent H a fait à l'écran pour réussir la tâche (trace condensée)

Chaque ligne : écran (URL, titre) → consigne en cours → actions de l'agent.

$trace

## 3. Règles vérifiées sur le web (Linkup)

$checks

## 4. Carte du logiciel (relevée par un agent H en lecture seule)

Écrans, chemin pour y arriver, libellés exacts : la base de `ui_contract.json`.

$map

## 5. Documentation publique du logiciel (Linkup)

$docs

## Pièces jointes

Les sorties complètes, en JSON, de chaque étape : `trace.json` (l'essai réussi), `trial.json` (tous les essais et le verdict de Holo), `procedure.json` (la méthode comprise par Holo), `notes.json` (ce que Holo a lu sur chaque capture), `map.json` (la carte), `docs.json` (la documentation), plus des captures d'écran.
