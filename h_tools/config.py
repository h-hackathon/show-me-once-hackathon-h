"""Le contexte d'un appel : l'adresse du logiciel et les identifiants de l'utilisateur, lus en attributs (cfg.site_url).

Rien n'est stocké dans le tool. SMO lit le vault H de l'agent à chaque appel et l'envoie dans le corps de la requête
({"context": {...}}) : aucune variable de site sur Railway, aucun secret dans GitHub. En local, et dans la session
Devin (qui reçoit ces valeurs en secrets de session), Context.from_env() lit SITE_URL, SITE_USERNAME, SITE_PASSWORD,
SITE_TOTP et SITE_API_KEY.

Un secret ne sort jamais du tool : repr() le masque, scrub() l'efface de tout résultat renvoyé.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:   # dans l'environnement de l'agent (tool de bureau) : pas de .env
    load_dotenv = None


ROOT = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(ROOT / ".env")   # en local seulement

# Champ du contexte → variable d'environnement (en local et chez Devin).
FIELDS = {"site_url": "SITE_URL", "username": "SITE_USERNAME", "password": "SITE_PASSWORD", "totp": "SITE_TOTP",
          "api_key": "SITE_API_KEY"}
SECRETS = ("password", "totp", "api_key")
MASK = "•••"


def url(value: str) -> str:
    """« xxx.up.railway.app » → « https://xxx.up.railway.app » ; localhost sans schéma → http://."""
    value = value.rstrip("/")
    if not value or "://" in value:
        return value
    local = value.startswith(("localhost", "127.0.0.1"))
    return f"{'http' if local else 'https'}://{value}"


class Context:
    """Champ absent ou vide → None. Les adresses (*_url) sont normalisées. Lecture seule."""

    def __init__(self, values: dict | None = None):
        clean = {}
        for key, value in (values or {}).items():
            value = "" if value is None else str(value).strip()
            if value:
                clean[key] = url(value) if key.endswith("_url") else value
        object.__setattr__(self, "_values", clean)

    @classmethod
    def from_env(cls) -> Context:
        return cls({field: os.environ.get(var) for field, var in FIELDS.items()})

    def __getattr__(self, name: str) -> str | None:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._values.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("le contexte d'un appel ne se modifie pas")

    def __repr__(self) -> str:
        return f"Context({ {k: MASK if k in SECRETS else v for k, v in self._values.items()} })"

    def scrub(self, value: Any) -> Any:
        """Le résultat sans aucune valeur secrète (un message d'erreur peut citer ce qui a été tapé)."""
        secrets = [v for k, v in self._values.items() if k in SECRETS and len(v) >= 4]
        return _scrub(value, secrets) if secrets else value


def _scrub(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, MASK)
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, secrets) for v in value]
    return value
