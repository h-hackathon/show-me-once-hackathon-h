"""Editions › Etats de synthèse › Situation intermédiaire : boîte de paramétrage (piège Imprimante),
aperçu à l'écran et transmission au client."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QRadioButton, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from .. import compta, config
from ..db import set_setting
from . import theme

LIGNES_PAR_PAGE = 40


class SituationDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main, self.conn = main, main.conn
        self.setWindowTitle("Situation intermédiaire")
        self.setModal(True)
        self.params = None                      # rempli quand l'édition part à l'écran
        lay = QVBoxLayout(self)
        self.onglets = QTabWidget()
        self.onglets.addTab(self._criteres(), "Critères")
        self.onglets.addTab(self._presentation(), "Présentation")
        self.onglets.addTab(self._destination(), "Destination")
        lay.addWidget(self.onglets)
        boutons = QHBoxLayout()
        boutons.addStretch()
        self.ok = theme.bouton("OK", self.lancer)
        self.ok.setDefault(True)
        boutons.addWidget(self.ok)
        boutons.addWidget(theme.bouton("Annuler", self.reject))
        boutons.addWidget(theme.bouton("Aide", lambda: theme.info(
            self, "L'aide en ligne nécessite Internet Explorer 6.0 SP1 ou supérieur.")))
        lay.addLayout(boutons)
        self.resize(560, 420)

    def _criteres(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.addWidget(QLabel("Dossier :"), 0, 0)
        g.addWidget(QLabel(f"<b>{escape(compta.libelle_dossier(self.main.dossier))}</b>"), 0, 1, 1, 3)
        theme.champ(g, 1, "Période du :", theme.lecture_seule(QLineEdit("01/01/2026")))
        self.au = theme.champ(g, 2, "au (JJ/MM/AAAA) * :", QLineEdit())
        self.au.setPlaceholderText("__/__/____")
        self.au.setMaxLength(10)
        self.type_gestion, self.type_fiscale = QRadioButton("Situation de gestion"), QRadioButton("Situation fiscale")
        self.type_gestion.setChecked(True)
        self._groupe(g, 3, "Type de situation :", [self.type_gestion, self.type_fiscale])
        self.cmp_aucun, self.cmp_n1, self.cmp_budget = (QRadioButton("Aucun"), QRadioButton("N-1 même période"),
                                                        QRadioButton("Budget"))
        self.cmp_aucun.setChecked(True)
        self._groupe(g, 4, "Comparatif :", [self.cmp_aucun, self.cmp_n1, self.cmp_budget])
        self.niveau = QComboBox()
        for code in ("3", "1", "2", "6"):
            self.niveau.addItem(compta.NIVEAUX[code], code)
        theme.champ(g, 5, "Niveau de détail :", self.niveau)
        self.brouillard = QCheckBox("Inclure les écritures en brouillard")
        self.abonnement = QCheckBox("Inclure les écritures d'abonnement")
        self.francs = QCheckBox("Afficher la contre-valeur en francs (FRF)")
        self.francs.setChecked(True)
        for i, c in enumerate((self.brouillard, self.abonnement, self.francs)):
            g.addWidget(c, 6 + i, 0, 1, 4)
        aide = QLabel("* Champ obligatoire. Format de date JJ/MM/AAAA uniquement (ex. : 31/10/2026).")
        aide.setStyleSheet("color: #4A4A4A;")
        g.addWidget(aide, 9, 0, 1, 4)
        g.setRowStretch(10, 1)
        return w

    def _groupe(self, g: QGridLayout, ligne: int, libelle: str, radios: list[QRadioButton]) -> None:
        g.addWidget(QLabel(libelle), ligne, 0)
        box = QHBoxLayout()
        groupe = QButtonGroup(self)
        for r in radios:
            groupe.addButton(r)
            box.addWidget(r)
        box.addStretch()
        g.addLayout(box, ligne, 1, 1, 3)

    def _presentation(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        self.titre = theme.champ(g, 0, "Titre de l'édition :", QLineEdit("SITUATION INTERMEDIAIRE DE GESTION"))
        self.portrait, paysage = QRadioButton("Portrait"), QRadioButton("Paysage")
        self.portrait.setChecked(True)
        self._groupe(g, 1, "Orientation :", [self.portrait, paysage])
        police = QComboBox()
        police.addItems(["Courier New 9", "Arial 8"])
        theme.champ(g, 2, "Police :", police)
        self.entete = QCheckBox("Imprimer l'en-tête du cabinet")
        self.entete.setChecked(True)
        numeroter = QCheckBox("Numéroter les pages")
        numeroter.setChecked(True)
        self.soldes = QCheckBox("Imprimer les comptes soldés")
        for i, c in enumerate((self.entete, numeroter, self.soldes)):
            g.addWidget(c, 3 + i, 0, 1, 3)
        g.setRowStretch(6, 1)
        return w

    def _destination(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.addWidget(QLabel("Envoyer l'édition vers :"), 0, 0, 1, 3)
        self.d_imprimante = QRadioButton("Imprimante")
        self.d_ecran = QRadioButton("Aperçu à l'écran")
        self.d_pdf = QRadioButton("Fichier PDF")
        groupe = QButtonGroup(self)
        for r in (self.d_imprimante, self.d_ecran, self.d_pdf):
            groupe.addButton(r)
        imprimantes = QComboBox()
        imprimantes.addItems([theme.IMPRIMANTE, "\\\\SRV-CAB01\\Canon iR2018"])
        imprimantes.setAccessibleName("Imprimante")
        g.addWidget(self.d_imprimante, 1, 0)
        g.addWidget(imprimantes, 1, 1)
        g.addWidget(theme.bouton("Propriétés...", lambda: theme.info(
            self, "Pilote d'impression indisponible sur ce poste.")), 1, 2)
        g.addWidget(self.d_ecran, 2, 0, 1, 3)
        g.addWidget(self.d_pdf, 3, 0)
        chemin = theme.lecture_seule(QLineEdit("C:\\COMPTAREX\\EDITIONS\\"))
        chemin.setAccessibleName("Dossier du fichier")
        g.addWidget(chemin, 3, 1)
        self.exemplaires = theme.champ(g, 4, "Nombre d'exemplaires :", QLineEdit("1"))
        self.exemplaires.setMaximumWidth(40)
        self.memoriser = QCheckBox("Mémoriser comme destination par défaut")
        g.addWidget(self.memoriser, 5, 0, 1, 3)
        note = QLabel("La destination par défaut se règle dans Paramètres › Postes de travail › Imprimantes.")
        note.setStyleSheet("color: #4A4A4A;")
        g.addWidget(note, 6, 0, 1, 3)
        g.setRowStretch(7, 1)
        {"ecran": self.d_ecran, "pdf": self.d_pdf}.get(compta.destination_defaut(self.conn),
                                                       self.d_imprimante).setChecked(True)
        return w

    def destination(self) -> str:
        return "ecran" if self.d_ecran.isChecked() else "pdf" if self.d_pdf.isChecked() else "imprimante"

    def lancer(self) -> None:
        jour = compta.parse_date_fr(self.au.text())
        if jour is None:
            self.onglets.setCurrentIndex(0)
            return theme.erreur(self, "Erreur 0x2F : date invalide (format JJ/MM/AAAA).")
        if not (compta.EXO_DEBUT <= jour <= compta.EXO_FIN):
            return theme.erreur(self, "La date d'arrêté doit appartenir à l'exercice 01/01/2026 - 31/12/2026.")
        if self.type_fiscale.isChecked():
            return theme.erreur(self, "Le module Liasse fiscale n'est pas installé sur ce poste (code 0x41).")
        if self.cmp_n1.isChecked():
            return theme.erreur(self, "Exercice N-1 non disponible : dossier repris en 2026 "
                                      "(balance d'ouverture uniquement).")
        if self.cmp_budget.isChecked():
            return theme.erreur(self, "Aucun budget saisi pour ce dossier.")
        dest = self.destination()
        if self.memoriser.isChecked():
            set_setting(self.conn, "destination_defaut", dest)
        params = {"au": jour.isoformat(), "brouillard": self.brouillard.isChecked(),
                  "niveau": self.niveau.currentData(), "francs": self.francs.isChecked(),
                  "titre": self.titre.text().strip() or "SITUATION INTERMEDIAIRE DE GESTION",
                  "entete": self.entete.isChecked(), "soldes": self.soldes.isChecked(), "destination": dest}
        edition_id = compta.nouvelle_edition(self.conn, self.main.dossier["code"], "situation", params)
        fichier = compta.nom_fichier_situation(self.main.dossier["code"], params["au"])
        if dest == "imprimante":
            theme.info(self, f"Edition envoyée vers {theme.IMPRIMANTE} (travail n° {4470 + edition_id}).\n"
                             "Récupérez votre document à l'imprimante.")
        elif dest == "pdf":
            theme.info(self, f"Fichier enregistré sous C:\\COMPTAREX\\EDITIONS\\{fichier} sur le serveur du cabinet.")
        else:
            theme.traitement(self, ["Lecture des écritures...", "Calcul des soldes...", "Mise en page..."])
            self.params = {**params, "edition_id": edition_id}
            self.accept()


def _mois(au: date) -> str:
    mois_suivant = (au.replace(day=28) + timedelta(days=4)).replace(day=1)
    if (mois_suivant - au).days == 1:
        return f"{au.month} mois"
    return f"{au.month - 1} mois et {au.day} jour(s)"


def pages_situation(conn, dossier, params: dict, numero: str, edite_le: datetime) -> list[str]:
    s = compta.situation(conn, dossier["code"], params["au"], params["brouillard"], params["niveau"], params["francs"])
    detail = [r for r in s["detail"] if params.get("soldes") or r["solde_debiteur"] or r["solde_crediteur"]]
    blocs = [detail[i:i + LIGNES_PAR_PAGE] for i in range(0, len(detail), LIGNES_PAR_PAGE)]
    total = 1 + len(blocs)
    au_fr = compta.date_fr(params["au"])
    style = ("font-family:'Courier New',Courier,monospace; font-size:12px; color:#000000;")

    def entete(page: int) -> str:
        cab = "FIDUCIAIRE MOREAU &amp; ASSOCIES" if params.get("entete", True) else "&nbsp;"
        return (f"<table width='100%' style='{style}'><tr><td>{cab}</td><td align='right'>Page : {page}/{total}</td></tr>"
                f"<tr><td>Dossier : {escape(compta.libelle_dossier(dossier))}</td>"
                f"<td align='right'>Edité le {edite_le:%d/%m/%Y %H:%M} par {config.USER_CODE}</td></tr></table>")

    def pied() -> str:
        return (f"<hr><table width='100%' style='{style}'><tr><td>COMPTAREX 6.2.4</td>"
                f"<td align='right'>Edition n° {numero}</td></tr></table>")

    def ligne(libelle, montant, extra="", gras=False):
        b, fb = ("<b>", "</b>") if gras else ("", "")
        return (f"<tr><td>{b}{escape(libelle)}{fb}</td><td align='right'>{b}{compta.fmt(montant)}{fb}</td>"
                f"<td align='right'>{extra}</td></tr>")

    p1 = [entete(1),
          f"<p align='center' style='{style} font-size:14px;'><b>{escape(params['titre'])} — PROVISOIRE</b></p>",
          f"<p align='center' style='{style}'>Période du 01/01/2026 au {au_fr} ({_mois(date.fromisoformat(params['au']))})<br>"
          f"Ecritures validées{' et brouillard' if params['brouillard'] else ' uniquement'} — Montants en euros</p>",
          f"<p style='{style}'><b><u>1. SOLDES INTERMEDIAIRES DE GESTION</u></b></p>",
          f"<table width='100%' cellspacing='0' style='{style}'><tr><th align='left'>Libellé</th>"
          f"<th align='right'>Période</th><th align='right'>% CA</th></tr>"]
    p1 += [ligne(l["libelle"], l["montant"], l["pct"], l["total"]) for l in s["sig"]]
    if s["resultat_frf"] is not None:
        p1.append(ligne("   soit en francs (FRF)", s["resultat_frf"]))
    p1.append("</table>")
    p1.append(f"<p style='{style}'><b><u>2. TRESORERIE AU {au_fr}</u></b></p><table width='100%' style='{style}'>")
    p1 += [ligne(f"{t['compte']} {t['libelle'].upper()}", t["solde"]) for t in s["tresorerie"]]
    p1.append(ligne("TOTAL TRESORERIE", s["tresorerie_total"], gras=True) + "</table>")
    p1.append(f"<p style='{style}'><b><u>3. TIERS ET TVA</u></b></p><table width='100%' style='{style}'>")
    p1 += [ligne("411 CLIENTS (solde débiteur)", s["clients"]),
           ligne(f"   dont échu à plus de 60 jours ({s['clients_echus_nb']} facture(s))", s["clients_echus"]),
           ligne("401 FOURNISSEURS (solde créditeur)", s["fournisseurs"]),
           ligne("44551 TVA A DECAISSER", s["tva_a_decaisser"]), "</table>"]
    if s["alertes"]:
        p1.append(f"<table width='100%' border='1' cellpadding='4' cellspacing='0' style='{style}'><tr><td>"
                  + "<br>".join(f"ATTENTION : {escape(a)}" for a in s["alertes"]) + "</td></tr></table>")
    p1.append(pied())
    pages = ["".join(p1)]
    for i, bloc in enumerate(blocs, start=2):
        lignes = "".join(
            f"<tr><td>{r['compte']}</td><td>{escape(r['libelle'] or '')}</td><td align='right'>{compta.fmt(r['debit'])}</td>"
            f"<td align='right'>{compta.fmt(r['credit'])}</td>"
            f"<td align='right'>{compta.fmt(r['solde_debiteur'] - r['solde_crediteur'])}</td></tr>" for r in bloc)
        pages.append(entete(i) + f"<p style='{style}'><b><u>4. DETAIL DES COMPTES ({escape(compta.NIVEAUX[params['niveau']])})"
                     f"</u></b></p><table width='100%' cellspacing='0' style='{style}'><tr><th align='left'>Compte</th>"
                     f"<th align='left'>Libellé</th><th align='right'>Débit</th><th align='right'>Crédit</th>"
                     f"<th align='right'>Solde</th></tr>{lignes}</table>" + pied())
    return pages


class ApercuWindow(QWidget):
    """Aperçu avant impression de la situation (sous-fenêtre MDI)."""

    def __init__(self, main, params: dict):
        super().__init__()
        self.main, self.conn, self.params = main, main.conn, params
        ed = compta.edition(self.conn, params["edition_id"])
        self.numero = ed["numero"] if ed else "—"
        self.fichier = compta.nom_fichier_situation(main.dossier["code"], params["au"])
        self.setWindowTitle(f"Aperçu — {self.fichier[:-4]}")
        self.pages = pages_situation(self.conn, main.dossier, params, self.numero, datetime.now())
        self.page = 0
        lay = QVBoxLayout(self)
        barre = QHBoxLayout()
        for texte, nom, slot in (("|<", "Première page", lambda: self.aller(0)),
                                 ("<", "Page précédente", lambda: self.aller(self.page - 1))):
            b = theme.bouton(texte, slot, nom)
            b.setMaximumWidth(30)
            barre.addWidget(b)
        self.lbl_page = QLabel()
        barre.addWidget(self.lbl_page)
        for texte, nom, slot in ((">", "Page suivante", lambda: self.aller(self.page + 1)),
                                 (">|", "Dernière page", lambda: self.aller(len(self.pages) - 1))):
            b = theme.bouton(texte, slot, nom)
            b.setMaximumWidth(30)
            barre.addWidget(b)
        self.zoom = QComboBox()
        self.zoom.addItems(["100 %", "75 %", "150 %"])
        self.zoom.setAccessibleName("Zoom")
        self.zoom.currentIndexChanged.connect(lambda _i: self.aller(self.page))
        barre.addWidget(QLabel("Zoom :"))
        barre.addWidget(self.zoom)
        barre.addWidget(theme.bouton("Imprimer...", lambda: theme.info(
            self, f"Edition envoyée vers {theme.IMPRIMANTE} (travail n° {4470 + params['edition_id']}).")))
        barre.addWidget(theme.bouton("Exporter...", lambda: theme.info(
            self, f"Fichier enregistré sous C:\\COMPTAREX\\EDITIONS\\{self.fichier} sur le serveur du cabinet.")))
        barre.addWidget(theme.bouton("Transmettre au client...", self.transmettre))
        barre.addStretch()
        barre.addWidget(theme.bouton("Fermer", lambda: self.parentWidget().close()))
        lay.addLayout(barre)
        self.vue = QTextBrowser()
        self.vue.setAccessibleName("Situation intermédiaire")
        self.vue.setStyleSheet("QTextBrowser { background: #FFFFFF; border: 12px solid #808080; padding: 18px; }")
        lay.addWidget(self.vue)
        self.aller(0)
        self.resize(820, 640)

    def aller(self, page: int) -> None:
        self.page = max(0, min(page, len(self.pages) - 1))
        facteur = {"100 %": 1.0, "75 %": 0.75, "150 %": 1.5}[self.zoom.currentText()]
        html = self.pages[self.page]
        for px in (14, 12):
            html = html.replace(f"font-size:{px}px", f"font-size:{round(px * facteur)}px")
        self.vue.setHtml(html)
        self.lbl_page.setText(f"  Page {self.page + 1} / {len(self.pages)}  ")

    def texte(self) -> str:
        return self.vue.toPlainText()

    def transmettre(self) -> None:
        TransmettreDialog(self.main, self.fichier, self.params["au"]).exec()


class TransmettreDialog(QDialog):
    def __init__(self, main, fichier: str, au: str):
        super().__init__(main)
        self.main = main
        self.fichier = fichier
        self.setWindowTitle("Transmission au client — Espace client")
        g = QGridLayout(self)
        self.dest = QComboBox()
        self.dest.addItems(compta.DESTINATAIRES.get(main.dossier["code"], ["CLIENT (espace client)"]))
        theme.champ(g, 0, "Destinataire * :", self.dest)
        self.objet = theme.champ(g, 1, "Objet * :", QLineEdit(f"SITUATION AU {compta.date_fr(au)}"))
        self.corps = QTextEdit()
        self.corps.setPlainText(f"Bonjour,\n\nVeuillez trouver ci-joint la situation intermédiaire au "
                                f"{compta.date_fr(au)}, provisoire.\n\nCordialement,\nC. Moreau")
        theme.champ(g, 2, "Message :", self.corps)
        g.addWidget(QLabel("Pièce jointe :"), 3, 0)
        g.addWidget(QLabel(f"{fichier} (84 Ko)"), 3, 1)
        accuse = QCheckBox("Demander un accusé de lecture")
        accuse.setChecked(True)
        g.addWidget(accuse, 4, 1)
        boutons = QHBoxLayout()
        boutons.addStretch()
        boutons.addWidget(theme.bouton("Envoyer", self.envoyer))
        boutons.addWidget(theme.bouton("Annuler", self.reject))
        g.addLayout(boutons, 5, 0, 1, 2)
        self.message_id = None
        self.resize(500, 320)

    def envoyer(self) -> None:
        if not self.objet.text().strip():
            return theme.erreur(self, "L'objet du message est obligatoire.")
        self.message_id = compta.envoyer_message(self.main.conn, self.main.dossier["code"], self.dest.currentText(),
                                                 self.objet.text(), self.corps.toPlainText(), self.fichier)
        theme.info(self, f"Message envoyé (réf. MSG-{date.today():%Y-%m}-{self.message_id:04d}). "
                         "Il sera visible par le client dans son espace sous 24 heures.")
        self.main.rafraichir_messagerie()
        self.accept()
