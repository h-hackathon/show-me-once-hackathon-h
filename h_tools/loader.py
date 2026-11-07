"""Charger un tool (tools/<nom>/tool.py) et l'exécuter dans un navigateur neuf."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .ui import contract_of


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: type[BaseModel]
    module: ModuleType
    path: Path

    @property
    def contract(self) -> dict:
        return getattr(self.module, "CONTRACT", None) or contract_of(str(self.path / "tool.py"))

    @property
    def skill(self) -> str | None:
        """La Skill de l'agent pour la reprise à l'écran, poussée dans H par SMO à chaque mise à jour."""
        path = self.path / "skill.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def describe(self) -> dict:
        """Ce que SMO déclare dans l'agent H : precheck_<nom> et run_<nom>, avec ce schéma de paramètres."""
        return {"name": self.name, "description": self.description, "params": input_schema(self.params),
                "skill": self.skill}

    def precheck(self, cfg) -> dict:
        return with_page(lambda page: self.module.precheck(page, cfg))

    def run(self, cfg, **values: Any) -> dict:
        try:
            params = self.params(**values)
        except ValidationError as err:
            return {"ok": False, "status": "error", "error": f"paramètres invalides : {err}"}
        return with_page(lambda page: self.module.run(page, params, cfg))


def with_page(fn: Callable) -> dict:
    """Un navigateur neuf par appel (l'API sync de Playwright ne se partage pas entre threads)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            return guarded(fn, browser.new_page())
        finally:
            browser.close()


def guarded(fn: Callable, page) -> dict:
    """Un tool qui casse ne doit jamais faire planter la session H : l'erreur devient un résultat."""
    try:
        return fn(page)
    except Exception as err:
        return {"ok": False, "status": "error", "error": f"{type(err).__name__}: {err}"}


def load_tool(folder: Path) -> Tool:
    spec = importlib.util.spec_from_file_location(f"h_tools_loaded.{folder.name}", folder / "tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return Tool(name=module.NAME, description=module.DESCRIPTION, params=module.Params, module=module, path=folder)


def input_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema
