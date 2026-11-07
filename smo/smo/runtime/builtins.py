"""Tools communs à tous les agents SMO : signaler un changement d'interface, vérifier un fournisseur, relire l'ERP."""
from __future__ import annotations

from typing import Callable

from hai_agents import Tool
from hai_agents.tools import tool as as_tool   # nom, description et schéma tirés de la fonction

from ..clients import linkup
from ..clients.site import Site


SUPPLIER_SCHEMA = {
    "type": "object",
    "properties": {
        "exists": {"type": "boolean"},
        "official_name": {"type": "string"},
        "country": {"type": "string"},
        "vat_number_matches": {"type": "boolean", "description": "le n° de TVA donné correspond à cette entreprise"},
        "notes": {"type": "string"},
    },
    "required": ["exists", "notes"],
}


def tools(cfg, on_drift: Callable[[str, str], None]) -> list[Tool]:
    def report_drift(tool: str, details: str) -> str:
        """Signale que l'interface a changé pour un tool (precheck en échec ou erreur à l'exécution).
        tool : nom du tool concerné ; details : ce qui a changé ou ce qui manquait. Déclenche sa réparation."""
        on_drift(tool, details)
        return "Signalé. Termine la tâche toi-même à l'écran en suivant la Skill."

    def check_supplier(name: str, vat_number: str = "") -> dict:
        """Vérifie sur le web qu'un fournisseur existe (raison sociale, pays) et, si donné, que son n° de TVA lui correspond."""
        if not cfg.linkup_api_key:
            return {"exists": None, "notes": "vérification indisponible (LINKUP_API_KEY absente)"}
        q = f"Entreprise « {name} »" + (f", n° de TVA intracommunautaire {vat_number}" if vat_number else "")
        answer = linkup.search(q + " : existe-t-elle, quel est son nom officiel et son pays ?",
                               cfg.linkup_api_key, schema=SUPPLIER_SCHEMA)
        return {**(answer.get("data") if isinstance(answer.get("data"), dict) else answer),
                "sources": linkup.source_urls(answer)[:3]}

    def verify_entry(reference: str) -> dict:
        """Relit dans le logiciel (API technique) la pièce enregistrée sous cette référence : statut et montants réels."""
        if not (cfg.site_url and cfg.site_admin_token):
            return {"found": None, "notes": "API du site non configurée"}
        found = Site(cfg.site_url, cfg.site_admin_token).invoices(reference)
        return {"found": bool(found), "entries": found}

    return [as_tool(f) for f in (report_drift, check_supplier, verify_entry)]
