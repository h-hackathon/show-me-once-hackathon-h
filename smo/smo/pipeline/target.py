"""Le logiciel cible d'un run : un site web (navigateur de l'agent H) ou une appli de bureau (environnement desktop).

L'appli de bureau tourne dans l'environnement desktop de test configuré dans H (H_DESKTOP_ENV) ; sans lui, SMO
prend le bureau de la machine où il tourne (utile en local seulement).

Un agent H par type, avec ses propres tools : les noms d'agent, de Skill et de tool portent le type.
"""
from __future__ import annotations

from hai_agents import Agent, Environment_Desktop

from ..clients import h
from ..config import Settings
from ..models import CaptureMeta


LOCAL_DESKTOP = Environment_Desktop(id="desktop", host="user_device")   # le bureau de la machine où tourne SMO


def is_desktop(meta: CaptureMeta) -> bool:
    return meta.software_kind == "desktop"


def desktop_environment(s: Settings):
    """L'environnement desktop de test configuré dans H (par son identifiant), sinon le bureau de cette machine."""
    return s.h_desktop_env or LOCAL_DESKTOP


def environment(meta: CaptureMeta, s: Settings):
    return desktop_environment(s) if is_desktop(meta) else h.web_environment(meta.software_url)


def as_dict(env) -> dict:
    """Pour agent.json : un environnement inline, ou l'identifiant d'un environnement du catalogue H."""
    return env.model_dump(mode="json") if hasattr(env, "model_dump") else {"id": env, "catalogue": True}


def credentials(meta: CaptureMeta, s: Settings) -> tuple[str | None, str | None]:
    return (s.desktop_login, s.desktop_password) if is_desktop(meta) else (s.site_login, s.site_password)


def where(meta: CaptureMeta) -> str:
    """Pour les consignes : où se fait la tâche."""
    if is_desktop(meta):
        return f"l'application de bureau « {meta.software_url} »"
    return f"le logiciel {meta.software_url}"


def session_agent(meta: CaptureMeta, s: Settings) -> str | Agent:
    """L'agent qui explore ou rejoue (cartographie, replay guidé) : navigateur ou bureau selon le type."""
    if is_desktop(meta):
        spec = Agent(name="smo-desktop", description="Agent SMO sur une application de bureau.",
                     environments=[desktop_environment(s)])
        return spec.model_copy(update={"model": s.agent_model}) if s.agent_model else spec
    return h.session_agent(s.replay_agent, meta.software_url, s.agent_model)


def prepare(meta: CaptureMeta) -> None:
    """Site en localhost : un Chromium local pour l'agent. Rien à faire pour le cloud ni pour le bureau."""
    if not is_desktop(meta):
        h.prepare_local_browser(meta.software_url)


DOSSIER_RULE = ("Si le logiciel demande de choisir un dossier ou une société, prends celui qui correspond à la pièce "
                "(le client indiqué dessus).")
