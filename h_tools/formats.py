"""Formats de l'écran d'un logiciel français et comparaison de noms, communs à tous les tools.

Sans Playwright : utilisable par les tools web et de bureau, et dans les tests hors ligne.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LEGAL_FORMS = {"SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCI", "SCM", "SELARL", "SCOP", "EI", "GIE"}


def decimal_fr(value):
    """« 1 234,50 », « 1234.50 € » ou 1234.5 → valeur lisible par Decimal ; comme sur la pièce (validateur pydantic)."""
    if isinstance(value, str):
        value = value.replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace("€", "")
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
    return value


def fr_amount(value: Decimal) -> str:
    """Decimal("1234.5") → « 1 234,50 » : un montant."""
    sign = "-" if value < 0 else ""
    units, cents = f"{abs(value).quantize(CENT, ROUND_HALF_UP):.2f}".split(".")
    return f"{sign}{int(units):,}".replace(",", " ") + f",{cents}"


def fr_number(value: Decimal) -> str:
    """Decimal("2") → « 2 », Decimal("1.50") → « 1,5 » : une quantité ou un taux."""
    return f"{value.normalize():f}".replace(".", ",")


def fr_date(value: date) -> str:
    """date(2026, 10, 5) → « 05/10/2026 » (JJ/MM/AAAA)."""
    return value.strftime("%d/%m/%Y")


def norm(text: str) -> str:
    """Comparaison de noms comme une autocomplétion : sans accents, en majuscules, espaces réduits."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return " ".join(re.sub(r"[^\w&]+", " ", text).split())


def sans_forme(text: str) -> str:
    """« NETCLOUD SERVICES SAS » → « NETCLOUD SERVICES »."""
    return " ".join(w for w in norm(text).split() if w not in LEGAL_FORMS)


def meme_nom(a: str, b: str) -> bool:
    return norm(a) == norm(b) or sans_forme(a) == sans_forme(b)
