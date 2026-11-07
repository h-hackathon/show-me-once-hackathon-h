"""Le driver : enchaîne les étapes d'un run, saute ce qui est déjà fait, s'arrête proprement sinon.

capture ─► transcribe ─► frames ─► read ─────► understand ─► enrich ─► skill ─► review ─► provision ─► trial ─► compile ─► upgrade
           Gladia        ffmpeg     Holo,        Holo, texte    Linkup    .md      humain     agent H     agent H   Devin      agent H
                                    1 capture    seul : étapes  (option)                      + Skill     CU→trace  tool       + tool
                                    par appel    et règles

L'agent existe dans H dès « provision » ; « trial » le fait travailler une fois à l'écran avec sa Skill, et sa trace
part chez Devin ; « upgrade » lui donne le tool. En exploitation, si le tool échoue, l'agent reprend en computer use
et sa nouvelle trace repart chez Devin (pipeline/compile.repair) pour corriger tool et Skill.
Chaque étape écrit un fichier dans runs/<id>/ : on peut relancer, reprendre, ou forcer une étape.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..config import ENV, Settings
from ..runs import Run
from . import capture, compile, enrich, mapping, provision, skill, trial, understand


@dataclass(frozen=True)
class Stage:
    name: str
    fn: Callable
    needs: tuple[str, ...]                 # réglages indispensables (voir config.ENV)
    done: Callable[[Run], bool]
    optional: bool = False                 # réglage absent ou échec → étape sautée, la suite continue
    join_before: str | None = None         # lancée en parallèle dès le début, attendue avant cette étape


STAGES = [
    Stage("map", mapping.run, ("hai_api_key", "site_login", "site_password"), lambda r: r.has("map.json"),
          optional=True, join_before="understand"),
    Stage("transcribe", capture.transcribe, ("gladia_api_key",), lambda r: r.has("transcript.json")),
    Stage("frames", capture.frames, (), lambda r: r.has("frames.json")),
    Stage("read", understand.read, ("hai_api_key",), lambda r: r.has("notes.json") or r.has("procedure.json")),
    Stage("understand", understand.synthesize, ("hai_api_key",), lambda r: r.has("procedure.json")),
    Stage("enrich", enrich.run, ("linkup_api_key",), lambda r: r.has("context.json"), optional=True),
    Stage("skill", skill.run, (), lambda r: r.has("skill.md")),
    Stage("review", skill.review, (), lambda r: r.has("skill.approved")),
    Stage("provision", provision.create, ("hai_api_key",), lambda r: r.has("agent.json")),
    Stage("trial", trial.run, ("hai_api_key", "site_login", "site_password"), lambda r: r.has("trace.json")),
    Stage("compile", compile.run, ("devin_api_key", "devin_org_id"), compile.is_done),
    Stage("upgrade", provision.upgrade, ("hai_api_key",), provision.tool_ready),
]
NAMES = [st.name for st in STAGES]


def run_pipeline(run: Run, s: Settings, *, start: str | None = None, stop: str | None = None,
                 only: list[str] | None = None, force: bool = False, auto: bool = False, wait: bool = True,
                 guided: bool = False, log: Callable[[str], None] = print) -> str:
    """Renvoie "done", "waiting" (Devin ou relecture humaine), "blocked" (réglage manquant) ou "failed"."""
    first = NAMES.index(start) if start else 0
    last = NAMES.index(stop) + 1 if stop else len(STAGES)
    selected = [st for st in STAGES[first:last] if not only or st.name in only]
    extras = {"review": {"auto": auto}, "compile": {"wait": wait}, "trial": {"guided": guided}}

    background: dict[str, tuple[Stage, threading.Thread]] = {}
    for stage in selected:
        if stage.join_before and not (stage.done(run) and not force):
            thread = threading.Thread(target=_execute, args=(stage, run, s, log, {}), daemon=True)
            thread.start()
            background[stage.join_before] = (stage, thread)

    for stage in selected:
        if stage.join_before:
            continue                                   # tourne déjà en parallèle
        if stage.name in background:
            waited, thread = background.pop(stage.name)
            if thread.is_alive():
                log(f"… attente de {waited.name}")
            thread.join(timeout=900)
        if stage.done(run) and not force:
            log(f"✓ {stage.name}")
            continue
        state = _execute(stage, run, s, log, extras.get(stage.name, {}))
        if state in ("blocked", "failed", "waiting"):
            return state
    for _, thread in background.values():           # ex. `--only map`, ou arrêt avant l'étape qui l'attend
        thread.join(timeout=900)
    return "done"


def _execute(stage: Stage, run: Run, s: Settings, log: Callable[[str], None], extra: dict) -> str:
    """Une étape : statut, durée, erreurs. Renvoie done, skipped, waiting, blocked ou failed."""
    missing = [ENV[n] for n in stage.needs if not getattr(s, n)]
    if missing:
        if stage.optional:
            run.set_status(stage.name, "skipped", missing=missing)
            log(f"– {stage.name} sautée (manque {', '.join(missing)})")
            return "skipped"
        run.set_status(stage.name, "blocked", missing=missing)
        log(f"■ {stage.name} bloquée : à renseigner dans smo/.env → {', '.join(missing)}")
        return "blocked"

    run.set_status(stage.name, "running")
    log(f"▶ {stage.name}")
    started = time.time()
    try:
        state = stage.fn(run, s, lambda msg: log(f"  {msg}"), **extra)
    except Exception as err:
        run.set_status(stage.name, "failed", error=f"{type(err).__name__}: {err}")
        log(f"✗ {stage.name} : {type(err).__name__}: {err}")
        return "skipped" if stage.optional else "failed"
    if state == "waiting":
        run.set_status(stage.name, "waiting")
        return "waiting"
    run.set_status(stage.name, "done", seconds=round(time.time() - started, 1))
    return "done"
