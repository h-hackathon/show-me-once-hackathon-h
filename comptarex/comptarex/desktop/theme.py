"""Look Windows 2000 et petites briques communes (champs libellés, boîtes de message, icônes)."""
from __future__ import annotations

from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressDialog, QPushButton, QWidget)

GRIS = "#D4D0C8"
BLEU = "#0A246A"
ROUGE = "#B00000"
TITRE = "COMPTAREX"
IMPRIMANTE = "\\\\SRV-CAB01\\HP LaserJet 4050 PCL6"
DUREE_TRAITEMENT_MS = 2000     # la fausse « édition en cours » (mise à 0 par les tests)


def appliquer(app: QApplication) -> None:
    app.setStyle("Windows")
    app.setAttribute(Qt.AA_DontUseNativeMenuBar, True)
    pal = QPalette()
    couleurs = {
        QPalette.Window: GRIS, QPalette.Button: GRIS, QPalette.Base: "#FFFFFF", QPalette.AlternateBase: "#F1EFE2",
        QPalette.Highlight: BLEU, QPalette.HighlightedText: "#FFFFFF", QPalette.WindowText: "#000000",
        QPalette.ButtonText: "#000000", QPalette.Text: "#000000", QPalette.ToolTipBase: "#FFFFE1",
        QPalette.ToolTipText: "#000000", QPalette.Light: "#FFFFFF", QPalette.Midlight: "#ECE9E4",
        QPalette.Mid: "#808080", QPalette.Dark: "#404040", QPalette.Shadow: "#000000",
        QPalette.PlaceholderText: "#6E6E6E",
    }
    for role, couleur in couleurs.items():
        pal.setColor(role, QColor(couleur))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#808080"))
    app.setPalette(pal)
    police = QFont()
    police.setFamilies(["Tahoma", "Verdana", "Arial"])
    police.setPixelSize(11)
    app.setFont(police)


# ---------------------------------------------------------------- boîtes de message (remplaçables en test)

def _boite(parent, icone, texte: str, titre: str, boutons=QMessageBox.Ok) -> int:
    box = QMessageBox(icone, titre, texte, boutons, parent)
    for bouton, libelle in ((QMessageBox.Yes, "Oui"), (QMessageBox.No, "Non"), (QMessageBox.Cancel, "Annuler")):
        if box.button(bouton):
            box.button(bouton).setText(libelle)
    return box.exec()


def info(parent, texte: str, titre: str = TITRE) -> None:
    _boite(parent, QMessageBox.Information, texte, titre)


def erreur(parent, texte: str, titre: str = TITRE) -> None:
    _boite(parent, QMessageBox.Warning, texte, titre)


def question(parent, texte: str, titre: str = TITRE) -> bool:
    return _boite(parent, QMessageBox.Question, texte, titre, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes


def module_indisponible(parent, nom: str = "") -> None:
    info(parent, f"Module {nom + ' ' if nom else ''}non disponible dans votre licence (code 0x41).\n"
                 "Contactez Comptarex S.A. pour une extension de licence.")


def ouvrir_pdf(chemin) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin)))


def traitement(parent, etapes: list[str]) -> None:
    """La fausse barre de progression des éditions."""
    dlg = QProgressDialog("Traitement en cours...", None, 0, len(etapes), parent)
    dlg.setWindowTitle("Edition en cours - ne pas fermer la fenêtre")
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.setCancelButton(None)
    for i, etape in enumerate(etapes):
        dlg.setLabelText(etape)
        dlg.setValue(i)
        if DUREE_TRAITEMENT_MS:
            boucle = QEventLoop()
            QTimer.singleShot(DUREE_TRAITEMENT_MS // len(etapes), boucle.quit)
            boucle.exec()
    dlg.setValue(len(etapes))
    dlg.close()


# ---------------------------------------------------------------- champs et décor

def champ(grille: QGridLayout, ligne: int, libelle: str, widget: QWidget, colonne: int = 0, aide: str = "") -> QWidget:
    """Ajoute « libellé + champ » à une grille ; le libellé est relié au champ (buddy + nom accessible)."""
    etiquette = QLabel(libelle)
    etiquette.setBuddy(widget)
    widget.setAccessibleName(libelle.rstrip(" :*").strip())
    grille.addWidget(etiquette, ligne, colonne)
    grille.addWidget(widget, ligne, colonne + 1)
    if aide:
        a = QLabel(aide)
        a.setStyleSheet("color: #4A4A4A;")
        grille.addWidget(a, ligne, colonne + 2)
    return widget


def bandeau(texte: str, sous_titre: str = "") -> QLabel:
    lbl = QLabel(f"<span style='font-size:20px; font-weight:bold; font-style:italic;'>COMPTAREX</span>"
                 f"&nbsp;&nbsp;{texte}" + (f"<br><span style='font-size:10px;'>{sous_titre}</span>" if sous_titre else ""))
    lbl.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BLEU}, stop:1 #3A6EA5);"
                      "color: white; padding: 8px 12px;")
    lbl.setAccessibleName("COMPTAREX " + texte)
    return lbl


