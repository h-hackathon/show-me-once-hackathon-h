"""Réglages d'un tool : ses variables d'environnement, lues en attributs (cfg.site_url → SITE_URL)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")   # en local ; sur Railway, ce sont les variables du service


def url(value: str) -> str:
    """« xxx.up.railway.app » → « https://xxx.up.railway.app » ; localhost sans schéma → http://."""
    value = value.rstrip("/")
    if not value or "://" in value:
        return value
    local = value.startswith(("localhost", "127.0.0.1"))
    return f"{'http' if local else 'https'}://{value}"


class Cfg:
    """Variable absente ou vide → None. Les adresses (*_url) sont normalisées."""

    def __getattr__(self, name: str) -> str | None:
        if name.startswith("_"):
            raise AttributeError(name)
        value = os.environ.get(name.upper(), "").strip()
        if name.endswith("_url"):
            value = url(value)
        return value or None
