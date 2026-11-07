"""Le conteneur d'un tool (un service Railway par tool) : il charge tool/ et l'expose en HTTP au watcher SMO.

    GET  /health     vivant ? avec le commit déployé (sha)
    GET  /describe   nom, description, schéma des paramètres, Skill : ce que SMO déclare dans l'agent H
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.
    POST /run        la saisie déterministe, paramètres en JSON

Pas de domaine public : seul le watcher, dans le même projet Railway, le joint (http://tool-<nom>.railway.internal:8080).

    TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080    # en local
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Body, FastAPI

from .config import Cfg
from .loader import load_tool


def build_app(folder: Path) -> FastAPI:
    tool, cfg = load_tool(folder), Cfg()
    version = folder / "VERSION"   # écrit par scripts/deploy_tool.sh : le commit déployé
    sha = version.read_text().strip() if version.exists() else "local"
    app = FastAPI(title=f"tool {tool.name}")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "tool": tool.name, "sha": sha}

    @app.get("/describe")
    def describe() -> dict:
        return {**tool.describe(), "sha": sha}

    @app.post("/precheck")
    def precheck() -> dict:
        return tool.precheck(cfg)

    @app.post("/run")
    def run(params: dict = Body(default_factory=dict)) -> dict:
        return tool.run(cfg, **params)

    return app


def create_app() -> FastAPI:
    return build_app(Path(os.environ.get("TOOL_DIR", "tool")))
