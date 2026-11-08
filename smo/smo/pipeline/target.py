"""Le logiciel cible d'un run : un site web (navigateur de l'agent H) ou une appli de bureau (environnement desktop).

L'appli de bureau tourne dans l'environnement desktop de test configuré dans H (H_DESKTOP_ENV), ou sur le PC du live
par son relais `holo local desktop` (H_DESKTOP_BRIDGE) ; sans l'un ni l'autre, SMO prend le bureau de la machine où il
tourne (utile en local seulement).

Un agent H par type, avec ses propres tools : les noms d'agent, de Skill et de tool portent le type.
"""
from __future__ import annotations

from hai_agents import Agent, Environment_Desktop, Environment_Workstation, WorkstationStorage

from ..clients import h, vault
from ..config import MissingConfig, Settings
from ..models import CaptureMeta


LOCAL_DESKTOP = Environment_Desktop(id="desktop", host="user_device")   # le bureau de la machine où tourne SMO
# Les pièces jointes d'une demande arrivent dans files/ de cette workstation, lues au shell (pdftotext). Elle ne se
# connecte jamais au logiciel : les identifiants restent dans le vault (navigateur) ou passent par le tool.
# Machine neuve à chaque session : le disque par défaut ne sert qu'à une session à la fois (« volume attached to
# another session » dès que deux agents tournent).
WORKSTATION = Environment_Workstation(id="workstation", host="cloud", lazy=True,
                                      storage=WorkstationStorage(ephemeral=True))


def is_desktop(meta: CaptureMeta) -> bool:
    return meta.software_kind == "desktop"


def desktop_environment(s: Settings):
    """L'environnement desktop de test configuré dans H (par son identifiant), sinon le relais du PC du live,
    sinon le bureau de cette machine.

    Le relais : session_id déjà rempli, le SDK ne lance pas de relais local et H envoie les commandes à celui qui sert
    cet identifiant (scripts/desktop_bridge.sh sur le PC du live)."""
    if s.h_desktop_env:
        return s.h_desktop_env
    if s.h_desktop_bridge:
        return Environment_Desktop(id="desktop", host="user_device", session_id=s.h_desktop_bridge)
    return LOCAL_DESKTOP


def has_remote_desktop(s: Settings) -> bool:
    """Un bureau joignable depuis un serveur sans écran (Railway) : l'environnement H ou le relais du PC du live."""
    return bool(s.h_desktop_env or s.h_desktop_bridge)


def environment(meta: CaptureMeta, s: Settings, vault_id: str | None = None):
    return desktop_environment(s) if is_desktop(meta) else h.web_environment(meta.software_url, vault_id)


def vault_item(meta: CaptureMeta, s: Settings, client=None) -> vault.Item | None:
    """L'élément du vault H de l'utilisateur pour ce site (retrouvé par son adresse), ou None."""
    if is_desktop(meta) or not s.hai_api_key:
        return None
    return vault.find_item(client or h.client(s.hai_api_key), meta.software_url, s.h_vault_id)


LOGIN_WITH_VAULT = ("Connexion : les identifiants de ce site sont dans ton vault ; remplis-les avec ton outil de secrets, "
                    "sans jamais les écrire ni les répéter en clair.")
LOGIN_IN_PROMPT = "Connexion : e-mail « {login} », mot de passe « {password} »."


def login_hint(meta: CaptureMeta, s: Settings, item: vault.Item | None) -> str:
    """La phrase de connexion des consignes de l'agent.

    Site en ligne : toujours par le vault, rattaché au navigateur cloud ; le modèle ne voit jamais le mot de passe.
    H ne rattache pas de vault à un navigateur local ni à un bureau : en localhost (développement) et sur
    l'appli de bureau seulement, les identifiants de smo/.env passent encore dans les consignes."""
    if item and not is_desktop(meta) and not h.is_local(meta.software_url):
        return LOGIN_WITH_VAULT
    login, password = credentials(meta, s)
    if (is_desktop(meta) or h.is_local(meta.software_url)) and login and password:
        return LOGIN_IN_PROMPT.format(login=login, password=password)
    if is_desktop(meta):
        return "Si l'application demande une connexion, arrête-toi et explique-le : aucun identifiant n'est fourni."
    raise MissingConfig(f"Le site {vault.host(meta.software_url) or meta.software_url} n'est pas dans le vault H : "
                        "ajoute-y un élément avec son adresse, l'identifiant et le mot de passe")


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


def session_agent(meta: CaptureMeta, s: Settings, item: vault.Item | None = None) -> str | Agent:
    """L'agent qui explore ou rejoue (cartographie, replay guidé) : navigateur (avec le vault de l'utilisateur) ou
    bureau selon le type."""
    if is_desktop(meta):
        spec = Agent(name="smo-desktop", description="Agent SMO sur une application de bureau.",
                     environments=[desktop_environment(s)])
        return spec.model_copy(update={"model": s.agent_model}) if s.agent_model else spec
    return h.session_agent(s.replay_agent, meta.software_url, s.agent_model, item.vault_id if item else None)


def prepare(meta: CaptureMeta) -> None:
    """Site en localhost : un Chromium local pour l'agent. Rien à faire pour le cloud ni pour le bureau."""
    if not is_desktop(meta):
        h.prepare_local_browser(meta.software_url)


DOSSIER_RULE = ("Si le logiciel demande de choisir un dossier ou une société, prends celui qui correspond à la pièce "
                "(le client indiqué dessus).")
