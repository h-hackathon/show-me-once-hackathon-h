"""Les tools écrits par Devin dans h-tools, exposés à l'agent H.

Tool web : deux custom tools, precheck_<nom> (l'interface a-t-elle changé ?) et run_<nom>, exécutés par le programme
qui suit la session (le worker SMO). Le tool tourne sur Railway (remote.py), ou depuis un clone local d'h-tools
(H_TOOLS_DIR). À chaque appel, SMO lit le vault H (le contexte) et passe l'adresse du logiciel et les identifiants
au tool ; le résultat renvoyé à l'agent n'en contient aucun (scrub).

Tool de bureau : pas de custom tool. Ses fichiers sont posés dans la Skill de l'agent bureau, qui le lance depuis son
shell, dans son propre environnement (desktop_files).
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

from ..clients.vault import Secrets
from . import builtins
from . import remote
from .remote import DesktopTool, RemoteTool
from .ui import contract_of


# Le contexte d'un appel : (valeurs envoyées au tool, secrets à effacer du résultat), lu au moment de l'appel.
ContextProvider = Callable[[], tuple[dict, Secrets]]


def no_context() -> tuple[dict, Secrets]:
    return {}, Secrets({})


def for_site(s, site_url: str | None) -> ContextProvider:
    """Le contexte des appels de tools sur ce logiciel : son adresse et son élément du vault H, relu à chaque appel
    (mot de passe changé, code TOTP du moment). Rien n'est gardé entre deux appels."""
    def provide() -> tuple[dict, Secrets]:
        if not (s.hai_api_key and site_url):
            return {"site_url": site_url}, Secrets({})
        from ..clients import h, vault
        return vault.tool_context(h.client(s.hai_api_key), site_url, s.h_vault_id)
    return provide


@dataclass(frozen=True)
class CompiledTool:
    name: str
    description: str
    params: type[BaseModel]
    module: ModuleType
    path: Path
    kind: str = "web"   # web : precheck(page, cfg) / run(page, params, cfg) ; desktop : lancé par l'agent

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

    def precheck(self, context: dict) -> dict:
        cfg = tool_context(context)
        if self.kind == "desktop":
            return guarded(lambda: self.module.precheck(cfg))
        return with_page(lambda page: self.module.precheck(page, cfg))

    def run(self, context: dict, **values: Any) -> dict:
        params, cfg = self.params(**values), tool_context(context)
        if self.kind == "desktop":
            return guarded(lambda: self.module.run(params, cfg))
        return with_page(lambda page: self.module.run(page, params, cfg))


class _Context(dict):
    """Repli si le clone d'h-tools n'a pas h_tools.config.Context : champ absent → None."""

    def __getattr__(self, name: str):
        return self.get(name)


def tool_context(values: dict):
    """Le contexte tel que l'attend un tool d'h-tools (cfg.site_url, cfg.username…)."""
    try:
        from h_tools.config import Context
    except ImportError:
        return _Context(values)
    return Context(values)


def guarded(fn: Callable) -> dict:
    try:
        return fn()
    except Exception as err:   # un tool qui casse ne doit jamais faire planter la session H
        return {"ok": False, "status": "error", "error": f"{type(err).__name__}: {err}"}


def with_page(fn: Callable) -> dict:
    """Un navigateur neuf par appel (l'API sync de Playwright ne se partage pas entre threads). Tool d'h-tools : le
    navigateur de son runtime (fr-FR, délais, étape en cause dans l'erreur), le même que sur Railway."""
    try:
        from h_tools.loader import with_page as runtime_with_page   # le clone est dans sys.path (load_tool)
    except ImportError:
        runtime_with_page = None
    if runtime_with_page is not None:
        return runtime_with_page(fn)
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
    """Le tool `name`, s'il existe : clone local d'h-tools d'abord, sinon ce qu'h-tools a déployé (service Railway
    appelé avec le mot de passe commun, ou fichiers d'un tool de bureau)."""
    folder = s.tools_dir / name
    if (folder / "tool.py").exists():
        return load_tool(folder)
    if kind_of(name) == "desktop":
        return DesktopTool.load(s, name)
    url = remote.tool_url(s, name)
    return RemoteTool.fetch(name, url, s.server_token) if url else None


DESKTOP_RUNTIME = ("__init__.py", "config.py", "loader.py", "desk.py", "cli.py")


def desktop_files(tool) -> dict[str, str]:
    """Les fichiers d'un tool de bureau, tels que l'agent les lance (./run.sh run '{...}') : ceux annoncés par h-tools,
    ou, depuis un clone local, le dossier du tool et le runtime sans Playwright (comme scripts/announce.py)."""
    if isinstance(tool, DesktopTool):
        return tool.files
    repo = tool.path.resolve().parent.parent
    files = {"run.sh": (repo / "scripts" / "run.sh").read_text(encoding="utf-8")}
    files |= {f"h_tools/{m}": (repo / "h_tools" / m).read_text(encoding="utf-8") for m in DESKTOP_RUNTIME}
    files |= {f"tool/{p.relative_to(tool.path).as_posix()}": p.read_text(encoding="utf-8")
              for p in sorted(tool.path.rglob("*"))
              if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("test_")}
    return files


def input_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def call_tool(method: str, tool, context: ContextProvider, **values: Any) -> dict:
    """Un appel de l'agent : le vault est lu maintenant, les secrets sont effacés du résultat avant qu'il reparte."""
    try:
        sent, secrets = context()
    except Exception as err:
        return {"ok": False, "status": "error", "error": f"vault H illisible ({type(err).__name__}) : fais-le à l'écran"}
    result = tool.precheck(sent) if method == "precheck" else tool.run(sent, **values)
    return secrets.scrub(result)


def h_tools(compiled: dict, cfg, on_drift: Callable[[str, str], None],
            context: ContextProvider = no_context) -> list[Tool]:
    """compiled : {nom: CompiledTool (local) ou RemoteTool (déployé)} ; tous ont name, description, schema.
    Les tools de bureau n'en font pas partie : l'agent les lance depuis son shell."""
    out: list[Tool] = []
    for t in compiled.values():
        if t.kind == "desktop":
            continue
        out.append(Tool(
            name=f"precheck_{t.name}",
            description=f"Vérifie, sans rien modifier, que l'interface utilisée par « {t.description} » n'a pas changé. "
                        "Renvoie ok (true/false) et la liste des éléments manquants.",
            input_schema={"type": "object", "properties": {}}, fn=partial(call_tool, "precheck", t, context)))
        out.append(Tool(
            name=f"run_{t.name}",
            description=f"{t.description} Fait la tâche de façon automatique et déterministe, sans jamais finaliser. "
                        "Renvoie status = draft_saved (enregistré, pas finalisé) | duplicate (déjà fait) | "
                        "flagged (une règle bloque, rien n'est enregistré) | error.",
            input_schema=t.schema, fn=partial(call_tool, "run", t, context)))
    return out + builtins.tools(on_drift)


def definitions(tools: list[Tool]) -> list[dict]:
    """Ce que l'agent custom déclare dans H (nom, description, schéma) ; l'exécution reste chez nous."""
    return [t.definition() for t in tools]
