"""Accès direct au Google Sheet via la mini API Apps Script (sheets/dashboard.gs) : lire, remettre à zéro.

On ne croit jamais l'agent sur parole : le score vient du contenu réel du Sheet.
"""
import json
import urllib.parse
import urllib.request

from .config import env
from .crm_data import COLONNES_RAPPORT, PAYS, generate, previous


def _url() -> str:
    return env("SHEET_WEBAPP_URL", required=True)


def _token() -> str:
    return env("SHEET_TOKEN", required=True)


def _call(req) -> dict:
    with urllib.request.urlopen(req, timeout=60) as r:  # urllib suit la redirection Apps Script (POST → GET)
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise SystemExit(f"❌ API du Sheet : {data['error']} (SHEET_TOKEN identique au TOKEN du script ?)")
    return data


def read() -> dict[str, list[list]]:
    """{pays: [[en-têtes], [ligne], …]} tel que dans le Sheet."""
    q = urllib.parse.urlencode({"token": _token()})
    return _call(urllib.request.Request(f"{_url()}?{q}"))["tabs"]


def reset(tables=None) -> int:
    """Remet chaque onglet pays au rapport de la semaine précédente (état « avant » de la démo)."""
    tables = tables or generate()
    tabs = {p: [[row[c] for c in COLONNES_RAPPORT] for row in previous(tables, p)] for p in PAYS}
    body = json.dumps({"token": _token(), "action": "reset", "tabs": tabs}).encode("utf-8")
    req = urllib.request.Request(_url(), data=body, headers={"Content-Type": "application/json"}, method="POST")
    return _call(req)["tabs"]
