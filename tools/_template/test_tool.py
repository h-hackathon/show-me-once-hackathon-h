"""Modèle de test d'un tool.

En CI, hors ligne seulement : aucun identifiant n'est dans GitHub. On teste les paramètres et les règles de la Skill.
Le precheck réel est fait par SMO après le déploiement, avec le vault de l'agent ; la saisie réelle, par Devin
pendant qu'il code (sa session reçoit SITE_URL, SITE_USERNAME, SITE_PASSWORD).
"""
from pathlib import Path

import pytest

from h_tools.config import Context
from h_tools.loader import load_tool

cfg = Context.from_env()
tool = load_tool(Path(__file__).parent)
pytestmark = pytest.mark.skipif(tool.name.startswith("nom_du_tool"), reason="modèle non rempli")
live = pytest.mark.skipif(not cfg.site_url, reason="hors ligne (CI) : pas de SITE_URL")

DEMO = {"reference": "A-REMPLIR"}         # les valeurs de la pièce de la démo


def test_params_of_the_demo_piece():
    assert tool.params(**DEMO).reference == DEMO["reference"]


def test_rules_accept_the_demo_piece():
    assert tool.module.rules(tool.params(**DEMO)) is None


# Un test par règle de la Skill : la pièce qui l'enfreint est arrêtée sans toucher au site (page=None).
# def test_flags_totals_that_do_not_add_up():
#     bad = tool.params(**{**DEMO, "ttc": 0})
#     assert tool.module.run(None, bad, cfg)["status"] == "flagged"


@live
def test_precheck_on_the_real_site():
    result = tool.precheck(cfg)
    assert result["ok"], result.get("missing") or result.get("error")
