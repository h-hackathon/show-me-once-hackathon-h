"""Génère 10 factures fournisseurs PDF de test + la vérité terrain (verite_terrain.csv).

Données 100 % fictives. 2 factures pièges :
  - INV-007 : fournisseur étranger (Allemagne), autoliquidation, TVA 0 %
  - INV-009 : total TTC imprimé faux (≠ HT + TVA)

Usage : ../.venv/bin/python generer_factures.py
"""
import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

DOSSIER = Path(__file__).parent
CLIENT = ("Atelier Dorn SAS", "12 rue des Lilas", "75011 Paris", "TVA : FR00123456789")


def arrondi(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def euros(x):
    return f"{arrondi(x):,.2f} €".replace(",", " ").replace(".", ",")


# id, fournisseur, adresse, ville, n° TVA, n° facture, date, échéance, lignes [(désignation, qté, PU HT, taux TVA)], piège
FACTURES = [
    ("INV-001", "Papeterie Martin SARL", "4 avenue Jean Jaurès", "69007 Lyon", "FR11222333444",
     "PM-2026-0412", "02/10/2026", "01/11/2026",
     [("Ramettes papier A4 80 g (carton de 5)", 10, "24.90", "20")], ""),
    ("INV-002", "NetCloud Services", "18 rue de la Paix", "44000 Nantes", "FR22333444555",
     "NCS-88231", "05/10/2026", "05/11/2026",
     [("Hébergement serveur – octobre 2026", 1, "149.00", "20"),
      ("Nom de domaine (1 an)", 2, "12.50", "20")], ""),
    ("INV-003", "Café Bureau Express", "7 place du Marché", "33000 Bordeaux", "FR33444555666",
     "CBE-1049", "06/10/2026", "06/11/2026",
     [("Café en grains 1 kg", 6, "18.40", "5.5"),
      ("Location machine à café – octobre", 1, "45.00", "20")], ""),
    ("INV-004", "Transports Leroy", "Zone industrielle Nord", "59000 Lille", "FR44555666777",
     "TL-2026-317", "08/10/2026", "07/11/2026",
     [("Livraison palette Paris → Lille", 3, "85.00", "20")], ""),
    ("INV-005", "Imprimerie du Centre", "22 boulevard Gambetta", "63000 Clermont-Ferrand", "FR55666777888",
     "IC-55120", "10/10/2026", "09/11/2026",
     [("Flyers A5 quadri (x1000)", 2, "89.00", "20"),
      ("Cartes de visite (x500)", 4, "29.90", "20"),
      ("Frais de calage", 1, "15.00", "20")], ""),
    ("INV-006", "Nettoyage Pro Sud", "3 chemin des Oliviers", "13008 Marseille", "FR66777888999",
     "NPS-0921", "12/10/2026", "11/11/2026",
     [("Entretien des locaux – octobre 2026", 1, "620.00", "20")], ""),
    # Piège 1 : fournisseur étranger, autoliquidation
    ("INV-007", "Bürotechnik Weber GmbH", "Hauptstraße 41", "10115 Berlin, Allemagne", "DE123456789",
     "RE-2026-7731", "14/10/2026", "13/11/2026",
     [("Bürostuhl ergonomisch / Fauteuil ergonomique", 4, "310.00", "0")],
     "fournisseur_etranger"),
    ("INV-008", "Formation Plus", "9 rue Nationale", "37000 Tours", "FR77888999000",
     "FP-2026-208", "16/10/2026", "15/11/2026",
     [("Formation Excel avancé (1 jour)", 3, "350.00", "20")], ""),
    # Piège 2 : total TTC imprimé faux
    ("INV-009", "Électricité Garnier", "15 rue Victor Hugo", "67000 Strasbourg", "FR88999000111",
     "EG-4410", "18/10/2026", "17/11/2026",
     [("Remplacement tableau électrique", 1, "780.00", "20"),
      ("Main d'œuvre (heures)", 5, "55.00", "20")],
     "montant_incoherent"),
    ("INV-010", "Fournitures Bertin", "30 rue de Strasbourg", "54000 Nancy", "FR99000111222",
     "FB-77013", "20/10/2026", "19/11/2026",
     [("Stylos bille bleus (boîte de 50)", 3, "14.90", "20"),
      ("Classeurs A4 dos 8 cm", 20, "3.20", "20"),
      ("Post-it 76x76 (lot de 12)", 5, "9.80", "20")], ""),
]

ERREUR_TTC = Decimal("100.00")  # écart volontaire ajouté au TTC imprimé de INV-009


def dessiner(f, chemin):
    inv_id, nom, adr, ville, tva_fourn, numero, date, echeance, lignes, piege = f
    etranger = piege == "fournisseur_etranger"
    c = canvas.Canvas(str(chemin), pagesize=A4)
    L, H = A4

    # En-tête fournisseur
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 25 * mm, nom)
    c.setFont("Helvetica", 9)
    for i, t in enumerate([adr, ville, f"N° TVA : {tva_fourn}"]):
        c.drawString(20 * mm, H - (32 + 5 * i) * mm, t)

    # Titre et références
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(L - 20 * mm, H - 25 * mm, "RECHNUNG / FACTURE" if etranger else "FACTURE")
    c.setFont("Helvetica", 10)
    refs = [f"N° facture : {numero}", f"Date : {date}", f"Échéance : {echeance}"]
    for i, t in enumerate(refs):
        c.drawRightString(L - 20 * mm, H - (33 + 5 * i) * mm, t)

    # Client
    c.setFont("Helvetica-Bold", 10)
    c.drawString(120 * mm, H - 60 * mm, "Facturé à :")
    c.setFont("Helvetica", 10)
    for i, t in enumerate(CLIENT):
        c.drawString(120 * mm, H - (66 + 5 * i) * mm, t)

    # Tableau des lignes
    y = H - 100 * mm
    cols = [20, 110, 130, 155, 175]
    c.setFillColor(colors.HexColor("#E8EEF4"))
    c.rect(18 * mm, y - 2 * mm, L - 36 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    for x, t in zip(cols, ["Désignation", "Qté", "PU HT", "TVA", "Total HT"]):
        c.drawString(x * mm, y, t)
    c.setFont("Helvetica", 9)

    total_ht, total_tva = Decimal(0), Decimal(0)
    for des, qte, pu, taux in lignes:
        y -= 8 * mm
        ht = arrondi(Decimal(pu) * qte)
        total_ht += ht
        total_tva += arrondi(ht * Decimal(taux) / 100)
        c.drawString(cols[0] * mm, y, des)
        c.drawString(cols[1] * mm, y, str(qte))
        c.drawString(cols[2] * mm, y, euros(pu))
        c.drawString(cols[3] * mm, y, f"{taux.replace('.', ',')} %")
        c.drawString(cols[4] * mm, y, euros(ht))

    total_ttc = total_ht + total_tva
    ttc_imprime = total_ttc + (ERREUR_TTC if piege == "montant_incoherent" else 0)

    # Totaux
    y -= 15 * mm
    c.line(130 * mm, y + 5 * mm, L - 20 * mm, y + 5 * mm)
    for libelle, val, gras in [("Total HT", total_ht, False), ("TVA", total_tva, False),
                               ("Total TTC", ttc_imprime, True)]:
        c.setFont("Helvetica-Bold" if gras else "Helvetica", 11 if gras else 10)
        c.drawString(130 * mm, y, libelle)
        c.drawRightString(L - 20 * mm, y, euros(val))
        y -= 7 * mm

    # Mentions
    c.setFont("Helvetica", 8)
    mentions = ["Paiement par virement à 30 jours. Pénalités de retard : 3 fois le taux d'intérêt légal.",
                "Indemnité forfaitaire pour frais de recouvrement : 40 €."]
    if etranger:
        mentions.insert(0, "Steuerschuldnerschaft des Leistungsempfängers / Autoliquidation – "
                           "art. 196 directive 2006/112/CE.")
    for i, t in enumerate(mentions):
        c.drawString(20 * mm, 30 * mm - i * 4 * mm, t)
    c.drawString(20 * mm, 15 * mm, "Document fictif généré pour tests — Hackathon H × 42AI.")

    c.save()
    return total_ht, total_tva, total_ttc, ttc_imprime


def main():
    lignes_csv = []
    for f in FACTURES:
        inv_id, nom, *_, numero, date, echeance, lignes, piege = f
        ht, tva, ttc, ttc_imprime = dessiner(f, DOSSIER / f"{inv_id}.pdf")
        attendu = {
            "": "saisir puis s'arrêter avant validation",
            "fournisseur_etranger": "saisir avec la taxe « 20% EU G » (autoliquidation intra-UE, net à payer 1240 €) et signaler à l'humain",
            "montant_incoherent": "ne pas valider : signaler l'écart TTC à l'humain",
        }[piege]
        lignes_csv.append([inv_id, nom, numero, date, f"{ht:.2f}", f"{tva:.2f}", f"{ttc:.2f}",
                           f"{ttc_imprime:.2f}", piege, attendu])

    with open(DOSSIER / "verite_terrain.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["invoice_id", "fournisseur", "numero_facture", "date", "total_ht", "total_tva",
                    "total_ttc_correct", "total_ttc_imprime", "piege", "comportement_attendu"])
        w.writerows(lignes_csv)
    print(f"{len(lignes_csv)} factures générées dans {DOSSIER}")


if __name__ == "__main__":
    main()
