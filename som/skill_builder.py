"""Étape 2 — Apprendre : phrases horodatées + captures d'écran → Skill (procédure + règles), via Holo (Models API H).

La Skill est écrite dans skills/<nom>.md : l'humain la relit et la corrige AVANT de lancer l'agent.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from .config import SKILLS, env
from .invoices import data_uri, to_png

HOLO_API = "https://api.hcompany.ai/v1/chat/completions"

CONSIGNE = """Un employé a fait une tâche une fois dans son logiciel en commentant à voix haute.
Tu reçois : la transcription horodatée de ce qu'il a dit{captures}, et le document qu'il traitait.

Rédige une SKILL en français, réutilisable par un agent computer-use qui devra refaire la même tâche
sur d'autres documents. Format Markdown, exactement ces 3 sections :

## ETAPES
La procédure dans le logiciel, numérotée : menus exacts, champs, boutons, et d'où vient chaque valeur
sur le document (ex. « Référence de la facture = n° en haut à droite du PDF »).

## REGLES
Les règles métier implicites dites par l'employé : contrôles, exceptions (« si… alors… »),
ce qu'il ne faut jamais faire. Une règle par ligne, formulée comme une consigne.

## ARRET
Les cas où l'agent doit s'arrêter et prévenir un humain au lieu de continuer.

Ne garde que ce qui est dit ou visible. N'invente aucune règle. Sois concis."""


def holo(content: list[dict], model: str) -> tuple[str, float]:
    import httpx
    t0 = time.time()
    r = httpx.post(HOLO_API, timeout=240,
                   headers={"Authorization": f"Bearer {env('HAI_API_KEY', required=True)}"},
                   json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - t0


def _sample(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    step = (len(items) - 1) / (n - 1) if n > 1 else 0
    return [items[round(i * step)] for i in range(n)]


def build(utterances: list[dict], frames: list[Path], document_png: Path,
          model: str, max_frames: int = 6) -> tuple[str, dict]:
    frames = _sample(frames, max_frames)
    lines = []
    for u in utterances:
        ref = f" [capture {frames.index(Path(u['frame'])) + 1}]" if u.get("frame") and Path(u["frame"]) in frames else ""
        lines.append(f"[{u.get('start', 0):.1f}s] {u['text']}{ref}")
    texte = CONSIGNE.format(captures=", des captures d'écran prises pendant la démo" if frames else "")
    texte += "\n\nTRANSCRIPTION :\n" + "\n".join(lines)

    images = [data_uri(document_png)] + [data_uri(f) for f in frames]
    try:
        content = [{"type": "image_url", "image_url": {"url": u}} for u in images] + [{"type": "text", "text": texte}]
        skill, duree = holo(content, model)
    except Exception as e:  # certains modèles refusent plusieurs images : on retente avec le document seul
        if len(images) == 1:
            raise
        print(f"⚠️  Holo a refusé {len(images)} images ({e.__class__.__name__}) → nouvel essai avec le document seul")
        content = [{"type": "image_url", "image_url": {"url": images[0]}}, {"type": "text", "text": texte}]
        skill, duree = holo(content, model)
        frames = []
    return skill, {"model": model, "seconds": round(duree, 1), "frames_used": len(frames)}


def from_sources(demo: Path | None, transcript: Path | None, document: str, name: str,
                 model: str | None = None, max_frames: int = 6) -> Path:
    model = model or env("HOLO_MODEL", "holo3-1-35b-a3b")
    if demo:
        data = json.loads(demo.read_text(encoding="utf-8"))
        utterances = data["utterances"]
        for u in utterances:  # chemins des captures relatifs au dossier de la démo
            if u.get("frame"):
                u["frame"] = str(demo.parent / u["frame"])
        frames = [Path(u["frame"]) for u in utterances if u.get("frame")]
    elif transcript:
        utterances = [{"start": 0, "text": transcript.read_text(encoding="utf-8").strip()}]
        frames = []
    else:
        raise SystemExit("❌ Donne --demo (sortie de `capture`) ou --transcript (texte)")

    skill, meta = build(utterances, frames, to_png(document), model, max_frames)
    SKILLS.mkdir(exist_ok=True)
    out = SKILLS / f"{name}.md"
    source = demo or transcript
    out.write_text(
        f"---\nname: {name}\n"
        f"description: Procédure apprise d'une démonstration humaine ({source.name}, document {document}).\n"
        f"generated: {datetime.now():%Y-%m-%d %H:%M} · {meta['model']} · {meta['seconds']}s · {meta['frames_used']} captures\n"
        f"reviewed: false   # passer à true après relecture humaine\n---\n\n{skill.strip()}\n",
        encoding="utf-8")
    print(f"🧠 Skill écrite en {meta['seconds']}s ({meta['model']}, {meta['frames_used']} captures)")
    print(f"✅ {out}  ← à relire et corriger avant de lancer l'agent")
    return out


def load(path: Path) -> str:
    """Contenu de la Skill sans l'en-tête, avec un avertissement si elle n'a pas été relue."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        head, _, text = text[3:].partition("\n---")
        if "reviewed: false" in head:
            print(f"⚠️  {path.name} n'a pas été relue (reviewed: false)")
    return text.strip()
