"""Helpers Playwright des tools : connexion, éléments par libellé, contrat d'interface.

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


def login(page: Page, cfg, dossier: str | None = None, *, path: str = "/login", email: str = "E-mail",
          password: str = "Mot de passe", submit: str = "Se connecter", code: str | None = None) -> None:
    """Connexion par les libellés visibles (ceux du logiciel cible : à adapter), puis ouverture du dossier de la pièce.

    Les identifiants viennent du contexte de l'appel (le vault H) ; `code` : le libellé du champ de double
    authentification, rempli avec le code TOTP du moment. Aucun dossier n'est imposé : le tool le reçoit en paramètre
    (le client indiqué sur la pièce)."""
    if not (cfg.site_url and cfg.username and cfg.password):
        raise RuntimeError("identifiants absents du contexte : ajouter le site dans le vault H de l'agent")
    page.goto(f"{cfg.site_url}{path}")
    page.get_by_label(email).fill(cfg.username)
    page.get_by_label(password).fill(cfg.password)
    page.get_by_role("button", name=submit).click()
    page.wait_for_load_state()
    if code and cfg.totp:
        page.get_by_label(code).fill(cfg.totp)
        page.keyboard.press("Enter")
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
