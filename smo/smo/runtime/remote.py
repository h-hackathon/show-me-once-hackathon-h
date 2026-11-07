"""Les tools déployés par h-tools : un service Railway par tool, joint sur le réseau privé du projet.

    GET  /describe   nom, description, schéma des paramètres, Skill, commit déployé (sha)
    POST /precheck   l'interface a-t-elle changé ? Ne modifie rien.
    POST /run        la saisie déterministe, paramètres en JSON

Adresse : http://tool-<nom>.railway.internal:8080 (« _ » remplacés par « - »), modifiable par SMO_TOOL_URL.
Seul un SMO dans le même projet Railway les joint ; en local, les tools se chargent depuis un clone d'h-tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_URL = "http://tool-{name}.railway.internal:8080"


def tool_url(template: str | None, name: str) -> str:
    return (template or DEFAULT_URL).format(name=name.replace("_", "-")).rstrip("/")


@dataclass(frozen=True)
class RemoteTool:
    name: str
    description: str
    schema: dict
    skill: str | None
    sha: str | None
    base_url: str
    kind: str = "web"

    @classmethod
    def fetch(cls, name: str, template: str | None = None, transport: httpx.BaseTransport | None = None,
              timeout_s: float = 10) -> RemoteTool | None:
        """Le tool tel qu'il est déployé, ou None s'il ne répond pas (pas encore déployé, ou SMO hors du projet)."""
        base = tool_url(template, name)
        try:
            with httpx.Client(timeout=timeout_s, transport=transport) as http:
                r = http.get(f"{base}/describe")
                r.raise_for_status()
                info = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        return cls(name=info.get("name", name), description=info.get("description", ""),
                   schema=info.get("params") or {"type": "object", "properties": {}}, skill=info.get("skill"),
                   sha=info.get("sha"), base_url=base)

    def _post(self, path: str, body: dict, timeout_s: float) -> dict:
        try:
            with httpx.Client(timeout=timeout_s) as http:
                r = http.post(f"{self.base_url}{path}", json=body)
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPError, ValueError) as err:   # comme un tool local : l'erreur devient un résultat
            return {"ok": False, "status": "error", "error": f"tool {self.name} injoignable : {err}"}

    def precheck(self, cfg) -> dict:
        return self._post("/precheck", {}, timeout_s=120)

    def run(self, cfg, **values: Any) -> dict:
        return self._post("/run", values, timeout_s=300)
