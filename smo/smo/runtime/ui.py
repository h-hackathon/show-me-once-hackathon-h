"""Helpers Playwright pour les tools compilés : connexion, éléments par libellé, contrat d'interface.

Un élément (« ancre ») se décrit comme un humain le voit, jamais par du CSS ni des coordonnées :
  {"role": "button", "name": "Enregistrer le brouillon"}   bouton, lien, onglet… et son texte
  {"label": "Référence fournisseur"}                       champ de formulaire par son libellé
  {"text": "Factures à traiter"}                           texte visible
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeout


def locate(page: Page, anchor: dict) -> Locator:
    exact = anchor.get("exact", True)
    if "role" in anchor:
        return page.get_by_role(anchor["role"], name=anchor.get("name"), exact=exact)
    if "label" in anchor:
        return page.get_by_label(anchor["label"], exact=exact)
    if "text" in anchor:
        return page.get_by_text(anchor["text"], exact=exact)
    raise ValueError(f"Ancre invalide : {anchor}")


def login(page: Page, cfg, dossier: str | None = None) -> None:
    """Connexion au site compta (docs/CONTRAT_SITE.md), puis ouverture du dossier de la pièce si on le donne.

    Aucun dossier n'est imposé : le tool le reçoit en paramètre (le client indiqué sur la pièce)."""
    page.goto(f"{cfg.site_url}/login")
    page.get_by_label("E-mail").fill(cfg.site_login)
    page.get_by_label("Mot de passe").fill(cfg.site_password)
    page.get_by_role("button", name="Se connecter").click()
    page.wait_for_load_state()
    if dossier:
        page.get_by_text(dossier, exact=False).first.click()
        page.wait_for_load_state()


def contract_of(tool_file: str) -> dict:
    """Le ui_contract.json posé à côté du tool.py."""
    path = Path(tool_file).with_name("ui_contract.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"screens": []}


def check_contract(page: Page, contract: dict, cfg, timeout_ms: int = 5000) -> dict:
    """Precheck : chaque écran du contrat montre-t-il encore ses éléments attendus ? Ne modifie rien."""
    missing, checked = [], 0
    for screen in contract.get("screens", []):
        if screen.get("path"):
            page.goto(f"{cfg.site_url}{screen['path']}")
        for via in screen.get("via", []):          # clics de navigation pour atteindre l'écran
            locate(page, via).first.click()
        page.wait_for_load_state()
        for anchor in screen.get("anchors", []):
            checked += 1
            try:
                locate(page, anchor).first.wait_for(state="visible", timeout=timeout_ms)
            except PlaywrightTimeout:
                missing.append({"screen": screen.get("name"), "anchor": anchor})
    return {"ok": not missing, "checked": checked, "missing": missing}
