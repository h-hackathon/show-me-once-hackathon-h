"""Règles métier partagées par le site web et l'application de bureau.

Situation intermédiaire, balance, grand livre, recherche d'écritures, saisie des factures
fournisseurs, messagerie, remise à zéro du banc de test. Montants en centimes.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta

from . import config
from .db import get_setting, set_setting
from .seed import tva

EXO_DEBUT, EXO_FIN = date(2026, 1, 1), date(2026, 12, 31)
FRF = 6.55957

# libellé affiché -> (taux en points de base, autoliquidation)
TAXES = {
    "20 %": (2000, False),
    "10 %": (1000, False),
    "5,5 %": (550, False),
    "0 %": (0, False),
    "20 % autoliquidation UE": (2000, True),
}
CATEGORIES = ["Fournitures de bureau", "Informatique et logiciels", "Déplacements", "Sous-traitance",
              "Energie", "Entretien et nettoyage", "Formation", "Transport", "Honoraires", "Autres achats"]

DESTINATIONS = {
    "imprimante": "\\\\SRV-CAB01\\HP LaserJet 4050 PCL6",
    "ecran": "Ecran (visualisation)",
    "pdf": "Fichier PDF",
}
NIVEAUX = {"1": "Classes (1 chiffre)", "2": "Comptes à 2 chiffres", "3": "Comptes à 3 chiffres",
           "6": "Comptes détaillés"}

CLASSES = {"1": "Comptes de capitaux", "2": "Comptes d'immobilisations", "3": "Comptes de stocks",
           "4": "Comptes de tiers", "5": "Comptes financiers", "6": "Comptes de charges",
           "7": "Comptes de produits"}
REGROUPEMENTS = {
    "10": "Capital et réserves", "11": "Report à nouveau", "16": "Emprunts et dettes assimilées",
    "21": "Immobilisations corporelles", "28": "Amortissements des immobilisations",
    "40": "Fournisseurs et comptes rattachés", "41": "Clients et comptes rattachés",
    "42": "Personnel et comptes rattachés", "43": "Sécurité sociale et organismes sociaux",
    "44": "Etat et autres collectivités publiques", "47": "Comptes transitoires ou d'attente",
    "51": "Banques et établissements financiers", "53": "Caisse", "60": "Achats",
    "61": "Services extérieurs", "62": "Autres services extérieurs",
    "63": "Impôts, taxes et versements assimilés", "64": "Charges de personnel",
    "66": "Charges financières", "68": "Dotations aux amortissements et provisions",
    "70": "Ventes, prestations de services", "77": "Produits exceptionnels",
    "101": "Capital", "106": "Réserves", "110": "Report à nouveau (créditeur)",
    "119": "Report à nouveau (débiteur)", "164": "Emprunts auprès des établissements de crédit",
    "215": "Installations techniques, matériel et outillage", "218": "Autres immobilisations corporelles",
    "281": "Amortissements des immobilisations corporelles", "401": "Fournisseurs", "411": "Clients",
    "421": "Personnel - rémunérations dues", "431": "Sécurité sociale",
    "445": "Etat - taxes sur le chiffre d'affaires", "471": "Comptes d'attente", "512": "Banques",
    "530": "Caisse", "601": "Achats stockés - matières premières",
    "602": "Achats stockés - autres approvisionnements", "604": "Achats d'études et prestations",
    "606": "Achats non stockés de matières et fournitures", "607": "Achats de marchandises",
    "613": "Locations", "615": "Entretien et réparations", "616": "Primes d'assurances",
    "622": "Rémunérations d'intermédiaires et honoraires", "623": "Publicité, publications",
    "624": "Transports de biens", "625": "Déplacements, missions et réceptions",
    "626": "Frais postaux et de télécommunications", "627": "Services bancaires",
    "631": "Impôts sur rémunérations", "633": "Impôts sur rémunérations (autres organismes)",
    "635": "Autres impôts et taxes", "641": "Rémunérations du personnel",
    "645": "Charges de sécurité sociale", "661": "Charges d'intérêts",
    "681": "Dotations aux amortissements - exploitation", "701": "Ventes de produits finis",
    "706": "Prestations de services", "707": "Ventes de marchandises",
    "771": "Produits exceptionnels sur opérations de gestion",
}


# ---------------------------------------------------------------- formats

def fmt(cents: int | None, vide: str = "") -> str:
    """1234567 -> « 12 345,67 » (format des éditions)."""
    if cents is None:
        return vide
    signe = "-" if cents < 0 else ""
    euros, cts = divmod(abs(int(cents)), 100)
    return f"{signe}{euros:,}".replace(",", " ") + f",{cts:02d}"


def pct(part: int, total: int) -> str:
    return f"{abs(part) * 100 / total:.2f}".replace(".", ",") if total else ""


def date_fr(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else ""


def parse_date_fr(texte: str) -> date | None:
    """Uniquement JJ/MM/AAAA, comme les vrais logiciels de 2004."""
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (texte or "").strip())
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def parse_montant(texte: str) -> int | None:
    t = (texte or "").strip().replace(" ", "").replace(" ", "").replace("€", "")
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "")
    t = t.replace(",", ".")
    try:
        return round(float(t) * 100)
    except ValueError:
        return None


def parse_quantite(texte: str) -> float | None:
    t = (texte or "").strip().replace(" ", "").replace(",", ".")
    try:
        q = float(t)
    except ValueError:
        return None
    return q if q > 0 else None


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def cle(texte: str) -> str:
    return re.sub(r"\s+", " ", sans_accents(texte or "").upper()).strip()


def maintenant() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- dossiers

def dossiers(conn, q: str = "", collab: str = "", etat: str = "", page: int = 1, par_page: int = 10):
    rows = [r for r in conn.execute("SELECT * FROM dossiers ORDER BY code")
            if (not q or cle(q) in cle(f"{r['code']} {r['nom']} {r['forme']}"))
            and (not collab or r["collab"] == collab)
            and (not etat or (etat == "Ouverts") == (r["etat"] != "Clôturé"))]
    pages = max(1, -(-len(rows) // par_page))
    page = min(max(1, page), pages)
    return rows[(page - 1) * par_page: page * par_page], len(rows), page, pages


def dossier(conn, code: str):
    return conn.execute("SELECT * FROM dossiers WHERE code = ?", (code,)).fetchone()


def libelle_dossier(row) -> str:
    """Le libellé stable du dossier, celui que cherchent les scripts : « 00417 ATELIER DORN SAS »."""
    return f"{row['code']} {row['nom']} {row['forme']}"


def libelle_compte(conn, dossier_code: str, numero: str) -> str:
    if len(numero) >= 6:
        row = conn.execute("SELECT libelle FROM comptes WHERE dossier = ? AND numero = ?",
                           (dossier_code, numero)).fetchone()
        return row["libelle"] if row else ""
    return CLASSES.get(numero) if len(numero) == 1 else REGROUPEMENTS.get(numero, f"Comptes {numero}")


def comptes(conn, dossier_code: str):
    return conn.execute(
        "SELECT c.numero, c.libelle FROM comptes c WHERE c.dossier = ? AND EXISTS ("
        "SELECT 1 FROM lignes l JOIN ecritures e ON e.id = l.ecriture_id "
        "WHERE e.dossier = c.dossier AND l.compte = c.numero) ORDER BY c.numero", (dossier_code,)).fetchall()


def infos_dossier(conn, dossier_code: str) -> dict:
    last = conn.execute("SELECT date, journal FROM ecritures WHERE dossier = ? AND statut = 'valide' "
                        "ORDER BY date DESC, id DESC LIMIT 1", (dossier_code,)).fetchone()
    brouillard = conn.execute("SELECT COUNT(*) FROM ecritures WHERE dossier = ? AND statut = 'brouillard'",
                              (dossier_code,)).fetchone()[0]
    return {"derniere": f"{date_fr(last['date'])} ({last['journal']})" if last else "aucune",
            "brouillard": brouillard}


# ---------------------------------------------------------------- soldes et états

def _statuts(brouillard: bool) -> tuple:
    return ("valide", "brouillard") if brouillard else ("valide",)


def soldes(conn, dossier_code: str, au: str, brouillard: bool = False) -> dict[str, tuple[int, int]]:
    """{compte: (total débit, total crédit)} des écritures datées jusqu'au `au` (ISO) inclus."""
    st = _statuts(brouillard)
    rows = conn.execute(
        f"SELECT l.compte, SUM(l.debit) AS d, SUM(l.credit) AS c FROM lignes l "
        f"JOIN ecritures e ON e.id = l.ecriture_id WHERE e.dossier = ? AND e.date <= ? "
        f"AND e.statut IN ({','.join('?' * len(st))}) GROUP BY l.compte",
        (dossier_code, au, *st)).fetchall()
    return {r["compte"]: (r["d"], r["c"]) for r in rows}


