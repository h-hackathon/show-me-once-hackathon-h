"""Charger un tool (tools/<nom>/tool.py) et l'exécuter : dans un navigateur neuf (web) ou sur le bureau (desktop)."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .config import Context


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: type[BaseModel]
    module: ModuleType
    path: Path
    kind: str = "web"   # web : precheck(page, cfg) / run(page, params, cfg) ; desktop : sans page, lancé par l'agent

    @property
    def contract(self) -> dict:
        from .ui import contract_of   # Playwright n'est pas installé sur le poste d'un tool de bureau
        return getattr(self.module, "CONTRACT", None) or contract_of(str(self.path / "tool.py"))

    @property
    def skill(self) -> str | None:
        """La Skill de l'agent pour la reprise à l'écran, poussée dans H par SMO à chaque mise à jour."""
        path = self.path / "skill.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def describe(self) -> dict:
        """Ce que SMO déclare dans l'agent H : precheck_<nom> et run_<nom>, avec ce schéma de paramètres."""
        return {"name": self.name, "description": self.description, "kind": self.kind,
                "params": input_schema(self.params), "skill": self.skill}

    def precheck(self, cfg: Context) -> dict:
        if self.kind == "desktop":
            return cfg.scrub(guarded(lambda _: self.module.precheck(cfg), None))
        return cfg.scrub(with_page(lambda page: self.module.precheck(page, cfg)))

    def run(self, cfg: Context, **values: Any) -> dict:
        try:
            params = self.params(**values)
        except ValidationError as err:
            return cfg.scrub({"ok": False, "status": "error", "error": f"paramètres invalides : {err}"})
        if self.kind == "desktop":
            return cfg.scrub(guarded(lambda _: self.module.run(params, cfg), None))
        return cfg.scrub(with_page(lambda page: self.module.run(page, params, cfg)))


LOCALE, TIMEZONE = "fr-FR", "Europe/Paris"
VIEWPORT = {"width": 1366, "height": 768}
ACTION_TIMEOUT_MS = 10_000      # une action (clic, saisie, attente d'un élément)
NAVIGATION_TIMEOUT_MS = 30_000  # un chargement de page


def browser_context(browser):
    """Le navigateur d'un utilisateur français ordinaire, comme celui de l'agent H : langue, fuseau, taille d'écran,
    et l'agent utilisateur de ce Chrome sans la mention « Headless ». Rien de plus : pas de contournement d'anti-bot
    (si un site bloque le tool, l'erreur rend la main à l'agent H, à l'écran)."""
    agent = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"
    context = browser.new_context(locale=LOCALE, timezone_id=TIMEZONE, viewport=VIEWPORT, user_agent=agent,
                                  extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    context.set_default_timeout(ACTION_TIMEOUT_MS)
    context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    return context


def with_page(fn: Callable) -> dict:
    """Un navigateur neuf par appel (l'API sync de Playwright ne se partage pas entre threads)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            return guarded(fn, browser_context(browser).new_page())
        finally:
            browser.close()


def guarded(fn: Callable, page) -> dict:
    """Un tool qui casse ne doit jamais faire planter la session H : l'erreur devient un résultat, avec l'étape où
    il a cassé (ui.step) pour que l'agent et la réparation sachent où regarder."""
    from .steps import StepError
    try:
        return fn(page)
    except StepError as err:
        return {"ok": False, "status": "error", "step": err.step, "error": f"{type(err.cause).__name__}: {err.cause}"}
    except Exception as err:
        return {"ok": False, "status": "error", "error": f"{type(err).__name__}: {err}"}


def load_tool(folder: Path) -> Tool:
    spec = importlib.util.spec_from_file_location(f"h_tools_loaded.{folder.name}", folder / "tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return Tool(name=module.NAME, description=module.DESCRIPTION, params=module.Params, module=module, path=folder,
                kind=getattr(module, "KIND", "web"))


def input_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema
