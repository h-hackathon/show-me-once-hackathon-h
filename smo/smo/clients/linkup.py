"""Linkup : recherche web sourcée (vérifier les règles dites par l'humain, chercher la doc publique du logiciel).

Linkup ne voit pas les pages derrière une connexion : il ne sert pas à explorer le logiciel lui-même.
"""
from __future__ import annotations

import json

import httpx


API = "https://api.linkup.so/v1"


def search(q: str, api_key: str, *, depth: str = "standard", output_type: str = "sourcedAnswer",
           schema: dict | None = None, include_domains: list[str] | None = None, timeout_s: float = 90) -> dict:
    body: dict = {"q": q, "depth": depth, "outputType": output_type}
    if schema is not None:
        body["outputType"] = "structured"
        body["structuredOutputSchema"] = json.dumps(schema)
        body["includeSources"] = True          # sinon la réponse structurée n'a aucune source ; elle devient {data, sources}
    if include_domains:
        body["includeDomains"] = include_domains
    r = httpx.post(f"{API}/search", json=body, timeout=timeout_s,
                   headers={"Authorization": f"Bearer {api_key}"})
    r.raise_for_status()
    return r.json()


def fetch(url: str, api_key: str, render_js: bool = False, timeout_s: float = 60) -> dict:
    """Une page publique → markdown."""
    r = httpx.post(f"{API}/fetch", json={"url": url, "renderJs": render_js}, timeout=timeout_s,
                   headers={"Authorization": f"Bearer {api_key}"})
    r.raise_for_status()
    return r.json()


def source_urls(response: dict) -> list[str]:
    """Les URL citées, quel que soit le format de sortie."""
    items = response.get("sources") or response.get("results") or []
    return [s["url"] for s in items if isinstance(s, dict) and s.get("url")]