def _solde(s: dict, *prefixes: str) -> int:
    """Solde débiteur (débit - crédit) des comptes commençant par ces préfixes."""
    return sum(d - c for compte, (d, c) in s.items() if compte.startswith(prefixes))


def situation(conn, dossier_code: str, au: str, brouillard: bool = False, niveau: str = "3",
              francs: bool = False) -> dict:
    s = soldes(conn, dossier_code, au, brouillard)
    ca = -_solde(s, "70")
    achats = _solde(s, "60")
    marge = ca - achats
    externes, impots, personnel = _solde(s, "61", "62"), _solde(s, "63"), _solde(s, "64")
    ebe = marge - externes - impots - personnel
    dotations = _solde(s, "68")
    autres = -_solde(s, "74", "75", "78") - _solde(s, "65")
    rex = ebe - dotations + autres
    financier = -_solde(s, "76") - _solde(s, "66")
    exceptionnel = -_solde(s, "77") - _solde(s, "67")
    net = rex + financier + exceptionnel

    def ligne(libelle, montant, total=False):
        return {"libelle": libelle, "montant": montant, "pct": pct(montant, ca), "total": total}

    sig = [ligne("Chiffre d'affaires (70)", ca), ligne("Achats consommés (60)", -achats),
           ligne("MARGE GLOBALE", marge, True), ligne("Charges externes (61/62)", -externes),
           ligne("Impôts et taxes (63)", -impots), ligne("Charges de personnel (64)", -personnel),
           ligne("EXCEDENT BRUT D'EXPLOITATION", ebe, True),
           ligne("Dotations aux amortissements (681)", -dotations)]
    if autres:
        sig.append(ligne("Autres produits et charges de gestion", autres))
    sig += [ligne("RESULTAT D'EXPLOITATION", rex, True), ligne("Résultat financier (66/76)", financier),
            ligne("Résultat exceptionnel (67/77)", exceptionnel),
            ligne("RESULTAT NET PROVISOIRE (avant IS)", net, True)]

    tresorerie = [{"compte": c, "libelle": libelle_compte(conn, dossier_code, c), "solde": d - cr}
                  for c, (d, cr) in sorted(s.items()) if c.startswith(("512", "53")) and d - cr]
    st = _statuts(brouillard)
    ph = ",".join("?" * len(st))
    limite = (date.fromisoformat(au) - timedelta(days=60)).isoformat()
    echus = conn.execute(
        f"SELECT COUNT(*), COALESCE(SUM(l.debit), 0) FROM lignes l JOIN ecritures e ON e.id = l.ecriture_id "
        f"WHERE e.dossier = ? AND l.compte LIKE '411%' AND l.debit > 0 AND e.date <= ? AND e.statut IN ({ph}) "
        f"AND l.echeance < ? AND NOT EXISTS (SELECT 1 FROM lignes l2 JOIN ecritures e2 ON e2.id = l2.ecriture_id "
        f"WHERE e2.dossier = e.dossier AND l2.lettrage = l.lettrage AND l2.compte LIKE '411%' AND l2.credit > 0 "
        f"AND e2.date <= ? AND e2.statut IN ({ph}))",
        (dossier_code, au, *st, limite, au, *st)).fetchone()

    alertes = []
    nb_brouillard = conn.execute("SELECT COUNT(*) FROM ecritures WHERE dossier = ? AND statut = 'brouillard' "
                                 "AND date <= ?", (dossier_code, au)).fetchone()[0]
    if nb_brouillard and not brouillard:
        alertes.append(f"{nb_brouillard} écriture(s) en brouillard exclue(s) de cette situation.")
    elif nb_brouillard:
        alertes.append(f"{nb_brouillard} écriture(s) en brouillard incluse(s) (non validées).")
    attente = _solde(s, "471")
    if attente:
        alertes.append(f"Compte d'attente 471000 non soldé : {fmt(attente)}.")
    pieces_ = conn.execute(
        "SELECT COUNT(*) FROM pieces p WHERE p.dossier = ? AND NOT EXISTS ("
        "SELECT 1 FROM factures f WHERE f.piece = p.code AND f.statut = 'validated')", (dossier_code,)).fetchone()[0]
    if pieces_:
        alertes.append(f"{pieces_} pièce(s) reçue(s) non comptabilisée(s), non incluse(s).")

    return {
        "dossier": dossier_code, "au": au, "brouillard": brouillard, "niveau": niveau,
        "sig": sig, "resultat_net": net, "resultat_frf": round(net * FRF) if francs else None,
        "tresorerie": tresorerie, "tresorerie_total": sum(t["solde"] for t in tresorerie),
        "clients": _solde(s, "411"), "clients_echus": echus[1], "clients_echus_nb": echus[0],
        "fournisseurs": -_solde(s, "401"), "tva_a_decaisser": -_solde(s, "4455"),
        "alertes": alertes, "detail": balance(conn, dossier_code, au, niveau, brouillard, s),
    }


