"""Test de l'API Gladia : transcrit un audio en français avec les horodatages.

Pourquoi les horodatages ? Pendant la démo, on les aligne avec les captures d'écran :
« à 0:12 l'humain dit "je vérifie toujours le total" pendant qu'il regarde l'écran X ».

Prérequis dans .env : GLADIA_API_KEY
Usage :
    .venv/bin/python 03_test_gladia.py [audio/demo_narration.wav]
"""
import os
import sys
import time

import httpx
from dotenv import load_dotenv


load_dotenv()

API = "https://api.gladia.io/v2"
AUDIO = sys.argv[1] if len(sys.argv) > 1 else "audio/demo_narration.wav"
headers = {"x-gladia-key": os.environ["GLADIA_API_KEY"]}

start = time.time()
with httpx.Client(headers=headers, timeout=60) as http:
    # 1. Envoi du fichier audio
    with open(AUDIO, "rb") as fh:
        up = http.post(f"{API}/upload", files={"audio": (os.path.basename(AUDIO), fh, "audio/wav")})
    up.raise_for_status()
    audio_url = up.json()["audio_url"]

    # 2. Demande de transcription
    job = http.post(f"{API}/pre-recorded", json={"audio_url": audio_url, "language": "fr"})
    job.raise_for_status()
    result_url = job.json()["result_url"]

    # 3. Attente du résultat
    while True:
        res = http.get(result_url).json()
        if res["status"] in ("done", "error"):
            break
        time.sleep(2)

elapsed = time.time() - start
print(f"status : {res['status']}")
print(f"time   : {elapsed:.1f}s")
if res["status"] == "done":
    for u in res["result"]["transcription"]["utterances"]:
        print(f"[{u['start']:6.1f}s → {u['end']:6.1f}s] {u['text']}")
else:
    print(res)
