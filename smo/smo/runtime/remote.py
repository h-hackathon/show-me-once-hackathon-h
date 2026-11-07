"""Les tools déployés par h-tools : un service Railway par tool, dans le projet Railway d'h-tools.

    GET  /describe   nom, description, schéma des paramètres, Skill, commit déployé (sha)
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.
    POST /run        la saisie déterministe, paramètres en JSON

SMO et h-tools sont dans deux projets Railway : SMO joint chaque tool par son adresse publique, avec le mot de passe
commun dans l'en-tête X-SMO-Token (SMO_SERVER_TOKEN). L'adresse, h-tools l'annonce à chaque déploiement
(POST /hooks/tool-deployed) ; SMO la garde dans runs/_tools.json. SMO_TOOL_URL (gabarit avec {name}) sert de repli.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def registry_path(s) -> Path:
    return s.runs_dir / "_tools.json"


def registered(s) -> dict:
    path = registry_path(s)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def register(s, name: str, url: str, sha: str | None) -> None:
    """h-tools vient de déployer `name` à cette adresse : on la retient (survit aux redémarrages, sur le volume)."""
    tools = registered(s)
    tools[name] = {"url": url.rstrip("/"), "sha": sha, "at": datetime.now().isoformat(timespec="seconds")}
    registry_path(s).parent.mkdir(parents=True, exist_ok=True)
    registry_path(s).write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")


def tool_url(s, name: str) -> str | None:
    """L'adresse annoncée par h-tools, sinon le gabarit SMO_TOOL_URL, sinon None (tool inconnu)."""
    if name in (tools := registered(s)):
        return tools[name]["url"]
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

    def precheck(self, cfg) -> dict:
        return self._post("/precheck", {}, timeout_s=120)

    def run(self, cfg, **values: Any) -> dict:
        return self._post("/run", values, timeout_s=300)


def _headers(token: str | None) -> dict:
    return {"X-SMO-Token": token} if token else {}
