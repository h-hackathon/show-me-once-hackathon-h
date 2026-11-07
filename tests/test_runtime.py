"""Tests hors ligne du runtime : réglages, chargement d'un tool, serveur du conteneur, choix des tools à déployer."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from h_tools import loader, server
from h_tools.config import Cfg


ROOT = Path(__file__).resolve().parent.parent

FAKE_TOOL = '''
from pydantic import BaseModel, Field

NAME = "faux_tool"
DESCRIPTION = "Un tool de test."


class Params(BaseModel):
    reference: str = Field(description="n° de la pièce")
    amount: float = 0


def precheck(page, cfg):
    return {"ok": True, "checked": 0, "missing": []}


def run(page, params, cfg):
    if params.amount < 0:
        raise RuntimeError("montant négatif")
    return {"status": "draft_saved", "reference": params.reference, "site": cfg.site_url}
'''


@pytest.fixture
def fake_tool(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "faux_tool"
    folder.mkdir()
    (folder / "tool.py").write_text(FAKE_TOOL, encoding="utf-8")
    (folder / "skill.md").write_text("# Skill de test\n", encoding="utf-8")
    (folder / "VERSION").write_text("abc123\n")
    monkeypatch.setattr(loader, "with_page", lambda fn: loader.guarded(fn, None))   # pas de navigateur
    monkeypatch.setenv("SITE_URL", "compta.example.com/")
    return folder


def test_cfg_reads_env_and_normalizes_urls(monkeypatch):
    monkeypatch.setenv("SITE_URL", "localhost:8042/")
    monkeypatch.setenv("SITE_LOGIN", "  ")
    cfg = Cfg()
    assert cfg.site_url == "http://localhost:8042"
    assert cfg.site_login is None and cfg.site_absente is None


def test_template_loads():
    tool = loader.load_tool(ROOT / "tools" / "_template")
    described = tool.describe()
    assert tool.name == "nom_du_tool"
    assert described["params"]["required"] == ["reference"]
    assert described["skill"] and tool.contract["screens"]


def test_server(fake_tool):
    client = TestClient(server.build_app(fake_tool))
    assert client.get("/health").json() == {"ok": True, "tool": "faux_tool", "sha": "abc123"}
    described = client.get("/describe").json()
    assert described["name"] == "faux_tool" and described["skill"] == "# Skill de test\n"
    assert set(described["params"]["properties"]) == {"reference", "amount"}
    assert client.post("/precheck").json()["ok"] is True
    assert client.post("/run", json={"reference": "F-1"}).json() == {
        "status": "draft_saved", "reference": "F-1", "site": "https://compta.example.com"}


def test_server_turns_failures_into_results(fake_tool):
    client = TestClient(server.build_app(fake_tool))
    invalid = client.post("/run", json={}).json()
    assert invalid["status"] == "error" and "paramètres invalides" in invalid["error"]
    crashed = client.post("/run", json={"reference": "F-1", "amount": -1}).json()
    assert crashed == {"ok": False, "status": "error", "error": "RuntimeError: montant négatif"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def changed(repo: Path, base: str) -> list[str]:
    script = ROOT / "scripts" / "changed_tools.sh"
    return subprocess.run(["bash", str(script), base], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.split()


def test_changed_tools(tmp_path):
    for name in ("_template", "alpha", "beta"):
        (tmp_path / "tools" / name).mkdir(parents=True)
        (tmp_path / "tools" / name / "tool.py").write_text("NAME = 'x'\n")
    (tmp_path / "h_tools").mkdir()
    (tmp_path / "h_tools" / "ui.py").write_text("")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "init")
    base = git(tmp_path, "rev-parse", "HEAD")

    assert changed(tmp_path, "") == ["alpha", "beta"]                                  # premier déploiement
    (tmp_path / "tools" / "alpha" / "tool.py").write_text("NAME = 'y'\n")
    (tmp_path / "tools" / "_template" / "tool.py").write_text("NAME = 'z'\n")
    git(tmp_path, "commit", "-qam", "alpha")
    assert changed(tmp_path, base) == ["alpha"]                                        # le modèle ne se déploie pas
    (tmp_path / "h_tools" / "ui.py").write_text("# changé\n")
    git(tmp_path, "commit", "-qam", "runtime")
    assert changed(tmp_path, base) == ["alpha", "beta"]                                # runtime commun → tous