def balance(conn, dossier_code: str, au: str, niveau: str = "6", brouillard: bool = False,
            s: dict | None = None) -> list[dict]:
    s = s if s is not None else soldes(conn, dossier_code, au, brouillard)
    n = int(niveau)
    groupes: dict[str, list[int]] = {}
    for compte, (d, c) in s.items():
        g = groupes.setdefault(compte[:n], [0, 0])
        g[0] += d
        g[1] += c
    return [{"compte": k, "libelle": libelle_compte(conn, dossier_code, k), "debit": d, "credit": c,
             "solde_debiteur": max(d - c, 0), "solde_crediteur": max(c - d, 0)}
            for k, (d, c) in sorted(groupes.items()) if d or c]


def grand_livre(conn, dossier_code: str, compte: str, du: str, au: str) -> dict:
    avant = conn.execute(
        "SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM lignes l JOIN ecritures e ON e.id = l.ecriture_id "
        "WHERE e.dossier = ? AND l.compte = ? AND e.date < ? AND e.statut = 'valide'",
        (dossier_code, compte, du)).fetchone()[0]
    rows = conn.execute(
        "SELECT e.date, e.journal, e.piece, l.libelle, l.debit, l.credit, l.lettrage FROM lignes l "
        "JOIN ecritures e ON e.id = l.ecriture_id WHERE e.dossier = ? AND l.compte = ? AND e.date >= ? "
        "AND e.date <= ? AND e.statut = 'valide' ORDER BY e.date, e.id", (dossier_code, compte, du, au)).fetchall()
    solde, lignes = avant, []
    for r in rows:
        solde += r["debit"] - r["credit"]
        lignes.append({**dict(r), "solde": solde})
    return {"compte": compte, "libelle": libelle_compte(conn, dossier_code, compte), "report": avant,
            "lignes": lignes, "solde": solde}


