"""Les tools déployés par h-tools.

Tool web : un service Railway par tool, dans le projet Railway d'h-tools.

    GET  /describe   nom, description, schéma des paramètres, Skill, commit déployé (sha)
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.          {"context": {...}}
    POST /run        la saisie déterministe                               {"params": {...}, "context": {...}}

SMO et h-tools sont dans deux projets Railway : SMO joint chaque tool par son adresse publique (HTTPS), avec le mot
de passe commun dans l'en-tête X-SMO-Token (SMO_SERVER_TOKEN). L'adresse, h-tools l'annonce à chaque déploiement
(POST /hooks/tool-deployed) ; SMO la garde dans runs/_tools.json. SMO_TOOL_URL (gabarit avec {name}) sert de repli.
Le contexte (adresse du logiciel, identifiants lus dans le vault H au moment de l'appel) ne passe que dans le corps.

Tool de bureau : pas de Railway. h-tools envoie ses fichiers (le tool, son runtime, run.sh) ; SMO les garde dans
runs/_tools/<nom>.json et les pose dans la Skill de l'agent bureau, qui lance le tool depuis son shell.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def registry_path(s) -> Path:
    return s.runs_dir / "_tools.json"


def bundle_path(s, name: str) -> Path:
    return s.runs_dir / "_tools" / f"{name}.json"


def registered(s) -> dict:
    path = registry_path(s)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def register(s, name: str, url: str | None, sha: str | None, kind: str = "web",
             files: dict | None = None, describe: dict | None = None) -> None:
    """h-tools vient de déployer `name` : on retient son adresse (web) ou ses fichiers (bureau), sur le volume."""
    tools = registered(s)
    tools[name] = {"url": url.rstrip("/") if url else None, "sha": sha, "kind": kind,
                   "at": datetime.now().isoformat(timespec="seconds")}
    registry_path(s).parent.mkdir(parents=True, exist_ok=True)
    registry_path(s).write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")
    if kind == "desktop":
        path = bundle_path(s, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sha": sha, "files": files or {}, "describe": describe or {}}, ensure_ascii=False),
                        encoding="utf-8")


def tool_url(s, name: str) -> str | None:
    """L'adresse annoncée par h-tools, sinon le gabarit SMO_TOOL_URL, sinon None (tool inconnu)."""
    if (entry := registered(s).get(name)) and entry.get("url"):
        return entry["url"]
    return s.tool_url.format(name=name.replace("_", "-")).rstrip("/") if s.tool_url else None


@dataclass(frozen=True)
class RemoteTool:
    name: str
    description: str
    schema: dict
    skill: str | None
    sha: str | None
    base_url: str
    token: str | None = None
    kind: str = "web"

    @classmethod
    def fetch(cls, name: str, base_url: str, token: str | None = None,
              transport: httpx.BaseTransport | None = None, timeout_s: float = 10) -> RemoteTool | None:
        """Le tool tel qu'il est déployé, ou None s'il ne répond pas (pas encore en ligne, mauvais mot de passe)."""
        try:
            with httpx.Client(timeout=timeout_s, transport=transport, headers=_headers(token)) as http:
                r = http.get(f"{base_url}/describe")
                r.raise_for_status()
                info = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        return cls(name=info.get("name", name), description=info.get("description", ""),
                   schema=info.get("params") or {"type": "object", "properties": {}}, skill=info.get("skill"),
                   sha=info.get("sha"), base_url=base_url, token=token)

    def _post(self, path: str, body: dict, timeout_s: float) -> dict:
        try:
            with httpx.Client(timeout=timeout_s, headers=_headers(self.token)) as http:
                r = http.post(f"{self.base_url}{path}", json=body)
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPError, ValueError) as err:   # comme un tool local : l'erreur devient un résultat
            return {"ok": False, "status": "error", "error": f"tool {self.name} injoignable : {err}"}

    def precheck(self, context: dict) -> dict:
        return self._post("/precheck", {"context": context}, timeout_s=120)

    def run(self, context: dict, **values: Any) -> dict:
        return self._post("/run", {"params": values, "context": context}, timeout_s=300)


@dataclass(frozen=True)
class DesktopTool:
    """Un tool de bureau : des fichiers posés dans la Skill de l'agent, qu'il lance depuis son shell (./run.sh)."""
    name: str
    description: str
    schema: dict
    skill: str | None
    sha: str | None
    files: dict = field(default_factory=dict)
    kind: str = "desktop"

    @classmethod
    def load(cls, s, name: str) -> DesktopTool | None:
        path = bundle_path(s, name)
        if not path.exists():
            return None
        bundle = json.loads(path.read_text(encoding="utf-8"))
        files, info = bundle.get("files") or {}, bundle.get("describe") or {}
        return cls(name=name, description=info.get("description", ""),
                   schema=info.get("params") or {"type": "object", "properties": {}},
                   skill=info.get("skill") or files.get("tool/skill.md"), sha=bundle.get("sha"), files=files)


def _headers(token: str | None) -> dict:
    return {"X-SMO-Token": token} if token else {}
