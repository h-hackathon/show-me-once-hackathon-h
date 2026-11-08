"""Chemins du projet et lecture du .env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv absent : on lit seulement l'environnement
    pass


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, "").strip() or default
    if required and not value:
        raise SystemExit(f"❌ Variable manquante dans .env : {name}")
    return value
