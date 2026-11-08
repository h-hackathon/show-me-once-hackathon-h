"""Contre le vrai site compta (Qonta) : le precheck doit passer en v1 et détecter la v2.

Le test bascule le site en v2 quelques secondes (version d'origine remise à la fin) : il ne tourne que sur un
Qonta local, ou en ligne si SMO_LIVE_TESTS=1, pour ne pas gêner l'équipe sur un site partagé.
Sauté aussi si le site est éteint ou si le jeton admin est refusé.
"""
import os

import httpx
import pytest

from smo.clients.h import is_local
from smo.clients.site import Site
from smo.config import load
from smo.runtime.tools import with_page
from smo.runtime.ui import check_contract, login


cfg = load()


def _skip_reason() -> str | None:
    if not (cfg.site_url and cfg.site_admin_token):
        return "SITE_URL / SITE_ADMIN_TOKEN absents"
    if not is_local(cfg.site_url) and os.environ.get("SMO_LIVE_TESTS") != "1":
        return "site en ligne partagé : SMO_LIVE_TESTS=1 pour le tester"
    try:
        Site(cfg.site_url, cfg.site_admin_token).invoices()
    except httpx.HTTPStatusError as err:
        return f"accès admin refusé (HTTP {err.response.status_code})"
    except httpx.HTTPError:
        return "site éteint"
    return None


SKIP = _skip_reason()
pytestmark = pytest.mark.skipif(SKIP is not None, reason=SKIP or "")

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
