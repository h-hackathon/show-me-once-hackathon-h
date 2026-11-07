"""Réglages lus dans l'environnement (fichier .env à la racine de logiciel-test/)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
INBOX = DATA / "inbox"
DB_PATH = Path(os.environ.get("COMPTAREX_DB", DATA / "comptarex.db"))

# En ligne (Railway, ou COMPTAREX_PROD=1) : cookies sécurisés, et pas de démarrage avec les secrets par défaut.
PROD = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("COMPTAREX_PROD"))

DEFAUT_PASSWORD, DEFAUT_SECRET = "Comptarex2026!", "comptarex-dev-secret"
LOGIN = os.environ.get("SITE_LOGIN", "c.moreau@fiduciaire-moreau.test")
PASSWORD = os.environ.get("SITE_PASSWORD", DEFAUT_PASSWORD)
ADMIN_TOKEN = os.environ.get("SITE_ADMIN_TOKEN", "")        # vide : API admin fermée
SECRET_KEY = os.environ.get("SECRET_KEY", DEFAUT_SECRET)
PORT = int(os.environ.get("PORT", "8042"))
HOST = os.environ.get("HOST", "0.0.0.0" if PROD else "127.0.0.1")


def verifier_production() -> None:
    """En ligne, refuse de démarrer si un secret est resté à sa valeur par défaut (visible dans le dépôt)."""
    if not PROD:
        return
    manquants = [nom for nom, valeur, defaut in (("SITE_PASSWORD", PASSWORD, DEFAUT_PASSWORD),
                                                 ("SECRET_KEY", SECRET_KEY, DEFAUT_SECRET),
                                                 ("SITE_ADMIN_TOKEN", ADMIN_TOKEN, ""))
                 if not valeur or valeur == defaut]
    if manquants:
        raise SystemExit("Comptarex en production : variables à définir avant de démarrer : " + ", ".join(manquants))

USER_CODE = "CMOREAU"             # le collaborateur du cabinet qui se connecte
CABINET = "Fiduciaire Moreau & Associés"
DOSSIER_DEMO = "00417"
