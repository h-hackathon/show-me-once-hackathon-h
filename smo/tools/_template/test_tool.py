"""Modèle de test : rejoue la pièce de la démo contre le site, puis relit le résultat par l'API technique."""
from pathlib import Path

import pytest

from smo.clients.site import Site
from smo.config import load
from smo.runtime.tools import load_tool


cfg = load()
tool = load_tool(Path(__file__).parent)
pytestmark = pytest.mark.skipif(tool.name == "nom_du_tool" or not (cfg.site_url and cfg.site_admin_token),
                                reason="modèle non rempli, ou SITE_URL / SITE_ADMIN_TOKEN absents")


def test_precheck_v1():
    result = tool.precheck(cfg)
    assert result["ok"], result["missing"]


def test_run_saves_draft_and_is_idempotent():
    site = Site(cfg.site_url, cfg.site_admin_token)
    site.reset()
    params = {"reference": "A-REMPLIR"}            # les valeurs de la pièce de la démo
    assert tool.run(cfg, **params)["status"] == "draft_saved"
    saved = site.invoices(params["reference"])
    assert len(saved) == 1 and saved[0]["status"] == "draft"
    assert tool.run(cfg, **params)["status"] == "duplicate"
