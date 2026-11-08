"""Client H Company Agents API (https://hub.hcompany.ai)."""
import base64
import re
import unicodedata
from pathlib import Path

import httpx

from . import config

MAX_IMAGES = 8
MAX_IMAGES_BYTES = 5_000_000


class HCompanyError(RuntimeError):
    pass


def _headers() -> dict:
    if not config.HAI_API_KEY:
        raise HCompanyError("HAI_API_KEY manquante")
    return {"Authorization": f"Bearer {config.HAI_API_KEY}"}


async def _request(method: str, path: str, **kw) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.request(method, f"{config.HAI_BASE_URL}{path}", headers=_headers(), **kw)
    if r.status_code >= 400:
        raise HCompanyError(f"{method} {path} → {r.status_code}: {r.text}")
    return r.json() if r.content else {}


def pick_screenshots(steps: list[dict], rec_dir: Path) -> list[str]:
    """Choisit jusqu'à MAX_IMAGES captures réparties sur la tâche, en data URI base64."""
    files = [s.get("screenshot") or s.get("screenshot_after") for s in steps]
    files = [f for f in files if f and (rec_dir / "screenshots" / f).exists()]
    if len(files) > MAX_IMAGES:
        stride = len(files) / MAX_IMAGES
        files = [files[int(i * stride)] for i in range(MAX_IMAGES)]
    out, total = [], 0
    for f in files:
        raw = (rec_dir / "screenshots" / f).read_bytes()
        if total + len(raw) > MAX_IMAGES_BYTES:
            break
        total += len(raw)
        out.append("data:image/jpeg;base64," + base64.b64encode(raw).decode())
    return out


async def create_skill(name: str, description: str, body: str) -> dict:
    return await _request("POST", "/skills", json={"name": name, "description": description, "body": body})


async def create_session(
    task: str,
    *,
    agent: str | None = None,
    start_url: str | None = None,
    images: list[str] | None = None,
    max_steps: int | None = None,
    timezone: str = "Europe/Paris",
) -> dict:
    body: dict = {"agent": agent or config.HAI_DEFAULT_AGENT, "messages": task, "timezone": timezone}
    if images:
        body["images"] = images
    if max_steps:
        body["max_steps"] = max_steps
    overrides = {f"agent.environments[kind=web].{k}": v for k, v in auth_fields().items()}
    if start_url:
        overrides["agent.environments[kind=web].start_url"] = start_url
    if overrides:
        body["overrides"] = overrides
    return await _request("POST", "/sessions", json=body)


async def get_session(session_id: str) -> dict:
    return await _request("GET", f"/sessions/{session_id}")


async def get_status(session_id: str) -> dict:
    return await _request("GET", f"/sessions/{session_id}/status")


# ---------- export "fichier agent H" ----------

AGENT_INSTRUCTIONS = (
    "You replay a procedure that a human demonstrated once (recorded with Show Me Once). "
    "Always load the attached skill first and follow its steps, adapting to UI changes. "
    "Never perform an irreversible action (accept, refuse, refund, pay, delete, send, submit a dispute response) "
    "unless the user's message explicitly asks for it: in that case stop before the final click and report "
    "what you would do and why. On a login page, use the stored credentials offered for that site; "
    "if none are offered or a code is sent by SMS/e-mail, stop and report which site needs a login."
)


def auth_fields() -> dict:
    """Champs du navigateur cloud qui permettent à l'agent d'être connecté aux sites."""
    f: dict = {}
    if config.HAI_VAULT_ID:
        f["vault_id"] = config.HAI_VAULT_ID
    if config.HAI_BROWSER_PROFILE_ID:
        f["browser_profile_id"] = config.HAI_BROWSER_PROFILE_ID
        f["persist_browser_profile"] = True
    elif config.HAI_USE_DEFAULT_PROFILE:
        f["use_default_browser_profile"] = True
    return f


def _covers(item_url: str, app_host: str) -> bool:
    from urllib.parse import urlparse

    h = (urlparse(item_url if "://" in item_url else f"https://{item_url}").hostname or "").lower()
    return bool(h) and (app_host == h or app_host.endswith("." + h))


