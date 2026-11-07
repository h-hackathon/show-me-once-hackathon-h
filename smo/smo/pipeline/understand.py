"""Étape 3 : Holo relie chaque phrase à ce qui est à l'écran → la procédure et les règles implicites."""
from __future__ import annotations

from typing import Callable

from ..clients import holo
from ..config import Settings
from ..models import Frame, FrameSet, Procedure, Transcript
from ..runs import Run


MAX_FRAMES = 12   # au-delà, la requête devient lourde pour Holo

PROMPT = """Un humain a fait une fois la tâche « {task} » dans le logiciel {software} ({url}), en commentant à voix haute.
Voici ce qu'il a dit, phrase par phrase, avec l'heure. Images jointes, dans l'ordre : {legend}.

{lines}

Rends UNIQUEMENT un objet JSON de cette forme :
{{"task": "...", "software": "...",
 "steps": [{{"index": 0, "action": "navigate|click|type|select|check|read", "target": "libellé visible de l'élément",
            "value_source": "d'où vient la valeur, ou null", "why": "la raison dite, ou null", "utterance_index": 0}}],
 "rules": [{{"text": "...", "kind": "check|exception|never|stop", "source": "voice|screen"}}],
 "stop_conditions": ["quand s'arrêter et prévenir un humain"],
 "inputs": ["champ à lire sur la pièce à traiter"]}}

Consignes :
- steps : chaque action à l'écran, dans l'ordre ; target = le libellé exact visible (bouton, champ, menu).
- rules : les règles implicites (contrôles, exceptions, interdits), dites ou visibles.
- N'invente rien qui ne soit ni dit ni visible."""


def sample(frames: list[Frame], n: int) -> list[Frame]:
    if len(frames) <= n:
        return frames
    step = len(frames) / n
    return [frames[int(i * step)] for i in range(n)]


def build_prompt(run: Run, transcript: Transcript, picked: list[Frame], references: list[Frame]) -> str:
    meta = run.meta
    image_of = {f.utterance_index: n for n, f in enumerate(picked, 1)}
    lines = "\n".join(
        f"[{u.start:6.1f}s]{f' [image {image_of[u.index]}]' if u.index in image_of else ''} « {u.text} »"
        for u in transcript.utterances)
    legend = [f"images 1 à {len(picked)} = captures d'écran des phrases marquées [image n]"] if picked else []
    legend += [f"image {len(picked) + k} = pièce de référence ({r.path.rsplit('/', 1)[-1]})"
               for k, r in enumerate(references, 1)]
    return PROMPT.format(task=meta.task, software=meta.software_name or "web", url=meta.software_url,
                         legend=" ; ".join(legend) or "aucune", lines=lines)


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    transcript = run.read_model("transcript.json", Transcript)
    frameset = run.read_model("frames.json", FrameSet)
    picked, references = sample(frameset.frames, MAX_FRAMES), frameset.references[:2]
    prompt = build_prompt(run, transcript, picked, references)
    images = [run.file(f.path) for f in picked + references]
    procedure = holo.chat_model(prompt, Procedure, s.hai_api_key, s.holo_model, images)
    run.write_model("procedure.json", procedure)
    log(f"{len(procedure.steps)} étapes, {len(procedure.rules)} règles ({s.holo_model})")
