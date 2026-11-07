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
    # 1. Idempotence : la pièce est-elle déjà saisie ? Par l'API technique si son jeton est donné (facultatif)…
    if cfg.site_admin_token and Site(cfg.site_url, cfg.site_admin_token).invoices(params.reference):
        return {"status": "duplicate", "reference": params.reference}

    # 2. Règles de la Skill, codées en dur (ex. HT + TVA = TTC) → flagged, rien n'est enregistré.

    # 3. Saisie, élément par élément, par libellé. Le dossier est celui de la pièce (un champ de Params), jamais imposé.
    login(page, cfg)   # login(page, cfg, params.dossier) si le logiciel demande de choisir un dossier
    # page.goto(f"{cfg.site_url}/factures/nouvelle")
    # locate(page, {"label": "Référence fournisseur"}).fill(params.reference)

    # 4. Enregistrer en brouillon ; ne jamais cliquer sur « Valider ».
    # locate(page, {"role": "button", "name": "Enregistrer le brouillon"}).click()
    # … sinon à l'écran : le logiciel refuse un doublon avec un message (Comptarex : « Doublon : … »).
    # if page.get_by_text("Doublon", exact=False).count(): return {"status": "duplicate", "reference": params.reference}
    return {"status": "draft_saved", "reference": params.reference}
