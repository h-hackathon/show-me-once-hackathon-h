"""Lecture du Google Sheet par son export CSV public (le Sheet est partagé par lien) : rien à déployer.

On ne croit jamais l'agent sur parole : le score vient du contenu réel du Sheet.
La remise à zéro se fait dans le Sheet : menu « Show me once » → « Remettre à zéro ».
"""
import csv
import io
import re
import urllib.parse
import urllib.request

from .config import env
from .crm_data import PAYS, previous


def sheet_id() -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", env("SHEET_URL", required=True))
    if not m:
        raise SystemExit("❌ SHEET_URL ne ressemble pas à un lien Google Sheet (…/spreadsheets/d/<id>/…)")
    return m.group(1)


def csv_url(tab: str) -> str:
    base = env("SHEET_CSV_BASE") or f"https://docs.google.com/spreadsheets/d/{sheet_id()}/gviz/tq"
    return f"{base}?{urllib.parse.urlencode({'tqx': 'out:csv', 'headers': 1, 'sheet': tab})}"


def read_tab(tab: str) -> list[list]:
    req = urllib.request.Request(csv_url(tab), headers={"User-Agent": "Mozilla/5.0 show-me-once"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    if text.lstrip().startswith("<"):
        raise SystemExit("❌ Le Sheet n'est pas lisible : partage-le « Tous les utilisateurs disposant du lien »")
    return [row for row in csv.reader(io.StringIO(text)) if any(c.strip() for c in row)]


def read() -> dict[str, list[list]]:
    """{pays: [[en-têtes], [ligne], …]} tel que dans le Sheet."""
    return {p: read_tab(p) for p in PAYS}


def is_reset(tables, tabs=None) -> tuple[bool, list[str]]:
    """Le Sheet est-il à l'état « semaine précédente » ? Renvoie (oui/non, pays différents)."""
    from .checker import parse_tab, same_rows
    tabs = tabs or read()
    diff = [p for p in PAYS if not same_rows(parse_tab(tabs.get(p)), previous(tables, p))[0]]
    return not diff, diff
