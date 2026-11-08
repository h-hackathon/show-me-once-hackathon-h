"""Helpers des tools de bureau : piloter l'appli par son arbre d'accessibilité avec `cua`, le CLI de H.

C'est la technique de H : l'agent bureau a un shell dans son environnement (bureau cloud de H ou poste de
l'utilisateur) et `cua` y est déjà. Le tool de bureau est livré avec la Skill (fichiers posés par SMO via l'API H) et
l'agent le lance depuis ce shell : rien à installer chez l'utilisateur.

Un contrôle se désigne comme à l'écran, par son libellé (et son rôle), jamais par des coordonnées :

    win = "Qonta"                                                  # la fenêtre de l'appli (titre ou nom d'appli)
    set_value(win, "Référence fournisseur", params.reference)      # remplit le champ et relit sa valeur
    click(win, "Enregistrer le brouillon", role="push button")
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

# Une ligne de `cua state` :  36 spin button "Decimal places:" value='0.0' @424,593-486,625
LINE = re.compile(r"^\s*(?P<n>\d+) (?P<role>.+?) \"(?P<label>.*?)\"(?: value='(?P<value>.*?)')?(?: |$)")


class DeskError(RuntimeError):
    pass


@dataclass(frozen=True)
class Control:
    n: int
    role: str
    label: str
    value: str | None = None


def cua(*args: str, timeout_s: float = 60) -> str:
    """Une commande `cua` ; code de sortie non nul (refus, rien vu, résultat inconnu) → DeskError avec son reçu."""
    exe = shutil.which("cua")
    if exe is None:
        raise DeskError("cua introuvable : un tool de bureau se lance dans l'environnement de l'agent H")
    done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout_s)
    if done.returncode != 0:
        receipt = (done.stdout + done.stderr).strip()[-600:]
        raise DeskError(f"cua {args[0]} (code {done.returncode}) : {receipt}")
    return done.stdout


def parse_state(text: str) -> list[Control]:
    return [Control(n=int(m["n"]), role=m["role"], label=m["label"], value=m["value"])
            for line in text.splitlines() if (m := LINE.match(line))]


def state(window: str | None = None, query: str | None = None) -> list[Control]:
    """Les contrôles numérotés de la fenêtre (celle qui a le focus par défaut), filtrés par libellé si demandé."""
    args = ["state", *([window] if window else []), *(["-q", query] if query else [])]
    return parse_state(cua(*args))


def find(window: str | None, label: str, role: str | None = None) -> Control:
    """Le contrôle qui porte exactement ce libellé (et ce rôle) ; absent → DeskError."""
    found = [c for c in state(window, re.escape(label))
             if c.label.strip().rstrip(":") == label.strip().rstrip(":") and (role is None or c.role == role)]
    if not found:
        raise DeskError(f"contrôle introuvable : {role or 'élément'} « {label} »")
    return found[0]


def set_value(window: str | None, label: str, value: str, role: str | None = None) -> None:
    cua("set", str(find(window, label, role).n), value)


def click(window: str | None, label: str, role: str | None = None) -> None:
    cua("click", str(find(window, label, role).n))


def check_contract(contract: dict) -> dict:
    """Precheck d'un tool de bureau : chaque écran montre-t-il encore ses contrôles attendus ? Ne modifie rien,
    sauf les clics de navigation (`via`) pour atteindre l'écran."""
    missing, checked = [], 0
    for screen in contract.get("screens", []):
        window = screen.get("window")
        for via in screen.get("via", []):
            click(window, via.get("label") or via.get("name"), via.get("role"))
        for anchor in screen.get("anchors", []):
            checked += 1
            try:
                find(window, anchor.get("label") or anchor.get("name") or anchor.get("text"), anchor.get("role"))
            except DeskError:
                missing.append({"screen": screen.get("name"), "anchor": anchor})
    return {"ok": not missing, "checked": checked, "missing": missing}
