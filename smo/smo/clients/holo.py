"""Holo (Models API de H, format compatible OpenAI) : lire des captures d'écran (repris de prep/04_test_holo.py)."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError


API = "https://api.hcompany.ai/v1/chat/completions"
M = TypeVar("M", bound=BaseModel)


def image_data_uri(path: Path) -> str:
    """PNG/JPG en data URI ; un PDF est d'abord converti en PNG (sips, macOS)."""
    if path.suffix.lower() == ".pdf":
        png = Path(tempfile.gettempdir()) / f"{path.stem}.png"
        subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(png)],
                       check=True, capture_output=True)
        path = png
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def chat(prompt: str, api_key: str, model: str, images: list[Path] = (), timeout_s: float = 300) -> tuple[str, float]:
    """Une question (texte + images dans l'ordre) → (réponse, durée en s)."""
    content = [{"type": "image_url", "image_url": {"url": image_data_uri(p)}} for p in images]
    content.append({"type": "text", "text": prompt})
    start = time.time()
    r = httpx.post(API, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_s, json={
        "model": model, "temperature": 0,
        "messages": [{"role": "user", "content": content}],
    })
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - start


def extract_json(text: str) -> dict:
    """Le premier objet JSON de la réponse (Holo l'entoure parfois de ```json ... ```)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(candidate)


def chat_model(prompt: str, model_cls: type[M], api_key: str, model: str, images: list[Path] = (),
               retries: int = 1) -> M:
    """Comme chat(), mais la réponse doit valider model_cls ; on redemande une fois avec l'erreur."""
    ask = prompt
    for attempt in range(retries + 1):
        answer, _ = chat(ask, api_key, model, images)
        try:
            return model_cls.model_validate(extract_json(answer))
        except (ValueError, ValidationError) as err:
            if attempt == retries:
                raise RuntimeError(f"Réponse de Holo invalide : {err}\n---\n{answer[:2000]}") from err
            ask = f"{prompt}\n\nTa réponse précédente était invalide ({err}). Rends uniquement le JSON demandé."
    raise AssertionError("unreachable")
