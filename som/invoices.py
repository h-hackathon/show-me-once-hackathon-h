"""Factures de test : vérité terrain, conversion PDF → PNG / texte."""
import base64
import csv
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import FACTURES, FACTURES_PNG


@dataclass
class Invoice:
    id: str
    fournisseur: str
    numero: str
    date: str            # JJ/MM/AAAA
    ht: float
    tva: float
    ttc: float           # total TTC correct
    ttc_imprime: float   # total imprimé sur le PDF (faux pour INV-009)
    piege: str
    attendu: str

    @property
    def pdf(self) -> Path:
        return FACTURES / f"{self.id}.pdf"


def load_truth() -> dict[str, Invoice]:
    with open(FACTURES / "verite_terrain.csv", encoding="utf-8") as fh:
        return {r["invoice_id"]: Invoice(
            id=r["invoice_id"], fournisseur=r["fournisseur"], numero=r["numero_facture"],
            date=r["date"], ht=float(r["total_ht"]), tva=float(r["total_tva"]),
            ttc=float(r["total_ttc_correct"]), ttc_imprime=float(r["total_ttc_imprime"]),
            piege=r["piege"], attendu=r["comportement_attendu"],
        ) for r in csv.DictReader(fh)}


def select(ids: str | None) -> list[Invoice]:
    """'INV-001,INV-009' → factures ; None ou 'all' → les 10."""
    truth = load_truth()
    if not ids or ids == "all":
        return list(truth.values())
    wanted = [i.strip().upper() for i in ids.split(",")]
    missing = [i for i in wanted if i not in truth]
    if missing:
        raise SystemExit(f"❌ Factures inconnues : {', '.join(missing)}")
    return [truth[i] for i in wanted]


def to_png(inv_id: str) -> Path:
    """1re page du PDF en PNG dans data/factures_png/ (PyMuPDF, sinon sips sur macOS, sinon pdftoppm)."""
    FACTURES_PNG.mkdir(parents=True, exist_ok=True)
    pdf, png = FACTURES / f"{inv_id}.pdf", FACTURES_PNG / f"{inv_id}.png"
    if png.exists() and png.stat().st_mtime >= pdf.stat().st_mtime:
        return png
    try:
        import fitz  # PyMuPDF
        with fitz.open(pdf) as doc:
            doc[0].get_pixmap(dpi=150).save(png)
        return png
    except ImportError:
        pass
    if platform.system() == "Darwin":
        subprocess.run(["sips", "-s", "format", "png", str(pdf), "--out", str(png)],
                       check=True, capture_output=True)
    elif shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", str(pdf), str(png.with_suffix(""))],
                       check=True, capture_output=True)
    else:
        raise SystemExit("❌ Impossible de convertir le PDF : installe pymupdf (pip install pymupdf)")
    return png


def to_text(inv_id: str) -> str:
    """Texte brut de la facture (mode sans URL : le contenu va dans la consigne de l'agent)."""
    pdf = FACTURES / f"{inv_id}.pdf"
    try:
        import fitz
        with fitz.open(pdf) as doc:
            return "\n".join(page.get_text() for page in doc).strip()
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                              capture_output=True, text=True).stdout.strip()
    raise SystemExit("❌ Impossible de lire le PDF : installe pymupdf (pip install pymupdf)")


def data_uri(png: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
