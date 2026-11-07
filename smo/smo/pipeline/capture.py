"""Étapes 1-2 : la voix (Gladia) et les images (ffmpeg) de la capture."""
from __future__ import annotations

import shutil
import subprocess
from typing import Callable

import imageio_ffmpeg

from ..clients import gladia
from ..config import Settings
from ..models import Frame, FrameSet, Transcript
from ..runs import Run


def _ffmpeg(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *args], check=True)


def transcribe(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    audio = run.audio()
    if audio is None:
        video = run.video()
        if video is None:
            raise RuntimeError("La capture ne contient ni vidéo ni audio.")
        audio = run.file("capture/audio-extrait.wav")
        _ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(audio))
    transcript = gladia.transcribe(audio, s.gladia_api_key, run.meta.language)
    run.write_model("transcript.json", transcript)
    log(f"{len(transcript.utterances)} phrases transcrites")


FPS = 1   # une image par seconde suffit : on garde ensuite la plus proche du milieu de chaque phrase


def frames(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    """Une capture d'écran au milieu de chaque phrase : ce que l'humain regardait quand il parlait.

    Un seul passage ffmpeg à FPS images/s plutôt qu'un saut à chaque instant : les .webm de MediaRecorder
    (page d'enregistrement) n'ont pas d'index et s'y positionnent mal.
    """
    transcript = run.read_model("transcript.json", Transcript)
    references = [Frame(utterance_index=None, time_s=None, path=str(p.relative_to(run.path))) for p in run.images()]
    shots: list[Frame] = []
    video = run.video()
    if video:
        every = run.file("frames/all")
        every.mkdir(parents=True, exist_ok=True)
        _ffmpeg("-i", str(video), "-vf", f"fps={FPS},scale='min(1280,iw)':-2", str(every / "f%05d.png"))
        stills = sorted(every.glob("f*.png"))          # f00001.png = l'image de 0 à 1 s
        for u in transcript.utterances:
            if not stills:
                break
            t = (u.start + u.end) / 2
            still = stills[min(int(t * FPS), len(stills) - 1)]
            path = run.file(f"frames/u{u.index:03d}.png")
            shutil.copy(still, path)
            shots.append(Frame(utterance_index=u.index, time_s=round(t, 2), path=str(path.relative_to(run.path))))
        shutil.rmtree(every)
    run.write_model("frames.json", FrameSet(frames=shots, references=references))
    log(f"{len(shots)} captures extraites, {len(references)} images de référence")
