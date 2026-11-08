"""Étape 2 — Apprendre : phrases horodatées + captures d'écran → Skill (procédure + règles), via Holo (Models API H).

La Skill est écrite dans skills/<nom>.md : l'humain la relit et la corrige AVANT de lancer l'agent.
"""
import base64
import json
import time
from datetime import datetime
from pathlib import Path

from .config import SKILLS, env

HOLO_API = "https://api.hcompany.ai/v1/chat/completions"

CONSIGNE = """Une personne de l'équipe ops a fait une tâche une fois sur son ordinateur en commentant à voix haute.
Tu reçois la transcription horodatée de ce qu'elle a dit{captures}.

Rédige une SKILL en français, réutilisable par un agent computer-use qui devra refaire la même tâche
sur d'autres dossiers du même type. Format Markdown, exactement ces 3 sections :

## ETAPES
La procédure numérotée : sites, menus, boutons, cellules ; ce qu'il faut copier, d'où, et où le coller.

## REGLES
Les règles métier implicites dites par la personne : contrôles, exceptions (« si… alors… »),
ce qu'il ne faut jamais faire. Une règle par ligne, formulée comme une consigne.

## ARRET
Les cas où l'agent doit s'arrêter et prévenir un humain au lieu de continuer.

Ne garde que ce qui est dit ou visible. N'invente aucune règle. Sois concis."""


def data_uri(png: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()


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


def build(utterances: list[dict], frames: list[Path], model: str, max_frames: int = 8) -> tuple[str, dict]:
    frames = _sample(frames, max_frames)
    lines = []
    for u in utterances:
        f = Path(u["frame"]) if u.get("frame") else None
        ref = f" [capture {frames.index(f) + 1}]" if f in frames else ""
        lines.append(f"[{u.get('start', 0):.1f}s] {u['text']}{ref}")
    texte = CONSIGNE.format(captures=", et des captures d'écran prises pendant la démo (dans l'ordre)" if frames else "")
    texte += "\n\nTRANSCRIPTION :\n" + "\n".join(lines)

    def ask(imgs):
        content = [{"type": "image_url", "image_url": {"url": data_uri(f)}} for f in imgs]
        return holo(content + [{"type": "text", "text": texte}], model)

    try:
        skill, duree = ask(frames)
    except Exception as e:  # certains modèles refusent plusieurs images : on retente avec moins
        if len(frames) <= 1:
            raise
        fewer = _sample(frames, 2)
        print(f"⚠️  Holo a refusé {len(frames)} images ({e.__class__.__name__}) → nouvel essai avec {len(fewer)}")
        skill, duree = ask(fewer)
        frames = fewer
    return skill, {"model": model, "seconds": round(duree, 1), "frames_used": len(frames)}


def from_sources(demo: Path | None, transcript: Path | None, name: str,
                 model: str | None = None, max_frames: int = 8) -> Path:
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

    skill, meta = build(utterances, frames, model, max_frames)
    SKILLS.mkdir(exist_ok=True)
    out = SKILLS / f"{name}.md"
    source = demo or transcript
    out.write_text(
        f"---\nname: {name}\n"
        f"description: Procédure apprise d'une démonstration humaine ({source.name}).\n"
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
