"""Un run = un dossier runs/<id>/ : la capture, puis un fichier par étape du pipeline."""
from __future__ import annotations

import json
import re
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import CaptureMeta


M = TypeVar("M", bound=BaseModel)
STATUS_LOCK = threading.Lock()

VIDEO = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}
IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}   # le PDF : pièce de référence (ex. la facture de la démo)


def slug(text: str, sep: str = "-", max_len: int = 48) -> str:
    """« Saisir une facture fournisseur » → « saisir-une-facture-fournisseur »."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    return sep.join(words)[:max_len].strip(sep) or "tache"


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.name

    @classmethod
    def create(cls, runs_dir: Path, meta: CaptureMeta, files: list[Path]) -> Run:
        run_id = f"{meta.created_at:%Y%m%d-%H%M%S}-{slug(meta.task, max_len=32)}"
        run = cls(runs_dir / run_id)
        (run.path / "capture").mkdir(parents=True)
        for src in files:
            kind = "images" if src.suffix.lower() in IMAGE else ""
            dest = run.path / "capture" / kind / src.name
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(src, dest)
        run.write_model("meta.json", meta)
        return run

    @classmethod
    def open(cls, runs_dir: Path, run_id: str) -> Run:
        path = runs_dir / run_id
        if not (path / "meta.json").exists():
            raise FileNotFoundError(f"Run introuvable : {path}")
        return cls(path)

    # --- fichiers de la capture
    def _capture(self, exts: set[str]) -> list[Path]:
        return sorted(p for p in (self.path / "capture").rglob("*") if p.suffix.lower() in exts)

    def video(self) -> Path | None:
        return next(iter(self._capture(VIDEO)), None)

    def audio(self) -> Path | None:
        return next(iter(self._capture(AUDIO)), None)

    def images(self) -> list[Path]:
        return self._capture(IMAGE)

    # --- artefacts
    @property
    def meta(self) -> CaptureMeta:
        return self.read_model("meta.json", CaptureMeta)

    def file(self, name: str) -> Path:
        return self.path / name

    def has(self, name: str) -> bool:
        return self.file(name).exists()

    def read_model(self, name: str, model: type[M]) -> M:
        return model.model_validate_json(self.file(name).read_text(encoding="utf-8"))

    def write_model(self, name: str, value: BaseModel) -> Path:
        return self.write_text(name, value.model_dump_json(indent=2))

    def read_json(self, name: str):
        return json.loads(self.file(name).read_text(encoding="utf-8"))

    def write_json(self, name: str, value) -> Path:
        return self.write_text(name, json.dumps(value, indent=2, ensure_ascii=False, default=str))

    def write_text(self, name: str, text: str) -> Path:
        path = self.file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    # --- état des étapes (status.json)
    def status(self) -> dict:
        return self.read_json("status.json") if self.has("status.json") else {}

    def set_status(self, stage: str, state: str, **extra) -> None:
        with STATUS_LOCK:   # la cartographie écrit en parallèle des autres étapes
            status = self.status()
            status[stage] = {"state": state, "at": datetime.now().isoformat(timespec="seconds"), **extra}
            self.write_json("status.json", status)

    # --- arrêt demandé depuis la page (fichier « stop »), vérifié entre deux étapes et entre deux essais
    def check_stop(self) -> None:
        if self.has("stop"):
            raise Stopped("arrêté depuis la page")


class Stopped(Exception):
    """L'humain a arrêté le run : l'étape en cours finit en échec, « Relancer » reprend où on en était."""
