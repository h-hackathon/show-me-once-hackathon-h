"""Saisir une facture fournisseur dans Qonta (Comptarex) à partir des valeurs lues sur la pièce, jusqu'au brouillon."""

import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from playwright.sync_api import expect
from pydantic import BaseModel, Field, field_validator

from h_tools.ui import StepError, check_contract, contract_of, logged_out, login, stay_logged_in, step


NAME = "saisir_une_facture_fournisseur_web"
DESCRIPTION = ("Saisit une facture fournisseur dans Qonta (dossier du client, fournisseur, référence, date, lignes) "
               "à partir des valeurs lues sur la pièce, vérifie le total TTC et l'enregistre en brouillon, sans jamais "
               "valider. Une pièce par appel.")
CONTRACT = contract_of(__file__)

Taxe = Literal["20 %", "10 %", "5,5 %", "0 %", "20 % autoliquidation UE"]
TAUX = {"20 %": Decimal("0.20"), "10 %": Decimal("0.10"), "5,5 %": Decimal("0.055"), "0 %": Decimal("0"),
        "20 % autoliquidation UE": Decimal("0")}   # autoliquidation : la TVA n'est pas facturée par le fournisseur
CENT = Decimal("0.01")
LEGAL_FORMS = {"SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCI", "SCM", "SELARL", "SCOP", "EI", "GIE"}


def decimal_fr(value):
    """« 1 234,50 », « 1234.50 € » ou 1234.5 → Decimal ; comme sur la pièce."""
    if isinstance(value, str):
        value = value.replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace("€", "")
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
    return value


class Ligne(BaseModel):
    libelle: str = Field(description="libellé de la ligne, tel qu'écrit sur la pièce")
    quantite: Decimal = Field(description="quantité de la ligne (ex. 2)")
    prix_unitaire_ht: Decimal = Field(description="prix unitaire HT de la ligne, en euros (ex. 12.50)")
    taxe: Taxe = Field("20 %", description="taux de TVA de la ligne, tel que proposé par Qonta : « 20 % », « 10 % », "
                                          "« 5,5 % », « 0 % » ou « 20 % autoliquidation UE »")

    _decimals = field_validator("quantite", "prix_unitaire_ht", mode="before")(decimal_fr)

    @field_validator("taxe", mode="before")
    @classmethod
    def _taxe(cls, value):
        if isinstance(value, (int, float, Decimal)):
            value = f"{value}"
        if isinstance(value, str) and "auto" not in value.lower():
            number = value.replace("%", "").replace(",", ".").strip()
            try:
                value = f"{fr_number(Decimal(number))} %"
            except ArithmeticError:
                pass
        return value

    @property
    def montant_ht(self) -> Decimal:
        return (self.quantite * self.prix_unitaire_ht).quantize(CENT, ROUND_HALF_UP)

    @property
    def tva(self) -> Decimal:
        return (self.montant_ht * TAUX[self.taxe]).quantize(CENT, ROUND_HALF_UP)


class Params(BaseModel):
    dossier: str = Field(description="le client indiqué sur la pièce (« Facturé à »), ex. « Atelier Dorn SAS » : "
                                     "c'est le dossier de travail à ouvrir")
    fournisseur: str = Field(description="nom du fournisseur lu sur la pièce, ex. « NetCloud Services »")
    reference: str = Field(description="n° de la facture lu sur la pièce (Référence fournisseur), ex. « NCS-88231 » ; "
                                       "sert aussi à détecter un doublon")
    date_facture: date = Field(description="date de la facture lue sur la pièce (AAAA-MM-JJ ou JJ/MM/AAAA)")
    lignes: list[Ligne] = Field(min_length=1, description="les lignes de la pièce, dans l'ordre")
    total_ht: Decimal = Field(description="montant total HT lu sur la pièce, en euros")
    total_ttc: Decimal = Field(description="montant total TTC lu sur la pièce, en euros")

    _decimals = field_validator("total_ht", "total_ttc", mode="before")(decimal_fr)

    @field_validator("date_facture", mode="before")
    @classmethod
    def _date(cls, value):
        if isinstance(value, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", value.strip()):
            return datetime.strptime(value.strip(), "%d/%m/%Y").date()
        return value

    @field_validator("dossier", "fournisseur", "reference")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())


