"""Le driver : enchaîne les étapes d'un run, saute ce qui est déjà fait, s'arrête proprement sinon.

capture ─► transcribe ─► frames ─► understand ─► enrich ─► skill ─► review ─► provision ─► trial ─► compile ─► upgrade
           Gladia        ffmpeg     Holo (LLM)    Linkup    .md      humain     agent H     agent H   Devin      agent H
                                    info digeste  (option)                      + Skill     CU→trace  tool       + tool

L'agent existe dans H dès « provision » ; « trial » le fait travailler une fois à l'écran avec sa Skill, et sa trace
part chez Devin ; « upgrade » lui donne le tool. En exploitation, si le tool échoue, l'agent reprend en computer use
et sa nouvelle trace repart chez Devin (pipeline/compile.repair) pour corriger tool et Skill.
Chaque étape écrit un fichier dans runs/<id>/ : on peut relancer, reprendre, ou forcer une étape.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ..config import ENV, Settings
from ..runs import Run
from . import capture, compile, enrich, provision, skill, trial, understand


@dataclass(frozen=True)
class Stage:
    name: str
    fn: Callable
    needs: tuple[str, ...]                 # réglages indispensables (voir config.ENV)
    done: Callable[[Run], bool]
    optional: bool = False                 # réglage absent → étape sautée, la suite continue


STAGES = [
    Stage("transcribe", capture.transcribe, ("gladia_api_key",), lambda r: r.has("transcript.json")),
    Stage("frames", capture.frames, (), lambda r: r.has("frames.json")),
    Stage("understand", understand.run, ("hai_api_key",), lambda r: r.has("procedure.json")),
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
    for stage in STAGES[first:last]:
        if only and stage.name not in only:
            continue
        if stage.done(run) and not force:
            log(f"✓ {stage.name}")
            continue
        missing = [ENV[n] for n in stage.needs if not getattr(s, n)]
        if missing:
            if stage.optional:
                run.set_status(stage.name, "skipped", missing=missing)
                log(f"– {stage.name} sautée (manque {', '.join(missing)})")
                continue
            run.set_status(stage.name, "blocked", missing=missing)
            log(f"■ {stage.name} bloquée : à renseigner dans smo/.env → {', '.join(missing)}")
            return "blocked"

        run.set_status(stage.name, "running")
        log(f"▶ {stage.name}")
        started = time.time()
        extra = {"review": {"auto": auto}, "compile": {"wait": wait}, "trial": {"guided": guided}}.get(stage.name, {})
        try:
            state = stage.fn(run, s, lambda msg: log(f"  {msg}"), **extra)
        except Exception as err:
            run.set_status(stage.name, "failed", error=f"{type(err).__name__}: {err}")
            log(f"✗ {stage.name} : {type(err).__name__}: {err}")
            return "failed"
        if state == "waiting":
            run.set_status(stage.name, "waiting")
            return "waiting"
        run.set_status(stage.name, "done", seconds=round(time.time() - started, 1))
    return "done"
