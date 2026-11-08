"""Modèle de test d'un tool de bureau : hors ligne (paramètres, règles). L'appli n'existe que chez l'agent H."""
from pathlib import Path

import pytest

from h_tools.config import Context
from h_tools.loader import load_tool

cfg = Context.from_env()
tool = load_tool(Path(__file__).parent)
pytestmark = pytest.mark.skipif(tool.name.startswith("nom_du_tool"), reason="modèle non rempli")

DEMO = {"reference": "A-REMPLIR"}         # les valeurs de la pièce de la démo


def test_params_of_the_demo_piece():
    assert tool.params(**DEMO).reference == DEMO["reference"]


def test_rules_accept_the_demo_piece():
    assert tool.module.rules(tool.params(**DEMO)) is None
