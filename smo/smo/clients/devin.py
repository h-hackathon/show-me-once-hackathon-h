"""Devin (API v3) : lancer une session qui écrit le tool, suivre son statut, récupérer la PR.

Pas de webhook sortant côté Devin : on interroge le statut à intervalle régulier.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import httpx


API = "https://api.devin.ai/v3"
FINISHED_STATUS = {"exit", "error", "suspended"}
FINISHED_DETAIL = {"finished", "waiting_for_user"}


class Devin:
    def __init__(self, api_key: str, org_id: str):
        self.http = httpx.Client(base_url=f"{API}/organizations/{org_id}", timeout=60,
                                 headers={"Authorization": f"Bearer {api_key}"})

    def upload(self, path: Path) -> str | None:
        """Pièce jointe → URL utilisable dans attachment_urls. Format de réponse peu documenté : None si échec."""
        try:
            with path.open("rb") as fh:
                r = self.http.post("/attachments", files={"file": (path.name, fh)})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        return data if isinstance(data, str) else data.get("url") or data.get("attachment_url")

    def create_session(self, prompt: str, *, tags: list[str] = (), max_acu: int | None = None,
                       attachment_urls: list[str] = (), output_schema: dict | None = None,
                       secrets: dict[str, str] | None = None) -> dict:
        """secrets : secrets de cette session seulement (session_secrets de l'API v3), jamais dans le prompt ni
        dans les secrets de l'organisation ; Devin les a en variables d'environnement, le temps de la session."""
        body: dict = {"prompt": prompt}
        if secrets:
            body["session_secrets"] = [{"key": k, "value": v, "sensitive": True} for k, v in secrets.items() if v]
        if output_schema:                  # JSON Schema autonome (sans $ref) : Devin doit rendre ce JSON
            body["structured_output_schema"] = output_schema
            body["structured_output_required"] = True
        if tags:
            body["tags"] = list(tags)
        if max_acu:
            body["max_acu_limit"] = max_acu
        if attachment_urls:
            body["attachment_urls"] = list(attachment_urls)
        r = self.http.post("/sessions", json=body)
        if r.status_code in (400, 422) and "session_secrets" in body:   # champ refusé : la session part quand même,
            body.pop("session_secrets")                                  # Devin code sans se connecter au site
            r = self.http.post("/sessions", json=body)
        r.raise_for_status()
        return r.json()

    def get_session(self, devin_id: str) -> dict:
        r = self.http.get(f"/sessions/{devin_id}")
        r.raise_for_status()
        return r.json()

    def list_sessions(self, limit: int = 1) -> httpx.Response:
        return self.http.get("/sessions", params={"limit": limit})

    def whoami(self) -> httpx.Response:
        """Identité du token (service user ou token personnel) et son org ; ne demande aucune permission."""
        return self.http.get(f"{API}/self")

    def wait(self, devin_id: str, timeout_s: float = 2700, poll_s: float = 30,
             on_update: Callable[[dict], None] | None = None) -> dict:
        deadline = time.monotonic() + timeout_s
        while True:
            session = self.get_session(devin_id)
            if on_update:
                on_update(session)
            if is_finished(session):
                return session
            if time.monotonic() > deadline:
                raise TimeoutError(f"Devin {devin_id} pas fini en {timeout_s:.0f}s")
            time.sleep(poll_s)


def session_id(session: dict) -> str:
    return session.get("devin_id") or session.get("session_id") or session["id"]


def pr_url(session: dict) -> str | None:
    prs = session.get("pull_requests") or []
    return prs[-1].get("pr_url") if prs else None


def is_finished(session: dict) -> bool:
    return session.get("status") in FINISHED_STATUS or session.get("status_detail") in FINISHED_DETAIL
