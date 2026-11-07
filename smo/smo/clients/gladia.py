"""Gladia : transcription horodatée (repris de prep/03_test_gladia.py)."""
from __future__ import annotations

import mimetypes
import time
from pathlib import Path

import httpx

from ..models import Transcript, Utterance


API = "https://api.gladia.io/v2"


def transcribe(audio: Path, api_key: str, language: str = "fr", timeout_s: float = 600) -> Transcript:
    headers = {"x-gladia-key": api_key}
    mime = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
    with httpx.Client(headers=headers, timeout=120) as http:
        # 1. Envoi du fichier
        with audio.open("rb") as fh:
            up = http.post(f"{API}/upload", files={"audio": (audio.name, fh, mime)})
        up.raise_for_status()

        # 2. Demande de transcription
        job = http.post(f"{API}/pre-recorded", json={"audio_url": up.json()["audio_url"], "language": language})
        job.raise_for_status()
        result_url = job.json()["result_url"]

        # 3. Attente du résultat
        deadline = time.monotonic() + timeout_s
        while True:
            res = http.get(result_url).json()
            if res["status"] in ("done", "error"):
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"Gladia n'a pas fini en {timeout_s:.0f}s")
            time.sleep(2)

    if res["status"] != "done":
        raise RuntimeError(f"Gladia : {res.get('error_code') or res}")
    utterances = res["result"]["transcription"]["utterances"]
    return Transcript(language=language, utterances=[
        Utterance(index=i, start=u["start"], end=u["end"], text=u["text"].strip())
        for i, u in enumerate(utterances)
    ])


def start_live(api_key: str, language: str = "fr") -> dict:
    """Ouvre une session de transcription en direct. Renvoie {id, url} : `url` (wss://…?token=…) porte un jeton
    temporaire, le navigateur s'y connecte directement et la clé ne quitte pas le serveur."""
    r = httpx.post(f"{API}/live", headers={"x-gladia-key": api_key}, timeout=30, json={
        "encoding": "wav/pcm", "sample_rate": 16000, "bit_depth": 16, "channels": 1,
        "language_config": {"languages": [language], "code_switching": False},
        "messages_config": {"receive_partial_transcripts": True, "receive_final_transcripts": True},
    })
    r.raise_for_status()
    return r.json()


def ping(api_key: str) -> int:
    """Code HTTP d'une lecture sans coût (liste des transcriptions)."""
    return httpx.get(f"{API}/pre-recorded", params={"limit": 1},
                     headers={"x-gladia-key": api_key}, timeout=30).status_code
