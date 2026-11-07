"""Étapes 1-2 : la voix (Gladia) et les images (ffmpeg) de la capture."""
from __future__ import annotations

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


def frames(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    """Une capture d'écran au milieu de chaque phrase : ce que l'humain regardait quand il parlait."""
    transcript = run.read_model("transcript.json", Transcript)
    references = [Frame(utterance_index=None, time_s=None, path=str(p.relative_to(run.path))) for p in run.images()]
    shots: list[Frame] = []
    video = run.video()
    if video:
        run.file("frames").mkdir(exist_ok=True)
        for u in transcript.utterances:
            t = round((u.start + u.end) / 2, 2)
            path = run.file(f"frames/u{u.index:03d}.png")
            _ffmpeg("-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", str(path))
            shots.append(Frame(utterance_index=u.index, time_s=t, path=str(path.relative_to(run.path))))
    run.write_model("frames.json", FrameSet(frames=shots, references=references))
    log(f"{len(shots)} captures extraites, {len(references)} images de référence")
