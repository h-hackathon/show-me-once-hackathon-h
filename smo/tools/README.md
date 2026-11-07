# Tools compilés

Un dossier par tâche apprise, écrit par Devin à partir d'une capture (voir `docs/DEVIN_BRIEF.md`).
Le serveur SMO charge chaque `tools/<nom>/tool.py` et l'expose à l'agent custom H sous deux noms :
`precheck_<nom>` (l'interface a-t-elle changé ?) et `run_<nom>` (la saisie déterministe).

```
tools/<nom>/
  tool.py            NAME, DESCRIPTION, Params, precheck(page, cfg), run(page, params, cfg)
  ui_contract.json   les écrans traversés et leurs éléments attendus
  test_tool.py       rejoue la pièce de la démo contre le site, vérifie par l'API technique
  skill.md           la Skill de l'agent (reprise à l'écran), poussée dans H à chaque `upgrade`
```

Devin crée ce dossier à partir de la trace de l'agent (étape `trial`), puis le corrige à chaque réparation : tool et Skill dans la même PR.

Partir de `tools/_template/` (ignoré par le serveur tant qu'il commence par `_`).

## Règles

- **Sélecteurs** : uniquement par rôle et libellé visible, via `smo.runtime.ui.locate` ou `page.get_by_role` / `get_by_label`. Jamais de coordonnées ni de CSS : c'est ce qui rend le precheck fiable.
- **`precheck`** ne modifie rien. En général : `login(page, cfg)` puis `check_contract(page, CONTRACT, cfg)`.
- **`run`** :
  - il est idempotent : une référence déjà saisie renvoie `{"status": "duplicate"}` ;
  - les règles de la Skill sont codées en dur : un écart renvoie `{"status": "flagged", "reason": ...}` sans rien enregistrer ;
  - il s'arrête toujours en brouillon et ne clique jamais sur « Valider ».
- **Statuts renvoyés par `run`** : `draft_saved`, `duplicate`, `flagged` ou `error`, plus les valeurs saisies.
- **`cfg`** donne `site_url`, `site_login`, `site_password`, `site_dossier` et `site_admin_token` (lus dans l'environnement).

## Format de `ui_contract.json`

```json
{
  "version": 1,
  "screens": [
    {"name": "Nouvelle facture", "path": "/factures/nouvelle",
     "anchors": [{"label": "Fournisseur"}, {"label": "Référence fournisseur"},
                 {"role": "button", "name": "Enregistrer le brouillon"}]}
  ]
}
```

Un écran s'atteint par `path` (URL relative au site), ou par `via` (une liste de clics, ex. `[{"role": "link", "name": "Factures fournisseurs"}]`).

## Tester

```bash
uv run pytest tools/<nom>          # contre SITE_URL (interface v1)
uv run smo tools --precheck        # precheck de tous les tools
```
