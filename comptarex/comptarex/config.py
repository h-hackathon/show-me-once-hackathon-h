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

LOGIN = os.environ.get("SITE_LOGIN", "c.moreau@fiduciaire-moreau.test")
PASSWORD = os.environ.get("SITE_PASSWORD", "Comptarex2026!")
ADMIN_TOKEN = os.environ.get("SITE_ADMIN_TOKEN", "")        # vide : API admin fermée
SECRET_KEY = os.environ.get("SECRET_KEY", "comptarex-dev-secret")
PORT = int(os.environ.get("PORT", "8042"))
HOST = os.environ.get("HOST", "127.0.0.1")

USER_CODE = "CMOREAU"             # le collaborateur du cabinet qui se connecte
CABINET = "Fiduciaire Moreau & Associés"
DOSSIER_DEMO = "00417"
