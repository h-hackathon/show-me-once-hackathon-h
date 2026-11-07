"""Données fictives : les 14 dossiers clients du cabinet, dont 00417 ATELIER DORN SAS très détaillé.

Tout est déterministe (graine fixe) : deux bases reconstruites sont identiques.
Pour 00417, la situation au 31/10/2026 est calée sur la maquette validée : chiffre d'affaires,
soldes intermédiaires de gestion, trésorerie, encours clients et fournisseurs.
Les 10 factures d'octobre de la boîte de réception (INV-001…010) ne sont PAS en comptabilité :
ce sont les pièces que l'agent doit saisir.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import config

FIN = date(2026, 10, 31)          # date de la situation de référence
DERNIER_JOUR = date(2026, 11, 4)  # dernière écriture du dossier 00417

COMPTES = {
    "101300": "Capital souscrit appelé versé",
    "106800": "Autres réserves",
    "110000": "Report à nouveau (solde créditeur)",
    "119000": "Report à nouveau (solde débiteur)",
    "164000": "Emprunts auprès des établissements de crédit",
    "215400": "Matériel industriel",
    "218300": "Matériel de bureau et informatique",
    "281540": "Amortissements du matériel industriel",
    "281830": "Amortissements du matériel de bureau",
    "401000": "Fournisseurs",
    "411000": "Clients",
    "421000": "Personnel - rémunérations dues",
    "431000": "Sécurité sociale (URSSAF)",
    "445200": "TVA due intracommunautaire",
    "445510": "TVA à décaisser",
    "445660": "TVA déductible sur autres biens et services",
    "445662": "TVA déductible intracommunautaire",
    "445670": "Crédit de TVA à reporter",
    "445710": "TVA collectée",
    "471000": "Compte d'attente",
    "512100": "BNP PARIBAS CPT COURANT",
    "512200": "CREDIT AGRICOLE",
    "530000": "Caisse",
    "601000": "Achats stockés - matières premières",
    "602200": "Fournitures consommables",
    "604000": "Achats d'études et prestations de services",
    "606100": "Fournitures non stockables (eau, énergie)",
    "606300": "Fournitures d'entretien et de petit équipement",
    "606400": "Fournitures administratives",
    "606800": "Autres matières et fournitures",
    "607000": "Achats de marchandises",
    "613200": "Locations immobilières",
    "615200": "Entretien et réparations sur biens immobiliers",
    "615600": "Maintenance",
    "616000": "Primes d'assurances",
    "622600": "Honoraires",
    "623600": "Catalogues et imprimés",
    "624100": "Transports sur achats",
    "625100": "Voyages et déplacements",
    "625700": "Réceptions",
    "626000": "Frais postaux et de télécommunications",
    "627000": "Services bancaires et assimilés",
    "631200": "Taxe d'apprentissage",
    "633300": "Participation à la formation professionnelle continue",
    "635110": "Cotisation foncière des entreprises",
    "635400": "Droits d'enregistrement et de timbre",
    "641100": "Salaires, appointements",
    "645100": "Cotisations à l'URSSAF",
    "661100": "Intérêts des emprunts et dettes",
    "681100": "Dotations aux amortissements des immobilisations corporelles",
    "701000": "Ventes de produits finis",
    "706000": "Prestations de services",
    "707000": "Ventes de marchandises",
    "771800": "Autres produits exceptionnels sur opérations de gestion",
}

DOSSIERS = [
    # code, nom, forme, régime TVA, clôture, collaborateur, état, verrou
    ("00398", "AMBULANCES ROCHE", "SARL", "RN MENSUEL", "31/12", "JPETIT", "Ouvert", None),
    ("00401", "AUTO-ECOLE DU PARC", "SARL", "RSI", "30/06", "CMOREAU", "Ouvert", None),
    ("00405", "BOULANGERIE FAVIER", "EURL", "RN MENSUEL", "30/09", "CMOREAU", "En révision", None),
    ("00409", "CABINET KINE LAFOND", "SCM", "EXONERE", "31/12", "APERRIN", "Ouvert", None),
    ("00412", "CHARPENTE DUVAL", "SARL", "RN MENSUEL", "31/03", "JPETIT", "Ouvert", "JPETIT"),
    ("00417", "ATELIER DORN", "SAS", "RN MENSUEL", "31/12", "CMOREAU", "Ouvert", None),
    ("00423", "GARAGE DES TILLEULS", "SARL", "RN MENSUEL", "31/12", "APERRIN", "Ouvert", None),
    ("00427", "HOTEL DU COMMERCE", "SAS", "RN MENSUEL", "30/09", "CMOREAU", "Clôturé", None),
    ("00431", "PHARMACIE CENTRALE", "SELARL", "RN MENSUEL", "31/12", "APERRIN", "Ouvert", None),
    ("00436", "SCI LES GLYCINES", "SCI", "EXONERE", "31/12", "JPETIT", "Ouvert", None),
    ("00441", "TRAITEUR BONNET", "SARL", "RN MENSUEL", "31/12", "CMOREAU", "Ouvert", None),
    ("00446", "VERGERS DU MOULIN", "EARL", "RSI", "31/12", "APERRIN", "Ouvert", None),
    ("00452", "IMMO CONSEIL LEROUX", "SAS", "RN MENSUEL", "31/12", "JPETIT", "Ouvert", None),
    ("00458", "TAXIS AZUR", "EURL", "RSI", "31/12", "CMOREAU", "Ouvert", None),
]

# Les pièces de la boîte de réception de 00417 : les factures de prep/factures (montant TTC imprimé).
PIECES = [
    ("INV-001", "PAPETERIE MARTIN SARL", "PM-2026-0412", 29880),
    ("INV-002", "NETCLOUD SERVICES", "NCS-88231", 20880),
    ("INV-003", "CAFE BUREAU EXPRESS", "CBE-1049", 17047),
    ("INV-004", "TRANSPORTS LEROY", "TL-2026-317", 30600),
    ("INV-005", "IMPRIMERIE DU CENTRE", "IC-55120", 37512),
    ("INV-006", "NETTOYAGE PRO SUD", "NPS-0921", 74400),
    ("INV-007", "BÃœROTECHNIK WEBER GMBH", "RE-2026-7731", 124000),   # nom mal décodé à l'import du mail
    ("INV-008", "FORMATION PLUS", "FP-2026-208", 126000),
    ("INV-009", "ELECTRICITE GARNIER", "EG-4410", 136600),            # TTC imprimé faux (+100 €)
    ("INV-010", "FOURNITURES BERTIN", "FB-77013", 18924),
]


def tva(ht: int, taux_pb: int) -> int:
    """TVA en centimes, arrondie au centime le plus proche (taux en points de base : 2000 = 20 %)."""
    return int((Decimal(ht) * taux_pb / 10000).quantize(Decimal(1), ROUND_HALF_UP))


def ht_depuis_ttc(ttc: int, taux_pb: int) -> int:
    base = round(ttc * 10000 / (10000 + taux_pb))
    for ecart in (0, -1, 1, -2, 2, -3, 3):
        if base + ecart + tva(base + ecart, taux_pb) == ttc:
            return base + ecart
    return base


@dataclass
class Facture:
    sens: str                 # "V" vente, "A" achat
    tiers: str
    date: date
    compte: str
    ht: int
    taux: int = 2000
    libelle: str = ""
    paiement: date | None = None   # None : jamais payée dans les données
    lettrage: str = ""

    @property
    def tva(self) -> int:
        return tva(self.ht, self.taux)

    @property
    def ttc(self) -> int:
        return self.ht + self.tva


@dataclass
class Livre:
    """Écrit les écritures d'un dossier en vérifiant qu'elles sont équilibrées."""
    conn: object
    dossier: str
    noms: dict = field(default_factory=dict)       # code tiers -> raison sociale
    compteurs: dict = field(default_factory=dict)
    n_lettrage: int = 0

    def lettre(self) -> str:
        self.n_lettrage += 1
        n, code = self.n_lettrage, ""
        while n:
            n, r = divmod(n - 1, 26)
            code = chr(65 + r) + code
        return code.rjust(3, "A")

    def ecrire(self, journal: str, jour: date, libelle: str, lignes: list[tuple], statut: str = "valide") -> int:
        lignes = [l for l in lignes if l[1] or l[2]]
        debit, credit = sum(l[1] for l in lignes), sum(l[2] for l in lignes)
        assert debit == credit, (self.dossier, libelle, debit, credit)
        n = self.compteurs[journal] = self.compteurs.get(journal, 0) + 1
        piece = f"{journal}{jour.month:02d}-{n:04d}"
        cur = self.conn.execute(
            "INSERT INTO ecritures (dossier, journal, date, piece, libelle, statut) VALUES (?, ?, ?, ?, ?, ?)",
            (self.dossier, journal, jour.isoformat(), piece, libelle, statut))
        for compte, d, c, *extra in lignes:
            tiers, lettrage, echeance = (list(extra) + [None, None, None])[:3]
            self.conn.execute(
                "INSERT INTO lignes (ecriture_id, compte, tiers, libelle, debit, credit, lettrage, echeance) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (cur.lastrowid, compte, tiers, libelle, d, c, lettrage, echeance))
        return cur.lastrowid

    def facture(self, f: Facture) -> None:
        f.lettrage = self.lettre()
        echeance = (f.date + timedelta(days=30)).isoformat()
        if f.sens == "V":
            self.ecrire("VT", f.date, f.libelle, [
                ("411000", f.ttc, 0, f.tiers, f.lettrage, echeance),
                (f.compte, 0, f.ht), ("445710", 0, f.tva)])
        else:
            self.ecrire("AC", f.date, f.libelle, [
                (f.compte, f.ht, 0), ("445660", f.tva, 0),
                ("401000", 0, f.ttc, f.tiers, f.lettrage, echeance)])
        if f.paiement and f.paiement <= DERNIER_JOUR:
            if f.sens == "V":
                self.ecrire("BQ1", f.paiement, f"VIR RECU {self.noms[f.tiers]}", [
                    ("512100", f.ttc, 0), ("411000", 0, f.ttc, f.tiers, f.lettrage)])
            else:
                self.ecrire("BQ1", f.paiement, f"REGLEMENT {self.noms[f.tiers]}", [
                    ("401000", f.ttc, 0, f.tiers, f.lettrage), ("512100", 0, f.ttc)])


def _repartir(factures: list[Facture], ecart: int) -> None:
    """Ajoute `ecart` centimes au HT d'un groupe de factures, réparti également."""
    part, reste = divmod(ecart, len(factures))
    for f in factures:
        f.ht += part
    factures[-1].ht += reste
    assert all(f.ht > 0 for f in factures), "répartition impossible"


