"""Tools communs à tous les agents SMO : signaler un changement d'interface, relire l'ERP.

Rien de métier ici (fournisseur, TVA…) : ce savoir-là va dans la Skill de la tâche, pas dans un tool commun.
"""
from __future__ import annotations

from typing import Callable

from hai_agents import Tool
from hai_agents.tools import tool as as_tool   # nom, description et schéma tirés de la fonction

from ..clients.site import Site


def tools(cfg, on_drift: Callable[[str, str], None]) -> list[Tool]:
    def report_drift(tool: str, details: str) -> str:
        """Signale que l'interface a changé pour un tool (precheck en échec ou erreur à l'exécution).
        tool : nom du tool concerné ; details : ce qui a changé ou ce qui manquait. Déclenche sa réparation."""
        on_drift(tool, details)
        return "Signalé. Termine la tâche toi-même à l'écran en suivant la Skill."

    def verify_entry(reference: str) -> dict:
        """Relit dans le logiciel (API technique) la pièce enregistrée sous cette référence : statut et montants réels."""
        if not (cfg.site_url and cfg.site_admin_token):
            return {"found": None, "notes": "API du site non configurée"}
        found = Site(cfg.site_url, cfg.site_admin_token).invoices(reference)
        return {"found": bool(found), "entries": found}

    return [as_tool(f) for f in (report_drift, verify_entry)]
