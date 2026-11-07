"""Les sous-fenêtres MDI : messagerie, factures à traiter, saisie de facture, consultations."""
from __future__ import annotations

from datetime import date
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout,
                               QWidget, QAbstractItemView, QHeaderView)

from .. import compta, config
from . import theme

PAR_PAGE = 15


def tableau(colonnes: list[str], nom: str) -> QTableWidget:
    t = QTableWidget(0, len(colonnes))
    t.setHorizontalHeaderLabels(colonnes)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(18)
    t.horizontalHeader().setStretchLastSection(True)
    t.setAccessibleName(nom)
    return t


def remplir(t: QTableWidget, lignes: list[list], droite: set[int] = frozenset(), gras=lambda i: False) -> None:
    t.setRowCount(len(lignes))
    for i, ligne in enumerate(lignes):
        for j, valeur in enumerate(ligne):
            item = QTableWidgetItem("" if valeur is None else str(valeur))
            if j in droite:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if gras(i):
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            t.setItem(i, j, item)
    t.resizeColumnsToContents()
    t.horizontalHeader().setStretchLastSection(True)


class Pagineur(QWidget):
    """|< < Page x / n > >| : 15 lignes par page, comme le vrai."""

    def __init__(self, rappel):
        super().__init__()
        self.rappel, self.page, self.pages = rappel, 1, 1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for texte, nom, delta in (("|<", "Première page", "debut"), ("<", "Page précédente", -1)):
            b = theme.bouton(texte, lambda _=False, d=delta: self.aller(d), nom)
            b.setMaximumWidth(30)
            lay.addWidget(b)
        self.lbl = QLabel()
        lay.addWidget(self.lbl)
        for texte, nom, delta in ((">", "Page suivante", 1), (">|", "Dernière page", "fin")):
            b = theme.bouton(texte, lambda _=False, d=delta: self.aller(d), nom)
            b.setMaximumWidth(30)
            lay.addWidget(b)

    def regler(self, nb: int) -> None:
        self.pages = max(1, -(-nb // PAR_PAGE))
        self.page = min(self.page, self.pages)
        self.lbl.setText(f" {nb} ligne(s) — Page {self.page}/{self.pages} ")

    def tranche(self, lignes: list) -> list:
        self.regler(len(lignes))
        return lignes[(self.page - 1) * PAR_PAGE: self.page * PAR_PAGE]

    def aller(self, delta) -> None:
        self.page = 1 if delta == "debut" else self.pages if delta == "fin" else self.page + delta
        self.page = max(1, min(self.page, self.pages))
        self.rappel()


def boutons(*items) -> QHBoxLayout:
    lay = QHBoxLayout()
    for item in items:
        if item is None:
            lay.addStretch()
        else:
            lay.addWidget(item)
    return lay


# ---------------------------------------------------------------- messagerie

class MessagerieWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        lay = QVBoxLayout(self)
        haut = QHBoxLayout()
        self.vue = QComboBox()
        self.vue.addItems(["Boîte de réception", "Messages envoyés"])
        self.vue.setAccessibleName("Afficher")
        self.vue.currentIndexChanged.connect(lambda _i: self.charger())
        haut.addWidget(QLabel("Afficher :"))
        haut.addWidget(self.vue)
        haut.addStretch()
        lay.addLayout(haut)
        self.table = tableau(["!", "Date", "De / A", "Objet", "P.J."], "Messages")
        self.table.doubleClicked.connect(lambda _i: self.lire())
        lay.addWidget(self.table)
        lay.addLayout(boutons(theme.bouton("Lire", self.lire), theme.bouton("Nouveau message...", self.nouveau),
                              theme.bouton("Actualiser", self.charger), None))
        self.charger()
        self.resize(620, 250)

    def charger(self) -> None:
        sens = "recu" if self.vue.currentIndex() == 0 else "envoye"
        self.rows = compta.messages(self.conn, self.main.dossier["code"], sens)
        non_lus = sum(1 for r in compta.messages(self.conn, self.main.dossier["code"], "recu") if not r["lu"])
        self.setWindowTitle(f"Messagerie — Boîte de réception ({non_lus} non lu(s))")
        remplir(self.table, [["" if r["lu"] else "!", compta.date_fr(r["date"]),
                              r["de"] if sens == "recu" else r["a"], r["objet"], "Oui" if r["piece_jointe"] else "Non"]
                             for r in self.rows], gras=lambda i: not self.rows[i]["lu"])
        self.main.maj_badge(non_lus)

    def lire(self) -> None:
        i = self.table.currentRow()
        if i < 0:
            return theme.info(self, "Sélectionnez un message dans la liste.")
        MessageDialog(self.main, compta.message(self.conn, self.rows[i]["id"])).exec()
        self.charger()

    def nouveau(self) -> None:
        if NouveauMessageDialog(self.main).exec():
            self.vue.setCurrentIndex(1)
            self.charger()


class MessageDialog(QDialog):
    def __init__(self, main, msg):
        super().__init__(main)
        self.main, self.msg = main, msg
        self.setWindowTitle(f"Message — {msg['objet']}")
        g = QGridLayout(self)
        for i, (lib, val) in enumerate((("De :", msg["de"]), ("A :", msg["a"]), ("Date :", compta.date_fr(msg["date"])),
                                        ("Objet :", msg["objet"]), ("Pièce jointe :", msg["piece_jointe"] or "aucune"))):
            theme.champ(g, i, lib, theme.lecture_seule(QLineEdit(val)))
        corps = QTextEdit()
        corps.setPlainText(msg["corps"] or "")
        corps.setReadOnly(True)
        theme.champ(g, 5, "Message :", corps)
        g.addLayout(boutons(None, theme.bouton("Répondre", self.repondre), theme.bouton("Fermer", self.accept)), 6, 0, 1, 2)
        self.resize(560, 380)

    def repondre(self) -> None:
        NouveauMessageDialog(self.main, f"RE: {self.msg['objet']}").exec()
        self.accept()


class NouveauMessageDialog(QDialog):
    def __init__(self, main, objet: str = "", piece_jointe: str = ""):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Nouveau message — Espace client")
        g = QGridLayout(self)
        self.dest = QComboBox()
        self.dest.addItems(compta.DESTINATAIRES.get(main.dossier["code"], ["CLIENT (espace client)"]))
        theme.champ(g, 0, "Destinataire * :", self.dest)
        self.objet = theme.champ(g, 1, "Objet * :", QLineEdit(objet))
        self.corps = QTextEdit()
        theme.champ(g, 2, "Message :", self.corps)
        self.pj = theme.champ(g, 3, "Pièce jointe :", QLineEdit(piece_jointe))
        g.addLayout(boutons(None, theme.bouton("Envoyer", self.envoyer), theme.bouton("Annuler", self.reject)), 4, 0, 1, 2)
        self.message_id = None
        self.resize(520, 340)

    def envoyer(self) -> None:
        if not self.objet.text().strip():
            return theme.erreur(self, "L'objet du message est obligatoire.")
        self.message_id = compta.envoyer_message(self.main.conn, self.main.dossier["code"], self.dest.currentText(),
                                                 self.objet.text(), self.corps.toPlainText(), self.pj.text().strip())
        theme.info(self, f"Message envoyé (réf. MSG-{date.today():%Y-%m}-{self.message_id:04d}). "
                         "Il sera visible par le client dans son espace sous 24 heures.")
        self.accept()


# ---------------------------------------------------------------- factures à traiter

class PiecesWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Double-cliquez sur une pièce pour ouvrir le PDF."))
        self.table = tableau(["N° pièce", "Reçue le", "Expéditeur", "Réf. fournisseur", "Montant TTC", "Statut"],
                             "Factures à traiter")
        self.table.doubleClicked.connect(lambda _i: self.ouvrir())
        lay.addWidget(self.table)
        self.saisir_btn = theme.bouton("Saisir la facture", self.saisir)
        self.saisir_btn.setEnabled(not main.lecture_seule)
        lay.addLayout(boutons(theme.bouton("Ouvrir la pièce (PDF)", self.ouvrir), self.saisir_btn,
                              theme.bouton("Actualiser", self.charger), None))
        self.charger()
        self.resize(680, 340)

    def charger(self) -> None:
        self.rows = compta.pieces(self.conn, self.main.dossier["code"])
        self.setWindowTitle(f"Factures à traiter ({sum(1 for r in self.rows if r['statut'] == 'A SAISIR')})")
        remplir(self.table, [[r["code"], compta.date_fr(r["recue_le"]), r["expediteur"], r["reference"],
                              compta.fmt(r["montant"]), r["statut"]] for r in self.rows], droite={4})

    def courante(self):
        i = self.table.currentRow()
        if i < 0:
            theme.info(self, "Sélectionnez une pièce dans la liste.")
            return None
        return self.rows[i]

    def ouvrir(self) -> None:
        p = self.courante()
        if p:
            theme.ouvrir_pdf(config.INBOX / p["fichier"])

    def saisir(self) -> None:
        p = self.courante()
        if p:
            self.main.ouvrir_facture(piece=p["code"])


# ---------------------------------------------------------------- saisie d'une facture fournisseur

COLONNES = ["Libellé", "Quantité", "Prix unitaire HT", "Taxe", "Montant HT"]


class CreerFournisseurDialog(QDialog):
    def __init__(self, parent, conn, dossier_code: str, nom: str = ""):
        super().__init__(parent)
        self.conn, self.dossier_code, self.tiers = conn, dossier_code, None
        self.setWindowTitle("Création d'un fournisseur")
        g = QGridLayout(self)
        self.nom = theme.champ(g, 0, "Raison sociale * :", QLineEdit(nom))
        self.pays = QComboBox()
        self.pays.addItems(["FR", "DE", "BE", "ES", "IT", "LU", "NL", "GB", "CH"])
        theme.champ(g, 1, "Pays :", self.pays)
        self.tva = theme.champ(g, 2, "N° TVA intracommunautaire :", QLineEdit())
        g.addWidget(QLabel("Le compte fournisseur (401…) est attribué automatiquement."), 3, 0, 1, 2)
        g.addLayout(boutons(None, theme.bouton("Créer", self.creer), theme.bouton("Annuler", self.reject)), 4, 0, 1, 2)

    def creer(self) -> None:
        try:
            self.tiers = compta.creer_fournisseur(self.conn, self.dossier_code, self.nom.text(),
                                                  self.pays.currentText(), self.tva.text())
        except ValueError as e:
            return theme.erreur(self, str(e))
        self.accept()


class FactureWindow(QWidget):
    def __init__(self, main, facture_id: int | None = None, piece: str | None = None):
        super().__init__()
        self.main, self.conn = main, main.conn
        self.dossier_code = main.dossier["code"]
        ui = compta.ui(self.conn)
        self.v2, self.confirmer = ui["version"] == "v2", ui["confirm"]
        self.facture_id, self.tiers_id = facture_id, None
        existante = compta.facture(self.conn, facture_id) if facture_id else None
        self.piece = piece or (existante["piece"] if existante else None)
        lay = QVBoxLayout(self)

        entete = QHBoxLayout()
        entete.addWidget(QLabel("Journal : <b>AC — ACHATS</b>"))
        if self.piece:
            entete.addWidget(QLabel("Pièce justificative :"))
            entete.addWidget(theme.bouton(f"{self.piece}.pdf (ouvrir)", self.ouvrir_piece))
        entete.addStretch()
        lay.addLayout(entete)

        self.fournisseur = QLineEdit()
        self.fournisseur.textEdited.connect(lambda _t: setattr(self, "tiers_id", None))
        self.completer_fournisseurs()
        self.reference = QLineEdit()
        self.date = QLineEdit()
        self.date.setPlaceholderText("JJ/MM/AAAA")
        self.date.setMaxLength(10)
        self.categorie = QComboBox()
        self.categorie.addItems(["-- Choisir --", *compta.CATEGORIES])
        creer = theme.bouton("+ Créer le fournisseur...", self.creer_fournisseur, "Créer le fournisseur")

        g = QGridLayout()
        theme.champ(g, 0, "Fournisseur", self.fournisseur)
        g.addWidget(creer, 0, 2)
        if self.v2:
            theme.champ(g, 1, "Date de facture", self.date, aide="(JJ/MM/AAAA)")
            theme.champ(g, 2, "Catégorie de dépense *", self.categorie)
            self.categorie.setAccessibleName("Catégorie de dépense")
        else:
            theme.champ(g, 1, "Référence fournisseur", self.reference)
            theme.champ(g, 2, "Date de facture", self.date, aide="(JJ/MM/AAAA)")
        general = QWidget()
        gl = QVBoxLayout(general)
        gl.addLayout(g)

        self.lignes = QTableWidget(0, len(COLONNES))
        self.lignes.setHorizontalHeaderLabels(COLONNES)
        self.lignes.setAccessibleName("Lignes de la facture")
        self.lignes.verticalHeader().setVisible(False)
        self.lignes.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lignes.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        gl.addWidget(self.lignes)
        bas = QHBoxLayout()
        bas.addWidget(theme.bouton("Ajouter une ligne", lambda: self.ajouter_ligne()))
        bas.addWidget(theme.bouton("Supprimer la ligne", self.supprimer_ligne))
        bas.addStretch()
        totaux = QGridLayout()
        self.total_ht, self.total_tva, self.total_ttc = QLabel(), QLabel(), QLabel()
        for i, (lib, lbl) in enumerate((("Total HT", self.total_ht), ("Total TVA", self.total_tva),
                                        ("Total TTC", self.total_ttc))):
            etiquette = QLabel(f"<b>{lib}</b>" if lib == "Total TTC" else lib)
            lbl.setAlignment(Qt.AlignRight)
            lbl.setAccessibleName(lib)
            lbl.setMinimumWidth(90)
            totaux.addWidget(etiquette, i, 0)
            totaux.addWidget(lbl, i, 1)
        self.autoliq = QLabel()
        self.autoliq.setStyleSheet("color: #4A4A4A;")
        totaux.addWidget(self.autoliq, 3, 0, 1, 2)
        bas.addLayout(totaux)
        gl.addLayout(bas)

        if self.v2:
            onglets = QTabWidget()
            onglets.addTab(general, "Général")
            details = QWidget()
            dg = QGridLayout(details)
            theme.champ(dg, 0, "Référence fournisseur", self.reference)
            dg.setRowStretch(1, 1)
            dg.setColumnStretch(2, 1)
            onglets.addTab(details, "Détails")
            self.onglets = onglets
            lay.addWidget(onglets)
        else:
            self.onglets = None
            lay.addWidget(general)

        self.etat = QLabel()
        self.etat.setStyleSheet("color: #0A246A; font-weight: bold;")
        lay.addWidget(self.etat)
        pied = QHBoxLayout()
        pied.addWidget(theme.avertissement("Une facture validée ne peut plus être modifiée (contre-passation obligatoire)."))
        pied.addStretch()
        self.btn_brouillon = theme.bouton("Sauvegarder" if self.v2 else "Enregistrer le brouillon",
                                          lambda: self.enregistrer(False))
        self.btn_valider = theme.bouton("Valider", lambda: self.enregistrer(True))
        pied.addWidget(self.btn_brouillon)
        pied.addWidget(self.btn_valider)
        pied.addWidget(theme.bouton("Annuler", lambda: self.parentWidget().close()))
        lay.addLayout(pied)

        if existante:
            self.charger(existante)
        else:
            self.ajouter_ligne()
            self.ajouter_ligne()
        if main.lecture_seule:
            self.btn_brouillon.setEnabled(False)
            self.btn_valider.setEnabled(False)
            self.etat.setText("Dossier ouvert en consultation : saisie impossible.")
        self.titre()
        self.recalculer()
        self.resize(780, 560)

    # -- fournisseurs
    def completer_fournisseurs(self) -> None:
        self.choix = {f"{r['nom']} — {r['code']}": r["id"] for r in compta.fournisseurs(self.conn, self.dossier_code)}
        completer = QCompleter(sorted(self.choix))
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated.connect(self.choisir)
        self.fournisseur.setCompleter(completer)

    def choisir(self, texte: str) -> None:
        self.fournisseur.setText(texte)
        self.tiers_id = self.choix.get(texte)

    def creer_fournisseur(self) -> None:
        nom = self.fournisseur.text().split(" — 401")[0]
        dlg = CreerFournisseurDialog(self, self.conn, self.dossier_code, nom)
        if dlg.exec() and dlg.tiers:
            self.appliquer_fournisseur(dlg.tiers)

    def appliquer_fournisseur(self, tiers) -> None:
        self.completer_fournisseurs()
        self.choisir(f"{tiers['nom']} — {tiers['code']}")

    def ouvrir_piece(self) -> None:
        p = compta.piece(self.conn, self.piece)
        if p:
            theme.ouvrir_pdf(config.INBOX / p["fichier"])

    # -- lignes
    def ajouter_ligne(self, libelle: str = "", quantite: str = "", prix: str = "", taxe: str = "20 %") -> None:
        i = self.lignes.rowCount()
        self.lignes.insertRow(i)
        for j, (valeur, nom) in enumerate(((libelle, "Libellé"), (quantite, "Quantité"), (prix, "Prix unitaire HT"))):
            edit = QLineEdit(valeur)
            edit.setAccessibleName(nom)
            edit.setFrame(False)
            if j:
                edit.setAlignment(Qt.AlignRight)
            edit.textChanged.connect(lambda _t: self.recalculer())
            self.lignes.setCellWidget(i, j, edit)
        combo = QComboBox()
        combo.addItems(list(compta.TAXES))
        combo.setCurrentText(taxe)
        combo.setAccessibleName("Taxe")
        combo.setAccessibleDescription("Taxe")
        combo.currentIndexChanged.connect(lambda _i: self.recalculer())
        self.lignes.setCellWidget(i, 3, combo)
        item = QTableWidgetItem("")
        item.setFlags(Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lignes.setItem(i, 4, item)
        self.lignes.setRowHeight(i, 22)
        self.lignes.setColumnWidth(3, 170)
        self.recalculer()

    def supprimer_ligne(self) -> None:
        i = self.lignes.currentRow()
        self.lignes.removeRow(i if i >= 0 else self.lignes.rowCount() - 1)
        self.recalculer()

    def lignes_brutes(self) -> list[dict]:
        out = []
        for i in range(self.lignes.rowCount()):
            w = [self.lignes.cellWidget(i, j) for j in range(4)]
            out.append({"libelle": w[0].text(), "quantite": w[1].text(), "prix_unitaire": w[2].text(),
                        "taxe": w[3].currentText()})
        return out

    def recalculer(self) -> None:
        valides = []
        for i, brute in enumerate(self.lignes_brutes()):
            q, p = compta.parse_quantite(brute["quantite"]), compta.parse_montant(brute["prix_unitaire"])
            item = self.lignes.item(i, 4)
            if q is not None and p is not None:
                ligne = {"quantite": q, "prix_unitaire": p, "taxe": brute["taxe"]}
                valides.append(ligne)
                if item:
                    item.setText(compta.fmt(round(q * p)))
            elif item:
                item.setText("")
        t = compta.calcul(valides)
        self.total_ht.setText(compta.fmt(t["total_ht"]))
        self.total_tva.setText(compta.fmt(t["total_tva"]))
        self.total_ttc.setText(f"<b>{compta.fmt(t['total_ttc'])}</b>")
        self.total_ttc.setAccessibleDescription(compta.fmt(t["total_ttc"]))
        self.autoliq.setText(f"TVA autoliquidée : {compta.fmt(t['tva_autoliquidee'])} (due et déductible)"
                             if t["tva_autoliquidee"] else "")

    # -- chargement / enregistrement
    def charger(self, f) -> None:
        self.fournisseur.setText(f"{f['fournisseur']} — {f['fournisseur_code']}")
        self.tiers_id = f["tiers_id"]
        self.reference.setText(f["reference"])
        self.date.setText(compta.date_fr(f["date"]))
        if f["categorie"]:
            self.categorie.setCurrentText(f["categorie"])
        for l in compta.facture_lignes(self.conn, f["id"]):
            q = l["quantite"]
            self.ajouter_ligne(l["libelle"], (str(int(q)) if float(q).is_integer() else str(q).replace(".", ",")),
                               compta.fmt(l["prix_unitaire"]).replace(" ", ""), l["taxe"])
        if f["statut"] == "validated":
            self.verrouiller()

    def titre(self) -> None:
        f = compta.facture(self.conn, self.facture_id)
        if not f:
            self.setWindowTitle("Factures fournisseurs — Nouvelle facture (non enregistrée)")
        else:
            etat = "validée" if f["statut"] == "validated" else "brouillon"
            self.setWindowTitle(f"Factures fournisseurs — Facture {f['numero']} ({etat})")
        if self.parentWidget():
            self.parentWidget().setWindowTitle(self.windowTitle())

    def donnees(self) -> dict:
        return {"fournisseur": self.fournisseur.text(), "fournisseur_id": self.tiers_id,
                "reference": self.reference.text(), "date": self.date.text(),
                "categorie": self.categorie.currentText() if self.categorie.currentIndex() > 0 else "",
                "piece": self.piece, "lignes": self.lignes_brutes()}

    def enregistrer(self, valider: bool) -> bool:
        if valider and not theme.question(self, "Valider la facture ?\nUne facture validée ne peut plus être "
                                                "modifiée (contre-passation obligatoire)."):
            return False
        if not valider and self.v2 and self.confirmer and not theme.question(self, "Confirmer l'enregistrement ?"):
            return False
        facture_id, erreurs = compta.enregistrer_facture(self.conn, self.dossier_code, self.donnees(), self.facture_id,
                                                         valider=valider, categorie_obligatoire=self.v2)
        if erreurs:
            theme.erreur(self, "La facture n'a pas été enregistrée :\n\n" + "\n".join(f"- {e}" for e in erreurs))
            return False
        self.facture_id = facture_id
        f = compta.facture(self.conn, facture_id)
        if valider:
            self.etat.setText(f"Facture validée et comptabilisée (n° {f['numero']}).")
            self.verrouiller()
        else:
            self.etat.setText(f"Brouillon enregistré (n° {f['numero']}).")
        self.main.statut(self.etat.text())
        self.titre()
        self.main.rafraichir_pieces()
        return True

    def verrouiller(self) -> None:
        for w in (self.fournisseur, self.reference, self.date):
            w.setReadOnly(True)
        self.categorie.setEnabled(False)
        self.lignes.setEnabled(False)
        self.btn_brouillon.setEnabled(False)
        self.btn_valider.setEnabled(False)


class ListeFacturesWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        self.setWindowTitle("Factures fournisseurs — Liste")
        lay = QVBoxLayout(self)
        self.table = tableau(["N°", "Date", "Fournisseur", "Référence", "HT", "TVA", "TTC", "Statut", "Pièce"],
                             "Factures fournisseurs")
        self.table.doubleClicked.connect(lambda _i: self.ouvrir())
        lay.addWidget(self.table)
        lay.addLayout(boutons(theme.bouton("Ouvrir", self.ouvrir),
                              theme.bouton("Nouvelle facture", lambda: main.ouvrir_facture()),
                              theme.bouton("Actualiser", self.charger), None))
        self.charger()
        self.resize(780, 380)

    def charger(self) -> None:
        self.rows = compta.factures(self.conn, self.main.dossier["code"])
        remplir(self.table, [[f["numero"], compta.date_fr(f["date"]), f["fournisseur"], f["reference"],
                              compta.fmt(f["total_ht"]), compta.fmt(f["total_tva"]), compta.fmt(f["total_ttc"]),
                              "VALIDEE" if f["statut"] == "validated" else "BROUILLON", f["piece"] or ""]
                             for f in self.rows], droite={4, 5, 6})

    def ouvrir(self) -> None:
        i = self.table.currentRow()
        if i < 0:
            return theme.info(self, "Sélectionnez une facture dans la liste.")
        self.main.ouvrir_facture(facture_id=self.rows[i]["id"])


# ---------------------------------------------------------------- consultations

def _periode(g: QGridLayout, ligne: int) -> tuple[QLineEdit, QLineEdit]:
    du = theme.champ(g, ligne, "Du (JJ/MM/AAAA) :", QLineEdit("01/01/2026"))
    au = theme.champ(g, ligne + 1, "Au (JJ/MM/AAAA) :", QLineEdit("31/12/2026"))
    return du, au


class GrandLivreWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        self.setWindowTitle("Consultation de compte")
        lay = QVBoxLayout(self)
        g = QGridLayout()
        self.compte = QComboBox()
        self.compte.setEditable(True)
        for r in compta.comptes(self.conn, main.dossier["code"]):
            self.compte.addItem(f"{r['numero']} — {r['libelle']}", r["numero"])
        self.compte.setCurrentIndex(-1)
        theme.champ(g, 0, "Compte * :", self.compte)
        self.du, self.au = _periode(g, 1)
        g.addWidget(theme.bouton("Afficher", self.afficher), 2, 2)
        g.setColumnStretch(3, 1)
        lay.addLayout(g)
        self.resume = QLabel()
        lay.addWidget(self.resume)
        self.table = tableau(["Date", "Jnl", "Pièce", "Libellé", "Débit", "Crédit", "Let.", "Solde"], "Ecritures du compte")
        lay.addWidget(self.table)
        self.pagineur = Pagineur(self.afficher_page)
        lay.addWidget(self.pagineur)
        self.lignes = []
        self.resize(820, 520)

    def afficher(self) -> None:
        numero = self.compte.currentData() or self.compte.currentText().split(" ")[0].strip()
        du, au = compta.parse_date_fr(self.du.text()), compta.parse_date_fr(self.au.text())
        if du is None or au is None:
            return theme.erreur(self, "Erreur 0x2F : date invalide (format JJ/MM/AAAA).")
        if not numero or not compta.libelle_compte(self.conn, self.main.dossier["code"], numero):
            return theme.erreur(self, f"Compte inexistant : « {numero} » (code 0x0C).")
        gl = compta.grand_livre(self.conn, self.main.dossier["code"], numero, du.isoformat(), au.isoformat())
        self.lignes = gl["lignes"]
        self.resume.setText(f"<b>{numero} {escape(gl['libelle'])}</b> — Report : {compta.fmt(gl['report'])} — "
                            f"Solde au {self.au.text()} : <b>{compta.fmt(gl['solde'])}</b>")
        self.pagineur.page = 1
        self.afficher_page()

    def afficher_page(self) -> None:
        remplir(self.table, [[compta.date_fr(l["date"]), l["journal"], l["piece"], l["libelle"],
                              compta.fmt(l["debit"] or None), compta.fmt(l["credit"] or None), l["lettrage"] or "",
                              compta.fmt(l["solde"])] for l in self.pagineur.tranche(self.lignes)], droite={4, 5, 7})


class RechercheWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        self.setWindowTitle("Recherche d'écritures")
        lay = QVBoxLayout(self)
        g = QGridLayout()
        self.journal = QComboBox()
        self.journal.addItem("-- Choisir --", "")
        self.journal.addItem("TOUS — tous les journaux", "TOUS")
        for code, nom in compta.JOURNAUX.items():
            self.journal.addItem(f"{code} — {nom}", code)
        theme.champ(g, 0, "Journal * :", self.journal)
        self.montant = theme.champ(g, 1, "Montant :", QLineEdit())
        self.libelle = theme.champ(g, 2, "Libellé contient :", QLineEdit())
        self.du, self.au = _periode(g, 3)
        g.addWidget(theme.bouton("Rechercher", self.rechercher), 4, 2)
        g.setColumnStretch(3, 1)
        lay.addLayout(g)
        self.table = tableau(["Date", "Jnl", "Pièce", "Compte", "Libellé", "Débit", "Crédit", "Statut"], "Résultats")
        lay.addWidget(self.table)
        self.pagineur = Pagineur(self.afficher_page)
        lay.addWidget(self.pagineur)
        self.rows = []
        self.resize(820, 520)

    def rechercher(self) -> None:
        if not self.journal.currentData():
            return theme.erreur(self, "Le code journal est obligatoire (code 0x07).")
        du, au = compta.parse_date_fr(self.du.text()), compta.parse_date_fr(self.au.text())
        if du is None or au is None:
            return theme.erreur(self, "Erreur 0x2F : date invalide (format JJ/MM/AAAA).")
        montant = compta.parse_montant(self.montant.text()) if self.montant.text().strip() else None
        if self.montant.text().strip() and montant is None:
            return theme.erreur(self, "Montant invalide.")
        self.rows = compta.recherche(self.conn, self.main.dossier["code"], self.journal.currentData(), montant,
                                     self.libelle.text(), du.isoformat(), au.isoformat())
        self.pagineur.page = 1
        self.afficher_page()
        if not self.rows:
            theme.info(self, "Aucune écriture ne correspond aux critères.")

    def afficher_page(self) -> None:
        remplir(self.table, [[compta.date_fr(r["date"]), r["journal"], r["piece"], r["compte"], r["libelle"],
                              compta.fmt(r["debit"] or None), compta.fmt(r["credit"] or None),
                              "BROUILLARD" if r["statut"] == "brouillard" else "Validée"]
                             for r in self.pagineur.tranche(self.rows)], droite={5, 6})


class BalanceWindow(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main, self.conn = main, main.conn
        self.setWindowTitle("Balance générale")
        lay = QVBoxLayout(self)
        g = QGridLayout()
        self.au = theme.champ(g, 0, "Au (JJ/MM/AAAA) * :", QLineEdit())
        self.au.setPlaceholderText("__/__/____")
        self.niveau = QComboBox()
        for code in ("6", "3", "2", "1"):
            self.niveau.addItem(compta.NIVEAUX[code], code)
        theme.champ(g, 1, "Niveau de détail :", self.niveau)
        self.brouillard = QCheckBox("Inclure les écritures en brouillard")
        g.addWidget(self.brouillard, 2, 0, 1, 2)
        g.addWidget(theme.bouton("Afficher", self.afficher), 2, 2)
        g.setColumnStretch(3, 1)
        lay.addLayout(g)
        self.table = tableau(["Compte", "Libellé", "Total débit", "Total crédit", "Solde débiteur", "Solde créditeur"],
                             "Balance générale")
        lay.addWidget(self.table)
        self.resize(780, 520)

    def afficher(self) -> None:
        au = compta.parse_date_fr(self.au.text())
        if au is None:
            return theme.erreur(self, "Erreur 0x2F : date invalide (format JJ/MM/AAAA).")
        rows = compta.balance(self.conn, self.main.dossier["code"], au.isoformat(), self.niveau.currentData(),
                              self.brouillard.isChecked())
        tot = [sum(r[k] for r in rows) for k in ("debit", "credit", "solde_debiteur", "solde_crediteur")]
        lignes = [[r["compte"], r["libelle"], compta.fmt(r["debit"]), compta.fmt(r["credit"]),
                   compta.fmt(r["solde_debiteur"] or None), compta.fmt(r["solde_crediteur"] or None)] for r in rows]
        lignes.append(["TOTAL", "", *map(compta.fmt, tot)])
        remplir(self.table, lignes, droite={2, 3, 4, 5}, gras=lambda i: i == len(lignes) - 1)
