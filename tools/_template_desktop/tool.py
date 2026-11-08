"""Modèle de tool de bureau : Devin le copie dans tools/<nom>_desktop/ et le complète (voir README.md).

Il ne tourne pas sur Railway : SMO le livre avec la Skill de l'agent bureau (fichiers posés par l'API H) et l'agent le
lance depuis son shell, dans son propre environnement, avec `./run.sh run '{...}'`. Il pilote l'appli par son arbre
d'accessibilité (`cua`, le CLI de H), par libellés : jamais de coordonnées.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from h_tools import desk

NAME = "nom_du_tool_desktop"             # = nom du dossier ; finit par _desktop
DESCRIPTION = "Saisit une pièce dans l'application de bureau à partir des valeurs lues dessus."
KIND = "desktop"
WINDOW = "Nom de l'appli"                # titre de la fenêtre ou nom de l'appli, comme `cua windows` le montre
CONTRACT = json.loads((Path(__file__).with_name("ui_contract.json")).read_text(encoding="utf-8"))


class Params(BaseModel):
    reference: str = Field(description="n° de la pièce ; sert aussi de clé d'idempotence")
    # Un champ par valeur lue sur la pièce, chacun avec sa description.


def rules(params: Params) -> str | None:
    """Les règles de la Skill, codées en dur : la raison de l'arrêt, ou None. Testées hors ligne (test_tool.py)."""
    return None


def precheck(cfg) -> dict:
    return desk.check_contract(CONTRACT)


def run(params: Params, cfg) -> dict:
    if reason := rules(params):
        return {"status": "flagged", "reason": reason, "reference": params.reference}
    # L'appli est ouverte et connectée par l'agent (identifiants du vault H) : le tool ne voit aucun mot de passe.
    # desk.click(WINDOW, "Nouvelle facture", role="push button")
    # desk.set_value(WINDOW, "Référence fournisseur", params.reference)
    # Idempotence : le message de doublon du logiciel → {"status": "duplicate", ...}
    # desk.click(WINDOW, "Enregistrer le brouillon", role="push button")   # jamais « Valider »
    return {"status": "draft_saved", "reference": params.reference}
