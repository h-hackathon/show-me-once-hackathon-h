"""Le conteneur d'un tool (un service Railway par tool) : il charge tool/ et l'expose en HTTP au serveur SMO.

    GET  /health     vivant ? avec le commit déployé (sha) ; ouvert
    GET  /describe   nom, description, schéma des paramètres, Skill : ce que SMO déclare dans l'agent H
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.          {"context": {...}}
    POST /run        la saisie déterministe                               {"params": {...}, "context": {...}}

Le contexte (adresse du logiciel, identifiants) vient du vault H, lu par SMO à chaque appel : le tool ne garde rien.
Sans contexte (en local), il est lu dans SITE_URL, SITE_USERNAME… (h_tools.config).

Le tool a une adresse publique (SMO tourne dans un autre projet Railway). Sauf /health, chaque appel doit porter
le mot de passe commun avec SMO dans l'en-tête X-SMO-Token (variable SMO_SERVER_TOKEN). Sans elle, tout est ouvert en
local, mais le conteneur (SMO_AUTH_REQUIRED=1, posé par le Dockerfile) refuse tout appel : un tool déployé n'est
jamais public par erreur. Les identifiants ne passent que dans le corps (HTTPS), jamais dans l'adresse ni dans les
journaux.

    TOOL_DIR=tools/<nom> uv run uvicorn --factory h_tools.server:create_app --port 8080    # en local
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException

from .config import Context
from .loader import load_tool


def check_token(x_smo_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SMO_SERVER_TOKEN", "").strip()
    if not expected:
        if os.environ.get("SMO_AUTH_REQUIRED"):
            raise HTTPException(503, "SMO_SERVER_TOKEN absent : le tool refuse tout appel")
        return
    if not hmac.compare_digest((x_smo_token or "").encode(), expected.encode()):
        raise HTTPException(401, "X-SMO-Token manquant ou invalide")


def context_of(body: dict) -> Context:
    """Le contexte envoyé par SMO ; en local, celui de l'environnement."""
    return Context(body["context"]) if isinstance(body.get("context"), dict) else Context.from_env()


def build_app(folder: Path) -> FastAPI:
    tool = load_tool(folder)
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
    def precheck(body: dict = Body(default_factory=dict)) -> dict:
        return tool.precheck(context_of(body))

    @app.post("/run", dependencies=protected)
    def run(body: dict = Body(default_factory=dict)) -> dict:
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        return tool.run(context_of(body), **params)

    return app


def create_app() -> FastAPI:
    return build_app(Path(os.environ.get("TOOL_DIR", "tool")))