async def auth_check(accounts: list[dict]) -> dict:
    """Croise les apps de l'enregistrement avec les items du vault H configuré."""
    mode = {
        "vault_id": config.HAI_VAULT_ID or None,
        "browser_profile": "uploaded" if config.HAI_BROWSER_PROFILE_ID else ("default" if config.HAI_USE_DEFAULT_PROFILE else None),
    }
    items: list[dict] = []
    vault_error = None
    if config.HAI_VAULT_ID and config.HAI_API_KEY:
        try:
            offset = 0
            while True:
                page = await _request("GET", f"/vaults/{config.HAI_VAULT_ID}/items", params={"limit": 200, "offset": offset})
                items += page.get("items", [])
                offset += page.get("limit", 200)
                if offset >= page.get("total", 0):
                    break
        except HCompanyError as e:
            vault_error = str(e)  # ex : vault 1Password (endpoint réservé aux vaults hébergés par H)
    out = []
    for acc in accounts:
        app = acc["app"]
        match = next((it for it in items if any(_covers(u, app) for u in it.get("urls", []))), None)
        if match:
            fields = set(match.get("fields", []))
            has_login = bool(fields & {"password", "api_key"})
            status = "ok" if has_login and "totp" in fields else ("no_totp" if has_login else "incomplete")
            out.append({**acc, "status": status, "vault_item": match.get("name"), "fields": sorted(fields)})
        else:
            out.append({**acc, "status": "profile_only" if mode["browser_profile"] else "missing", "vault_item": None, "fields": []})
    return {"mode": mode, "vault_error": vault_error, "accounts": out}


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].strip("-")) or "procedure"


def build_h_export(session: dict, skill_md: str, rec_id: str) -> dict:
    """Fichier autonome : le skill + l'agent qui l'utilise, au format exact des API H (POST /skills, POST /agents)."""
    from . import config  # import local pour lire la config à jour

    base = slugify(re.sub(r"^Show Me Once\s*[—-]\s*", "", session.get("title") or "procedure"))
    suffix = rec_id.split("-")[-1]
    ns = f"{config.HAI_SKILL_NAMESPACE}/" if config.HAI_SKILL_NAMESPACE else ""
    skill_name = f"{ns}smo-{base}-{suffix}"
    agent_name = f"{ns}smo-agent-{base}-{suffix}"
    goal = (session.get("goal") or session.get("title") or "the recorded procedure").strip()
    one_line_goal = " ".join(goal.split())[:300]
    env = {"id": "browser", "kind": "web", "mode": {"type": "visual", "width": 1280, "height": 800}}
    if session.get("start_url"):
        env["start_url"] = session["start_url"]
    env.update(auth_fields())
    return {
        "format": "show-me-once/h-export@1",
        "recording_id": rec_id,
        "skill": {
            "name": skill_name,
            "description": f"Use when asked to: {one_line_goal}",
            "body": skill_md,
            "url_pattern": _url_pattern(session.get("apps") or []),
        },
        "agent": {
            "name": agent_name,
            "description": f"{session.get('title') or 'Recorded procedure'}: {one_line_goal}"[:500],
            "environments": [env],
            "instructions": AGENT_INSTRUCTIONS,
            "skills": [skill_name],
        },
    }


def _url_pattern(apps: list[str]) -> str | None:
    hosts = sorted(set(a for a in apps if a))
    return ("https://(" + "|".join(re.escape(h) for h in hosts) + ")/.*") if hosts else None


def skill_file(export: dict) -> str:
    """SKILL.md avec frontmatter (format Agent Skills), à coller dans H ou ailleurs."""
    sk = export["skill"]
    desc = sk["description"].replace('"', "'")
    return f'---\nname: {sk["name"]}\ndescription: "{desc}"\n---\n\n{sk["body"]}'


async def import_export(export: dict) -> dict:
    """Crée le skill puis l'agent dans le catalogue H. Idempotent si on relance (409 = déjà créé)."""
    sk = {k: v for k, v in export["skill"].items() if v is not None}
    result = {"skill": sk["name"], "agent": export["agent"]["name"]}
    try:
        await _request("POST", "/skills", json=sk)
        result["skill_status"] = "created"
    except HCompanyError as e:
        if "409" not in str(e):
            raise
        result["skill_status"] = "already_exists"
    try:
        res = await _request("POST", "/agents", json=export["agent"])
        result["agent_status"] = "created"
        result["agent_revision"] = res.get("revision")
    except HCompanyError as e:
        if "409" not in str(e):
            raise
        # L'agent existe déjà : on le met à jour (nouveau vault / profil / start_url) avec If-Match
        res = await _update_agent(export["agent"])
        result["agent_status"] = "updated"
        result["agent_revision"] = res.get("revision")
    return result


async def _update_agent(agent: dict) -> dict:
    name = agent["name"]
    async with httpx.AsyncClient(timeout=60) as client:
        cur = await client.get(f"{config.HAI_BASE_URL}/agents/{name}", headers=_headers())
        if cur.status_code >= 400:
            raise HCompanyError(f"GET /agents/{name} → {cur.status_code}: {cur.text}")
        headers = dict(_headers())
        if cur.headers.get("ETag"):
            headers["If-Match"] = cur.headers["ETag"]
        r = await client.put(f"{config.HAI_BASE_URL}/agents/{name}", headers=headers, json=agent)
    if r.status_code >= 400:
        raise HCompanyError(f"PUT /agents/{name} → {r.status_code}: {r.text}")
    return r.json() if r.content else {}