def recherche(conn, dossier_code: str, journal: str, montant: int | None = None, libelle: str = "",
              du: str = "2026-01-01", au: str = "2026-12-31") -> list:
    sql = ("SELECT e.date, e.journal, e.piece, e.statut, l.compte, l.libelle, l.debit, l.credit FROM lignes l "
           "JOIN ecritures e ON e.id = l.ecriture_id WHERE e.dossier = ? AND e.date >= ? AND e.date <= ?")
    params: list = [dossier_code, du, au]
    if journal != "TOUS":
        sql += " AND e.journal = ?"
        params.append(journal)
    if montant is not None:
        sql += " AND (l.debit = ? OR l.credit = ?)"
        params += [montant, montant]
    rows = conn.execute(sql + " ORDER BY e.date, e.id, l.id", params).fetchall()
    return [r for r in rows if not libelle or cle(libelle) in cle(r["libelle"])]


JOURNAUX = {"AC": "ACHATS", "VT": "VENTES", "BQ1": "BNP PARIBAS", "BQ2": "CREDIT AGRICOLE", "CA": "CAISSE",
            "OD": "OPERATIONS DIVERSES", "AN": "A NOUVEAUX"}


# ---------------------------------------------------------------- éditions

def nouvelle_edition(conn, dossier_code: str, type_: str, params: dict) -> int:
    cur = conn.execute("INSERT INTO editions (dossier, type, params, created_at) VALUES (?, ?, ?, ?)",
                       (dossier_code, type_, json.dumps(params), maintenant()))
    numero = f"{datetime.now():%Y-%m}-{400 + cur.lastrowid:04d}"
    conn.execute("UPDATE editions SET numero = ? WHERE id = ?", (numero, cur.lastrowid))
    conn.commit()
    return cur.lastrowid


