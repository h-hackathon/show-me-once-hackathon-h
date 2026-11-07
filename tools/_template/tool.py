"""Modèle de tool : Devin le copie dans tools/<nom>/ et le complète (voir README.md)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from h_tools.site import SiteAPI
from h_tools.ui import check_contract, contract_of, locate, login


NAME = "nom_du_tool"                     # = nom du dossier ; lettres minuscules, chiffres et _
DESCRIPTION = "Saisit une pièce dans le logiciel à partir des valeurs lues dessus."
CONTRACT = contract_of(__file__)


class Params(BaseModel):
    reference: str = Field(description="n° de la pièce ; sert aussi de clé d'idempotence")
    # Un champ par valeur lue sur la pièce, chacun avec sa description.


def precheck(page, cfg) -> dict:
    login(page, cfg)
    return check_contract(page, CONTRACT, cfg)


def run(page, params: Params, cfg) -> dict:
    # 1. L'interface d'abord, comme precheck : si elle a changé, rien n'est saisi et l'agent prend la main à l'écran.
    login(page, cfg)   # login(page, cfg, params.dossier) si le logiciel demande de choisir un dossier
    check = check_contract(page, CONTRACT, cfg)
    if not check["ok"]:
        return {"status": "error", "reason": "interface changée", "missing": check["missing"]}

    # 2. Idempotence : la pièce est-elle déjà saisie ? Par l'API technique si son jeton est donné (facultatif)…
    if cfg.site_admin_token and SiteAPI(cfg).get("/api/invoices", reference=params.reference):
        return {"status": "duplicate", "reference": params.reference}

    # 3. Règles de la Skill, codées en dur (ex. HT + TVA = TTC) → flagged, rien n'est enregistré.

    # 4. Saisie, élément par élément, par libellé. Le dossier est celui de la pièce (un champ de Params), jamais imposé.
    # page.goto(f"{cfg.site_url}/factures/nouvelle")
    # locate(page, {"label": "Référence fournisseur"}).fill(params.reference)
    # … sinon à l'écran : le logiciel refuse un doublon avec un message (Qonta : « Doublon : … »).
    # if page.get_by_text("Doublon", exact=False).count(): return {"status": "duplicate", "reference": params.reference}

    # 5. Enregistrer en brouillon ; ne jamais valider ni soumettre.
    # locate(page, {"role": "button", "name": "Enregistrer le brouillon"}).click()
    return {"status": "draft_saved", "reference": params.reference}
