"""Tests hors ligne du runtime : contexte d'un appel, chargement d'un tool, serveur du conteneur, CLI, bureau,
choix des tools à déployer et paquet d'un tool de bureau."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from h_tools import cli, desk, loader, server
from h_tools.config import MASK, Context


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import announce  # noqa: E402

FAKE_TOOL = '''
from pydantic import BaseModel, Field

NAME = "faux_tool"
DESCRIPTION = "Un tool de test."


class Params(BaseModel):
    reference: str = Field(description="n° de la pièce")
    amount: float = 0


def precheck(page, cfg):
    return {"ok": True, "checked": 0, "missing": [], "user": cfg.username}


def run(page, params, cfg):
    if params.amount < 0:
        raise RuntimeError(f"montant négatif (connecté avec {cfg.password})")
    return {"status": "draft_saved", "reference": params.reference, "site": cfg.site_url}
'''

CONTEXT = {"site_url": "compta.example.com/", "username": "catherine@cabinet.fr", "password": "s3cret-pass"}


@pytest.fixture
def fake_tool(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "faux_tool"
    folder.mkdir()
    (folder / "tool.py").write_text(FAKE_TOOL, encoding="utf-8")
    (folder / "skill.md").write_text("# Skill de test\n", encoding="utf-8")
    (folder / "VERSION").write_text("abc123\n")
    monkeypatch.setattr(loader, "with_page", lambda fn: loader.guarded(fn, None))   # pas de navigateur
    monkeypatch.delenv("SMO_SERVER_TOKEN", raising=False)   # ouvert, sauf dans le test du jeton
    for var in ("SITE_URL", "SITE_USERNAME", "SITE_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    return folder


def test_context_normalizes_and_masks_secrets(monkeypatch):
    cfg = Context({**CONTEXT, "totp": " ", "site_url": "localhost:8042/"})
    assert cfg.site_url == "http://localhost:8042" and cfg.totp is None and cfg.absent is None
    assert "s3cret-pass" not in repr(cfg) and MASK in repr(cfg) and "catherine@cabinet.fr" in repr(cfg)
    assert cfg.scrub({"error": ["tapé s3cret-pass", 3]}) == {"error": [f"tapé {MASK}", 3]}
    with pytest.raises(AttributeError):
        cfg.password = "autre"
    monkeypatch.setenv("SITE_USERNAME", "devin@test")
    assert Context.from_env().username == "devin@test"


def test_templates_load():
    web = loader.load_tool(ROOT / "tools" / "_template")
    assert web.name == "nom_du_tool" and web.kind == "web"
    assert web.describe()["params"]["required"] == ["reference"] and web.describe()["skill"] and web.contract["screens"]
    bureau = loader.load_tool(ROOT / "tools" / "_template_desktop")
    assert bureau.name == "nom_du_tool_desktop" and bureau.kind == "desktop" and bureau.describe()["kind"] == "desktop"


def test_server_uses_the_context_of_each_call(fake_tool):
    client = TestClient(server.build_app(fake_tool))
    assert client.get("/health").json() == {"ok": True, "tool": "faux_tool", "sha": "abc123"}
    described = client.get("/describe").json()
    assert described["name"] == "faux_tool" and described["skill"] == "# Skill de test\n"
    assert set(described["params"]["properties"]) == {"reference", "amount"}
    assert client.post("/precheck", json={"context": CONTEXT}).json()["user"] == "catherine@cabinet.fr"
    assert client.post("/run", json={"params": {"reference": "F-1"}, "context": CONTEXT}).json() == {
        "status": "draft_saved", "reference": "F-1", "site": "https://compta.example.com"}


def test_server_falls_back_to_env_locally(fake_tool, monkeypatch):
    monkeypatch.setenv("SITE_URL", "localhost:8042")
    client = TestClient(server.build_app(fake_tool))
    assert client.post("/run", json={"params": {"reference": "F-1"}}).json()["site"] == "http://localhost:8042"


def test_server_only_answers_smo_when_a_token_is_set(fake_tool, monkeypatch):
    monkeypatch.setenv("SMO_SERVER_TOKEN", "x" * 24)
    client = TestClient(server.build_app(fake_tool))
    assert client.get("/health").status_code == 200                       # /health reste ouvert
    assert client.get("/describe").status_code == 401
    assert client.post("/run", json={"params": {"reference": "A"}}).status_code == 401
    ok = client.get("/describe", headers={"X-SMO-Token": "x" * 24})
    assert ok.status_code == 200 and ok.json()["sha"] == "abc123"


def test_failures_become_results_without_secrets(fake_tool):
    client = TestClient(server.build_app(fake_tool))
    invalid = client.post("/run", json={"params": {}, "context": CONTEXT}).json()
    assert invalid["status"] == "error" and "paramètres invalides" in invalid["error"]
    crashed = client.post("/run", json={"params": {"reference": "F-1", "amount": -1}, "context": CONTEXT}).json()
    assert crashed == {"ok": False, "status": "error", "error": f"RuntimeError: montant négatif (connecté avec {MASK})"}


def test_a_failure_names_the_step_where_it_happened():
    from h_tools.steps import step

    def fill(_page):
        with step("ouverture de la facture"):
            with step("saisie du fournisseur"):
                raise TimeoutError("Fournisseur introuvable")
    assert loader.guarded(fill, None) == {"ok": False, "status": "error", "step": "saisie du fournisseur",
                                          "error": "TimeoutError: Fournisseur introuvable"}


def test_the_browser_looks_like_a_french_user():
    class Browser:
        version = "131.0.6778.33"

        def new_context(self, **kw):
            self.kw = kw
            return type("C", (), {"set_default_timeout": lambda s, ms: None,
                                  "set_default_navigation_timeout": lambda s, ms: None})()
    browser = Browser()
    loader.browser_context(browser)
    assert browser.kw["locale"] == "fr-FR" and browser.kw["timezone_id"] == "Europe/Paris"
    assert "Headless" not in browser.kw["user_agent"] and "Chrome/131.0.6778.33" in browser.kw["user_agent"]


def test_cli(fake_tool, monkeypatch, capsys):
    monkeypatch.setenv("SITE_PASSWORD", "s3cret-pass")
    assert cli.main([str(fake_tool), "run", '{"reference": "F-2"}']) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "draft_saved"
    assert cli.main([str(fake_tool), "run", '{"reference": "F-2", "amount": -1}']) == 1
    out = capsys.readouterr().out
    assert "s3cret-pass" not in out and json.loads(out)["status"] == "error"
    assert cli.main([str(fake_tool), "run", "pas du json"]) == 1


STATE = """[state 'Qonta'] app=Qonta pid=2457 win=67113502 controls=3 texts=1 coords=0-1000 over the screen
  12 text field "Référence fournisseur:" value='F-1' @424,593-486,625
  13 push button "Enregistrer le brouillon" @500,700-600,730
     Brouillon enregistré
  14 combo box "Catégorie" value='' @10,10-20,20
