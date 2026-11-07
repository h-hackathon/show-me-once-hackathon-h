"""Étape 1 — Capture : vidéo de démo commentée → phrases horodatées (Gladia) + 1 image d'écran par phrase.

Sortie : runs/demo/<nom>/demo.json  {video, utterances: [{start, end, text, frame}]}
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

from .config import RUNS, env

GLADIA = "https://api.gladia.io/v2"


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit("❌ ffmpeg introuvable : pip install imageio-ffmpeg")
        return exe


def extract_audio(video: Path, wav: Path) -> Path:
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(video),
                    "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    return wav


def extract_frame(video: Path, t: float, png: Path) -> Path:
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale='min(1600,iw)':-2", str(png)], check=True)
    return png


def transcribe(audio: Path, language: str = "fr") -> list[dict]:
    """Envoie l'audio à Gladia et renvoie [{start, end, text}] (une entrée par phrase)."""
    import httpx
    headers = {"x-gladia-key": env("GLADIA_API_KEY", required=True)}
    with httpx.Client(headers=headers, timeout=120) as http:
        with open(audio, "rb") as fh:
            up = http.post(f"{GLADIA}/upload", files={"audio": (audio.name, fh, "audio/wav")})
        up.raise_for_status()
        job = http.post(f"{GLADIA}/pre-recorded", json={"audio_url": up.json()["audio_url"], "language": language})
        job.raise_for_status()
        result_url = job.json()["result_url"]
        for _ in range(150):  # 5 min max
            res = http.get(result_url).json()
            if res["status"] in ("done", "error"):
                break
            time.sleep(2)
    if res["status"] != "done":
        raise SystemExit(f"❌ Gladia : {res}")
    return [{"start": u["start"], "end": u["end"], "text": u["text"].strip()}
            for u in res["result"]["transcription"]["utterances"]]


def capture(media: Path, name: str | None = None) -> Path:
    """Vidéo (.mov/.mp4) → phrases + captures. Un simple audio (.wav) marche aussi, sans captures."""
    out = RUNS / "demo" / (name or media.stem)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    is_video = media.suffix.lower() in (".mov", ".mp4", ".m4v", ".webm", ".mkv")

    t0 = time.time()
    audio = extract_audio(media, out / "audio.wav") if is_video else media
    utterances = transcribe(audio)
    print(f"🎙️  Gladia : {len(utterances)} phrases en {time.time() - t0:.1f}s")

    for i, u in enumerate(utterances):
        u["frame"] = None
        if is_video:
            # image prise juste avant la fin de la phrase : l'action décrite est en général visible
            t = max(u["start"], u["end"] - 0.3)
            u["frame"] = str(extract_frame(media, t, out / "frames" / f"{i:03d}.png").relative_to(out))
        print(f"   [{u['start']:6.1f}s → {u['end']:6.1f}s] {u['text']}")

    demo = out / "demo.json"
    demo.write_text(json.dumps({"media": str(media), "utterances": utterances}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"✅ {demo}")
    return demo
