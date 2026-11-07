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
    "site_dossier": "SITE_DOSSIER",
    "server_url": "SMO_SERVER_URL",
    "server_token": "SMO_SERVER_TOKEN",
    "h_webhook_secret": "H_WEBHOOK_SECRET",
    "auto_repair": "SMO_AUTO_REPAIR",
    "runs_dir": "SMO_RUNS_DIR",
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
    site_dossier: str | None       # dossier à ouvrir après la connexion (ex. « 00417 ATELIER DORN SAS »)
    server_url: str | None       # serveur SMO déployé (Railway)
    server_token: str | None
    h_webhook_secret: str | None
    auto_repair: bool              # interface changée → Devin relancé tout seul
    runs_dir: Path
    tools_dir: Path

    def require(self, *names: str) -> None:
        missing = [ENV[n] for n in names if not getattr(self, n)]
        if missing:
            raise MissingConfig(f"À renseigner dans smo/.env : {', '.join(missing)}")


def load() -> Settings:
    def env(name: str) -> str | None:
        value = os.environ.get(ENV[name], "").strip()
        return value or DEFAULTS.get(name)

    return Settings(
        hai_api_key=env("hai_api_key"),
        holo_model=env("holo_model"),
        agent_model=env("agent_model"),
        replay_agent=env("replay_agent"),
        agent_prefix=env("agent_prefix"),
        gladia_api_key=env("gladia_api_key"),
        linkup_api_key=env("linkup_api_key"),
        devin_api_key=env("devin_api_key"),
        devin_org_id=env("devin_org_id"),
        devin_repo=env("devin_repo"),
        devin_max_acu=int(env("devin_max_acu")),
        site_url=(env("site_url") or "").rstrip("/") or None,
        site_login=env("site_login"),
        site_password=env("site_password"),
        site_admin_token=env("site_admin_token"),
        site_dossier=env("site_dossier"),
        server_url=(env("server_url") or "").rstrip("/") or None,
        server_token=env("server_token"),
        h_webhook_secret=env("h_webhook_secret"),
        auto_repair=env("auto_repair") == "1",
        runs_dir=Path(env("runs_dir")),
        tools_dir=ROOT / "tools",
    )
