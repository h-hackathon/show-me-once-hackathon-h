"""Client Gladia v2 (transcription pré-enregistrée) : upload → init → polling."""
import asyncio
from pathlib import Path

import httpx

from . import config


class GladiaError(RuntimeError):
    pass


def _headers() -> dict:
    if not config.GLADIA_API_KEY:
        raise GladiaError("GLADIA_API_KEY manquante")
    return {"x-gladia-key": config.GLADIA_API_KEY}


async def transcribe(audio_path: Path, timeout_s: int = 900) -> dict:
    """Renvoie la réponse complète de GET /pre-recorded/{id} une fois terminée."""
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Upload du fichier (Gladia accepte audio et vidéo, webm compris)
        with audio_path.open("rb") as f:
            r = await client.post(
                f"{config.GLADIA_BASE_URL}/upload",
                headers=_headers(),
                files={"audio": (audio_path.name, f, "audio/webm")},
            )
        if r.status_code >= 400:
            raise GladiaError(f"upload {r.status_code}: {r.text}")
        audio_url = r.json()["audio_url"]

        # 2. Lancement de la transcription
        body: dict = {
            "audio_url": audio_url,
            "language_config": {"languages": config.GLADIA_LANGUAGES, "code_switching": len(config.GLADIA_LANGUAGES) > 1},
        }
        if config.GLADIA_SUMMARIZE:
            body["summarization"] = True
            body["summarization_config"] = {"type": "concise"}
        r = await client.post(f"{config.GLADIA_BASE_URL}/pre-recorded", headers=_headers(), json=body)
        if r.status_code >= 400:
            raise GladiaError(f"init {r.status_code}: {r.text}")
        job_id = r.json()["id"]

        # 3. Polling
        elapsed = 0
        while elapsed < timeout_s:
            r = await client.get(f"{config.GLADIA_BASE_URL}/pre-recorded/{job_id}", headers=_headers())
            if r.status_code >= 400:
                raise GladiaError(f"poll {r.status_code}: {r.text}")
            data = r.json()
            if data.get("status") == "done":
                return data
            if data.get("status") == "error":
                raise GladiaError(f"transcription en erreur: {data.get('error_code')} {data}")
            await asyncio.sleep(3)
            elapsed += 3
        raise GladiaError("timeout transcription")


def utterances(gladia_result: dict | None) -> list[dict]:
    """Extrait [{start, end, text}] de la réponse Gladia, recoupé en vraies phrases.

    Gladia coupe ses "utterances" aux pauses de la voix, souvent au milieu d'une phrase
    ("je viens cliquer sur" | "litige."). On reconstruit les phrases à partir des mots
    horodatés, en coupant sur la ponctuation de fin de phrase.
    """
    if not gladia_result:
        return []
    tr = (gladia_result.get("result") or {}).get("transcription") or {}
    utts = [u for u in tr.get("utterances", []) if u.get("text", "").strip()]
    words = [w for u in utts for w in (u.get("words") or [])]
    if not words:
        return [{"start": u["start"], "end": u["end"], "text": u["text"].strip()} for u in utts]

    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if w.get("word", "").strip().endswith((".", "?", "!", "…")):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    return [
        {"start": ws[0]["start"], "end": ws[-1]["end"], "text": " ".join(w["word"].strip() for w in ws)}
        for ws in sentences
    ]


def full_transcript(gladia_result: dict | None) -> str:
    if not gladia_result:
        return ""
    tr = (gladia_result.get("result") or {}).get("transcription") or {}
    return tr.get("full_transcript", "") or " ".join(u["text"] for u in utterances(gladia_result))


def summary(gladia_result: dict | None) -> str:
    if not gladia_result:
        return ""
    s = (gladia_result.get("result") or {}).get("summarization") or {}
    return s.get("results") or ""
