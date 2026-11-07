"""Agents API de H : trace d'une session, création de Skill et d'agent custom (SDK hai_agents)."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx
from hai_agents import Client, ConflictError

from ..models import Trace, TraceStep


def client(api_key: str) -> Client:
    return Client(api_key=api_key)


def web_environment(start_url: str, host: str = "cloud") -> dict:
    """Navigateur cloud H (site en ligne), ou navigateur sur ta machine (host="user_device", site en localhost)."""
    return {"kind": "web", "id": "web", "host": host, "start_url": start_url}


def is_local(url: str) -> bool:
    return "localhost" in url or "127.0.0.1" in url


def browser_overrides(url: str) -> dict:
    """Garde l'agent H tel quel, mais ouvre son navigateur sur cette machine si le site est en localhost
    (le navigateur cloud de H ne voit pas localhost). Syntaxe : SessionRequest.overrides."""
    if not is_local(url):
        return {}
    return {"overrides": {"agent.environments[kind=web].host": "user_device",
                          "agent.environments[kind=web].start_url": url}}


def as_dict(event: Any) -> dict:
    return event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)


def _clip(text: Any, limit: int) -> str | None:
    if text is None:
        return None
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + " […]"


def _message_text(data: dict) -> str | None:
    if isinstance(data.get("message"), str):
        return data["message"]
    parts = [c.get("text") for c in data.get("content") or [] if isinstance(c, dict) and c.get("text")]
    return " ".join(parts) or None


def condense(events: list[dict]) -> tuple[list[TraceStep], list[tuple[int, dict]]]:
    """Événements bruts → une étape par observation (URL, titre, texte, capture) + les actions qui suivent.

    Renvoie aussi les images à enregistrer : [(index de l'étape, ImageContent)].
    """
    steps: list[TraceStep] = []
    images: list[tuple[int, dict]] = []
    instruction: str | None = None
    current: TraceStep | None = None
    for ev in events:
        kind_of_event, data = ev.get("type", ""), ev.get("data") or {}
        if "UserMessage" in kind_of_event:
            instruction = _message_text(data) or instruction
            continue
        if kind_of_event != "AgentEvent":
            continue
        kind = data.get("kind")
        if kind == "observation_event":
            meta = data.get("metadata") or {}
            current = TraceStep(index=len(steps), timestamp=ev.get("timestamp"), instruction=instruction,
                                url=meta.get("url"), title=meta.get("title"),
                                page_text=_clip(meta.get("text") or data.get("text"), 4000))
            steps.append(current)
            if data.get("image"):
                images.append((current.index, data["image"]))
        elif kind == "policy_event":
            if current is None or current.actions:
                current = TraceStep(index=len(steps), timestamp=ev.get("timestamp"), instruction=instruction)
                steps.append(current)
            current.reasoning = _clip(data.get("reasoning_content") or data.get("content"), 1500)
            current.actions = [{"tool_name": r.get("tool_name"), "args": r.get("args")}
                               for r in data.get("tool_reqs") or []]
        elif kind == "tool_result" and current is not None:
            current.results.append(_clip(data.get("result"), 1000))
    return steps, images


def save_screenshots(steps: list[TraceStep], images: list[tuple[int, dict]], out_dir: Path, api_key: str) -> None:
    """Enregistre les captures en local ; garde l'URL si le téléchargement échoue."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for index, image in images:
        path = out_dir / f"step-{index:03d}.png"
        source = image.get("source", "")
        try:
            if image.get("type") == "base64":
                path.write_bytes(base64.b64decode(source))
            else:
                r = httpx.get(source, headers={"Authorization": f"Bearer {api_key}"},
                              follow_redirects=True, timeout=60)
                r.raise_for_status()
                path.write_bytes(r.content)
            steps[index].screenshot = str(path)
        except (httpx.HTTPError, ValueError):
            steps[index].screenshot = source if source.startswith("http") else None


def build_trace(h: Client, session_id: str, out_dir: Path, api_key: str, events: list | None = None) -> Trace:
    """La trace d'une session (terminée ou en pause) : events.jsonl brut + captures + étapes condensées."""
    if events is None:
        events = list(h.session(session_id).stream(from_index=0, wait_for_seconds=0, timeout_seconds=300))
    raw = [as_dict(e) for e in events]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in raw), encoding="utf-8")
    steps, images = condense(raw)
    save_screenshots(steps, images, out_dir, api_key)
    session = h.sessions.get_session(session_id)
    agent = session.request.agent
    answer = next((e["data"].get("answer") for e in reversed(raw)
                   if (e.get("data") or {}).get("kind") == "answer_event"), None)
    return Trace(session_id=session_id, agent=agent if isinstance(agent, str) else agent.name,
                 status=str(session.status.status if hasattr(session.status, "status") else session.status),
                 steps=steps, answer=answer, agent_view_url=session.agent_view_url)


def drain(handle, events: list, timeout_s: float = 600) -> None:
    """Lit les événements jusqu'à ce que l'agent attende la consigne suivante (idle) ou ait fini.

    Le curseur du SDK = nombre d'événements déjà lus, d'où from_index=len(events).
    """
    for event in handle.stream(from_index=len(events), until="settled", timeout_seconds=timeout_s):
        events.append(event)


def wait_active(handle, timeout_s: float = 30) -> None:
    """Après send_message, l'agent peut rester idle une seconde : on attend qu'il reprenne."""
    deadline = time.monotonic() + timeout_s
    while handle.status().status == "idle" and time.monotonic() < deadline:
        time.sleep(1)


def upsert_skill(h: Client, name: str, description: str, body: str):
    try:
        return h.skills.create_skill(name=name, description=description, body=body)
    except ConflictError:
        return h.skills.update_skill(name, name=name, description=description, body=body)


def upsert_agent(h: Client, name: str, **spec):
    """Crée l'agent, ou ajoute une révision s'il existe déjà."""
    try:
        return h.agents.create_agent(name=name, **spec)
    except ConflictError:
        return h.agents.update_agent(name, name=name, **spec)
