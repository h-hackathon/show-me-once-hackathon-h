"""Étape 9 : l'agent custom fait la tâche une fois en computer use, avec sa Skill et sans tool.

C'est le test de la Skill : sa trace (écrans, libellés, actions réelles) est ce que Devin compile en tool.
On relit aussi ce qui est réellement enregistré dans le logiciel (on ne croit jamais l'agent sur parole).
Option --guided : l'agent est guidé phrase par phrase par ce que l'humain a dit (replay.py).
"""
from __future__ import annotations

from typing import Callable

from ..clients import h
from ..clients.site import Site
from ..config import Settings
from ..models import Provisioned
from ..runs import Run
from ..runtime.tools import h_tools, load_tools
from . import replay
from .skill import tool_name


TASK = """Traite la pièce {sample} en suivant ta Skill, du début à la fin, en computer use.
Connexion : e-mail « {login} », mot de passe « {password} ».{dossier}
Ne clique jamais sur « Valider » : la pièce reste en brouillon."""


def run(run: Run, s: Settings, log: Callable[[str], None], guided: bool = False) -> None:
    if guided:
        return replay.run(run, s, log)
    meta, agent = run.meta, run.read_model("agent.json", Provisioned)
    task = TASK.format(sample=meta.sample or "de la démonstration", login=s.site_login, password=s.site_password,
                       dossier=f"\nAprès la connexion, ouvre le dossier « {s.site_dossier} »." if s.site_dossier else "")

    # L'agent déclare ses tools (au moins report_drift, check_supplier, verify_entry) : c'est nous qui les exécutons.
    compiled = load_tools(s.tools_dir)
    tname = tool_name(run)
    drifts: list[tuple[str, str]] = []
    tools = h_tools({tname: compiled[tname]} if agent.tool_ready else {}, s, on_drift=lambda *d: drifts.append(d))

    client = h.client(s.hai_api_key)
    h.prepare_local_browser(meta.software_url)
    handle = client.start_session(agent=agent.agent_name, messages=task, timezone="Europe/Paris")
    run.write_json("trial_session.json", {"session_id": handle.id})
    log(f"session H {handle.id} (agent {agent.agent_name})")
    events = list(handle.stream(tools=tools, until="settled", timeout_seconds=1800))

    trace = h.build_trace(client, handle.id, run.file("trace"), s.hai_api_key, events=events)
    run.write_model("trace.json", trace)
    saved = Site(s.site_url, s.site_admin_token).invoices() if s.site_url and s.site_admin_token else None
    run.write_json("trial.json", {"session_id": handle.id, "answer": trace.answer, "drifts": drifts,
                                  "saved_in_software": saved})
    log(f"{len(trace.steps)} étapes · réponse : {str(trace.answer)[:160]}")
    if saved is not None:
        log(f"{len(saved)} pièce(s) réellement enregistrée(s) dans le logiciel")
