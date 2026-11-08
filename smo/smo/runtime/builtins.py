"""Tools communs à tous les agents SMO : signaler un changement d'interface.

Rien de métier ni de propre à un logiciel ici (fournisseur, TVA, API de Qonta…) : ce savoir-là va dans la Skill de la
tâche et dans son tool, pas dans un tool commun.
"""
from __future__ import annotations

from typing import Callable

from hai_agents import Tool
from hai_agents.tools import tool as as_tool   # nom, description et schéma tirés de la fonction


def tools(on_drift: Callable[[str, str], None]) -> list[Tool]:
    def report_drift(tool: str, details: str) -> str:
        """Signale que l'interface a changé pour un tool (precheck en échec ou erreur à l'exécution).
        tool : nom du tool concerné ; details : ce qui a changé ou ce qui manquait. Déclenche sa réparation."""
        on_drift(tool, details)
        return "Signalé. Termine la tâche toi-même à l'écran en suivant la Skill."

    return [as_tool(report_drift)]