def edition(conn, edition_id: int):
    row = conn.execute("SELECT * FROM editions WHERE id = ?", (edition_id,)).fetchone()
    return ({**dict(row), "params": json.loads(row["params"])}) if row else None


def destination_defaut(conn) -> str:
    return get_setting(conn, "destination_defaut", "imprimante")


def nom_fichier_situation(dossier_code: str, au: str) -> str:
    return f"SIT_{dossier_code}_{au.replace('-', '')}.PDF"


# ---------------------------------------------------------------- pièces et fournisseurs

def pieces(conn, dossier_code: str) -> list[dict]:
    out = []
    for p in conn.execute("SELECT * FROM pieces WHERE dossier = ? ORDER BY code", (dossier_code,)):
        f = conn.execute("SELECT numero, statut FROM factures WHERE piece = ? ORDER BY id DESC LIMIT 1",
                         (p["code"],)).fetchone()
        statut = "A SAISIR" if not f else ("BROUILLON " if f["statut"] == "draft" else "VALIDEE ") + f["numero"]
        out.append({**dict(p), "statut": statut})
    return out


def piece(conn, code: str):
    return conn.execute("SELECT * FROM pieces WHERE code = ?", (code,)).fetchone()


def fournisseurs(conn, dossier_code: str) -> list:
    return conn.execute("SELECT id, code, nom, pays, tva FROM tiers WHERE dossier = ? AND type = 'F' "
                        "ORDER BY nom", (dossier_code,)).fetchall()


def trouver_fournisseur(conn, dossier_code: str, texte: str, tiers_id: str | int | None = None):
    if tiers_id:
        row = conn.execute("SELECT * FROM tiers WHERE id = ? AND dossier = ? AND type = 'F'",
                           (tiers_id, dossier_code)).fetchone()
        if row and cle(texte).startswith(cle(row["nom"])):
            return row
    nom = re.split(r"\s+[—-]\s+401", texte or "")[0]
    for row in fournisseurs(conn, dossier_code):
        if cle(row["nom"]) == cle(nom):
            return conn.execute("SELECT * FROM tiers WHERE id = ?", (row["id"],)).fetchone()
    return None


def creer_fournisseur(conn, dossier_code: str, nom: str, pays: str = "FR", numero_tva: str = ""):
    """Création à la volée depuis la saisie : nom en majuscules sans accents, comme le reste du fichier."""
    nom = cle(nom)
    if not nom:
        raise ValueError("La raison sociale est obligatoire.")
    existant = trouver_fournisseur(conn, dossier_code, nom)
    if existant:
        return existant
    base = "401" + "".join(c for c in nom if c.isalnum())[:5]
    code, n = base, 1
    while conn.execute("SELECT 1 FROM tiers WHERE dossier = ? AND code = ?", (dossier_code, code)).fetchone():
        n += 1
        code = f"{base[:7]}{n}"
    cur = conn.execute("INSERT INTO tiers (dossier, code, nom, type, pays, tva, compte_charge, cree_par_saisie) "
                       "VALUES (?, ?, ?, 'F', ?, ?, '606800', 1)",
                       (dossier_code, code, nom, (pays or "FR").upper()[:2], (numero_tva or "").upper()))
    conn.commit()
    return conn.execute("SELECT * FROM tiers WHERE id = ?", (cur.lastrowid,)).fetchone()


# ---------------------------------------------------------------- factures fournisseurs

def calcul(lignes: list[dict]) -> dict:
    """lignes : [{quantite: float, prix_unitaire: centimes, taxe: libellé}] -> totaux en centimes."""
    total_ht = total_tva = autoliquidee = 0
    for l in lignes:
        ht = round(l["quantite"] * l["prix_unitaire"])
        taux, autoliq = TAXES[l["taxe"]]
        l["montant_ht"] = ht
        if autoliq:
            autoliquidee += tva(ht, taux)
        else:
            total_tva += tva(ht, taux)
        total_ht += ht
    return {"total_ht": total_ht, "total_tva": total_tva, "total_ttc": total_ht + total_tva,
            "tva_autoliquidee": autoliquidee}


