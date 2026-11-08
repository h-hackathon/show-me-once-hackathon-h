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


# Valeurs visibles dans le dépôt (code et .env.example) : jamais acceptées en ligne.
VALEURS_PUBLIQUES = {"", DEFAUT_PASSWORD, DEFAUT_SECRET, "changez-moi"}


def verifier_production() -> None:
    """En ligne, refuse de démarrer si un secret est absent, public (code, .env.example) ou trop court."""
    if not PROD:
        return
    refus = []
    for nom, valeur, longueur_min in (("SITE_PASSWORD", PASSWORD, 8), ("SECRET_KEY", SECRET_KEY, 16),
                                      ("SITE_ADMIN_TOKEN", ADMIN_TOKEN, 16)):
        if valeur.strip() in VALEURS_PUBLIQUES:
            refus.append(f"{nom} (absente ou valeur d'exemple)")
        elif len(valeur) < longueur_min:
            refus.append(f"{nom} (moins de {longueur_min} caractères)")
    if refus:
        raise SystemExit("Qonta en production : secrets à définir avant de démarrer : " + ", ".join(refus))

USER_CODE = "CMOREAU"             # le collaborateur du cabinet qui se connecte
CABINET = "Fiduciaire Moreau & Associés"
DOSSIER_DEMO = "00417"
