"""Étape map : un agent H parcourt le logiciel en lecture seule et relève les écrans de la tâche.

La démo donne la méthode (règles, pourquoi) ; la carte donne le terrain (écrans, chemin, libellés exacts).
Elle tourne en parallèle de la transcription et de la compréhension (voir orchestrator), puis sert à Holo
(Skill), à l'agent qui essaie (section « Carte du logiciel » de la Skill) et à Devin (contrat d'interface).

Elle est gardée par logiciel et par tâche dans runs/_maps/ : la capture suivante la réutilise tout de suite.
Un precheck qui voit l'interface changer l'efface (worker), et elle est refaite au run suivant.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from ..clients import h, holo
from ..config import Settings
from ..models import MapAnswer, SoftwareMap
from ..runs import Run, slug


PROMPT = """Tu cartographies un logiciel avant qu'un agent apprenne la tâche « {task} ».
Logiciel : {url}. Connexion : e-mail « {login} », mot de passe « {password} ».{dossier}
Parcours les écrans nécessaires à cette tâche, en LECTURE SEULE : ne crée, ne modifie, n'enregistre et ne valide
rien ; si un formulaire s'ouvre, n'y saisis rien et quitte-le.
Pour chaque écran utile, note : son nom (titre visible), son adresse (URL) si tu la vois, comment y arriver depuis
l'écran précédent (menus, boutons), les libellés exacts des champs et des boutons.
Signale dans notes les pièges vus (écran intermédiaire, fenêtre de confirmation, champ obligatoire).
Réponds au format demandé."""


def cache_path(s: Settings, software_url: str, task: str) -> Path:
    host = urlparse(software_url).netloc or software_url
    return s.runs_dir / "_maps" / f"{slug(host, max_len=60)}--{slug(task, max_len=40)}.json"


def forget(s: Settings, software_url: str) -> int:
    """L'interface a changé : on efface les cartes de ce logiciel (toutes tâches)."""
    host = slug(urlparse(software_url).netloc or software_url, max_len=60)
    maps = list((s.runs_dir / "_maps").glob(f"{host}--*.json")) if (s.runs_dir / "_maps").exists() else []
    for path in maps:
        path.unlink()
    return len(maps)


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta = run.meta
    cached = cache_path(s, meta.software_url, meta.task)
    if cached.exists():
        run.write_text("map.json", cached.read_text(encoding="utf-8"))
        log(f"carte déjà connue pour ce logiciel et cette tâche : {cached.name}")
        return

    prompt = PROMPT.format(task=meta.task, url=meta.software_url, login=s.site_login, password=s.site_password,
                           dossier=f"\nAprès la connexion, ouvre le dossier « {s.site_dossier} »." if s.site_dossier else "")
    client = h.client(s.hai_api_key)
    h.prepare_local_browser(meta.software_url)
    handle = client.start_session(agent=h.session_agent(s.replay_agent, meta.software_url, s.agent_model),
                                  messages=prompt, answer_schema=MapAnswer, timezone="Europe/Paris")
    log(f"cartographe : session H {handle.id}")
    events = list(h.stream_turn(handle, timeout_s=900))
    trace = h.build_trace(client, handle.id, run.file("map"), s.hai_api_key, events=events)
    answer = trace.answer
    if isinstance(answer, str):   # réponse au format imposé, rendue en texte JSON
        try:
            answer = holo.extract_json(answer)
        except ValueError:
            answer = None
    if not isinstance(answer, dict):
        raise RuntimeError(f"le cartographe n'a pas rendu de carte (réponse : {str(trace.answer)[:200]})")
    soft_map = SoftwareMap(**MapAnswer.model_validate(answer).model_dump(), software_url=meta.software_url,
                           task=meta.task, session_id=handle.id, replay_url=trace.agent_view_url)
    run.write_model("map.json", soft_map)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(soft_map.model_dump_json(indent=2), encoding="utf-8")
    log(f"{len(soft_map.screens)} écrans relevés : {', '.join(sc.name for sc in soft_map.screens)[:200]}")


def summary(soft_map: SoftwareMap) -> str:
    """La carte en quelques lignes, pour Holo, la Skill et Devin."""
    lines = []
    for sc in soft_map.screens:
        line = f"- {sc.name}" + (f" ({sc.url})" if sc.url else "")
        if sc.how_to_reach:
            line += f" : {sc.how_to_reach}"
        if sc.fields:
            line += f". Champs : {', '.join(sc.fields)}"
        if sc.buttons:
            line += f". Boutons : {', '.join(sc.buttons)}"
        lines.append(line)
    if soft_map.notes:
        lines.append(f"- Pièges : {soft_map.notes}")
    return "\n".join(lines)


def load(run: Run) -> SoftwareMap | None:
    return run.read_model("map.json", SoftwareMap) if run.has("map.json") else None