def lire_lignes(form_lignes: list[dict]) -> tuple[list[dict], list[str]]:
    """Lignes brutes du formulaire {libelle, quantite, prix_unitaire, taxe} (textes) -> lignes + erreurs."""
    lignes, erreurs = [], []
    for i, brute in enumerate(form_lignes, start=1):
        libelle = (brute.get("libelle") or "").strip()
        q_txt, p_txt = (brute.get("quantite") or "").strip(), (brute.get("prix_unitaire") or "").strip()
        if not (libelle or q_txt or p_txt):
            continue
        q, p, taxe = parse_quantite(q_txt), parse_montant(p_txt), brute.get("taxe") or ""
        if not libelle:
            erreurs.append(f"Ligne {i} : le libellé est obligatoire.")
        if q is None:
            erreurs.append(f"Ligne {i} : quantité invalide.")
        if p is None:
            erreurs.append(f"Ligne {i} : prix unitaire HT invalide.")
        if taxe not in TAXES:
            erreurs.append(f"Ligne {i} : code taxe inconnu.")
        lignes.append({"libelle": libelle, "quantite": q or 0, "prix_unitaire": p or 0, "taxe": taxe,
                       "quantite_txt": q_txt, "prix_txt": p_txt})
    if not lignes:
        erreurs.append("La facture doit comporter au moins une ligne.")
    return lignes, erreurs


def enregistrer_facture(conn, dossier_code: str, donnees: dict, facture_id: int | None = None,
                        valider: bool = False, categorie_obligatoire: bool = False) -> tuple[int | None, list[str]]:
    """Crée ou met à jour une facture fournisseur. donnees : fournisseur, fournisseur_id, reference, date,
    categorie, piece, lignes (textes du formulaire). Renvoie (id, erreurs)."""
    erreurs = []
    existante = facture(conn, facture_id) if facture_id else None
    if existante and existante["statut"] == "validated":
        return facture_id, ["Facture validée : modification impossible (contre-passation obligatoire)."]
    tiers = trouver_fournisseur(conn, dossier_code, donnees.get("fournisseur", ""), donnees.get("fournisseur_id"))
    if not (donnees.get("fournisseur") or "").strip():
        erreurs.append("Le fournisseur est obligatoire.")
    elif tiers is None:
        erreurs.append(f"Fournisseur inconnu : « {donnees['fournisseur'].strip()} ». Sélectionnez-le dans la "
                       "liste ou créez-le avec « + Créer le fournisseur ».")
    reference = (donnees.get("reference") or "").strip()
    if not reference:
        erreurs.append("La référence fournisseur est obligatoire.")
    jour = parse_date_fr(donnees.get("date", ""))
    if jour is None:
        erreurs.append("Erreur 0x2F : date de facture invalide (format JJ/MM/AAAA).")
    elif not (EXO_DEBUT <= jour <= EXO_FIN):
        erreurs.append("La date de facture doit appartenir à l'exercice 01/01/2026 - 31/12/2026.")
    categorie = (donnees.get("categorie") or "").strip()
    if categorie_obligatoire and categorie not in CATEGORIES:
        erreurs.append("La catégorie de dépense est obligatoire.")
    lignes, err_lignes = lire_lignes(donnees.get("lignes", []))
    erreurs += err_lignes
    if tiers and reference:
        doublon = conn.execute("SELECT numero FROM factures WHERE dossier = ? AND tiers_id = ? AND reference = ? "
                               "AND id IS NOT ?", (dossier_code, tiers["id"], reference, facture_id)).fetchone()
        if doublon:
            erreurs.append(f"Doublon : la facture {reference} de {tiers['nom']} existe déjà "
                           f"(n° {doublon['numero']}).")
    if erreurs:
        return facture_id, erreurs

    totaux = calcul(lignes)
    statut = "validated" if valider else "draft"
    now = maintenant()
    piece_code = donnees.get("piece") or (existante["piece"] if existante else None)
    if existante:
        conn.execute("UPDATE factures SET tiers_id = ?, reference = ?, date = ?, categorie = ?, piece = ?, statut = ?, "
                     "total_ht = ?, total_tva = ?, total_ttc = ?, updated_at = ? WHERE id = ?",
                     (tiers["id"], reference, jour.isoformat(), categorie, piece_code, statut, totaux["total_ht"],
                      totaux["total_tva"], totaux["total_ttc"], now, facture_id))
        conn.execute("DELETE FROM facture_lignes WHERE facture_id = ?", (facture_id,))
    else:
        n = conn.execute("SELECT COUNT(*) FROM factures WHERE dossier = ?", (dossier_code,)).fetchone()[0] + 1
        while conn.execute("SELECT 1 FROM factures WHERE dossier = ? AND numero = ?",
                           (dossier_code, f"FA-2026-{n:04d}")).fetchone():
            n += 1
        cur = conn.execute(
            "INSERT INTO factures (dossier, numero, tiers_id, reference, date, categorie, piece, statut, total_ht, "
            "total_tva, total_ttc, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dossier_code, f"FA-2026-{n:04d}", tiers["id"], reference, jour.isoformat(), categorie, piece_code,
             statut, totaux["total_ht"], totaux["total_tva"], totaux["total_ttc"], now, now))
        facture_id = cur.lastrowid
    conn.executemany("INSERT INTO facture_lignes (facture_id, position, libelle, quantite, prix_unitaire, taxe) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     [(facture_id, i, l["libelle"], l["quantite"], l["prix_unitaire"], l["taxe"])
                      for i, l in enumerate(lignes, start=1)])
    if valider:
        _comptabiliser(conn, dossier_code, facture_id, tiers, jour, lignes, totaux)
    conn.commit()
    return facture_id, []