"""


def test_desk_reads_controls_and_acts_by_label(monkeypatch):
    calls = []

    def fake_cua(*args, timeout_s=60):
        calls.append(args)
        return STATE if args[0] == "state" else "confirmed"

    monkeypatch.setattr(desk, "cua", fake_cua)
    assert [(c.n, c.role, c.label, c.value) for c in desk.parse_state(STATE)] == [
        (12, "text field", "Référence fournisseur:", "F-1"), (13, "push button", "Enregistrer le brouillon", None),
        (14, "combo box", "Catégorie", "")]
    desk.set_value("Qonta", "Référence fournisseur", "F-9")
    desk.click("Qonta", "Enregistrer le brouillon", role="push button")
    assert calls[1] == ("set", "12", "F-9") and calls[3] == ("click", "13")
    with pytest.raises(desk.DeskError):
        desk.click("Qonta", "Valider")
    contract = {"screens": [{"name": "Saisie", "window": "Qonta",
                             "anchors": [{"label": "Catégorie"}, {"role": "push button", "label": "Valider"}]}]}
    assert desk.check_contract(contract) == {"ok": False, "checked": 2, "missing": [
        {"screen": "Saisie", "anchor": {"role": "push button", "label": "Valider"}}]}


def test_desktop_bundle_holds_what_the_agent_runs():
    files = announce.bundle("_template_desktop", "abc123")
    assert {"run.sh", "h_tools/cli.py", "h_tools/desk.py", "tool/tool.py", "tool/ui_contract.json",
            "tool/skill.md"} <= set(files)
    assert files["tool/VERSION"] == "abc123\n" and "tool/test_tool.py" not in files
    assert not any(name.startswith("h_tools/") and name.endswith(("server.py", "ui.py")) for name in files)


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
