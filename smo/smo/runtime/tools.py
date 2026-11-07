"""Les tools écrits par Devin dans h-tools, exposés à l'agent H comme custom tools.

Côté H, un custom tool est exécuté par le programme qui suit la session : ici le worker SMO.
Chaque tool donne deux custom tools : precheck_<nom> (l'interface a-t-elle changé ?) et run_<nom>.
Où on le trouve (find) : dans un clone local d'h-tools (H_TOOLS_DIR, obligatoire pour les tools de bureau, qui
tournent sur le Mac), sinon déployé par h-tools sur Railway (remote.py, réseau privé du projet).
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from hai_agents import Tool
from pydantic import BaseModel

from . import builtins
from . import remote
from .remote import RemoteTool
from .ui import contract_of


@dataclass(frozen=True)
class CompiledTool:
    name: str
    description: str
    params: type[BaseModel]
    module: ModuleType
    path: Path
    kind: str = "web"   # web : precheck(page, cfg) / run(page, params, cfg) ; desktop : sans page (accessibilité macOS)

    @property
    def contract(self) -> dict:
        return getattr(self.module, "CONTRACT", None) or contract_of(str(self.path / "tool.py"))

    @property
    def schema(self) -> dict:
        return input_schema(self.params)

    @property
    def skill(self) -> str | None:
        """La Skill du repo d'h-tools (tools/<nom>/skill.md), que Devin fait évoluer."""
        path = self.path / "skill.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def precheck(self, cfg) -> dict:
        if self.kind == "desktop":
            return guarded(lambda: self.module.precheck(cfg))
        return with_page(lambda page: self.module.precheck(page, cfg))

    def run(self, cfg, **values: Any) -> dict:
        params = self.params(**values)
        if self.kind == "desktop":
            return guarded(lambda: self.module.run(params, cfg))
        return with_page(lambda page: self.module.run(page, params, cfg))


def guarded(fn: Callable) -> dict:
    try:
        return fn()
    except Exception as err:   # un tool qui casse ne doit jamais faire planter la session H
        return {"ok": False, "status": "error", "error": f"{type(err).__name__}: {err}"}


def with_page(fn: Callable) -> dict:
    """Un navigateur neuf par appel (l'API sync de Playwright ne se partage pas entre threads)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            return fn(browser.new_page())
        except Exception as err:   # un tool qui casse ne doit jamais faire planter la session H
            return {"ok": False, "status": "error", "error": f"{type(err).__name__}: {err}"}
        finally:
            browser.close()


def load_tool(folder: Path) -> CompiledTool:
    repo = str(folder.resolve().parent.parent)   # les tools d'h-tools importent h_tools.ui : la racine du clone
    if repo not in sys.path:
        sys.path.insert(0, repo)
    spec = importlib.util.spec_from_file_location(f"smo_tools.{folder.name}", folder / "tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return CompiledTool(name=module.NAME, description=module.DESCRIPTION, params=module.Params,
                        module=module, path=folder, kind=getattr(module, "KIND", "web"))


def load_tools(tools_dir: Path) -> dict[str, CompiledTool]:
    """Tous les tools prêts (on ignore _template et les dossiers sans tool.py)."""
    folders = [f for f in sorted(tools_dir.iterdir()) if f.is_dir() and not f.name.startswith(("_", "."))
               and (f / "tool.py").exists()] if tools_dir.exists() else []
    return {t.name: t for t in map(load_tool, folders)}


def kind_of(name: str) -> str:
    return "desktop" if name.endswith("_desktop") else "web"


def find(s, name: str):
    """Le tool `name`, s'il existe : clone local d'h-tools d'abord, sinon le service déployé par h-tools
    (adresse annoncée à SMO, appelée avec le mot de passe commun)."""
    folder = s.tools_dir / name
    if (folder / "tool.py").exists():
        return load_tool(folder)
    url = remote.tool_url(s, name)
    return RemoteTool.fetch(name, url, s.server_token) if url else None


def input_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def _precheck(tool, cfg) -> dict:
    return tool.precheck(cfg)


def _run(tool, cfg, **values: Any) -> dict:
    return tool.run(cfg, **values)


def h_tools(compiled: dict, cfg, on_drift: Callable[[str, str], None]) -> list[Tool]:
    """compiled : {nom: CompiledTool (local) ou RemoteTool (déployé)} ; tous ont name, description, schema."""
    out: list[Tool] = []
    for t in compiled.values():
        out.append(Tool(
            name=f"precheck_{t.name}",
            description=f"Vérifie, sans rien modifier, que l'interface utilisée par « {t.description} » n'a pas changé. "
                        "Renvoie ok (true/false) et la liste des éléments manquants.",
            input_schema={"type": "object", "properties": {}}, fn=partial(_precheck, t, cfg)))
        out.append(Tool(
            name=f"run_{t.name}",
            description=f"{t.description} Saisie automatique et déterministe, qui s'arrête en brouillon. "
                        "Renvoie status = draft_saved | duplicate | flagged | error.",
            input_schema=t.schema, fn=partial(_run, t, cfg)))
    return out + builtins.tools(cfg, on_drift)


def definitions(tools: list[Tool]) -> list[dict]:
    """Ce que l'agent custom déclare dans H (nom, description, schéma) ; l'exécution reste chez nous."""
    return [t.definition() for t in tools]
