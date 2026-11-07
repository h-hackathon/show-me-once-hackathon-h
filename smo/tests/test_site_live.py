"""Contre le vrai site compta (Comptarex) : sauté si SITE_URL / SITE_ADMIN_TOKEN absents ou site éteint.

Le precheck doit passer en v1 et détecter la v2 ; la version d'origine est remise à la fin.
"""
import httpx
import pytest

from smo.clients.site import Site
from smo.config import load
from smo.runtime.tools import with_page
from smo.runtime.ui import check_contract, login


cfg = load()


def _site_up() -> bool:
    if not (cfg.site_url and cfg.site_admin_token):
        return False
    try:
        return Site(cfg.site_url).health()["ok"]
    except (httpx.HTTPError, KeyError):
        return False


pytestmark = pytest.mark.skipif(not _site_up(), reason="site compta non configuré ou éteint")

CONTRACT = {"version": 1, "screens": [{"name": "Nouvelle facture", "path": "/factures/nouvelle", "anchors": [
    {"label": "Fournisseur"}, {"label": "Référence fournisseur"}, {"label": "Date de facture"},
    {"role": "button", "name": "Enregistrer le brouillon"}]}]}


@pytest.fixture
def site():
    api = Site(cfg.site_url, cfg.site_admin_token)
    before = api.ui_version()
    yield api
    api.set_ui_version(before)


def precheck(page) -> dict:
    login(page, cfg)
    return check_contract(page, CONTRACT, cfg, timeout_ms=3000)


def test_precheck_passes_on_v1_and_catches_v2(site):
    site.set_ui_version("v1")
    assert with_page(precheck) == {"ok": True, "checked": 4, "missing": []}
    site.set_ui_version("v2")
    missing = [m["anchor"] for m in with_page(precheck)["missing"]]
    assert {"label": "Référence fournisseur"} in missing                   # passée dans l'onglet « Détails »
    assert {"role": "button", "name": "Enregistrer le brouillon"} in missing   # devenu « Sauvegarder »