def barre_titre(texte: str) -> QLabel:
    lbl = QLabel(texte)
    lbl.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BLEU}, stop:1 #3A6EA5);"
                      "color: white; font-weight: bold; padding: 3px 6px;")
    return lbl


def avertissement(texte: str) -> QLabel:
    lbl = QLabel(texte)
    lbl.setStyleSheet(f"color: {ROUGE};")
    lbl.setWordWrap(True)
    return lbl


def panneau(texte: str = "") -> QLabel:
    lbl = QLabel(texte)
    lbl.setFrameStyle(QFrame.Panel | QFrame.Sunken)
    lbl.setContentsMargins(4, 0, 4, 0)
    return lbl


def bouton(texte: str, slot=None, nom: str = "") -> QPushButton:
    b = QPushButton(texte)
    b.setAutoDefault(False)
    b.setAccessibleName(nom or texte.replace("&", ""))
    if slot:
        b.clicked.connect(slot)
    return b


def lecture_seule(edit: QLineEdit) -> QLineEdit:
    edit.setReadOnly(True)
    edit.setStyleSheet("background: #ECE9D8;")
    return edit


# ---------------------------------------------------------------- icônes 16 px dessinées à la main

def icone(nom: str) -> QIcon:
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, False)
    noir = QPen(QColor("#404040"))
    p.setPen(noir)
    if nom in ("dossier", "fermer"):
        p.setBrush(QColor("#F4D26B" if nom == "dossier" else GRIS))
        p.drawPolygon([QPoint(x, y) for x, y in [(1, 4), (6, 4), (7, 5), (14, 5), (14, 13), (1, 13)]])
        if nom == "fermer":
            p.setPen(QPen(QColor(ROUGE), 2))
            p.drawLine(5, 7, 10, 12)
            p.drawLine(10, 7, 5, 12)
    elif nom == "saisie":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(2, 2, 10, 12)
        p.drawLine(4, 5, 10, 5)
        p.drawLine(4, 8, 10, 8)
        p.setPen(QPen(QColor(BLEU), 2))
        p.drawLine(9, 13, 14, 6)
    elif nom == "loupe":
        p.setPen(QPen(QColor("#404040"), 2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(2, 2, 8, 8)
        p.drawLine(10, 10, 14, 14)
    elif nom == "balance":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(1, 2, 13, 11)
        p.drawLine(1, 6, 14, 6)
        p.drawLine(6, 2, 6, 13)
        p.drawLine(10, 2, 10, 13)
    elif nom == "imprimer":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(4, 1, 8, 5)
        p.setBrush(QColor("#B8B4AC"))
        p.drawRect(1, 6, 13, 6)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(4, 10, 8, 4)
    elif nom == "message":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(1, 3, 13, 9)
        p.drawLine(1, 3, 8, 9)
        p.drawLine(8, 9, 14, 3)
    elif nom == "aide":
        p.setBrush(QColor("#FFFFE1"))
        p.drawEllipse(1, 1, 13, 13)
        p.setPen(QPen(QColor(BLEU), 2))
        p.drawText(pix.rect(), Qt.AlignCenter, "?")
    elif nom == "situation":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(2, 1, 11, 14)
        p.setBrush(QBrush(QColor(BLEU)))
        p.drawRect(4, 9, 2, 4)
        p.drawRect(7, 6, 2, 7)
        p.drawRect(10, 4, 2, 9)
    p.end()
    return QIcon(pix)
