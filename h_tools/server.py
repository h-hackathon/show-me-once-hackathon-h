"""Le conteneur d'un tool (un service Railway par tool) : il charge tool/ et l'expose en HTTP au serveur SMO.

    GET  /health     vivant ? avec le commit déployé (sha) ; ouvert
    GET  /describe   nom, description, schéma des paramètres, Skill : ce que SMO déclare dans l'agent H
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.
    POST /run        la saisie déterministe, paramètres en JSON

Le tool a une adresse publique (SMO tourne dans un autre projet Railway). Sauf /health, chaque appel doit porter
le mot de passe commun avec SMO dans l'en-tête X-SMO-Token (variable SMO_SERVER_TOKEN) ; sans elle, en local, tout
est ouvert.

    TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080    # en local
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException

from .config import Cfg
from .loader import load_tool


def check_token(x_smo_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SMO_SERVER_TOKEN", "").strip()
    if expected and not hmac.compare_digest((x_smo_token or "").encode(), expected.encode()):
        raise HTTPException(401, "X-SMO-Token manquant ou invalide")


def build_app(folder: Path) -> FastAPI:
    tool, cfg = load_tool(folder), Cfg()
    version = folder / "VERSION"   # écrit par scripts/deploy_tool.sh : le commit déployé
    sha = version.read_text().strip() if version.exists() else "local"
    app = FastAPI(title=f"tool {tool.name}")
    protected = [Depends(check_token)]

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "tool": tool.name, "sha": sha}

    @app.get("/describe", dependencies=protected)
    def describe() -> dict:
        return {**tool.describe(), "sha": sha}

    @app.post("/precheck", dependencies=protected)
    def precheck() -> dict:
        return tool.precheck(cfg)

    @app.post("/run", dependencies=protected)
    def run(params: dict = Body(default_factory=dict)) -> dict:
        return tool.run(cfg, **params)

    return app


def create_app() -> FastAPI:
    return build_app(Path(os.environ.get("TOOL_DIR", "tool")))
