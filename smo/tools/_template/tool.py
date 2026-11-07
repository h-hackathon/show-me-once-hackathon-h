"""Modèle de tool compilé : Devin le copie dans tools/<nom>/ et le complète (voir tools/README.md)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from smo.clients.site import Site
from smo.runtime.ui import check_contract, contract_of, locate, login


NAME = "nom_du_tool"                     # = nom du dossier ; lettres, chiffres et _
DESCRIPTION = "Saisit une pièce dans le logiciel à partir des valeurs lues dessus."
CONTRACT = contract_of(__file__)


class Params(BaseModel):
    reference: str = Field(description="n° de la pièce ; sert aussi de clé d'idempotence")
    # Un champ par valeur lue sur la pièce, chacun avec sa description.


def precheck(page, cfg) -> dict:
    login(page, cfg)
    return check_contract(page, CONTRACT, cfg)


def run(page, params: Params, cfg) -> dict:
    # 1. Idempotence : la pièce est-elle déjà saisie ?
    if cfg.site_admin_token and Site(cfg.site_url, cfg.site_admin_token).invoices(params.reference):
        return {"status": "duplicate", "reference": params.reference}

    # 2. Règles de la Skill, codées en dur (ex. HT + TVA = TTC) → flagged, rien n'est enregistré.

    # 3. Saisie, élément par élément, par libellé :
    login(page, cfg)
    # page.goto(f"{cfg.site_url}/invoices/new")
    # locate(page, {"label": "Référence fournisseur"}).fill(params.reference)

    # 4. Enregistrer en brouillon ; ne jamais cliquer sur « Valider ».
    # locate(page, {"role": "button", "name": "Enregistrer le brouillon"}).click()
    return {"status": "draft_saved", "reference": params.reference}
