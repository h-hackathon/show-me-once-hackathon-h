"""Accès au serveur SMO : un jeton partagé dans l'en-tête X-SMO-Token.

En local sans jeton, tout est ouvert. En ligne (Railway), un serveur sans jeton laisserait n'importe qui lancer des
runs et dépenser nos crédits H, Holo, Devin et Gladia : il refuse alors de démarrer.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException

from ..config import Settings


MIN_TOKEN_LENGTH = 16


def require_safe_deployment(s: Settings) -> None:
    if os.environ.get("RAILWAY_ENVIRONMENT") and len(s.server_token or "") < MIN_TOKEN_LENGTH:
        raise RuntimeError(f"En ligne, SMO_SERVER_TOKEN est obligatoire ({MIN_TOKEN_LENGTH} caractères minimum)")


def token_checker(s: Settings):
    """Dépendance FastAPI : refuse la requête si le jeton ne correspond pas (comparaison en temps constant)."""
    def check(x_smo_token: str | None = Header(default=None)) -> None:
        if s.server_token and not hmac.compare_digest((x_smo_token or "").encode(), s.server_token.encode()):
            raise HTTPException(401, "Jeton SMO requis (X-SMO-Token)")
    return check
