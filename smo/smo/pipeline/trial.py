"""Étape 9 : l'agent H essaie la tâche à l'écran, seul, avec sa Skill ; Holo juge ; on recommence si besoin.

    démo → Skill → essai 1 → Holo compare l'écran final de l'agent à la fin de la démo
                               ├─ oui : cet essai part chez Devin (trace.json)
                               └─ non : la leçon entre dans la Skill, nouvel essai (MAX_ATTEMPTS au plus)

Chaque essai repart de zéro (nouvelle session, logiciel vidé) : on prouve que la Skill seule suffit, comme pour
les futurs runs de l'agent. Après MAX_ATTEMPTS échecs, l'étape attend l'humain (Skill à corriger, puis relance).
Option --guided : l'agent est guidé phrase par phrase par ce que l'humain a dit (replay.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..clients import h, holo
from ..clients.site import Site
from ..config import Settings
from ..models import Attempt, FrameSet, Provisioned, Trace, Trial, Verdict
from ..runs import Run
from ..runtime.tools import h_tools, load_tools
from ..runtime.worker import SERVED_ELSEWHERE
from . import replay
from .provision import skill_description
from .skill import tool_name


MAX_ATTEMPTS = 3
LESSONS = "## Leçons des essais"

TASK = """Traite la pièce {sample} en suivant ta Skill, du début à la fin, en computer use.
Connexion : e-mail « {login} », mot de passe « {password} ».{dossier}
Ne clique jamais sur « Valider » : la pièce reste en brouillon."""

JUDGE = """Tâche : « {task} ».
Image 1 : l'écran à la fin de la démonstration de l'humain (le résultat attendu).
Image 2 : l'écran à la fin de l'essai de l'agent.
Réponse de l'agent : {answer}
L'agent a-t-il obtenu le même résultat que l'humain ? Rends UNIQUEMENT ce JSON :
{{"success": true ou false, "gap": "ce qui diffère, ou null",
 "lesson": "une consigne courte pour réussir au prochain essai, ou null"}}"""

JUDGE_WITHOUT_DEMO = """Tâche : « {task} ».
L'image est l'écran à la fin de l'essai de l'agent. Réponse de l'agent : {answer}
La tâche est-elle accomplie ? Rends UNIQUEMENT ce JSON :
{{"success": true ou false, "gap": "ce qui manque, ou null",
 "lesson": "une consigne courte pour réussir au prochain essai, ou null"}}"""


def demo_end(run: Run) -> Path | None:
    """Le résultat attendu : la dernière image de la vidéo de démo."""
    frameset = run.read_model("frames.json", FrameSet) if run.has("frames.json") else None
    return run.file(frameset.final) if frameset and frameset.final else None


def agent_end(trace: Trace) -> Path | None:
    shot = next((st.screenshot for st in reversed(trace.steps)
                 if st.screenshot and not st.screenshot.startswith("http")), None)
    return Path(shot) if shot else None


def judge(run: Run, s: Settings, trace: Trace) -> Verdict:
    end = agent_end(trace)
    if end is None:
        return Verdict(success=False, gap="aucune capture de l'écran final de l'agent")
    expected = demo_end(run)
    prompt = (JUDGE if expected else JUDGE_WITHOUT_DEMO).format(task=run.meta.task, answer=str(trace.answer)[:1500])
    return holo.chat_model(prompt, Verdict, s.hai_api_key, s.holo_model, [expected, end] if expected else [end])


def attempt(run: Run, s: Settings, n: int, agent: Provisioned, task: str, log: Callable[[str], None]) -> Trace:
    """Un essai : nouvelle session de l'agent, ses tools servis ici, trace dans trials/<n>/."""
    compiled = load_tools(s.tools_dir)
    tname = tool_name(run)
    tools = h_tools({tname: compiled[tname]} if agent.tool_ready else {}, s, on_drift=lambda *_: None)
    client = h.client(s.hai_api_key)
    h.prepare_local_browser(run.meta.software_url)
    handle = client.start_session(agent=agent.agent_name, messages=task, timezone="Europe/Paris")
    log(f"essai {n} : session H {handle.id}")
    SERVED_ELSEWHERE.add(handle.id)   # c'est nous qui servons ses tools, pas le worker du serveur
    try:
        events = list(h.stream_turn(handle, tools=tools, timeout_s=1800))   # session neuve : pas d'ancien « idle »
    finally:
        SERVED_ELSEWHERE.discard(handle.id)
    return h.build_trace(client, handle.id, run.file(f"trials/{n}"), s.hai_api_key, events=events)


def add_lesson(run: Run, n: int, verdict: Verdict) -> str:
    skill = run.file("skill.md").read_text(encoding="utf-8").rstrip()
    lesson = verdict.lesson or verdict.gap
    if lesson:
        if LESSONS not in skill:
            skill += f"\n\n{LESSONS}"
        skill += f"\n- Essai {n} : {lesson}"
    run.write_text("skill.md", skill + "\n")
    return skill + "\n"


def run(run: Run, s: Settings, log: Callable[[str], None], guided: bool = False) -> str | None:
    if guided:
        return replay.run(run, s, log)
    meta, agent = run.meta, run.read_model("agent.json", Provisioned)
    task = TASK.format(sample=meta.sample or "de la démonstration", login=s.site_login, password=s.site_password,
                       dossier=f"\nAprès la connexion, ouvre le dossier « {s.site_dossier} »." if s.site_dossier else "")
    site = Site(s.site_url, s.site_admin_token) if s.site_url and s.site_admin_token else None
    client = h.client(s.hai_api_key)
    # La Skill a pu être corrigée par l'humain depuis la création de l'agent : H doit avoir la dernière version.
    h.upsert_skill(client, agent.skill_name, description=skill_description(run),
                   body=run.file("skill.md").read_text(encoding="utf-8"))

    trial = Trial()
    for n in range(1, MAX_ATTEMPTS + 1):
        if site:
            site.reset()   # sinon l'essai suivant serait refusé comme doublon
        trace = attempt(run, s, n, agent, task, log)
        verdict = judge(run, s, trace)
        trial.attempts.append(Attempt(n=n, session_id=trace.session_id, replay_url=trace.agent_view_url,
                                      answer=trace.answer, verdict=verdict))
        trial.success = verdict.success
        run.write_model("trial.json", trial)
        if verdict.success:
            run.write_model("trace.json", trace)   # c'est cet essai que Devin compile
            log(f"essai {n} réussi")
            return None
        log(f"essai {n} raté : {verdict.gap or 'résultat différent de la démo'}")
        body = add_lesson(run, n, verdict)
        h.upsert_skill(client, agent.skill_name, description=skill_description(run), body=body)
        if verdict.lesson:
            log(f"leçon ajoutée à la Skill : {verdict.lesson}")
    log(f"{MAX_ATTEMPTS} essais sans réussite : relis la Skill (leçons comprises), puis relance")
    return "waiting"
