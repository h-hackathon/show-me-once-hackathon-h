"""API technique du logiciel cible, s'il en a une (SITE_URL + SITE_ADMIN_TOKEN).

Elle sert à l'idempotence et aux tests : on relit ce qui est réellement enregistré. La saisie, elle, passe
toujours par l'interface, comme le ferait l'humain.
"""
from __future__ import annotations

from typing import Any

import httpx


class SiteAPI:
    def __init__(self, cfg, token_header: str = "X-Admin-Token"):
        headers = {token_header: cfg.site_admin_token} if cfg.site_admin_token else {}
        self.http = httpx.Client(base_url=cfg.site_url, headers=headers, timeout=30)

    def get(self, path: str, **params: Any) -> Any:
        r = self.http.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: Any = None) -> Any:
        r = self.http.post(path, json=json)
        r.raise_for_status()
        return r.json() if r.content else None
