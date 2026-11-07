"""Étape 6 : l'agent H refait la tâche, guidé phrase par phrase par ce que l'humain a dit.

La trace de sa session (URL, titres, texte des pages, actions, captures) donne à Devin
ce que la vidéo ne donne pas : les écrans exacts et les libellés réels.
"""
from __future__ import annotations

from typing import Callable

from ..clients import h
from ..config import Settings
from ..models import Procedure, Transcript
from ..runs import Run


INTRO = """Tu vas refaire une tâche dans le logiciel {url}, guidé pas à pas par la personne qui l'a montrée.
Tâche : {task}.{sample}
Connexion : e-mail « {login} », mot de passe « {password} ».{dossier}
Dans chaque message, fais uniquement l'étape demandée, puis arrête-toi et attends la suivante.
Ne clique jamais sur « Valider » ni « Confirmer » : la pièce reste en brouillon.
Commence par te connecter, puis attends la première étape."""

VERB = {"navigate": "va sur", "click": "clique sur", "type": "remplis", "select": "choisis dans",
        "check": "vérifie", "read": "lis"}


def instructions(procedure: Procedure, transcript: Transcript) -> list[str]:
    said = {u.index: u.text for u in transcript.utterances}
    total, out = len(procedure.steps), []
    for st in procedure.steps:
        msg = f"Étape {st.index + 1}/{total} : {VERB[st.action]} « {st.target} »"
        if st.value_source:
            msg += f" (valeur : {st.value_source})"
        if st.utterance_index in said:
            msg += f". La personne avait dit : « {said[st.utterance_index]} »"
        out.append(msg + ".")
    out.append("C'est fini. Ne valide rien. Résume ce que tu as fait et les valeurs saisies.")
    return out


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta = run.meta
    procedure = run.read_model("procedure.json", Procedure)
    transcript = run.read_model("transcript.json", Transcript)
    intro = INTRO.format(
        url=meta.software_url, task=meta.task, login=s.site_login, password=s.site_password,
        sample=f"\nPièce à traiter : {meta.sample}." if meta.sample else "",
        dossier=f"\nAprès la connexion, ouvre le dossier « {s.site_dossier} »." if s.site_dossier else "")

    client = h.client(s.hai_api_key)
    handle = client.start_session(agent=s.replay_agent, messages=intro, idle_timeout_s=900, timezone="Europe/Paris")
    run.write_json("replay_session.json", {"session_id": handle.id})
    log(f"session H {handle.id}")

    events: list = []
    h.drain(handle, events)
    for msg in instructions(procedure, transcript):
        log(f"→ {msg[:110]}")
        handle.send_message(msg)
        h.wait_active(handle)
        h.drain(handle, events)
    handle.cancel()   # sinon la session reste ouverte idle_timeout_s

    trace = h.build_trace(client, handle.id, run.file("trace"), s.hai_api_key, events=events)
    run.write_model("trace.json", trace)
    log(f"{len(trace.steps)} étapes tracées ; replay : {trace.agent_view_url or '—'}")
