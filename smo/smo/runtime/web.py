"""Page d'enregistrement : la capture part du navigateur, le pipeline tourne ici, la page suit son avancement.

    GET  /                            la page (smo/web/)
    GET  /api/config                  valeurs par défaut et libellés des étapes
    POST /api/live                    ouvre une transcription Gladia en direct (le navigateur reçoit une URL à jeton)
    POST /api/captures                vidéo + tâche → nouveau run, pipeline lancé jusqu'à la relecture
    GET  /api/runs/{id}               état des étapes, Skill, liens, dernières lignes du journal
    PUT  /api/runs/{id}/skill         Skill corrigée par l'humain
    POST /api/runs/{id}/approve       Skill validée → le pipeline continue
    POST /api/runs/{id}/resume        relance après une attente (PR à fusionner) ou un échec
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..clients import gladia
from ..config import Settings
from ..models import CaptureMeta, CompileResult, Provisioned, SoftwareMap, Trace, Trial
from ..pipeline.orchestrator import NAMES, run_pipeline
from ..runs import Run
from .auth import token_checker


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD_MB = 500   # ~25 min d'écran enregistré par la page ; au-delà, 413

LABELS = {
    "map": "Cartographie du logiciel (agent H)",
    "docs": "Documentation du logiciel (Linkup)",
    "transcribe": "Transcription de la voix (Gladia)",
    "frames": "Captures d'écran, une par phrase",
    "read": "Lecture des écrans (Holo)",
    "understand": "Compréhension de la méthode (Holo)",
    "enrich": "Vérification des règles (Linkup)",
    "skill": "Skill écrite",
    "review": "Relecture de la Skill",
    "provision": "Agent créé dans H",
    "trial": "L'agent essaie la tâche à l'écran (3 essais max)",
    "compile": "Devin code le tool",
    "upgrade": "L'agent reçoit son tool",
}


class Runner:
    """Un pipeline à la fois par run, dans un thread ; son journal va dans runs/<id>/log.txt."""

    def __init__(self, s: Settings):
        self.s = s
        self.threads: dict[str, threading.Thread] = {}
        self.lock = threading.Lock()

    def busy(self, run_id: str) -> bool:
        thread = self.threads.get(run_id)
        return bool(thread and thread.is_alive())

    def start(self, run: Run) -> bool:
        with self.lock:
            if self.busy(run.id):
                return False
            thread = threading.Thread(target=self._go, args=(run,), daemon=True)
            self.threads[run.id] = thread
            thread.start()
            return True

    def _go(self, run: Run) -> None:
        def log(msg: str) -> None:
            with run.file("log.txt").open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%H:%M:%S} {msg}\n")
        try:
            log(f"→ {run_pipeline(run, self.s, auto=False, wait=True, log=log)}")
        except Exception as err:   # le thread ne doit pas mourir en silence
            log(f"✗ {type(err).__name__}: {err}")


class SkillText(BaseModel):
    skill: str


def overall(status: dict, busy: bool) -> str:
    states = [status.get(n, {}).get("state") for n in NAMES]
    for state in ("failed", "blocked", "waiting"):
        if state in states and not busy:
            return state
    if busy or "running" in states:
        return "running"
    return "done" if states[-1] == "done" else "idle"


def links(run: Run) -> dict:
    out: dict = {}
    if run.has("map.json"):
        out["map"] = run.read_model("map.json", SoftwareMap).replay_url
    if run.has("agent.json"):
        agent = run.read_model("agent.json", Provisioned)
        out |= {"agent": agent.agent_name, "tool_ready": agent.tool_ready}
    if run.has("trace.json"):
        out["trial_replay"] = run.read_model("trace.json", Trace).agent_view_url
    if run.has("compile.json"):
        compiled = run.read_model("compile.json", CompileResult)
        out |= {"devin": compiled.url, "pr": compiled.pr_url, "devin_report": compiled.report}
    return out


def attempts(run: Run) -> list[dict]:
    if not run.has("trial.json"):
        return []
    return [{"n": a.n, "success": a.verdict.success, "gap": a.verdict.gap, "lesson": a.verdict.lesson,
             "replay": a.replay_url} for a in run.read_model("trial.json", Trial).attempts]


def router_for(s: Settings) -> tuple[APIRouter, Runner]:
    router = APIRouter(prefix="/api")
    runner = Runner(s)
    check_token = token_checker(s)

    def open_run(run_id: str) -> Run:
        try:
            return Run.open(s.runs_dir, run_id)
        except FileNotFoundError:
            raise HTTPException(404, f"Run introuvable : {run_id}")

    @router.get("/config", dependencies=[Depends(check_token)])
    def config() -> dict:
        return {"site_url": s.site_url, "live": bool(s.gladia_api_key),
                "stages": [{"name": n, "label": LABELS[n]} for n in NAMES]}

    @router.post("/live", dependencies=[Depends(check_token)])
    def live() -> dict:
        if not s.gladia_api_key:
            raise HTTPException(503, "GLADIA_API_KEY absente")
        return {"url": gladia.start_live(s.gladia_api_key)["url"]}

    @router.post("/captures", dependencies=[Depends(check_token)])
    async def create_capture(video: UploadFile, task: str = Form(...), url: str = Form(...),
                             owner: str = Form("demo"), sample: str = Form(""), software_kind: str = Form("web"),
                             software_name: str = Form("")) -> dict:
        if software_kind not in ("web", "desktop"):
            raise HTTPException(422, "software_kind : web ou desktop")
        if software_kind == "desktop" and not s.h_desktop_env and os.environ.get("RAILWAY_ENVIRONMENT"):
            raise HTTPException(422, "Appli de bureau : renseigne H_DESKTOP_ENV, l'identifiant de l'environnement "
                                     "desktop de test configuré dans H.")
        folder = Path(tempfile.mkdtemp())
        dest = folder / f"capture{Path(video.filename or '').suffix or '.webm'}"
        size = 0
        with dest.open("wb") as fh:
            while chunk := await video.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1_000_000:
                    shutil.rmtree(folder)
                    raise HTTPException(413, f"Vidéo trop lourde (plus de {MAX_UPLOAD_MB} Mo)")
                fh.write(chunk)
        meta = CaptureMeta(task=task.strip(), software_kind=software_kind, software_url=url.strip(),
                           software_name=software_name.strip() or None, owner=owner.strip() or "demo",
                           sample=sample.strip() or None)
        run = Run.create(s.runs_dir, meta, [dest])
        shutil.rmtree(folder)
        runner.start(run)
        return {"run_id": run.id}

    @router.get("/runs/{run_id}", dependencies=[Depends(check_token)])
    def run_state(run_id: str) -> dict:
        run = open_run(run_id)
        status, busy = run.status(), runner.busy(run.id)
        log_lines = run.file("log.txt").read_text(encoding="utf-8").splitlines()[-12:] if run.has("log.txt") else []
        return {"id": run.id, "meta": run.meta.model_dump(mode="json"), "state": overall(status, busy), "busy": busy,
                "status": status, "approved": run.has("skill.approved"),
                "skill": run.file("skill.md").read_text(encoding="utf-8") if run.has("skill.md") else None,
                "links": links(run), "attempts": attempts(run), "log": log_lines}

    @router.put("/runs/{run_id}/skill", dependencies=[Depends(check_token)])
    def save_skill(run_id: str, body: SkillText) -> dict:
        open_run(run_id).write_text("skill.md", body.skill.rstrip() + "\n")
        return {"saved": True}

    @router.post("/runs/{run_id}/approve", dependencies=[Depends(check_token)])
    def approve(run_id: str) -> dict:
        run = open_run(run_id)
        run.write_text("skill.approved", "ok\n")
        return {"started": runner.start(run)}

    @router.post("/runs/{run_id}/resume", dependencies=[Depends(check_token)])
    def resume(run_id: str) -> dict:
        return {"started": runner.start(open_run(run_id))}

    return router, runner