def _comptabiliser(conn, dossier_code, facture_id, tiers, jour, lignes, totaux) -> None:
    f = facture(conn, facture_id)
    cur = conn.execute("INSERT INTO ecritures (dossier, journal, date, piece, libelle, statut, facture_id) "
                       "VALUES (?, 'AC', ?, ?, ?, 'valide', ?)",
                       (dossier_code, jour.isoformat(), f["numero"], f"FACT {tiers['nom']} {f['reference']}",
                        facture_id))
    tva_normale = totaux["total_tva"]
    ecr = [(tiers["compte_charge"] or "606800", totaux["total_ht"], 0, None, None),
           ("445660", tva_normale, 0, None, None),
           ("445662", totaux["tva_autoliquidee"], 0, None, None),
           ("445200", 0, totaux["tva_autoliquidee"], None, None),
           ("401000", 0, totaux["total_ttc"], tiers["code"], f"F{facture_id}")]
    for compte, d, c, t, lettrage in ecr:
        if d or c:
            conn.execute("INSERT INTO lignes (ecriture_id, compte, tiers, libelle, debit, credit, lettrage, echeance) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (cur.lastrowid, compte, t, f"FACT {tiers['nom']}", d, c, lettrage,
                          (jour + timedelta(days=30)).isoformat() if compte == "401000" else None))


def facture(conn, facture_id: int | None):
    if not facture_id:
        return None
    return conn.execute("SELECT f.*, t.nom AS fournisseur, t.code AS fournisseur_code FROM factures f "
                        "LEFT JOIN tiers t ON t.id = f.tiers_id WHERE f.id = ?", (facture_id,)).fetchone()


def facture_lignes(conn, facture_id: int) -> list:
    return conn.execute("SELECT * FROM facture_lignes WHERE facture_id = ? ORDER BY position",
                        (facture_id,)).fetchall()


def factures(conn, dossier_code: str | None = None, reference: str | None = None) -> list:
    sql = ("SELECT f.*, t.nom AS fournisseur, t.code AS fournisseur_code FROM factures f "
           "LEFT JOIN tiers t ON t.id = f.tiers_id WHERE 1 = 1")
    params = []
    if dossier_code:
        sql += " AND f.dossier = ?"
        params.append(dossier_code)
    if reference:
        sql += " AND f.reference = ?"
        params.append(reference)
    return conn.execute(sql + " ORDER BY f.id", params).fetchall()


def facture_api(conn, f) -> dict:
    """Format de l'API technique (contrat SMO)."""
    def nombre(x):
        return int(x) if float(x).is_integer() else x
    return {
        "id": f["id"], "numero": f["numero"], "dossier": f["dossier"],
        "supplier": f["fournisseur"], "supplier_code": f["fournisseur_code"],
        "reference": f["reference"], "date": f["date"],
        "lines": [{"label": l["libelle"], "quantity": nombre(l["quantite"]),
                   "unit_price": l["prix_unitaire"] / 100, "tax": l["taxe"]} for l in facture_lignes(conn, f["id"])],
        "total_ht": f["total_ht"] / 100, "total_tva": f["total_tva"] / 100, "total_ttc": f["total_ttc"] / 100,
        "status": f["statut"], "category": f["categorie"] or None, "piece": f["piece"],
        "created_at": f["created_at"], "updated_at": f["updated_at"],
    }