def _jour(rng: random.Random, mois: int, mini: int = 2, maxi: int = 27) -> date:
    return date(2026, mois, rng.randint(mini, maxi))


def _fin_mois(mois: int) -> date:
    return (date(2026, mois % 12 + 1, 1) - timedelta(days=1)) if mois < 12 else date(2026, 12, 31)


def build(conn) -> None:
    for code, nom, forme, regime, cloture, collab, etat, verrou in DOSSIERS:
        conn.execute("INSERT INTO dossiers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (code, nom, forme, regime, cloture, collab, None, etat, verrou))
        conn.executemany("INSERT INTO comptes VALUES (?, ?, ?)",
                         [(code, numero, libelle) for numero, libelle in COMPTES.items()])
    for key, value in {"ui_version": "v1", "ui_confirm": "0", "destination_defaut": "imprimante"}.items():
        conn.execute("INSERT INTO settings VALUES (?, ?)", (key, value))
    _atelier_dorn(conn)
    for i, (code, nom, *_rest) in enumerate(DOSSIERS):
        if code != config.DOSSIER_DEMO:
            _dossier_simple(conn, code, nom, random.Random(1000 + i))
    for code, *_rest in DOSSIERS:
        last = conn.execute("SELECT MAX(date) FROM ecritures WHERE dossier = ?", (code,)).fetchone()[0]
        conn.execute("UPDATE dossiers SET derniere_saisie = ? WHERE code = ?", (last, code))
    _messages(conn)


# ---------------------------------------------------------------- 00417 ATELIER DORN SAS

CLIENTS = [
    ("411ARNAU", "MENUISERIE ARNAUD"), ("411BEAUR", "HOTEL BEAURIVAGE"),
    ("411KLEIN", "STUDIO KLEIN ARCHITECTES"), ("411NOVA", "GALERIE NOVA"),
    ("411PIXEL", "AGENCE PIXEL OUEST"), ("411ARTS", "CAFE DES ARTS"),
    ("411STAUB", "MAIRIE DE SAINT-AUBIN-SUR-LOIRE"), ("411TILLE", "RESIDENCE LES TILLEULS"),
]

# code, nom, compte de charge, pays, n° TVA
FOURNISSEURS = [
    ("401SCIER", "SCIERIE DU JURA", "601000", "FR", "FR52418903215"),
    ("401METAU", "METAUX NEGOCE EST", "601000", "FR", "FR30512870441"),
    ("401QUINC", "QUINCAILLERIE PRO", "602200", "FR", "FR77433120985"),
    ("401GARNI", "ELECTRICITE GARNIER", "606100", "FR", "FR91325870113"),
    ("401BERTI", "FOURNITURES BERTIN", "606300", "FR", "FR66501223874"),
    ("401PAPMA", "PAPETERIE MARTIN SARL", "606400", "FR", "FR11222333444"),
    ("401CANAL", "SCI DU CANAL", "613200", "FR", "FR04820331570"),
    ("401NETPR", "NETTOYAGE PRO SUD", "615200", "FR", "FR58789120334"),
    ("401NETCL", "NETCLOUD SERVICES", "615600", "FR", "FR22333444555"),
    ("401ASSUR", "MUTUELLE ASSUR OUEST", "616000", "FR", ""),
    ("401FIDMO", "FIDUCIAIRE MOREAU & ASSOCIES", "622600", "FR", "FR83394028617"),
    ("401IMPRI", "IMPRIMERIE DU CENTRE", "623600", "FR", "FR93445210776"),
    ("401LEROY", "TRANSPORTS LEROY", "624100", "FR", "FR44555666777"),
    ("401CAFEB", "CAFE BUREAU EXPRESS", "625700", "FR", "FR33444555666"),
    ("401TELOU", "TELECOM OUEST", "626000", "FR", "FR19388104552"),
]


def _atelier_dorn(conn) -> None:
    d = config.DOSSIER_DEMO
    rng = random.Random(417)
    livre = Livre(conn, d)
    noms = livre.noms
    for code, nom in CLIENTS:
        conn.execute("INSERT INTO tiers (dossier, code, nom, type, pays, tva, compte_charge) "
                     "VALUES (?, ?, ?, 'C', 'FR', '', '')", (d, code, nom))
        noms[code] = nom
    for code, nom, compte, pays, num in FOURNISSEURS:
        conn.execute("INSERT INTO tiers (dossier, code, nom, type, pays, tva, compte_charge) "
                     "VALUES (?, ?, ?, 'F', ?, ?, ?)", (d, code, nom, pays, num, compte))
        noms[code] = nom

    # --- Ventes : 412 380,00 HT de janvier à octobre
    poids = [0.80, 0.85, 1.00, 1.05, 1.10, 1.15, 0.90, 0.60, 1.10, 1.20]
    ventes: list[Facture] = []
    for mois, w in enumerate(poids, start=1):
        cible = round(41238000 * w / sum(poids))
        parts = [rng.uniform(0.6, 1.4) for _ in range(rng.randint(4, 6))]
        for p in parts:
            client = rng.choice(CLIENTS)[0]
            jour = _jour(rng, mois, 3, 28)
            compte = "701000" if rng.random() < 0.35 else "706000"
            ht = round(cible * p / sum(parts) / 1000) * 1000      # montants ronds à 10 €
            delai = rng.randint(20, 45)
            paiement = jour + timedelta(days=delai)
            if mois <= 9:
                paiement = min(paiement, date(2026, 10, rng.randint(20, 30)))
            ventes.append(Facture("V", client, jour, compte, ht, 2000, "", paiement if mois <= 9 else None))
    # 3 factures échues depuis plus de 60 jours : 8 900,00 TTC
    juin_juillet = [f for f in ventes if f.date.month in (6, 7) and f.date.day <= 25][:3]
    for f, ttc in zip(juin_juillet, (240000, 365000, 285000)):
        f.ht, f.paiement = ht_depuis_ttc(ttc, 2000), None
    # encours clients au 31/10 : 67 450,00 TTC (les factures d'octobre ne sont pas encore payées)
    octobre = sorted((f for f in ventes if f.date.month == 10), key=lambda f: f.date)
    ajusteur = octobre[-1]
    while True:
        autres = sum(f.ttc for f in ventes if (f.paiement is None or f.paiement > FIN) and f is not ajusteur)
        besoin = 6745000 - autres
        if besoin >= 150000:
            break
        payee = next(f for f in octobre if f is not ajusteur and f.paiement is None)
        payee.paiement = date(2026, 10, 30)                     # paiement à réception
    ajusteur.ht = ht_depuis_ttc(besoin, 2000)
    # deux factures d'octobre réglées début novembre
    for f, jour in zip([f for f in octobre if f.paiement is None and f is not ajusteur][:2], (2, 4)):
        f.paiement = date(2026, 11, jour)
    payees = [f for f in ventes if f.paiement and f.paiement <= date(2026, 9, 30) and f.date.month <= 8]
    _repartir(payees, 41238000 - sum(f.ht for f in ventes))
    for f in ventes:
        f.libelle = f"FACTURE {noms[f.tiers]}"

    # --- Achats (les factures d'octobre de la boîte de réception ne sont pas saisies)
    achats: list[Facture] = []

    def achat(code, jour, ht, taux=2000, delai=30, compte=None):
        compte = compte or next(c for k, _n, c, *_ in FOURNISSEURS if k == code)
        achats.append(Facture("A", code, jour, compte, ht, taux, f"FACT {noms[code]}",
                              jour + timedelta(days=delai) if delai is not None else None))

    en_attente = {"401PAPMA", "401NETCL", "401CAFEB", "401LEROY", "401IMPRI",
                  "401NETPR", "401GARNI", "401BERTI"}                # leur facture d'octobre est en attente
    for mois in range(1, 11):
        for jour in (8, 22):
            achat("401SCIER", _jour(rng, mois, jour - 2, jour + 2), rng.randint(280000, 480000))
        achat("401METAU", _jour(rng, mois, 10, 14), rng.randint(180000, 340000))
        achat("401QUINC", _jour(rng, mois, 16, 20), rng.randint(60000, 130000))
        achat("401CANAL", date(2026, mois, 1), 280000, delai=4)
        achat("401TELOU", date(2026, mois, 10), 8900, delai=0)
        achat("401FIDMO", date(2026, mois, 28), 95000)
        if mois in (1, 4, 7, 10):
            achat("401ASSUR", date(2026, mois, 15), 115000, taux=0, delai=0)
        for code, ht, jour, taux in (("401NETPR", 62000, 12, 2000), ("401NETCL", 17400, 5, 2000),
                                     ("401GARNI", rng.randint(95000, 140000), 20, 2000),
                                     ("401LEROY", rng.randint(18000, 34000), 15, 2000),
                                     ("401CAFEB", rng.randint(12000, 19000), 6, 550)):
            if not (mois == 10 and code in en_attente):
                achat(code, date(2026, mois, jour), ht, taux)
        if mois % 2 == 0 and mois < 10:
            achat("401BERTI", date(2026, mois, 20), rng.randint(90000, 160000))
        if mois % 2 == 1 and mois < 10:
            achat("401PAPMA", date(2026, mois, 3), rng.randint(20000, 45000))
        if mois in (3, 6):
            achat("401IMPRI", date(2026, mois, 11), rng.randint(120000, 180000))
    achat("401CANAL", date(2026, 11, 1), 280000, delai=4)
    achat("401SCIER", date(2026, 11, 3), 352080)
    # encours fournisseurs au 31/10 : 23 118,56 TTC
    scierie_oct = sorted((f for f in achats if f.tiers == "401SCIER" and f.date.month == 10), key=lambda f: f.date)
    ajusteur = scierie_oct[-1]
    non_payees = lambda f: f.date <= FIN and (f.paiement is None or f.paiement > FIN)  # noqa: E731
    while True:
        autres = sum(f.ttc for f in achats if non_payees(f) and f is not ajusteur)
        besoin = 2311856 - autres
        if besoin >= 150000:
            break
        anticipee = next(f for f in sorted(achats, key=lambda f: f.date) if non_payees(f) and f is not ajusteur)
        anticipee.paiement = date(2026, 10, 30)
    ajusteur.ht = ht_depuis_ttc(besoin, 2000)

    # dépenses payées directement par la banque ou la caisse : (journal, jour, compte, montant, libellé)
    directes = []
    for mois in range(1, 11):
        directes.append(("BQ1", _fin_mois(mois), "627000", 4500, "FRAIS TENUE DE COMPTE"))
        directes.append(("BQ1", _jour(rng, mois, 18, 22), "625100", rng.randint(22000, 38000),
                         "CB DEPLACEMENTS CHANTIERS"))
    for mois in (2, 5, 9):
        directes.append(("CA", date(2026, mois, 14), "625700", 6250, "VIENNOISERIES REUNION CLIENTS"))
    directes += [("BQ1", date(2026, 2, 27), "633300", 248000, "CONTRIBUTION FORMATION PRO"),
                 ("BQ1", date(2026, 4, 30), "631200", 198000, "TAXE D'APPRENTISSAGE"),
                 ("BQ1", date(2026, 6, 15), "635110", 120500, "ACOMPTE CFE 2026")]
    # calage des soldes intermédiaires de gestion
    _repartir([f for f in achats if f.tiers == "401SCIER" and f.paiement and f.paiement <= date(2026, 9, 30)],
              13892045 - sum(f.ht for f in achats if f.compte.startswith("60") and f.date <= FIN))
    externes = (sum(f.ht for f in achats if f.compte[:2] in ("61", "62") and f.date <= FIN)
                + sum(m for _j, _d, c, m, _l in directes if c[:2] in ("61", "62")))
    deplacements = [i for i, x in enumerate(directes) if x[2] == "625100"]
    ecart = 6421030 - externes
    for n, i in enumerate(deplacements):
        j, jour, c, m, l = directes[i]
        part = ecart // len(deplacements) + (ecart % len(deplacements) if n == len(deplacements) - 1 else 0)
        directes[i] = (j, jour, c, m + part, l)
    impots = sum(m for _j, _d, c, m, _l in directes if c.startswith("63"))
    directes.append(("BQ1", date(2026, 4, 20), "635400", 684500 - impots, "DROITS ENREGISTREMENT BAIL"))

    for f in sorted(ventes + achats, key=lambda f: f.date):
        livre.facture(f)
    for journal, jour, compte, montant, libelle in directes:
        tresorerie = "530000" if journal == "CA" else "512100"
        livre.ecrire(journal, jour, libelle, [(compte, montant, 0), (tresorerie, 0, montant)])
    livre.ecrire("BQ1", date(2026, 6, 15), "INDEMNITE SINISTRE ATELIER",
                 [("512100", 42000, 0), ("771800", 0, 42000)])

    # salaires (4 salariés), amortissements, emprunt, virements internes
    for mois in range(1, 11):
        fin = _fin_mois(mois)
        livre.ecrire("OD", fin, f"SALAIRES {mois:02d}/2026", [
            ("641100", 1100000, 0), ("645100", 414000, 0), ("421000", 0, 858000), ("431000", 0, 656000)])
        livre.ecrire("BQ1", fin, f"VIR SALAIRES {mois:02d}/2026", [("421000", 858000, 0), ("512100", 0, 858000)])
        if mois <= 9:
            livre.ecrire("BQ1", date(2026, mois + 1, 15), f"PRLV URSSAF {mois:02d}/2026",
                         [("431000", 656000, 0), ("512100", 0, 656000)])
        livre.ecrire("OD", fin, f"DOTATION AMORT. {mois:02d}/2026", [
            ("681100", 98500, 0), ("281540", 0, 82000), ("281830", 0, 16500)])
        livre.ecrire("BQ1", date(2026, mois, 5), "VIREMENT INTERNE VERS CA", [("512200", 140000, 0), ("512100", 0, 140000)])
    capital, interets = 4800000, []
    for mois in range(1, 11):
        interets.append(round(capital * 0.031 / 12))
        capital -= 135000 - interets[-1]
    interets[-1] += 123640 - sum(interets)
    for mois, interet in enumerate(interets, start=1):
        livre.ecrire("BQ2", date(2026, mois, 10), f"ECHEANCE PRET N° 7781 {mois:02d}/10", [
            ("164000", 135000 - interet, 0), ("661100", interet, 0), ("512200", 0, 135000)])

    # TVA : déclarations mensuelles ; celle de septembre n'est pas payée (relance)
    for mois in range(1, 10):
        collectee = sum(f.tva for f in ventes if f.date.month == mois)
        deductible = sum(f.tva for f in achats if f.date.month == mois and f.date.year == 2026)
        net = collectee - deductible
        jour = date(2026, mois + 1, 15)
        livre.ecrire("OD", jour, f"TVA CA3 {mois:02d}/2026", [
            ("445710", collectee, 0), ("445660", 0, deductible),
            ("445510", 0, max(net, 0)), ("445670", max(-net, 0), 0)])
        if mois <= 8 and net > 0:
            livre.ecrire("BQ1", date(2026, mois + 1, 19), f"PRLV DGFIP TVA {mois:02d}/2026",
                         [("445510", net, 0), ("512100", 0, net)])

    # relevé bancaire importé mais pas encore validé (brouillard) : 23 lignes
    brouillard = [
        (26, "PRLV SEPA EDF COLLECTIVITES", "471000", -18430), (26, "CB BRICOLAGE DU CENTRE", "606300", -6420),
        (27, "VIR RECU REF 88412", "471000", 186000), (27, "CB SNCF INTERNET", "625100", -8600),
        (28, "PRLV SEPA ASSURANCE FLOTTE", "471000", -21300), (28, "CB STATION TOTAL", "625100", -7215),
        (29, "VIR RECU GALERIE NOVA", "471000", 432000), (29, "COMMISSION INTERVENTION", "627000", -1240),
        (29, "CB RESTAURANT LE QUAI", "625700", -9450), (30, "PRLV SEPA ELECTRICITE GARNIER EG-4410", "471000", -126600),
        (30, "CHQ N° 0004512", "471000", -54000), (30, "CB AMAZON MARKETPLACE", "471000", -3999),
        (31, "VIR RECU MAIRIE ST AUBIN", "471000", 610000), (31, "FRAIS CARTE BUSINESS", "627000", -4800),
    ]
    novembre = [
        (1, "CB PEAGE A11", "625100", -1460), (2, "VIR RECU REF 90133", "471000", 96000),
        (2, "PRLV SEPA TELECOM OUEST", "471000", -10680), (3, "CB SNCF INTERNET", "625100", -12400),
        (3, "CHQ N° 0004513", "471000", -21000), (3, "VIR RECU STUDIO KLEIN", "471000", 288000),
        (4, "CB FOURNITURES EXPRESS", "606400", -5630), (4, "PRLV SEPA URSSAF", "471000", -656000),
        (4, "FRAIS VIREMENT SEPA", "627000", -350),
    ]
    for mois, lignes in ((10, brouillard), (11, novembre)):
        for jour, libelle, compte, montant in lignes:
            if montant > 0:
                ecr = [("512100", montant, 0), (compte, 0, montant)]
            else:
                ecr = [(compte, -montant, 0), ("512100", 0, -montant)]
            livre.ecrire("BQ1", date(2026, mois, jour), libelle, ecr, statut="brouillard")

    # à-nouveaux au 01/01/2026 : la trésorerie du 31/10 tombe sur la maquette
    def flux(compte):
        return conn.execute(
            "SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM lignes l JOIN ecritures e ON e.id = l.ecriture_id "
            "WHERE e.dossier = ? AND l.compte = ? AND e.date <= ? AND e.statut = 'valide'",
            (d, compte, FIN.isoformat())).fetchone()[0]
    bnp, ca, caisse = 4821377 - flux("512100"), 1204010 - flux("512200"), 31250 - flux("530000")
    assert min(bnp, ca, caisse) > 0, (bnp, ca, caisse)
    actif = 8500000 + 1200000 - 3400000 - 620000 + bnp + ca + caisse
    report = actif - 4800000 - 5000000 - 800000
    livre.ecrire("AN", date(2026, 1, 1), "A NOUVEAUX 2026", [
        ("215400", 8500000, 0), ("218300", 1200000, 0), ("281540", 0, 3400000), ("281830", 0, 620000),
        ("512100", bnp, 0), ("512200", ca, 0), ("530000", caisse, 0),
        ("164000", 0, 4800000), ("101300", 0, 5000000), ("106800", 0, 800000),
        ("110000", 0, max(report, 0)), ("119000", max(-report, 0), 0)])

    for code, expediteur, reference, montant in PIECES:
        conn.execute("INSERT INTO pieces VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (code, d, "2026-11-05", expediteur, reference, montant, f"{code}.pdf"))


# ---------------------------------------------------------------- les 13 autres dossiers (plus sommaires)

ACTIVITES = {
    "00398": ("706000", ["GARAGE AUTO SERVICES", "MEDIPHARM DISTRIBUTION", "CARBURANTS DE L'OUEST"]),
    "00401": ("706000", ["AUTOS PEDAGOGIE", "CARBURANTS DE L'OUEST", "EDITIONS CODE ROUSSEAU"]),
    "00405": ("701000", ["MINOTERIE DU VAL", "EMBALLAGES NORMANDS", "ENERGIE OUEST"]),
    "00409": ("706000", ["MEDICAL EQUIPEMENT SUD", "LINGE PRO SERVICE", "SCI DU PARC"]),
    "00412": ("706000", ["BOIS ET CHARPENTES DU JURA", "QUINCAILLERIE PRO", "LOCATION NACELLES 44"]),
    "00423": ("707000", ["PIECES AUTO DISTRIBUTION", "PNEUS GROSSISTE OUEST", "ENERGIE OUEST"]),
    "00427": ("706000", ["BLANCHISSERIE CENTRALE", "METRO CASH GROSSISTE", "ENERGIE OUEST"]),
    "00431": ("707000", ["OCP REPARTITION", "CERP GROSSISTE", "ENERGIE OUEST"]),
    "00436": ("706000", ["SYNDIC IMMO GESTION", "ASSURANCES HABITAT", "ENTRETIEN JARDINS"]),
    "00441": ("701000", ["METRO CASH GROSSISTE", "PRIMEURS DU MARCHE", "EMBALLAGES NORMANDS"]),
    "00446": ("701000", ["COOPERATIVE AGRICOLE", "ENGRAIS ET SEMENCES", "MACHINISME AGRICOLE"]),
    "00452": ("706000", ["PORTAIL IMMO PUBLICITE", "IMPRIMERIE DU CENTRE", "TELECOM OUEST"]),
    "00458": ("706000", ["CARBURANTS DE L'OUEST", "GARAGE AUTO SERVICES", "ASSURANCE FLOTTE"]),
}


def _dossier_simple(conn, code: str, nom: str, rng: random.Random) -> None:
    livre = Livre(conn, code)
    compte_ventes, fournisseurs = ACTIVITES[code]
    noms = livre.noms
    noms["411DIVER"] = "CLIENTS DIVERS"
    conn.execute("INSERT INTO tiers (dossier, code, nom, type, pays, tva, compte_charge) "
                 "VALUES (?, '411DIVER', 'CLIENTS DIVERS', 'C', 'FR', '', '')", (code,))
    comptes_charge = ["607000" if compte_ventes == "707000" else "601000", "606800", "606100"]
    codes = []
    for i, fnom in enumerate(fournisseurs):
        fcode = "401" + "".join(ch for ch in fnom if ch.isalpha())[:5]
        conn.execute("INSERT INTO tiers (dossier, code, nom, type, pays, tva, compte_charge) "
                     "VALUES (?, ?, ?, 'F', 'FR', '', ?)", (code, fcode, fnom, comptes_charge[i]))
        noms[fcode] = fnom
        codes.append((fcode, comptes_charge[i]))
    fin_saisie = rng.randint(7, 10)
    ca_mensuel = rng.randint(800000, 4500000)
    salaires = rng.choice([0, 250000, 420000, 680000])
    for mois in range(1, fin_saisie + 1):
        for _ in range(3):
            jour = _jour(rng, mois)
            livre.facture(Facture("V", "411DIVER", jour, compte_ventes, round(ca_mensuel * rng.uniform(0.2, 0.45)),
                                  2000, "FACTURE CLIENTS DIVERS", jour + timedelta(days=rng.randint(10, 40))))
        for fcode, compte in codes:
            jour = _jour(rng, mois)
            livre.facture(Facture("A", fcode, jour, compte, round(ca_mensuel * rng.uniform(0.05, 0.15)),
                                  2000, f"FACT {noms[fcode]}", jour + timedelta(days=30)))
        if salaires:
            fin = _fin_mois(mois)
            livre.ecrire("OD", fin, f"SALAIRES {mois:02d}/2026", [
                ("641100", salaires, 0), ("645100", round(salaires * 0.38), 0),
                ("421000", 0, round(salaires * 0.78)), ("431000", 0, round(salaires * 0.6))])
            livre.ecrire("BQ1", fin, f"VIR SALAIRES {mois:02d}/2026",
                         [("421000", round(salaires * 0.78), 0), ("512100", 0, round(salaires * 0.78))])
        livre.ecrire("BQ1", _fin_mois(mois), "FRAIS TENUE DE COMPTE", [("627000", 3500, 0), ("512100", 0, 3500)])
    banque = rng.randint(1500000, 6000000)
    livre.ecrire("AN", date(2026, 1, 1), "A NOUVEAUX 2026", [
        ("512100", banque, 0), ("101300", 0, 1000000), ("110000", 0, banque - 1000000)])


def _messages(conn) -> None:
    d = config.DOSSIER_DEMO
    msgs = [
        (d, "2026-11-05", "P. DORN (client)", "CMOREAU", "FACTURES FOURNISSEURS OCTOBRE (10 PIECES)",
         "Bonjour,\n\nJe vous ai déposé les 10 factures fournisseurs d'octobre dans l'espace documents.\n"
         "Il y en a une d'un fournisseur allemand, je ne sais pas trop comment elle se traite.\n\n"
         "Cordialement,\nPierre Dorn", "10 fichiers PDF", 0, "recu"),
        (d, "2026-11-04", "SYSTEME", "CMOREAU", "RELANCE : TVA 09/2026 NON PAYEE (ECHEANCE DU 19/10/2026)",
         "Le paiement de la déclaration CA3 de septembre 2026 n'a pas été constaté en banque.\n"
         "Merci de régulariser auprès du service des impôts des entreprises.", "", 0, "recu"),
        (d, "2026-11-03", "P. DORN (client)", "CMOREAU", "BESOIN D'UNE SITUATION A FIN OCTOBRE POUR LA BANQUE",
         "Bonjour,\n\nMa banque me demande une situation intermédiaire au 31 octobre avant notre rendez-vous "
         "de jeudi. Pouvez-vous me l'envoyer dans mon espace ?\n\nMerci,\nPierre Dorn", "", 0, "recu"),
        (d, "2026-11-02", "CMOREAU", "P. DORN (client)", "DEMANDE RELEVE BANCAIRE OCTOBRE (BNP)",
         "Bonjour,\n\nPourriez-vous me transmettre le relevé BNP d'octobre ?\n\nC. Moreau", "", 1, "envoye"),
        (d, "2026-10-15", "P. DORN (client)", "CMOREAU", "QUESTION SUR LA CFE",
         "Bonjour, j'ai reçu un avis de CFE, faut-il payer le solde maintenant ?", "AVIS_CFE_2026.PDF", 1, "recu"),
        (d, "2026-09-30", "CMOREAU", "P. DORN (client)", "SITUATION AU 31/08/2026",
         "Bonjour,\n\nVeuillez trouver ci-joint la situation au 31/08/2026.\n\nC. Moreau",
         "SIT_00417_20260831.PDF", 1, "envoye"),
        ("00405", "2026-11-06", "M. FAVIER (client)", "CMOREAU", "INVENTAIRE AU 30/09",
         "Bonjour, voici les chiffres de l'inventaire.", "INVENTAIRE.XLS", 0, "recu"),
        ("00401", "2026-10-28", "SYSTEME", "CMOREAU", "RELANCE : PIECES MANQUANTES 09/2026", "", "", 1, "recu"),
        ("00427", "2026-10-20", "CMOREAU", "DIRECTION HOTEL DU COMMERCE", "LIASSE FISCALE 2026",
         "Bonjour, la liasse a été télétransmise.", "LIASSE_00427.PDF", 1, "envoye"),
    ]
    conn.executemany("INSERT INTO messages (dossier, date, de, a, objet, corps, piece_jointe, lu, sens, seed) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)", msgs)
