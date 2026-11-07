"""Réglages SMO, lus dans l'environnement (fichier smo/.env, jamais commité)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Attribut de Settings → variable d'environnement (sert aussi aux messages d'erreur).
ENV = {
    "hai_api_key": "HAI_API_KEY",
    "holo_model": "HOLO_MODEL",
    "synth_model": "HOLO_SYNTH_MODEL",
    "agent_model": "SMO_AGENT_MODEL",
    "replay_agent": "SMO_REPLAY_AGENT",
    "agent_prefix": "SMO_AGENT_PREFIX",
    "gladia_api_key": "GLADIA_API_KEY",
    "linkup_api_key": "LINKUP_API_KEY",
    "devin_api_key": "DEVIN_API_KEY",
    "devin_org_id": "DEVIN_ORG_ID",
    "devin_repo": "DEVIN_REPO",
    "devin_max_acu": "DEVIN_MAX_ACU",
    "site_url": "SITE_URL",
    "site_login": "SITE_LOGIN",
    "site_password": "SITE_PASSWORD",
    "site_admin_token": "SITE_ADMIN_TOKEN",
    "desktop_login": "DESKTOP_LOGIN",
    "desktop_password": "DESKTOP_PASSWORD",
    "server_url": "SMO_SERVER_URL",
    "server_token": "SMO_SERVER_TOKEN",
    "h_webhook_secret": "H_WEBHOOK_SECRET",
    "auto_repair": "SMO_AUTO_REPAIR",
    "runs_dir": "SMO_RUNS_DIR",
    "h_tools_dir": "H_TOOLS_DIR",
    "tool_url": "SMO_TOOL_URL",
    "worker_kinds": "SMO_WORKER_KINDS",
    "h_desktop_env": "H_DESKTOP_ENV",
}

DEFAULTS = {
    "holo_model": "holo3-1-35b-a3b",   # gratuit ; holo4-* demandent des crédits
    "replay_agent": "h/web-surfer-pro",
    "agent_prefix": "smo-",
    "devin_max_acu": "10",
    "runs_dir": str(ROOT / "runs"),
    "auto_repair": "0",
}


class MissingConfig(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    hai_api_key: str | None
    holo_model: str
    synth_model: str | None        # passe 2 de la compréhension (texte seul) ; vide = HOLO_MODEL
    agent_model: str | None        # modèle de l'agent custom (None = défaut H, holo4-27b)
    replay_agent: str              # agent H qui refait la démo, guidé pas à pas
    agent_prefix: str              # les agents créés par SMO commencent par ce préfixe
    gladia_api_key: str | None
    linkup_api_key: str | None
    devin_api_key: str | None
    devin_org_id: str | None
    devin_repo: str | None         # ex. "owner/smo" : le repo où Devin ouvre ses PR
    devin_max_acu: int
    site_url: str | None           # logiciel cible (site compta)
    site_login: str | None
    site_password: str | None
    site_admin_token: str | None
    desktop_login: str | None      # appli de bureau (base locale) : identifiants propres, sinon ceux du site
    desktop_password: str | None
    server_url: str | None       # serveur SMO déployé (Railway)
    server_token: str | None
    h_webhook_secret: str | None
    auto_repair: bool              # interface changée → Devin relancé tout seul
    runs_dir: Path
    tools_dir: Path                # les tools d'h-tools : <H_TOOLS_DIR>/tools si un clone local existe
    tool_url: str | None           # adresse des tools déployés (défaut : réseau privé Railway du projet)
    worker_kinds: tuple[str, ...]  # agents servis par ce serveur (défaut : web et desktop)
    h_desktop_env: str | None      # l'environnement desktop de test configuré dans H (son identifiant)

    def require(self, *names: str) -> None:
        missing = [ENV[n] for n in names if not getattr(self, n)]
        if missing:
            raise MissingConfig(f"À renseigner dans smo/.env : {', '.join(missing)}")


def url(value: str | None) -> str | None:
    """« xxx.up.railway.app » → « https://xxx.up.railway.app » ; localhost sans schéma → http://."""
    value = (value or "").strip().rstrip("/")
    if not value or "://" in value:
        return value or None
    local = value.startswith(("localhost", "127.0.0.1"))
    return f"{'http' if local else 'https'}://{value}"


def load() -> Settings:
    def env(name: str) -> str | None:
        value = os.environ.get(ENV[name], "").strip()
        return value or DEFAULTS.get(name)

    return Settings(
        hai_api_key=env("hai_api_key"),
        holo_model=env("holo_model"),
        synth_model=env("synth_model"),
        agent_model=env("agent_model"),
        replay_agent=env("replay_agent"),
        agent_prefix=env("agent_prefix"),
        gladia_api_key=env("gladia_api_key"),
        linkup_api_key=env("linkup_api_key"),
        devin_api_key=env("devin_api_key"),
        devin_org_id=env("devin_org_id"),
        devin_repo=env("devin_repo"),
        devin_max_acu=int(env("devin_max_acu")),
        site_url=url(env("site_url")),
        site_login=env("site_login"),
        site_password=env("site_password"),
        site_admin_token=env("site_admin_token"),
        desktop_login=env("desktop_login") or env("site_login"),
        desktop_password=env("desktop_password") or env("site_password"),
        server_url=url(env("server_url")),
        server_token=env("server_token"),
        h_webhook_secret=env("h_webhook_secret"),
        auto_repair=env("auto_repair") == "1",
        runs_dir=Path(env("runs_dir")),
        tools_dir=Path(env("h_tools_dir")) / "tools" if env("h_tools_dir") else ROOT / "tools",
        tool_url=env("tool_url"),
        worker_kinds=worker_kinds(env("worker_kinds")),
        h_desktop_env=env("h_desktop_env"),
    )


def worker_kinds(value: str | None) -> tuple[str, ...]:
    """Un seul serveur sert les agents web et bureau ; SMO_WORKER_KINDS le restreint si deux serveurs tournent."""
    if value:
        return tuple(k.strip() for k in value.split(",") if k.strip())
    return ("web", "desktop")
