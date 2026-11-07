"""Étape docs : Linkup cherche la documentation publique du logiciel pour la tâche, en parallèle de la capture.

Holo s'en sert pour écrire la Skill (vocabulaire du logiciel, procédure documentée), Devin pour le tool.
Linkup ne voit que le web public : pour un logiciel connu (Odoo, Pennylane, Sage) il trouve la doc officielle ;
pour un logiciel maison, seulement ses pages publiques (accueil, connexion, aide si elle est ouverte).
"""
from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse

import httpx

from ..clients import linkup
from ..config import Settings
from ..runs import Run
from . import target


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta = run.meta
    name = meta.software_name or (meta.software_url if target.is_desktop(meta) else urlparse(meta.software_url).netloc)
    query = f"Documentation de {name} : comment {meta.task.lower()}"
    found = linkup.search(query, s.linkup_api_key)
    pages = []
    if not target.is_desktop(meta) and meta.software_url.startswith("http"):
        try:
            page = linkup.fetch(meta.software_url, s.linkup_api_key)
            text = page.get("markdown") or page.get("content") or page.get("text") or ""
            pages.append({"url": meta.software_url, "text": text[:4000]})
        except httpx.HTTPError as err:
            log(f"page publique du logiciel illisible : {err}")
    run.write_json("docs.json", {"query": query, "answer": found.get("answer"),
                                 "sources": linkup.source_urls(found)[:5], "pages": pages})
    log(f"{len(linkup.source_urls(found))} sources · {len(pages)} page(s) du logiciel lue(s)")


def summary(run: Run, limit: int = 2500) -> str:
    """La documentation en quelques lignes, pour Holo et Devin ; vide s'il n'y en a pas."""
    if not run.has("docs.json"):
        return ""
    docs = run.read_json("docs.json")
    parts = []
    if docs.get("answer"):
        parts.append(f"Ce que dit la documentation : {docs['answer']}")
    if docs.get("sources"):
        parts.append("Sources : " + ", ".join(docs["sources"]))
    for page in docs.get("pages", []):
        if page.get("text"):
            parts.append(f"Page publique {page['url']} :\n{page['text'][:1200]}")
    return "\n".join(parts)[:limit]
