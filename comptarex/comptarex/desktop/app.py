"""COMPTAREX Cabinet 6.2, version logiciel : connexion, choix du dossier, fenêtre principale MDI.

    uv run --extra desktop comptarex-desktop
"""
from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMdiArea, QMdiSubWindow, QVBoxLayout)

from .. import compta, config, db
from . import fenetres, theme
from .situation import ApercuWindow, SituationDialog


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("COMPTAREX Cabinet 6.2 — Identification")
        self.essais = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.addWidget(theme.bandeau("Cabinet 6.2", "Comptabilité générale, analytique et tiers — "
                                                   "Fiduciaire Moreau &amp; Associés"))
        corps = QVBoxLayout()
        corps.setContentsMargins(16, 8, 16, 0)
        corps.addWidget(theme.barre_titre("Identification de l'utilisateur"))
        corps.addWidget(QLabel("Veuillez saisir vos identifiants."))
        g = QGridLayout()
        self.email = theme.champ(g, 0, "E-mail", QLineEdit())
        self.mdp = theme.champ(g, 1, "Mot de passe", QLineEdit())
        self.mdp.setEchoMode(QLineEdit.Password)
        self.exercice = QComboBox()
        self.exercice.addItems(["2026", "2025", "2024"])
        theme.champ(g, 2, "Exercice", self.exercice)
        langue = QComboBox()
        langue.addItem("Français")
        theme.champ(g, 3, "Langue", langue)
        corps.addLayout(g)
        corps.addWidget(QCheckBox("Mémoriser mes identifiants sur ce poste (déconseillé)"))
        self.connexion = theme.bouton("Se connecter", self.verifier)
        self.connexion.setDefault(True)
        corps.addLayout(fenetres.boutons(None, self.connexion, theme.bouton("Effacer", self.effacer)))
        corps.addWidget(theme.avertissement("Attention : après 3 essais infructueux, votre compte sera bloqué. "
                                            "Contactez votre administrateur."))
        pied = QLabel("Poste : CAB-PC07 — © 2004 Comptarex S.A. — v6.2.4 (build 20041117)")
        pied.setStyleSheet("color: #4A4A4A;")
        corps.addWidget(pied)
        lay.addLayout(corps)
        self.resize(460, 380)

    def effacer(self) -> None:
        self.email.clear()
        self.mdp.clear()

    def verifier(self) -> None:
        if (self.email.text().strip().lower() != config.LOGIN.lower()) or self.mdp.text() != config.PASSWORD:
            self.essais += 1
            return theme.erreur(self, f"Identifiants incorrects (code 0x12).\nIl vous reste "
                                      f"{max(1, 3 - self.essais)} essai(s).")
        if self.exercice.currentText() != "2026":
            return theme.erreur(self, f"Exercice {self.exercice.currentText()} archivé : "
                                      "contactez votre administrateur.")
        self.accept()


class DossierDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.choix: tuple[str, bool] | None = None      # (code, consultation seule)
        self.page = 1
        self.setWindowTitle("Sélection du dossier de travail")
        lay = QVBoxLayout(self)
        lay.addWidget(theme.barre_titre("Sélection du dossier de travail"))
        filtres = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setAccessibleName("Rechercher")
        lbl = QLabel("Rechercher :")
        lbl.setBuddy(self.q)
        filtres.addWidget(lbl)
        filtres.addWidget(self.q)
        filtres.addWidget(theme.bouton("OK", self.chercher, "Lancer la recherche"))
        self.collab = QComboBox()
        self.collab.addItems(["Tous", "CMOREAU", "JPETIT", "APERRIN"])
        self.collab.setAccessibleName("Collaborateur")
        self.etat = QComboBox()
        self.etat.addItems(["Tous", "Ouverts", "Clôturés"])
        self.etat.setAccessibleName("Etat")
        for libelle, w in (("Collaborateur :", self.collab), ("Etat :", self.etat)):
            lbl = QLabel(libelle)
            lbl.setBuddy(w)
            filtres.addWidget(lbl)
            filtres.addWidget(w)
            w.currentIndexChanged.connect(lambda _i: self.chercher())
        filtres.addStretch()
        self.lbl_page = QLabel()
        filtres.addWidget(self.lbl_page)
        for texte, nom, delta in (("<<", "Première page", -99), ("<", "Page précédente", -1),
                                  (">", "Page suivante", 1), (">>", "Dernière page", 99)):
            b = theme.bouton(texte, lambda _=False, d=delta: self.aller(d), nom)
            b.setMaximumWidth(30)
            filtres.addWidget(b)
        lay.addLayout(filtres)
        self.table = fenetres.tableau(["Dossier", "Régime TVA", "Clôture", "Collab.", "Dern. saisie", "Etat"],
                                      "Dossiers clients")
        self.table.doubleClicked.connect(lambda _i: self.ouvrir(False))
        lay.addWidget(self.table)
        lay.addWidget(QLabel("Double-cliquez sur une ligne pour ouvrir le dossier, ou sélectionnez-la puis cliquez "
                             "sur « Ouvrir le dossier ».\nUn dossier verrouillé par un autre collaborateur ne peut être "
                             "ouvert qu'en consultation."))
        lay.addLayout(fenetres.boutons(theme.bouton("Ouvrir le dossier", lambda: self.ouvrir(False)),
                                       theme.bouton("Ouvrir en consultation", lambda: self.ouvrir(True)),
                                       theme.bouton("Actualiser", self.charger), None,
                                       theme.bouton("Quitter", self.reject)))
        self.charger()
        self.resize(760, 430)

    def chercher(self) -> None:
        self.page = 1
        self.charger()

    def aller(self, delta: int) -> None:
        self.page += delta
        self.charger()

    def charger(self) -> None:
        collab = "" if self.collab.currentText() == "Tous" else self.collab.currentText()
        etat = "" if self.etat.currentText() == "Tous" else self.etat.currentText()
        self.rows, total, self.page, pages = compta.dossiers(self.conn, self.q.text(), collab, etat, self.page)
        self.lbl_page.setText(f"{total} dossier(s) — Page {self.page}/{pages}")
        fenetres.remplir(self.table, [[compta.libelle_dossier(r), r["regime_tva"], r["cloture"], r["collab"],
                                       compta.date_fr(r["derniere_saisie"]),
                                       f"Verrouillé par {r['verrou']}" if r["verrou"] else r["etat"]]
                                      for r in self.rows])

    def ouvrir(self, consultation: bool) -> None:
        i = self.table.currentRow()
        if i < 0:
            return theme.info(self, "Sélectionnez un dossier dans la liste.")
        r = self.rows[i]
        if r["verrou"] and not consultation:
            if not theme.question(self, f"Dossier verrouillé par {r['verrou']}.\n"
                                        "Ouvrir le dossier en consultation seule ?"):
                return
            consultation = True
        if r["etat"] == "Clôturé" and not consultation:
            theme.info(self, "Exercice clôturé : le dossier est ouvert en consultation.")
            consultation = True
        self.choix = (r["code"], consultation)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, conn, code: str, consultation: bool = False):
        super().__init__()
        self.conn = conn
        self.mdi = QMdiArea()
        self.mdi.setBackground(QBrush(QColor("#808080")))
        self.setCentralWidget(self.mdi)
        self.menuBar().setNativeMenuBar(False)
        self._menus()
        self._outils()
        self._barre_etat()
        self.charger_dossier(code, consultation)
        self.resize(1024, 740)

    # -- construction
    def _action(self, menu, texte: str, slot, raccourci: str | None = None, saisie: bool = False) -> QAction:
        a = QAction(texte, self)
        if raccourci:
            a.setShortcut(QKeySequence(raccourci))
        a.triggered.connect(slot)
        menu.addAction(a)
        if saisie:
            self.actions_saisie.append(a)
        return a

    def _indispo(self, nom: str):
        return lambda: theme.module_indisponible(self, nom)

    def _menus(self) -> None:
        self.actions_saisie: list[QAction] = []
        mb = self.menuBar()
        m = mb.addMenu("&Fichier")
        self._action(m, "Changer de dossier...", self.changer_dossier, "Ctrl+O")
        self._action(m, "Paramètres d'impression...", self._indispo("Paramètres d'impression"))
        m.addSeparator()
        self._action(m, "Quitter", self.close, "Ctrl+Q")
        m = mb.addMenu("&Dossier")
        self._action(m, "Informations du dossier...", self.infos)
        self._action(m, "Fermer le dossier", self.changer_dossier)
        m = mb.addMenu("&Saisie")
        self._action(m, "Saisie par journal...", self._indispo("Saisie par journal"))
        self._action(m, "Factures à traiter...", self.ouvrir_pieces, "Ctrl+T")
        self._action(m, "Nouvelle facture fournisseur...", lambda: self.ouvrir_facture(), "Ctrl+N", saisie=True)
        self._action(m, "Liste des factures fournisseurs...", lambda: self.ouvrir(fenetres.ListeFacturesWindow(self)))
        self._action(m, "Factures clients...", self._indispo("Factures clients"))
        m = mb.addMenu("&Consultation")
        self._action(m, "Consultation de compte...", lambda: self.ouvrir(fenetres.GrandLivreWindow(self)), "Ctrl+K")
        self._action(m, "Recherche d'écritures...", lambda: self.ouvrir(fenetres.RechercheWindow(self)), "Ctrl+F")
        m = mb.addMenu("&Editions")
        self._action(m, "Journaux...", self._indispo("Journaux"), "Ctrl+J")
        self._action(m, "Grand livre...", lambda: self.ouvrir(fenetres.GrandLivreWindow(self)), "Ctrl+G")
        self._action(m, "Balance générale...", lambda: self.ouvrir(fenetres.BalanceWindow(self)), "Ctrl+B")
        self._action(m, "Balance âgée tiers...", self._indispo("Balance âgée"))
        m.addSeparator()
        sm = m.addMenu("Etats de synthèse")
        self._action(sm, "Bilan...", self._indispo("Bilan"))
        self._action(sm, "Compte de résultat...", self._indispo("Compte de résultat"))
        self._action(sm, "Situation intermédiaire...", self.situation)
        self._action(sm, "Soldes intermédiaires de gestion...", self._indispo("SIG"))
        m.addSeparator()
        self._action(m, "Rééditer la dernière édition", self.reediter, "Ctrl+R")
        self._action(m, "Historique des éditions...", self._indispo("Historique des éditions"))
        self._action(m, "Paramétrage des états...", self._indispo("Paramétrage des états"))
        m = mb.addMenu("&Révision")
        self._action(m, "Dossier de révision...", self._indispo("Révision"))
        self._action(m, "Lettrage...", self._indispo("Lettrage"))
        m = mb.addMenu("C&ommunication")
        self._action(m, "Messagerie...", self.ouvrir_messagerie, "Ctrl+M")
        self._action(m, "Nouveau message...", self.nouveau_message)
        m = mb.addMenu("Fe&nêtre")
        self._action(m, "Cascade", self.mdi.cascadeSubWindows)
        self._action(m, "Mosaïque", self.mdi.tileSubWindows)
        self._action(m, "Fermer tout", self.mdi.closeAllSubWindows)
        m = mb.addMenu("&?")
        self._action(m, "Aide", lambda: theme.info(self, "L'aide en ligne nécessite Internet Explorer 6.0 SP1."), "F1")
        self._action(m, "A propos de COMPTAREX...", lambda: theme.info(
            self, "COMPTAREX Cabinet 6.2.4 (build 20041117)\n© 2004 Comptarex S.A.\n"
                  "Licence CFM-042-2004 — 12 postes — Fiduciaire Moreau & Associés"))

    def _outils(self) -> None:
        tb = self.addToolBar("Outils")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        for item in (("dossier", "Changer de dossier", self.changer_dossier),
                     ("fermer", "Fermer toutes les fenêtres", self.mdi.closeAllSubWindows), None,
                     ("saisie", "Nouvelle facture fournisseur", lambda: self.ouvrir_facture()),
                     ("loupe", "Consultation de compte", lambda: self.ouvrir(fenetres.GrandLivreWindow(self))),
                     ("balance", "Balance générale", lambda: self.ouvrir(fenetres.BalanceWindow(self))),
                     ("situation", "Situation intermédiaire", self.situation),
                     ("imprimer", "Imprimer", lambda: theme.info(self, "Aucun document à imprimer.")), None,
                     ("message", "Messagerie", self.ouvrir_messagerie), "badge", None,
                     ("aide", "Aide", lambda: theme.info(self, "L'aide en ligne nécessite Internet Explorer 6.0 SP1."))):
            if item is None:
                tb.addSeparator()
            elif item == "badge":
                self.badge = QLabel()
                self.badge.setStyleSheet(f"background: {theme.ROUGE}; color: white; font-weight: bold; padding: 0 3px;")
                tb.addWidget(self.badge)
            else:
                nom_icone, texte, slot = item
                a = tb.addAction(theme.icone(nom_icone), texte)
                a.setToolTip(texte)
                a.triggered.connect(slot)
                tb.widgetForAction(a).setAccessibleName(texte)
                if nom_icone == "saisie":
                    self.actions_saisie.append(a)

    def _barre_etat(self) -> None:
        sb = self.statusBar()
        self.p_pret = theme.panneau("Prêt")
        sb.addWidget(self.p_pret, 1)
        self.p_dossier, self.p_exo, self.p_periode = theme.panneau(), theme.panneau(), theme.panneau("Période 11/2026")
        self.p_user, self.p_heure = theme.panneau(config.USER_CODE), theme.panneau()
        self.p_exo.setText("Exercice 01/01/2026 - 31/12/2026")
        for p in (self.p_dossier, self.p_exo, self.p_periode, self.p_user, self.p_heure):
            sb.addPermanentWidget(p)
        self.horloge = QTimer(self)
        self.horloge.timeout.connect(lambda: self.p_heure.setText(f"{datetime.now():%H:%M}"))
        self.horloge.start(30000)
        self.p_heure.setText(f"{datetime.now():%H:%M}")

    # -- dossier
    def charger_dossier(self, code: str, consultation: bool) -> None:
        self.mdi.closeAllSubWindows()
        self.dossier = compta.dossier(self.conn, code)
        self.lecture_seule = consultation
        version = "6.3" if compta.ui(self.conn)["version"] == "v2" else "6.2"
        self.setWindowTitle(f"COMPTAREX Cabinet {version} — [{compta.libelle_dossier(self.dossier)} — Exercice 2026]"
                            + (" (consultation)" if consultation else ""))
        self.p_dossier.setText(f"Dossier {code}" + (" — CONSULTATION" if consultation else ""))
        for a in self.actions_saisie:
            a.setEnabled(not consultation)
        self.ouvrir(fenetres.MessagerieWindow(self)).move(16, 14)
        if compta.pieces(self.conn, code):
            self.ouvrir(fenetres.PiecesWindow(self)).move(300, 150)

    def changer_dossier(self) -> None:
        dlg = DossierDialog(self.conn, self)
        if dlg.exec() and dlg.choix:
            self.charger_dossier(*dlg.choix)

    def infos(self) -> None:
        i = compta.infos_dossier(self.conn, self.dossier["code"])
        theme.info(self, f"{compta.libelle_dossier(self.dossier)}\nRégime TVA : {self.dossier['regime_tva']}\n"
                         f"Clôture : {self.dossier['cloture']}\nCollaborateur : {self.dossier['collab']}\n"
                         f"Dernière écriture : {i['derniere']}\nEcritures en brouillard : {i['brouillard']}")

    # -- sous-fenêtres
    def ouvrir(self, widget, cle: str | None = None) -> QMdiSubWindow:
        cle = cle or type(widget).__name__
        for sw in self.mdi.subWindowList():
            if getattr(sw, "cle", None) == cle:
                widget.deleteLater()
                self.mdi.setActiveSubWindow(sw)
                sw.showNormal()
                return sw
        sw = self.mdi.addSubWindow(widget)
        sw.cle = cle
        sw.setAttribute(Qt.WA_DeleteOnClose)
        sw.setWindowTitle(widget.windowTitle())
        sw.setWindowIcon(theme.icone("balance"))
        sw.resize(widget.size().width() + 8, widget.size().height() + 28)
        n = len(self.mdi.subWindowList()) - 1
        sw.move(24 * (n % 8), 24 * (n % 8))
        sw.show()
        return sw

    def sous_fenetres(self, classe) -> list:
        return [sw.widget() for sw in self.mdi.subWindowList() if isinstance(sw.widget(), classe)]

    def ouvrir_messagerie(self) -> None:
        self.ouvrir(fenetres.MessagerieWindow(self))

    def ouvrir_pieces(self) -> None:
        self.ouvrir(fenetres.PiecesWindow(self))

    def ouvrir_facture(self, facture_id: int | None = None, piece: str | None = None) -> None:
        if self.lecture_seule and not facture_id:
            return theme.erreur(self, "Dossier ouvert en consultation : saisie impossible.")
        cle = f"facture-{facture_id}" if facture_id else f"nouvelle-{datetime.now().timestamp()}"
        self.ouvrir(fenetres.FactureWindow(self, facture_id, piece), cle)

    def nouveau_message(self) -> None:
        if fenetres.NouveauMessageDialog(self).exec():
            self.rafraichir_messagerie()

    def situation(self) -> None:
        dlg = SituationDialog(self)
        if dlg.exec() and dlg.params:
            self.apercu(dlg.params)

    def apercu(self, params: dict) -> None:
        self.derniere_edition = params
        self.ouvrir(ApercuWindow(self, params), f"apercu-{params['edition_id']}").showMaximized()

    def reediter(self) -> None:
        if not getattr(self, "derniere_edition", None):
            return theme.info(self, "Aucune édition dans l'historique de la session.")
        self.apercu(self.derniere_edition)

    # -- rafraîchissements
    def statut(self, texte: str) -> None:
        self.p_pret.setText(texte)
        QTimer.singleShot(8000, lambda: self.p_pret.setText("Prêt"))

    def maj_badge(self, non_lus: int) -> None:
        self.badge.setText(str(non_lus) if non_lus else "")
        self.badge.setVisible(bool(non_lus))

    def rafraichir_messagerie(self) -> None:
        for w in self.sous_fenetres(fenetres.MessagerieWindow):
            w.charger()

    def rafraichir_pieces(self) -> None:
        for w in self.sous_fenetres(fenetres.PiecesWindow) + self.sous_fenetres(fenetres.ListeFacturesWindow):
            w.charger()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("COMPTAREX Cabinet")
    theme.appliquer(app)
    app.setWindowIcon(theme.icone("balance"))
    conn = db.connect()
    if LoginDialog().exec() != QDialog.Accepted:
        return
    dlg = DossierDialog(conn)
    if dlg.exec() != QDialog.Accepted or not dlg.choix:
        return
    fenetre = MainWindow(conn, *dlg.choix)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
