"""Le logiciel cible d'un run : un site web (navigateur de l'agent H) ou une appli de bureau (bureau du Mac).

Un agent H par type, avec ses propres tools : les noms d'agent, de Skill et de tool portent le type.
"""
from __future__ import annotations

from hai_agents import Agent, Environment_Desktop

from ..clients import h
from ..config import Settings
from ..models import CaptureMeta


DESKTOP = Environment_Desktop(id="desktop", host="user_device")   # pilote souris, clavier et écran du Mac


def is_desktop(meta: CaptureMeta) -> bool:
    return meta.software_kind == "desktop"


def environment(meta: CaptureMeta):
    return DESKTOP if is_desktop(meta) else h.web_environment(meta.software_url)


def credentials(meta: CaptureMeta, s: Settings) -> tuple[str | None, str | None]:
    return (s.desktop_login, s.desktop_password) if is_desktop(meta) else (s.site_login, s.site_password)


def where(meta: CaptureMeta) -> str:
    """Pour les consignes : où se fait la tâche."""
    if is_desktop(meta):
        return f"l'application de bureau « {meta.software_url} », déjà ouverte sur le Mac"
    return f"le logiciel {meta.software_url}"


def session_agent(meta: CaptureMeta, s: Settings) -> str | Agent:
    """L'agent qui explore ou rejoue (cartographie, replay guidé) : navigateur ou bureau selon le type."""
    if is_desktop(meta):
        spec = Agent(name="smo-local-desktop", description="Agent SMO sur une application de bureau du Mac.",
                     environments=[DESKTOP])
        return spec.model_copy(update={"model": s.agent_model}) if s.agent_model else spec
    return h.session_agent(s.replay_agent, meta.software_url, s.agent_model)


def prepare(meta: CaptureMeta) -> None:
    """Site en localhost : un Chromium local pour l'agent. Rien à faire pour le cloud ni pour le bureau."""
    if not is_desktop(meta):
        h.prepare_local_browser(meta.software_url)


DOSSIER_RULE = ("Si le logiciel demande de choisir un dossier ou une société, prends celui qui correspond à la pièce "
                "(le client indiqué dessus).")
