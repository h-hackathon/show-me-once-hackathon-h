"""`smo doctor` : chaque API répond-elle avec nos clés ? `--probe` : les capacités dont dépend le plan.

Les checks ne coûtent rien ou presque. Les probes lancent de vraies sessions H (crédits).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import httpx

from .clients import devin, gladia, h, holo, linkup, vault
from .clients.site import Site
from .config import ENV, Settings


@dataclass
class Check:
    name: str
    state: str          # ok | warn | fail | skip
    detail: str


ICON = {"ok": "✅", "warn": "⚠️ ", "fail": "❌", "skip": "⏭️ "}


def _guard(name: str, needs: tuple[str, ...], s: Settings, fn: Callable[[], Check]) -> Check:
    missing = [ENV[n] for n in needs if not getattr(s, n)]
    if missing:
        return Check(name, "skip", f"manque {', '.join(missing)}")
    try:
        return fn()
    except httpx.HTTPStatusError as err:
        return Check(name, "fail", f"HTTP {err.response.status_code} : {err.response.text[:160]}")
    except Exception as err:
        return Check(name, "fail", f"{type(err).__name__}: {str(err)[:200]}")


def checks(s: Settings) -> list[Check]:
    def h_agents() -> Check:
        quota = h.client(s.hai_api_key).sessions.get_session_quota()
        return Check("H Agents API", "ok", f"quota : {quota}"[:200])

    def holo_models() -> Check:
        results = []
        for model in dict.fromkeys([s.holo_model, "holo4-27b"]):
            try:
                _, seconds = holo.chat("Réponds juste OK.", s.hai_api_key, model)
                results.append(f"{model} OK ({seconds:.1f}s)")
            except httpx.HTTPStatusError as err:
                code = err.response.status_code
                results.append(f"{model} {code}{' (crédits nécessaires)' if code == 402 else ''}")
        state = "ok" if all("OK" in r for r in results) else "warn" if any("OK" in r for r in results) else "fail"
        return Check("Holo (Models API)", state, " · ".join(results))

    def gladia_key() -> Check:
        code = gladia.ping(s.gladia_api_key)
        return Check("Gladia", "ok" if code < 300 else "fail", f"HTTP {code}")

    def linkup_key() -> Check:
        r = linkup.search("H Company Holo computer use agent", s.linkup_api_key, output_type="searchResults")
        return Check("Linkup", "ok", f"{len(r.get('results', []))} résultats (≈0,005 $)")

    def devin_key() -> Check:
        if s.devin_api_key.startswith("apk_"):
            return Check("Devin API", "fail", "clé legacy apk_ refusée par l'API v3 : crée un service user "
                         "(Settings > Devin API > Service users, rôles ViewOrgSessions + UseDevinSessions) → token cog_…")
        api = devin.Devin(s.devin_api_key, s.devin_org_id)
        me = api.whoami()
        if me.status_code >= 300:
            return Check("Devin API", "fail", f"/v3/self HTTP {me.status_code} : token invalide")
        org = me.json().get("org_id") or me.json().get("devin_sessions_org_id")
        if org and org != s.devin_org_id:
            return Check("Devin API", "fail", f"token de l'org {org}, DEVIN_ORG_ID = {s.devin_org_id}")
        listed = api.list_sessions()
        if listed.status_code == 403:
            return Check("Devin API", "warn", "token OK, mais il manque la permission ViewOrgSessions (liste des sessions)")
        return Check("Devin API", "ok" if listed.status_code < 300 else "fail",
                     f"{me.json().get('principal_type')} · sessions HTTP {listed.status_code}")

    def site() -> Check:
        api = Site(s.site_url, s.site_admin_token)
        health = api.health()
        detail = f"ui {health.get('ui_version')}"
        if s.site_admin_token:   # facultatif : seulement pour relire ce qui est enregistré
            try:
                detail += f" · {len(api.invoices())} factures en base"
            except httpx.HTTPStatusError as err:
                return Check("Site compta", "warn", f"{detail} · jeton admin refusé (HTTP {err.response.status_code}, facultatif)")
        return Check("Site compta", "ok", detail)

    def vault_item() -> Check:
        """L'élément du site dans le vault H, sans lire ses valeurs (ni journal d'accès, ni secret affiché)."""
        client = h.client(s.hai_api_key)
        vaults = vault.vault_ids(client, s.h_vault_id)
        item = vault.find_item(client, s.site_url, s.h_vault_id)
        if item is None:
            return Check("Vault H", "warn", f"{len(vaults)} vault(s), aucun élément pour {vault.host(s.site_url)} : "
                                            "ajoute le site dans le vault H (adresse, identifiant, mot de passe)")
        fields = next((i.fields for i in client.vaults.list_vault_items(item.vault_id, limit=200).items
                       if i.id == item.item_id), [])
        return Check("Vault H", "ok", f"« {item.name} » ({', '.join(map(str, fields))}) dans le vault {item.vault_id}")

    def server() -> Check:
        r = httpx.get(f"{s.server_url}/health", timeout=20)
        r.raise_for_status()
        return Check("Serveur SMO", "ok", json.dumps(r.json(), ensure_ascii=False)[:160])

    return [
        _guard("H Agents API", ("hai_api_key",), s, h_agents),
        _guard("Holo (Models API)", ("hai_api_key",), s, holo_models),
        _guard("Gladia", ("gladia_api_key",), s, gladia_key),
        _guard("Linkup", ("linkup_api_key",), s, linkup_key),
        _guard("Devin API", ("devin_api_key", "devin_org_id"), s, devin_key),
        _guard("Site compta", ("site_url",), s, site),
        _guard("Vault H", ("hai_api_key", "site_url"), s, vault_item),
        _guard("Serveur SMO", ("server_url",), s, server),
    ]


# --- probes : les 3 capacités dont dépend le plan ------------------------------------------------

def probe_skill(s: Settings, log) -> Check:
    """Créer, relire et supprimer une Skill par API."""
    client, name = h.client(s.hai_api_key), "smo-probe-skill"
    h.upsert_skill(client, name, "Skill de test SMO.", "# Test\n1. Ne rien faire.\n")
    body = client.skills.get_skill(name).body
    client.skills.delete_skill(name)
    return Check("probe skill", "ok", f"créée, relue ({len(body)} car.), supprimée")


def probe_guided(s: Settings, log) -> Check:
    """Agent H guidé : envoyer des consignes pendant la session, et voir ce que contient une action."""
    client = h.client(s.hai_api_key)
    url = s.site_url or "https://example.com"
    h.prepare_local_browser(url)
    handle = client.start_session(agent=h.session_agent(s.replay_agent, url, s.agent_model), idle_timeout_s=300,
                                  messages=f"Va sur {url}, décris la page en une phrase, puis attends ma consigne.")
    events: list = []
    h.drain(handle, events, timeout_s=240)
    handle.send_message("Clique sur le premier lien ou bouton visible, puis décris ce qui a changé. Ne remplis rien.")
    h.wait_active(handle)
    h.drain(handle, events, timeout_s=240)
    handle.cancel()
    out = s.runs_dir / "_probes" / f"guided-{datetime.now():%Y%m%d-%H%M%S}"
    trace = h.build_trace(client, handle.id, out, s.hai_api_key, events=events)
    (out / "trace.json").write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    actions = [a for st in trace.steps for a in st.actions]
    names = sorted({a["tool_name"] for a in actions if a.get("tool_name")})
    sample = json.dumps(actions[0], ensure_ascii=False)[:200] if actions else "—"
    log(f"  trace : {out}")
    reached = any((st.url or "").startswith(url.rstrip("/")) for st in trace.steps)
    state = "ok" if actions and reached else "warn" if actions else "fail"
    where = "site atteint" if reached else f"site NON atteint ({trace.steps[-1].url if trace.steps else '—'})"
    return Check("probe guided", state, f"{len(trace.steps)} étapes · {where} · actions {names} · ex. {sample}")


def probe_tool(s: Settings, log) -> Check:
    """Le cas Catherine : un agent du catalogue déclare un tool, la session est lancée sans nous,
    et un AUTRE programme (le worker) répond au tool."""
    from hai_agents.types.tool_definition import ToolDefinition

    client, name, calls = h.client(s.hai_api_key), f"{s.agent_prefix}probe-tool", []

    def smo_ping(text: str) -> str:
        """Renvoie « pong » suivi du texte reçu."""
        calls.append(text)
        return f"pong {text}"

    h.upsert_agent(client, name, description="Agent de test SMO : appelle un custom tool.", environments=[],
                   instructions="Appelle smo_ping avec le texte demandé, puis réponds avec le résultat exact du tool.",
                   tools=[ToolDefinition(name="smo_ping", description="Renvoie « pong » suivi du texte reçu.",
                                         input_schema={"type": "object", "properties": {"text": {"type": "string"}},
                                                       "required": ["text"]})])
    try:
        session = client.sessions.create_session(agent=name, messages="Appelle smo_ping avec le texte « bonjour ».")
        for _ in client.session(session.id).stream(tools=[smo_ping], timeout_seconds=300):
            pass
        answer = client.sessions.get_session(session.id).latest_answer
    finally:
        client.agents.delete_agent(name)
    ok = bool(calls) and "pong" in json.dumps(answer, ensure_ascii=False, default=str)
    return Check("probe tool", "ok" if ok else "fail", f"appels reçus {calls} · réponse {str(answer)[:120]}")


def probe_devin(s: Settings, log) -> Check:
    """Créer une vraie session Devin (permission UseDevinSessions), plafonnée à 1 crédit, sans toucher à un repo."""
    api = devin.Devin(s.devin_api_key, s.devin_org_id)
    session = api.create_session("Test de SMO : réponds seulement « OK ». Ne clone aucun repo, n'ouvre aucune PR.",
                                 tags=["smo", "probe"], max_acu=1)
    devin_id = devin.session_id(session)
    status = api.get_session(devin_id).get("status")
    log(f"  session Devin : {session.get('url') or devin_id}")
    return Check("probe devin", "ok", f"session créée ({status}), 1 crédit au plus : {session.get('url') or devin_id}")


def probe_desktop_tool(s: Settings, log) -> Check:
    """Un tool de bureau livré avec la Skill : l'agent bureau trouve-t-il les fichiers de sa Skill, et peut-il lancer
    run.sh depuis son shell ? (là où un vrai tool de bureau tournera, sans rien installer chez l'utilisateur)"""
    from .pipeline import target

    client, name = h.client(s.hai_api_key), f"{s.agent_prefix}probe-desktop-tool"
    h.upsert_skill(client, "smo-probe-files", "Skill de test SMO : un fichier exécutable livré avec la Skill.",
                   "# Test\nLance `./run.sh` depuis le dossier de cette Skill et rapporte sa sortie exacte.\n",
                   files={"run.sh": "#!/bin/sh\necho \"pong depuis $(pwd)\"\ncommand -v cua python3\n"},
                   executable_files=["run.sh"])
    h.upsert_agent(client, name, description="Agent de test SMO : lance un fichier de sa Skill.",
                   environments=[target.desktop_environment(s)], skills=["smo-probe-files"],
                   instructions="Charge ta Skill smo-probe-files, lance ./run.sh depuis son dossier avec ton shell, "
                                "puis réponds avec le chemin du dossier et la sortie exacte de la commande.")
    try:
        session = client.sessions.create_session(agent=name, messages="Lance le run.sh de ta Skill smo-probe-files.")
        for _ in client.session(session.id).stream(timeout_seconds=600):
            pass
        answer = client.sessions.get_session(session.id).latest_answer
    finally:
        client.agents.delete_agent(name)
        client.skills.delete_skill("smo-probe-files")
    text = json.dumps(answer, ensure_ascii=False, default=str)
    return Check("probe desktop-tool", "ok" if "pong" in text else "fail", text[:300])


PROBES = {"skill": probe_skill, "guided": probe_guided, "tool": probe_tool, "devin": probe_devin,
          "desktop-tool": probe_desktop_tool}
NEEDS = {"devin": ("devin_api_key", "devin_org_id")}


def run(s: Settings, probes: list[str], log: Callable[[str], None] = print) -> bool:
    results = checks(s)
    for name in probes:
        log(f"… probe {name}")
        results.append(_guard(f"probe {name}", NEEDS.get(name, ("hai_api_key",)), s,
                              lambda name=name: PROBES[name](s, log)))
    for c in results:
        log(f"{ICON[c.state]} {c.name:<20} {c.detail}")
    return all(c.state in ("ok", "skip", "warn") for c in results)