# ---------------------------------------------------------------- messagerie

def messages(conn, dossier_code: str, sens: str | None = None) -> list:
    sql, params = "SELECT * FROM messages WHERE dossier = ?", [dossier_code]
    if sens:
        sql += " AND sens = ?"
        params.append(sens)
    return conn.execute(sql + " ORDER BY date DESC, id DESC", params).fetchall()


def message(conn, message_id: int, marquer_lu: bool = True):
    if marquer_lu:
        conn.execute("UPDATE messages SET lu = 1 WHERE id = ?", (message_id,))
        conn.commit()
    return conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def envoyer_message(conn, dossier_code: str, a: str, objet: str, corps: str, piece_jointe: str = "") -> int:
    cur = conn.execute("INSERT INTO messages (dossier, date, de, a, objet, corps, piece_jointe, lu, sens, seed) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'envoye', 0)",
                       (dossier_code, date.today().isoformat(), config.USER_CODE, a, cle(objet), corps, piece_jointe))
    conn.commit()
    return cur.lastrowid


DESTINATAIRES = {config.DOSSIER_DEMO: ["P. DORN (client)", "M. DORN - Comptabilité (client)"]}


# ---------------------------------------------------------------- banc de test

def ui(conn) -> dict:
    return {"version": get_setting(conn, "ui_version", "v1"), "confirm": get_setting(conn, "ui_confirm", "0") == "1"}


def set_ui(conn, version: str, confirm: bool | None = None) -> dict:
    if version not in ("v1", "v2"):
        raise ValueError("version : v1 ou v2")
    set_setting(conn, "ui_version", version)
    if confirm is not None:
        set_setting(conn, "ui_confirm", "1" if confirm else "0")
    return ui(conn)


def reset_saisies(conn: sqlite3.Connection) -> dict:
    """Vide ce que l'agent a pu produire (factures, fournisseurs créés, messages envoyés, éditions,
    destination mémorisée). Garde la boîte de réception et la comptabilité d'origine."""
    n = conn.execute("SELECT COUNT(*) FROM factures").fetchone()[0]
    conn.execute("DELETE FROM lignes WHERE ecriture_id IN (SELECT id FROM ecritures WHERE facture_id IS NOT NULL)")
    conn.execute("DELETE FROM ecritures WHERE facture_id IS NOT NULL")
    conn.execute("DELETE FROM facture_lignes")
    conn.execute("DELETE FROM factures")
    conn.execute("DELETE FROM tiers WHERE cree_par_saisie = 1")
    conn.execute("DELETE FROM messages WHERE seed = 0")
    conn.execute("UPDATE messages SET lu = 0 WHERE seed = 1 AND date >= '2026-11-03' AND sens = 'recu' "
                 "AND dossier = ?", (config.DOSSIER_DEMO,))
    conn.execute("DELETE FROM editions")
    conn.commit()
    set_setting(conn, "destination_defaut", "imprimante")
    return {"ok": True, "factures_supprimees": n}


def verite_situation(conn) -> dict:
    """Chiffres attendus des situations du dossier de démo (fichier de vérité terrain du benchmark)."""
    out = {}
    for au in ("2026-09-30", "2026-10-31", "2026-11-04"):
        for brouillard in (False, True):
            s = situation(conn, config.DOSSIER_DEMO, au, brouillard)
            sig = {l["libelle"]: l["montant"] / 100 for l in s["sig"]}
            out[f"{au}{'+brouillard' if brouillard else ''}"] = {
                "date": au, "brouillard_inclus": brouillard, "soldes_intermediaires": sig,
                "resultat_net_provisoire": s["resultat_net"] / 100,
                "tresorerie": {t["compte"]: t["solde"] / 100 for t in s["tresorerie"]},
                "tresorerie_total": s["tresorerie_total"] / 100,
                "clients_411": s["clients"] / 100, "clients_echus_plus_60j": s["clients_echus"] / 100,
                "fournisseurs_401": s["fournisseurs"] / 100, "tva_a_decaisser_44551": s["tva_a_decaisser"] / 100,
            }
    return out
