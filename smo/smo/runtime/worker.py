"""Le worker répond aux custom tools des agents SMO, même quand la session est lancée depuis l'interface H.

Catherine lance son agent dans H → la session passe en « awaiting_tool_results » → H prévient le serveur
(webhook) ou le worker le voit en interrogeant H → le worker se rattache à la session et exécute les tools.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime

from ..clients import h
from ..config import Settings
from .tools import h_tools, load_tools


log = logging.getLogger("smo.worker")


class Worker:
    def __init__(self, s: Settings):
        s.require("hai_api_key")
        self.s = s
        self.h = h.client(s.hai_api_key)
        self.compiled = load_tools(s.tools_dir)
        self.active: set[str] = set()
        self.drifts: dict[str, list[dict]] = {}
        self.lock = threading.Lock()

    def is_managed(self, agent: str | None) -> bool:
        return bool(agent) and agent.startswith(self.s.agent_prefix)

    def agent_of(self, session_id: str) -> str | None:
        agent = self.h.sessions.get_session(session_id).request.agent
        return agent if isinstance(agent, str) else getattr(agent, "name", None)

    def attach(self, session_id: str) -> bool:
        """Sert la session dans un thread ; False si elle est déjà servie."""
        with self.lock:
            if session_id in self.active:
                return False
            self.active.add(session_id)
        threading.Thread(target=self._serve, args=(session_id,), daemon=True).start()
        return True

    def _serve(self, session_id: str) -> None:
        def on_drift(tool: str, details: str) -> None:
            self.drifts.setdefault(session_id, []).append({"tool": tool, "details": details})

        log.info("session %s : rattachée", session_id)
        try:
            tools = h_tools(self.compiled, self.s, on_drift)
            for _ in self.h.session(session_id).stream(tools=tools, until="settled", timeout_seconds=3600):
                pass
        except Exception:
            log.exception("session %s : erreur", session_id)
        finally:
            with self.lock:
                self.active.discard(session_id)
            for drift in self.drifts.pop(session_id, []):
                self._on_drift(session_id, drift)

    def _on_drift(self, session_id: str, drift: dict) -> None:
        """Garde une trace du changement d'interface et, si demandé, relance Devin."""
        record = {"session_id": session_id, "at": datetime.now().isoformat(timespec="seconds"), **drift}
        out = self.s.runs_dir / "_drifts" / f"{datetime.now():%Y%m%d-%H%M%S}-{session_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        log.warning("interface changée (%s) : %s", drift["tool"], drift["details"])
        if self.s.auto_repair:
            from ..pipeline.compile import repair
            tool = drift["tool"].removeprefix("run_").removeprefix("precheck_")
            repair(tool, session_id, drift["details"], self.s, log=log.info)

    def on_webhook(self, data: dict) -> bool:
        """Payload de session.status_updated : {session_id, status, previous_status}."""
        if data.get("status") != "awaiting_tool_results":
            return False
        session_id = data["session_id"]
        return self.is_managed(self.agent_of(session_id)) and self.attach(session_id)

    def poll_once(self) -> int:
        page = self.h.sessions.list_sessions(status="awaiting_tool_results", size=50)
        return sum(self.attach(s.id) for s in page.items if self.is_managed(s.agent))

    def poll_forever(self, interval_s: float = 5) -> None:
        """Filet de sécurité si le webhook n'est pas configuré (ou en local, sans URL publique)."""
        while True:
            try:
                self.poll_once()
            except Exception:
                log.exception("poll")
            time.sleep(interval_s)
