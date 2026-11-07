"""API technique du site compta (contrat : docs/CONTRAT_SITE.md).

Sert au contrôle : on lit ce qui est réellement enregistré, on ne croit jamais l'agent sur parole.
"""
from __future__ import annotations

import httpx


class Site:
    def __init__(self, url: str, admin_token: str | None = None):
        headers = {"X-Admin-Token": admin_token} if admin_token else {}
        self.http = httpx.Client(base_url=url, headers=headers, timeout=30)

    def health(self) -> dict:
        r = self.http.get("/api/health")
        r.raise_for_status()
        return r.json()

    def invoices(self, reference: str | None = None) -> list[dict]:
        r = self.http.get("/api/invoices", params={"reference": reference} if reference else None)
        r.raise_for_status()
        return r.json()

    def reset(self) -> None:
        self.http.post("/api/admin/reset").raise_for_status()

    def ui_version(self) -> str:
        r = self.http.get("/api/admin/ui-version")
        r.raise_for_status()
        return r.json()["version"]

    def set_ui_version(self, version: str) -> None:
        self.http.post("/api/admin/ui-version", json={"version": version}).raise_for_status()