# ------------------------------------------------------------------ formats de l'écran (un helper par format)

def fr_amount(value: Decimal) -> str:
    """Decimal("1234.5") → « 1 234,50 » : le format des montants de Qonta."""
    sign = "-" if value < 0 else ""
    units, cents = f"{abs(value).quantize(CENT, ROUND_HALF_UP):.2f}".split(".")
    return f"{sign}{int(units):,}".replace(",", " ") + f",{cents}"


def fr_number(value: Decimal) -> str:
    """Decimal("2") → « 2 », Decimal("1.50") → « 1,5 » : une quantité ou un taux."""
    text = f"{value.normalize():f}"
    return text.replace(".", ",")


def fr_date(value: date) -> str:
    """date(2026, 10, 5) → « 05/10/2026 » (JJ/MM/AAAA, exigé par le champ Date de facture)."""
    return value.strftime("%d/%m/%Y")


def norm(text: str) -> str:
    """Comparaison de noms comme l'autocomplétion de Qonta : sans accents, en majuscules, espaces réduits."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return " ".join(re.sub(r"[^\w&]+", " ", text).split())


def sans_forme(text: str) -> str:
    """« NETCLOUD SERVICES SAS » → « NETCLOUD SERVICES »."""
    return " ".join(w for w in norm(text).split() if w not in LEGAL_FORMS)


def meme_nom(a: str, b: str) -> bool:
    return norm(a) == norm(b) or sans_forme(a) == sans_forme(b)


# ------------------------------------------------------------------ règles de la Skill (hors ligne)

def rules(params: Params) -> str | None:
    if len(sans_forme(params.fournisseur).replace(" ", "")) < 2:
        return "fournisseur illisible : au moins 2 lettres du nom sont nécessaires"
    if not params.reference:
        return "référence fournisseur (n° de facture) absente de la pièce"
    for i, ligne in enumerate(params.lignes, 1):
        if not ligne.libelle.strip():
            return f"ligne {i} : libellé absent"
        if ligne.quantite <= 0:
            return f"ligne {i} : quantité {ligne.quantite} invalide (elle doit être positive)"
        if ligne.prix_unitaire_ht < 0:
            return f"ligne {i} : prix unitaire HT négatif"
    ht = sum((l.montant_ht for l in params.lignes), Decimal(0))
    ttc = ht + sum((l.tva for l in params.lignes), Decimal(0))
    if ht != params.total_ht:
        return f"total HT des lignes ({fr_amount(ht)}) ≠ total HT de la pièce ({fr_amount(params.total_ht)})"
    if ttc != params.total_ttc:
        return f"total TTC calculé ({fr_amount(ttc)}) ≠ total TTC de la pièce ({fr_amount(params.total_ttc)})"
    return None


# ------------------------------------------------------------------ écran

class Stop(Exception):
    """Fin anticipée de run avec un résultat (doublon, écart, erreur expliquée)."""

    def __init__(self, result: dict):
        super().__init__(result.get("reason", result.get("status")))
        self.result = result


def screens(dossier_ouvert: bool) -> dict:
    return {"screens": [s for s in CONTRACT["screens"] if bool(s.get("dossier_ouvert")) == dossier_ouvert]}


def verifier_interface(page, cfg, dossier_ouvert: bool) -> None:
    check = check_contract(page, screens(dossier_ouvert), cfg)
    if not check["ok"]:
        raise Stop({"status": "error", "reason": "interface changée", "missing": check["missing"]})


def connexion(page, cfg) -> None:
    with step("connexion"):
        login(page, cfg)
        if logged_out(page):
            raise Stop({"status": "error", "reason": "connexion refusée : vérifier l'identifiant du site dans le vault"})


def ouvrir_dossier(page, cfg, dossier: str) -> str:
    """Écran « Sélection du dossier de travail » : recherche du client de la pièce, puis clic sur son nom."""
    with step("ouverture du dossier"):
        page.goto(f"{cfg.site_url}/dossiers")
        for query in dict.fromkeys([dossier, sans_forme(dossier)]):
            page.get_by_label("Rechercher :").fill(query)
            page.get_by_role("button", name="OK").click()
            page.wait_for_load_state()
            table = page.get_by_role("main").get_by_role("table")
            noms = [n.strip() for n in table.get_by_role("link").all_inner_texts()]
            trouves = [n for n in noms if meme_nom(n, dossier) or meme_nom(re.sub(r"^\d+\s+", "", n), dossier)]
            if trouves:
                break
        if len(trouves) != 1:
            raise Stop({"status": "error", "dossier": dossier, "reason": (
                f"dossier « {dossier} » introuvable" if not trouves else
                f"plusieurs dossiers correspondent à « {dossier} » : {', '.join(trouves)}")})
        nom = trouves[0]
        table.get_by_role("link", name=nom, exact=True).click()
        page.wait_for_load_state()
        if "/bureau" not in page.url:
            alerte = page.get_by_role("alert")
            detail = alerte.first.inner_text() if alerte.count() else page.url
            raise Stop({"status": "error", "dossier": nom, "reason": f"le dossier « {nom} » ne s'ouvre pas : {detail}"})
        expect(page.get_by_text(f"Dossier : {nom}", exact=False)).to_be_visible()
        return nom


def table_rows(page) -> list[dict]:
    """Les lignes du tableau principal, en dictionnaires {en-tête: valeur}."""
    table = page.get_by_role("main").get_by_role("table")
    headers = [h.strip() for h in table.get_by_role("columnheader").all_inner_texts()]
    rows = []
    for row in table.get_by_role("row").all()[1:]:   # la première ligne est celle des en-têtes
        cells = [c.strip() for c in row.get_by_role("cell").all_inner_texts()]
        rows.append(dict(zip(headers, cells)))
    return rows


def chercher_doublon(page, cfg, params: Params) -> dict | None:
    """Liste des factures fournisseurs : la pièce (même fournisseur, même référence) est-elle déjà saisie ?"""
    with step("recherche d'un doublon dans la liste des factures"):
        page.goto(f"{cfg.site_url}/factures")
        expect(page.get_by_text("Factures fournisseurs — liste", exact=False).first).to_be_visible()
        while True:
            for row in table_rows(page):
                tiers = row.get("Fournisseur", "")
                if norm(row.get("Référence", "")) == norm(params.reference) and meme_nom(tiers, params.fournisseur):
                    return doublon(params, row.get("N°"), row.get("Statut"), row.get("Fournisseur"))
            pages = re.search(r"Page (\d+)/(\d+)", page.get_by_role("main").inner_text())
            if not pages or int(pages.group(1)) >= int(pages.group(2)):
                return None
            courante = pages.group(0)
            page.get_by_role("link", name="Page suivante").click()
            expect(page.get_by_text(courante, exact=False)).to_have_count(0)


def doublon(params: Params, numero: str | None, statut: str | None, fournisseur: str | None = None) -> dict:
    result = {"status": "duplicate", "reference": params.reference, "fournisseur": fournisseur or params.fournisseur,
              "numero": numero, "statut": statut}
    if statut and "VALID" in norm(statut):
        result["reason"] = "facture déjà validée et comptabilisée : prévenir un humain"
    return result


def choisir_fournisseur(page, nom: str) -> str:
    """Autocomplétion : taper le nom comme un humain, puis choisir le compte fournisseur dans la liste."""
    champ = page.get_by_role("combobox", name="Fournisseur")
    liste = page.get_by_role("listbox", name="Fournisseurs proposés")
    vus: list[str] = []
    for query in dict.fromkeys([nom, sans_forme(nom), sans_forme(nom).split()[0]]):
        if len(query) < 2:
            continue
        champ.fill("")
        champ.press_sequentially(query, delay=50)
        expect(liste).to_be_visible()
        options = [o.strip() for o in liste.get_by_role("option").all_inner_texts()]
        comptes = [o for o in options if not o.startswith("+")]   # « + Créer le fournisseur … » : jamais par le tool
        vus = comptes or vus
        exacts = [o for o in comptes if meme_nom(o.split(" — ")[0], nom)]
        if len(exacts) == 1:
            liste.get_by_role("option", name=exacts[0], exact=True).click()
            compte = exacts[0].split(" — ")[0]
            expect(champ).to_have_value(compte)
            return compte
        if len(exacts) > 1:
            break
    raise Stop({"status": "error", "fournisseur": nom, "reason": (
        f"fournisseur « {nom} » introuvable ou ambigu dans la liste des comptes"
        + (f" (proposés : {', '.join(vus)})" if vus else "")
        + " : le tool ne crée pas de fournisseur, un humain doit le choisir ou le créer")})


def ligne_ecran(page, i: int):
    """La ligne n° i du tableau de saisie, repérée par son bouton « Supprimer la ligne i »."""
    return page.get_by_role("row").filter(has=page.get_by_role("button", name=f"Supprimer la ligne {i}", exact=True))


def saisir(page, cfg, params: Params) -> dict:
    """Le formulaire « Nouvelle facture », rempli puis vérifié ; renvoie le compte fournisseur choisi."""
    with step("ouverture du formulaire Nouvelle facture"):
        page.goto(f"{cfg.site_url}/factures/nouvelle")
        expect(page.get_by_text("Nouvelle facture (non enregistrée)", exact=False).first).to_be_visible()

    with step("ajout des lignes de facture"):
        n = len(params.lignes)
        while not ligne_ecran(page, n).count():
            dernier = page.get_by_role("button", name=re.compile(r"^Supprimer la ligne \d+$")).count()
            page.get_by_role("button", name="Ajouter une ligne").click()
            expect(ligne_ecran(page, dernier + 1)).to_be_visible()

    with step("saisie du fournisseur"):
        compte = choisir_fournisseur(page, params.fournisseur)

    with step("saisie de la référence fournisseur"):
        champ = page.get_by_label("Référence fournisseur", exact=True)
        champ.fill(params.reference)
        expect(champ).to_have_value(params.reference)

    with step("saisie de la date de facture"):
        champ = page.get_by_label("Date de facture", exact=True)
        champ.fill(fr_date(params.date_facture))
        expect(champ).to_have_value(fr_date(params.date_facture))

    for i, ligne in enumerate(params.lignes, 1):
        with step(f"saisie de la ligne {i}"):
            row = ligne_ecran(page, i)
            for nom, valeur in (("Libellé", ligne.libelle), ("Quantité", fr_number(ligne.quantite)),
                                ("Prix unitaire HT", fr_number(ligne.prix_unitaire_ht))):
                champ = row.get_by_role("textbox", name=nom, exact=True)
                champ.fill(valeur)
                expect(champ).to_have_value(valeur)
            taxe = row.get_by_role("combobox", name="Taxe", exact=True)
            taxe.select_option(label=ligne.taxe)
            expect(row.get_by_role("cell", name=fr_amount(ligne.montant_ht), exact=True)).to_be_visible()

    with step("contrôle du total TTC"):
        totaux = page.get_by_label("Totaux de la facture")
        attendu = fr_amount(params.total_ttc)
        try:
            expect(totaux).to_contain_text(re.compile(r"Total TTC\s*" + re.escape(attendu)), timeout=3000)
        except AssertionError:
            affiche = re.search(r"Total TTC\s*([-\d  ]+,\d{2})", totaux.inner_text())
            raise Stop({"status": "flagged", "reference": params.reference, "reason": (
                f"total TTC affiché par Qonta ({affiche.group(1) if affiche else '?'}) ≠ total TTC de la pièce "
                f"({attendu}) : rien n'a été enregistré")})
    return {"compte": compte}


def enregistrer_brouillon(page, params: Params) -> dict:
    with step("enregistrement du brouillon"):
        page.get_by_role("button", name="Enregistrer le brouillon", exact=True).click()   # une seule fois
        page.wait_for_load_state()
        reponse = (page.get_by_role("status").or_(page.get_by_role("alert")).or_(page.get_by_role("alertdialog"))
                   .first)
        expect(reponse).to_be_visible()
        texte = " ".join(reponse.inner_text().split())
        numero = re.search(r"FA-[\w-]+\w", texte)
        if page.get_by_role("alertdialog").count():
            return {"status": "error", "reference": params.reference,
                    "reason": f"fenêtre de confirmation inattendue, non confirmée par le tool : {texte}"}
        if "Doublon" in texte:
            return {**doublon(params, numero and numero.group(0), None), "message": texte}
        if page.get_by_role("alert").count():
            return {"status": "error", "reference": params.reference, "reason": f"erreur de validation : {texte}"}
        if not numero:
            return {"status": "error", "reference": params.reference,
                    "reason": f"confirmation inattendue après l'enregistrement : {texte}"}
        return {"numero": numero.group(0), "message": texte}


def precheck(page, cfg) -> dict:
    """Connexion, écran de choix du dossier, puis les écrans de saisie dans le premier dossier ouvert. Ne modifie rien."""
    login(page, cfg)
    avant = check_contract(page, screens(False), cfg)
    # Le precheck n'a pas de pièce : il ouvre le premier dossier à l'état « Ouvert » de la liste.
    ouvert = page.get_by_role("row").filter(has=page.get_by_role("cell", name="Ouvert", exact=True)).first
    ouvert.get_by_role("link").first.click()
    page.wait_for_load_state()
    apres = check_contract(page, screens(True), cfg)
    missing = avant["missing"] + apres["missing"]
    return {"ok": not missing, "checked": avant["checked"] + apres["checked"], "missing": missing}


def run(page, params: Params, cfg) -> dict:
    if reason := rules(params):
        return {"status": "flagged", "reason": reason, "reference": params.reference}
    try:
        connexion(page, cfg)
        verifier_interface(page, cfg, dossier_ouvert=False)
        dossier = ouvrir_dossier(page, cfg, params.dossier)
        verifier_interface(page, cfg, dossier_ouvert=True)
        for _ in range(2):   # une reprise au plus, si la session a expiré pendant la saisie
            if found := chercher_doublon(page, cfg, params):
                return found
            saisie = saisir(page, cfg, params)
            if stay_logged_in(page, cfg):
                ouvrir_dossier(page, cfg, params.dossier)
                continue
            break
        else:
            return {"status": "error", "reference": params.reference, "reason": "session expirée deux fois de suite"}
        saved = enregistrer_brouillon(page, params)
    except Stop as stop:
        return stop.result
    except StepError as err:
        if isinstance(err.cause, Stop):   # arrêt expliqué, levé à l'intérieur d'une étape nommée
            return {**err.cause.result, "step": err.step}
        raise
    if "status" in saved:
        return saved
    return {"status": "draft_saved", "numero": saved["numero"], "message": saved["message"], "dossier": dossier,
            "fournisseur": saisie["compte"], "reference": params.reference, "date_facture": fr_date(params.date_facture),
            "lignes": [{"libelle": l.libelle, "quantite": fr_number(l.quantite),
                        "prix_unitaire_ht": fr_amount(l.prix_unitaire_ht), "taxe": l.taxe,
                        "montant_ht": fr_amount(l.montant_ht)} for l in params.lignes],
            "total_ht": fr_amount(params.total_ht), "total_ttc": fr_amount(params.total_ttc)}
