"""Chaque tool du repo est bien formé : c'est le test hors ligne que la CI passe sur tous, sans identifiant."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from h_tools.loader import load_tool


ROOT = Path(__file__).resolve().parent.parent
FOLDERS = sorted(p.parent for p in (ROOT / "tools").glob("*/tool.py"))
ANCHOR_KEYS = {"role", "label", "name", "text"}


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda f: f.name)
def test_tool_is_well_formed(folder: Path):
    tool = load_tool(folder)
    template = folder.name.startswith("_")
    assert template or tool.name == folder.name, "NAME = nom du dossier"
    assert re.fullmatch(r"[a-z0-9_]+", tool.name)
    assert tool.kind in ("web", "desktop") and (tool.kind == "desktop") == tool.name.endswith("_desktop")
    assert tool.description and tool.describe()["params"]["type"] == "object"
    assert (folder / "skill.md").read_text(encoding="utf-8").strip(), "skill.md : la Skill de l'agent"
    assert (folder / "test_tool.py").exists()
    for name in ("precheck", "run", "rules"):
        assert callable(getattr(tool.module, name, None)), f"{name}() manquant"
    screens = tool.contract.get("screens")
    assert screens, "ui_contract.json : au moins un écran"
    for screen in screens:
        assert screen.get("name") and screen.get("anchors")
        for anchor in screen["anchors"] + screen.get("via", []):
            assert ANCHOR_KEYS & set(anchor), f"ancre sans libellé : {anchor}"
            assert not {"x", "y", "css", "selector", "xpath"} & set(anchor), f"pas de coordonnées ni de CSS : {anchor}"


def test_no_credentials_in_the_repo():
    """Les identifiants viennent du vault H : aucun fichier de tool ne doit en contenir."""
    pattern = re.compile(r"(password|mot_de_passe|passwd|secret|token)\s*=\s*['\"][^'\"]{4,}", re.I)
    leaks = [str(p.relative_to(ROOT)) for p in (ROOT / "tools").rglob("*.py") if pattern.search(p.read_text("utf-8"))]
    assert not leaks, f"identifiants en dur : {leaks}"
