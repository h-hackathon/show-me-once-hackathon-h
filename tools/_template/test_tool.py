"""Modèle de test : rejoue la pièce de la démo contre le logiciel, puis relit le résultat par l'API technique.

Il tourne en CI avant la fusion et avant chaque déploiement : sans SITE_*, il échoue (il ne saute pas).
"""
from pathlib import Path

import pytest

from h_tools.config import Cfg
from h_tools.loader import load_tool
from h_tools.site import SiteAPI


cfg = Cfg()
tool = load_tool(Path(__file__).parent)
pytestmark = pytest.mark.skipif(tool.name == "nom_du_tool", reason="modèle non rempli")


@pytest.fixture(autouse=True)
def configured():
    assert cfg.site_url and cfg.site_admin_token, "SITE_URL et SITE_ADMIN_TOKEN sont requis (secrets GitHub, ou .env)"


def test_precheck():
    result = tool.precheck(cfg)
    assert result["ok"], result["missing"]


def test_run_saves_draft_and_is_idempotent():
    site = SiteAPI(cfg)
    site.post("/api/admin/reset")
    params = {"reference": "A-REMPLIR"}            # les valeurs de la pièce de la démo
    assert tool.run(cfg, **params)["status"] == "draft_saved"
    saved = site.get("/api/invoices", reference=params["reference"])
    assert len(saved) == 1 and saved[0]["status"] == "draft"
    assert tool.run(cfg, **params)["status"] == "duplicate"
