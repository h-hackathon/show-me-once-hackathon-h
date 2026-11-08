"""Le vault H : là où l'utilisateur range ses identifiants, la seule source de SMO.

SMO n'en garde rien, ni sur disque ni dans un prompt :
- le navigateur de l'agent reçoit le vault (vault_id) : H remplit les champs sans que le modèle voie les valeurs ;
- un tool reçoit, à chaque appel, l'élément du site lu à ce moment-là (reveal, accès journalisé par H), dans le
  corps de la requête ; la valeur n'existe qu'en mémoire, le temps de l'appel ;
- la session Devin les reçoit en secrets de session (jamais dans le brief).

L'élément du site se retrouve par son adresse : celui dont une URL a le même hôte que le logiciel.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from hai_agents import Client


MASK = "•••"
SECRETS = ("password", "totp", "api_key")


def host(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").removeprefix("www.")


@dataclass(frozen=True)
class Item:
    """Un élément du vault, sans ses valeurs."""
    vault_id: str
    item_id: str
    name: str


class Secrets:
    """Les valeurs d'un élément, le temps d'un appel. repr() les masque ; scrub() les efface d'un résultat."""

    def __init__(self, values: dict):
        object.__setattr__(self, "_values", {k: v for k, v in values.items() if v})

    def __getattr__(self, name: str) -> str | None:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._values.get(name)

    def __setattr__(self, name, value) -> None:
        raise AttributeError("lecture seule")

    def __repr__(self) -> str:
        return f"Secrets({ {k: MASK if k in SECRETS else v for k, v in self._values.items()} })"

    def as_dict(self) -> dict:
        return dict(self._values)

    def scrub(self, value):
        secrets = [v for k, v in self._values.items() if k in SECRETS and len(v) >= 4]
        return _scrub(value, secrets) if secrets else value


def _scrub(value, secrets: list[str]):
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, MASK)
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, secrets) for v in value]
    return value


def vault_ids(h: Client, only: str | None = None) -> list[str]:
    if only:
        return [only]
    return [v.id for v in h.vaults.list_vaults(limit=100).vaults]


def find_item(h: Client, site_url: str | None, only_vault: str | None = None) -> Item | None:
    """L'élément du vault dont une URL a l'hôte du logiciel, ou None (l'utilisateur ne l'a pas encore rangé)."""
    target = host(site_url)
    if not target:
        return None
    for vault_id in vault_ids(h, only_vault):
        try:
            items = h.vaults.list_vault_items(vault_id, limit=200).items
        except Exception:   # un vault externe (1Password) ne liste pas ses éléments ici : on passe au suivant
            continue
        for item in items:
            if any(host(u) == target for u in item.urls):
                return Item(vault_id=vault_id, item_id=item.id, name=item.name)
    return None


def reveal(h: Client, item: Item) -> Secrets:
    """Les valeurs de l'élément, lues maintenant (H journalise chaque lecture) ; le code TOTP du moment, jamais la graine."""
    revealed = h.vaults.reveal_vault_item(item.vault_id, item.item_id)
    values = revealed.values or {}
    return Secrets({"username": values.get("username") or values.get("email"), "password": values.get("password"),
                    "totp": revealed.totp_code, "api_key": values.get("api_key")})


def tool_context(h: Client, site_url: str | None, only_vault: str | None = None) -> tuple[dict, Secrets]:
    """Le contexte d'un appel de tool : l'adresse du logiciel et l'élément du vault, lu au moment de l'appel."""
    item = find_item(h, site_url, only_vault)
    secrets = reveal(h, item) if item else Secrets({})
    return {"site_url": site_url, **secrets.as_dict()}, secrets
