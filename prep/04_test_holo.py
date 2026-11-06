"""Test de Holo4 (Models API de H) : les 2 capacités dont le projet a besoin.

Test 1 — Lire une facture (image) : extraire les champs ET repérer une incohérence (INV-009, TTC faux).
Test 2 — Écrire une Skill : à partir de la transcription d'une démo + l'image de la facture,
         rédiger la procédure et les règles implicites.

Usage :
    .venv/bin/python 04_test_holo.py [modele]   # défaut holo3-1-35b-a3b (gratuit) ; holo4-35b-a3b et holo4-27b demandent des crédits payants
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


load_dotenv()

API = "https://api.hcompany.ai/v1/chat/completions"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "holo3-1-35b-a3b"
HEADERS = {"Authorization": f"Bearer {os.environ['HAI_API_KEY']}"}
ICI = Path(__file__).parent


def image_facture(inv_id):
    """Convertit la 1re page du PDF en PNG (outil sips de macOS) et la renvoie en data URI."""
    png = Path(tempfile.gettempdir()) / f"{inv_id}.png"
    subprocess.run(["sips", "-s", "format", "png", str(ICI / "factures" / f"{inv_id}.pdf"),
                    "--out", str(png)], check=True, capture_output=True)
    return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()


def demander(texte, image=None):
    contenu = [{"type": "text", "text": texte}]
    if image:
        contenu.insert(0, {"type": "image_url", "image_url": {"url": image}})
    start = time.time()
    r = httpx.post(API, headers=HEADERS, timeout=180, json={
        "model": MODEL, "temperature": 0,
        "messages": [{"role": "user", "content": contenu}],
    })
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - start


print(f"=== Modèle : {MODEL}\n")

# Test 1 : lecture + contrôle de cohérence
reponse, duree = demander(
    "Voici une facture fournisseur. Extrais en JSON : fournisseur, numero_facture, date, "
    "total_ht, total_tva, total_ttc (nombres). Puis vérifie si total_ht + total_tva = total_ttc "
    "et ajoute un champ coherent (true/false) avec une courte explication.",
    image_facture("INV-009"))
print(f"--- Test 1 : lecture d'INV-009 ({duree:.1f}s)\n{reponse}\n")

# Test 2 : rédaction d'une Skill à partir d'une démo commentée
transcription = (ICI / "audio" / "demo_narration.txt").read_text(encoding="utf-8")
reponse, duree = demander(
    "Un comptable a saisi la facture ci-jointe dans le logiciel Odoo en commentant à voix haute. "
    "Voici la transcription de ce qu'il a dit :\n\n" + transcription + "\n\n"
    "Rédige une SKILL réutilisable par un agent qui devra traiter d'autres factures, en français, avec :\n"
    "1. ETAPES : la procédure dans Odoo, étape par étape (menus, champs, d'où vient chaque valeur sur la facture).\n"
    "2. REGLES : les règles métier implicites (contrôles, exceptions, ce qu'il ne faut jamais faire).\n"
    "3. ARRET : quand l'agent doit s'arrêter et prévenir un humain.\n"
    "Sois concis et précis.",
    image_facture("INV-001"))
print(f"--- Test 2 : Skill écrite à partir de la démo ({duree:.1f}s)\n{reponse}")
