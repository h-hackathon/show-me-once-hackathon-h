"""Étape 3 : comprendre la démo, en deux passes.

Passe 1 (read) : Holo lit chaque capture avec la phrase dite à ce moment, une par appel, en parallèle → notes.json.
Passe 2 (understand) : un appel en texte seul assemble phrases et notes → étapes, règles, arrêts (procedure.json).
Aucun appel ne reçoit plus d'une image : sur une démo de plusieurs minutes, un appel unique avec toutes les
captures risquerait de survoler ou de perdre des détails.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ..clients import holo
from ..config import Settings
from ..models import (DocumentNote, DocumentReading, FrameSet, Notes, Procedure, ScreenNote, ScreenReading,
                      Transcript)
from ..runs import Run
from . import mapping


MAX_SCREENS = 60   # au-delà, captures prises à intervalles réguliers, dernière comprise (souvent « Enregistrer »)
WORKERS = 4        # appels Holo en parallèle

SCREEN_PROMPT = """Capture d'écran prise pendant que la personne disait : « {text} »
(phrase {n}/{total}, à {t:.0f} s ; phrase précédente : « {prev} »).
Décris ce qu'elle fait à ce moment. Rends UNIQUEMENT ce JSON :
{{"screen": "titre ou nom de l'écran visible",
 "action": "navigate|click|type|select|check|read|none",
 "target": "libellé exact de l'élément concerné, ou null",
 "value": "valeur saisie ou lue, ou null"}}
N'invente rien : si la capture ne montre pas l'action, mets "action": "none"."""

DOCUMENT_PROMPT = """Voici une pièce utilisée pendant une démonstration (par exemple une facture).
Rends UNIQUEMENT ce JSON : {"kind": "type de pièce", "fields": {"nom du champ": "valeur lue"}}
Recopie les valeurs exactement (montants, dates, numéros, taux de TVA)."""

SCHEMA = """{"task": "...", "software": "...",
 "steps": [{"index": 0, "action": "navigate|click|type|select|check|read", "target": "libellé visible de l'élément",
            "value_source": "d'où vient la valeur, ou null", "why": "la raison dite, ou null", "utterance_index": 0}],
 "rules": [{"text": "...", "kind": "check|exception|never|stop", "source": "voice|screen"}],
 "stop_conditions": ["quand s'arrêter et prévenir un humain"],
 "inputs": ["champ à lire sur la pièce à traiter"]}"""

SYNTH_PROMPT = """Un humain a fait une fois la tâche « {task} » dans le logiciel {software} ({url}), en commentant à voix haute.
Pour chaque phrase : ce qu'il a dit, puis ce qu'on voyait à l'écran à ce moment (lu sur la capture).

{lines}
{documents}{map}
Rends UNIQUEMENT un objet JSON de cette forme :
{schema}

Consignes :
- steps : chaque action à l'écran, dans l'ordre ; target = le libellé exact vu à l'écran (bouton, champ, menu).
- Si la carte du logiciel est fournie, prends ses libellés exacts et son chemin entre les écrans.
- value_source : relie chaque valeur saisie au champ de la pièce d'où elle vient, quand c'est possible.
- rules : les règles implicites (contrôles, exceptions, interdits), dites ou visibles.
- N'invente rien qui ne soit ni dit ni vu."""


# --- passe 1 -------------------------------------------------------------------------------------

def read_screen(run: Run, s: Settings, transcript: Transcript, index: int, shot: str) -> ScreenNote:
    utterances = transcript.utterances
    u = utterances[index]
    prompt = SCREEN_PROMPT.format(text=u.text, n=index + 1, total=len(utterances), t=u.start,
                                  prev=utterances[index - 1].text if index else "—")
    try:
        reading = holo.chat_model(prompt, ScreenReading, s.hai_api_key, s.holo_model, [run.file(shot)])
    except Exception as err:   # une capture illisible ne doit pas faire échouer toute la démo
        return ScreenNote(utterance_index=index, error=f"{type(err).__name__}: {str(err)[:200]}")
    return ScreenNote(utterance_index=index, **reading.model_dump())


def read_document(run: Run, s: Settings, path: str) -> DocumentNote:
    try:
        reading = holo.chat_model(DOCUMENT_PROMPT, DocumentReading, s.hai_api_key, s.holo_model, [run.file(path)])
    except Exception as err:   # comme une capture : une pièce illisible n'arrête pas la démo
        return DocumentNote(path=path, error=f"{type(err).__name__}: {str(err)[:200]}")
    return DocumentNote(path=path, **reading.model_dump())


def spread(items: list, n: int) -> list:
    """n éléments à intervalles réguliers, premier et dernier compris."""
    if len(items) <= n:
        return items
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def read(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    transcript = run.read_model("transcript.json", Transcript)
    frameset = run.read_model("frames.json", FrameSet)
    all_shots = [(f.utterance_index, f.path) for f in frameset.frames if f.utterance_index is not None]
    shots = spread(all_shots, MAX_SCREENS)
    started = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        screens = list(pool.map(lambda shot: read_screen(run, s, transcript, *shot), shots))
        documents = list(pool.map(lambda ref: read_document(run, s, ref.path), frameset.references[:3]))
    run.write_model("notes.json", Notes(screens=screens, documents=documents))
    unreadable = sum(1 for n in [*screens, *documents] if n.error)
    skipped = f", {len(all_shots) - len(shots)} ignorées (plus de {MAX_SCREENS})" if len(all_shots) > len(shots) else ""
    log(f"{len(screens)} captures lues{skipped}, {len(documents)} pièce(s) de référence, {unreadable} illisible(s) "
        f"· {s.holo_model} · {time.time() - started:.0f} s")


# --- passe 2 -------------------------------------------------------------------------------------

def _seen(note: ScreenNote) -> str:
    parts = [f"écran « {note.screen} »" if note.screen else None,
             f"{note.action} « {note.target} »" if note.target else (note.action if note.action != "none" else None),
             f"valeur {note.value}" if note.value not in (None, "") else None]
    return " · ".join(p for p in parts if p)


def synthesis_prompt(run: Run, transcript: Transcript, notes: Notes) -> str:
    meta = run.meta
    by_index = {n.utterance_index: n for n in notes.screens if not n.error}
    lines = []
    for u in transcript.utterances:
        line = f"[{u.start:6.1f}s] « {u.text} »"
        if u.index in by_index and (seen := _seen(by_index[u.index])):
            line += f"\n          vu : {seen}"
        lines.append(line)
    documents = "".join(
        f"\nPièce de référence ({Path(d.path).name}) : {d.kind or 'pièce'}\n"
        + "\n".join(f"  - {k} : {v}" for k, v in d.fields.items()) + "\n"
        for d in notes.documents if not d.error)
    soft_map = mapping.load(run)
    map_text = (f"\nCarte du logiciel, relevée par un agent qui l'a parcouru (libellés exacts) :\n"
                f"{mapping.summary(soft_map)}\n") if soft_map else ""
    return SYNTH_PROMPT.format(task=meta.task, software=meta.software_name or "web", url=meta.software_url,
                               lines="\n".join(lines), documents=documents, map=map_text, schema=SCHEMA)


def synthesize(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    transcript = run.read_model("transcript.json", Transcript)
    notes = run.read_model("notes.json", Notes)
    model = s.synth_model or s.holo_model
    started = time.time()
    procedure = holo.chat_model(synthesis_prompt(run, transcript, notes), Procedure, s.hai_api_key, model)
    run.write_model("procedure.json", procedure)
    log(f"{len(procedure.steps)} étapes, {len(procedure.rules)} règles · {model} · {time.time() - started:.0f} s")
