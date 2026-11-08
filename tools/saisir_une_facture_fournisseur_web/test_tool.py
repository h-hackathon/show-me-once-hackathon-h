"""Tests hors ligne de saisir_une_facture_fournisseur_web : paramètres, règles de la Skill, formats de l'écran.

Aucun identifiant n'est dans GitHub : les tests qui touchent le site sont sautés sans SITE_URL.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from h_tools.config import Context
from h_tools.loader import load_tool

cfg = Context.from_env()
tool = load_tool(Path(__file__).parent)
m = tool.module
live = pytest.mark.skipif(not cfg.site_url, reason="hors ligne (CI) : pas de SITE_URL")

DEMO = {
    "dossier": "Atelier Dorn SAS",
    "fournisseur": "NetCloud Services",
    "reference": "NCS-88231",
    "date_facture": "05/10/2026",
    "lignes": [
        {"libelle": "Hébergement serveur – octobre 2026", "quantite": 1, "prix_unitaire_ht": "149,00", "taxe": "20 %"},
        {"libelle": "Nom de domaine (1 an)", "quantite": 2, "prix_unitaire_ht": "12,50", "taxe": "20 %"},
    ],
    "total_ht": "174,00",
    "total_ttc": "208,80",
}


def demo(**changes):
    return tool.params(**{**DEMO, **changes})


def line(i, **changes):
    lignes = [dict(ligne) for ligne in DEMO["lignes"]]
    lignes[i].update(changes)
    return lignes


def test_params_of_the_demo_piece():
    p = demo()
    assert p.reference == "NCS-88231"
    assert p.date_facture == date(2026, 10, 5)
    assert p.lignes[1].quantite == 2 and p.lignes[1].prix_unitaire_ht == Decimal("12.50")
    assert p.total_ttc == Decimal("208.80")


def test_rules_accept_the_demo_piece():
    assert m.rules(demo()) is None


def test_amounts_and_taxes_as_written_on_the_piece():
    p = demo(lignes=line(0, prix_unitaire_ht="1 149,00 €", taxe=20), total_ht="1 174,00", total_ttc="1 408,80")
    assert p.lignes[0].prix_unitaire_ht == Decimal("1149.00")
    assert p.lignes[0].taxe == "20 %"
    assert m.rules(p) is None
    assert tool.params(**{**DEMO, "lignes": line(0, taxe="5.5%")}).lignes[0].taxe == "5,5 %"


def test_iso_date_is_accepted():
    assert demo(date_facture="2026-10-05").date_facture == date(2026, 10, 5)


def test_unknown_tax_rate_is_rejected():
    with pytest.raises(ValueError):
        demo(lignes=line(0, taxe="7 %"))


def test_a_piece_without_lines_is_rejected():
    with pytest.raises(ValueError):
        demo(lignes=[])


# Règle : vérifier que le total TTC affiché est égal au total TTC de la pièce ; sinon s'arrêter et expliquer l'écart.
def test_flags_a_ttc_total_that_does_not_add_up():
    out = m.run(None, demo(total_ttc="209,80"), cfg)
    assert out["status"] == "flagged" and "208,80" in out["reason"] and "209,80" in out["reason"]


def test_flags_an_ht_total_that_does_not_add_up():
    assert m.run(None, demo(total_ht="170,00"), cfg)["status"] == "flagged"


# Règle : le champ Fournisseur s'identifie en tapant au moins 2 lettres du nom lu sur la pièce.
def test_flags_an_unreadable_supplier():
    assert m.run(None, demo(fournisseur="X"), cfg)["status"] == "flagged"


# Étape 6 : la Référence fournisseur est le n° de facture lu sur la pièce.
def test_flags_a_missing_reference():
    assert m.run(None, demo(reference="  "), cfg)["status"] == "flagged"


# Étape 8 : chaque ligne a un libellé, une quantité et un prix unitaire HT.
def test_flags_a_line_without_label():
    assert m.run(None, demo(lignes=line(0, libelle=" ")), cfg)["status"] == "flagged"


def test_flags_a_zero_quantity():
    assert m.run(None, demo(lignes=line(1, quantite=0)), cfg)["status"] == "flagged"


def test_flags_a_negative_unit_price():
    assert m.run(None, demo(lignes=line(1, prix_unitaire_ht="-12,50")), cfg)["status"] == "flagged"


def test_reverse_charge_adds_no_vat():
    p = demo(lignes=line(0, taxe="20 % autoliquidation UE"), total_ttc="179,00")
    assert m.rules(p) is None


# Étape 5 : ne pas choisir « + Créer le fournisseur … » ; s'il est absent de la liste, s'arrêter et prévenir un humain.
def test_a_supplier_absent_from_the_accounts_is_flagged():
    out = m.fournisseur_non_choisi("Bürotechnik Weber GmbH", [], [])
    assert out["status"] == "flagged" and "créer" in out["reason"]


def test_a_supplier_with_only_other_accounts_proposed_goes_back_to_the_screen():
    out = m.fournisseur_non_choisi("Bureau Express", ["CAFE BUREAU EXPRESS — 401CAFEB"], [])
    assert out["status"] == "error" and "CAFE BUREAU EXPRESS" in out["reason"]


def test_an_ambiguous_supplier_goes_back_to_the_screen():
    ambigus = ["NETCLOUD SERVICES — 401NETCL", "NETCLOUD SERVICES — 401NETC2"]
    out = m.fournisseur_non_choisi("NetCloud Services", ambigus, ambigus)
    assert out["status"] == "error" and "401NETC2" in out["reason"]


def test_fr_amount():
    assert m.fr_amount(Decimal("1234.5")) == "1 234,50"
    assert m.fr_amount(Decimal("208.8")) == "208,80"
    assert m.fr_amount(Decimal("-3")) == "-3,00"


def test_fr_number():
    assert m.fr_number(Decimal("2")) == "2"
    assert m.fr_number(Decimal("1.50")) == "1,5"
    assert m.fr_number(Decimal("12.50")) == "12,5"


# Règle : la date doit être saisie au format JJ/MM/AAAA.
def test_fr_date():
    assert m.fr_date(date(2026, 10, 5)) == "05/10/2026"


def test_names_compare_like_the_autocomplete():
    assert m.meme_nom("NetCloud Services", "NETCLOUD SERVICES")
    assert m.meme_nom("Atelier Dorn SAS", "ATELIER DORN")
    assert m.meme_nom("Électricité Générale", "ELECTRICITE GENERALE")
    assert not m.meme_nom("NetCloud", "NetCloud Services")


def test_the_tool_never_validates():
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert 'name="Valider"' not in source and "name='Valider'" not in source


@live
def test_precheck_on_the_real_site():
    result = tool.precheck(cfg)
    assert result["ok"], result.get("missing") or result.get("error")


def test_a_one_cent_gap_is_flagged():
    assert m.rules(demo(total_ht="174,01", total_ttc="208,81")) is not None
    assert m.rules(demo(total_ttc="208,81")) is not None


def test_a_longer_name_is_another_supplier():
    assert not m.meme_nom("ACME HOLDINGS", "Acme")
    assert m.meme_nom("ACME", "Acme SARL")
