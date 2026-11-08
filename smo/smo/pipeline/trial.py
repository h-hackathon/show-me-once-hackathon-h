"""Étape 9 : l'agent H essaie la tâche à l'écran, seul, avec sa Skill ; Holo juge ; on recommence si besoin.

    démo → Skill → essai 1 → Holo compare l'écran final de l'agent à la fin de la démo
                               ├─ oui : cet essai part chez Devin (trace.json)
                               └─ non : la leçon entre dans la Skill, nouvel essai (MAX_ATTEMPTS au plus)

Chaque essai part d'une nouvelle session : on prouve que la Skill seule suffit, comme pour les futurs runs.
L'agent reçoit la demande d'essai comme un vrai utilisateur la lui enverrait (« Saisis la facture jointe »), avec
ses pièces jointes (trial_request.json, trial_files/) : Holo la propose, l'humain la corrige à la relecture.
Rien n'est supprimé entre deux essais. Après MAX_ATTEMPTS échecs, l'étape attend l'humain (Skill à corriger, relance).
Option --guided : l'agent est guidé phrase par phrase par ce que l'humain a dit (replay.py).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from hai_agents import file_from_path

from ..clients import h, holo
from ..config import Settings
from ..models import Attempt, FrameSet, Procedure, Provisioned, Trace, Trial, TrialRequest, Verdict
from ..runs import Run
from ..runtime.tools import find, for_site, h_tools
from ..runtime.worker import SERVED_ELSEWHERE
from . import replay, target
from .provision import push_skill
from .skill import NEVER_FINALIZE, tool_name


MAX_ATTEMPTS = 3
LESSONS = "## Leçons des essais"

TASK = """{request}

Suis ta Skill, du début à la fin, dans {where}.
{login_hint}
{dossier_rule}
""" + NEVER_FINALIZE

JUDGE = """Tâche : « {task} ». L'humain l'a faite une fois pendant la démonstration. L'agent a reçu la demande :
« {request} »{files}.
Image 1 : l'écran à la fin de la démonstration de l'humain (le résultat attendu, pour sa pièce à lui).
Image 2 : l'écran à la fin de l'essai de l'agent.
Réponse de l'agent : {answer}
L'agent a-t-il obtenu le résultat équivalent pour sa demande (même étape atteinte, champs remplis avec les valeurs
de ses pièces) ? {draft}
Rends UNIQUEMENT ce JSON :
{{"success": true ou false, "gap": "ce qui diffère, ou null",
 "lesson": "une consigne courte pour réussir au prochain essai, ou null"}}"""

JUDGE_WITHOUT_DEMO = """Tâche : « {task} ».
L'image est l'écran à la fin de l'essai de l'agent. Réponse de l'agent : {answer}
La tâche est-elle accomplie ? {draft}
Rends UNIQUEMENT ce JSON :
{{"success": true ou false, "gap": "ce qui manque, ou null",
 "lesson": "une consigne courte pour réussir au prochain essai, ou null"}}"""


# Les essais s'arrêtent avant de finaliser (consigne TASK) : le juge ne doit ni le compter comme un échec, ni en tirer
# une leçon qui ferait finaliser, même si l'écran de fin de la démo montre des pièces déjà finalisées.
DRAFT_RULE = ("Le résultat attendu est un travail enregistré sans être finalisé (brouillon, en attente) : ce n'est pas "
              "un échec ; une action définitive (validation, envoi, paiement, suppression) en est un. Aucune leçon ne "
              "doit pousser à finaliser.")

FILES_DIR = "trial_files"


def trial_request(run: Run) -> TrialRequest:
    """La demande d'essai relue par l'humain, sinon celle que Holo a proposée, sinon la tâche elle-même."""
    if run.has("trial_request.json"):
        return run.read_model("trial_request.json", TrialRequest)
    proposed = run.read_model("procedure.json", Procedure).request if run.has("procedure.json") else None
    return TrialRequest(message=proposed or f"{run.meta.task}.")


def trial_files(run: Run, request: TrialRequest) -> list[Path]:
    return [run.file(f"{FILES_DIR}/{name}") for name in request.files if run.has(f"{FILES_DIR}/{name}")]


def demo_end(run: Run) -> Path | None:
    """Le résultat attendu : la dernière image de la vidéo de démo."""
    frameset = run.read_model("frames.json", FrameSet) if run.has("frames.json") else None
    return run.file(frameset.final) if frameset and frameset.final else None


def agent_end(trace: Trace) -> Path | None:
    shot = next((st.screenshot for st in reversed(trace.steps)
                 if st.screenshot and not st.screenshot.startswith("http")), None)
    return Path(shot) if shot else None


def judge(run: Run, s: Settings, trace: Trace, request: TrialRequest) -> Verdict:
    end = agent_end(trace)
    if end is None:
        return Verdict(success=False, gap="aucune capture de l'écran final de l'agent")
    expected = demo_end(run)
    prompt = (JUDGE if expected else JUDGE_WITHOUT_DEMO).format(
        task=run.meta.task, request=request.message,
        files=f", avec les pièces jointes {', '.join(request.files)}" if request.files else "",
        answer=str(trace.answer)[:1500], draft=DRAFT_RULE)
    return holo.chat_model(prompt, Verdict, s.hai_api_key, s.holo_model, [expected, end] if expected else [end])


def attempt(run: Run, s: Settings, n: int, agent: Provisioned, task: str, files: list[Path],
            log: Callable[[str], None]) -> Trace:
    """Un essai : nouvelle session de l'agent, pièces jointes au message (H les pose sur sa workstation), ses tools
    servis ici, trace dans trials/<n>/."""
    tname = tool_name(run)
    tool = find(s, tname) if agent.tool_ready else None
    tools = h_tools({tname: tool} if tool else {}, s, on_drift=lambda *_: None,
                    context=for_site(s, run.meta.software_url))
    client = h.client(s.hai_api_key)
    target.prepare(run.meta)
    messages = [{"type": "user_message", "message": task, "files": [file_from_path(f) for f in files]}] if files else task
    handle = client.start_session(agent=agent.agent_name, messages=messages, timezone="Europe/Paris")
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
    tool = find(s, tool_name(run)) if agent.tool_ready else None
    client = h.client(s.hai_api_key)
    # l'agent a le vault sur son navigateur (provision) : la consigne ne contient aucun mot de passe
    login_hint = target.login_hint(meta, s, target.vault_item(meta, s, client))
    # La Skill a pu être corrigée par l'humain depuis la création de l'agent : H doit avoir la dernière version.
    push_skill(client, run, s, tool, run.file("skill.md").read_text(encoding="utf-8"))

    request = trial_request(run)
    files = trial_files(run, request)
    task = TASK.format(request=request.message, where=target.where(meta), login_hint=login_hint,
                       dossier_rule=target.DOSSIER_RULE)
    trial = Trial()
    for n in range(1, MAX_ATTEMPTS + 1):
        log(f"essai {n} : « {request.message} »" + (f" + {', '.join(f.name for f in files)}" if files else ""))
        trace = attempt(run, s, n, agent, task, files, log)
        verdict = judge(run, s, trace, request)
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
        push_skill(client, run, s, tool, body)
        if verdict.lesson:
            log(f"leçon ajoutée à la Skill : {verdict.lesson}")
    log(f"{MAX_ATTEMPTS} essais sans réussite : relis la Skill (leçons comprises), puis relance")
    return "waiting"
