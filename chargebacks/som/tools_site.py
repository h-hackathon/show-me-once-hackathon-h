"""Données de l'app « outils internes » (dossier app/) : back-office Sportiva Admin, transporteur Parcelia Pro,
support Sportiva Care. Marques 100 % fictives.

  python -m som outils   → app/data.json (lu par app/server.py, à déployer sur Railway)

Les 60 commandes en litige viennent de som/scenarios.py ; on ajoute ~260 commandes « normales » sur 90 jours
+ l'historique d'achat des clients en litige. Tout est corrélé : commande ↔ colis ↔ ticket ↔ client. Les pages n'affichent jamais la décision attendue.
"""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import ROOT
from .scenarios import NOMS, PRENOMS, PRODUITS, VILLES, generate

APP = ROOT / "app"
COMPTES = {
    "admin": ("ops@sportiva.test", "Sportiva-Ops-2026"),
    "parcelia": ("SPORTIVA-PRO", "Parcelia-2026"),
    "care": ("agent@sportiva.test", "Care-2026"),
}
# compatibilité avec le runner (anciens noms)
COMPTES["commandes"], COMPTES["transporteur"], COMPTES["support"] = COMPTES["admin"], COMPTES["parcelia"], COMPTES["care"]

SKU = {nom: f"SPV-{1000 + i * 37}" for i, (nom, _) in enumerate(PRODUITS + [("Gants tactiles", 14.49)])}
TODAY = date(2026, 11, 7)


def _tax(ttc: float) -> float:
    return round(ttc - ttc / 1.2, 2)


def _shipment(tracking, order_id, dest, events, code, label, date_liv, signe_par, preuve, poids):
    return {"tracking": tracking, "order_id": order_id, "destination": dest, "service": "Parcelia Express 48h",
            "poids_kg": poids, "code": code, "statut": label, "date_livraison": date_liv, "signe_par": signe_par,
            "preuve": preuve, "evenements": events}


def _from_scenario(s: dict) -> tuple[dict, dict, list]:
    c, l = s["client"], s["livraison"]
    events = []
    for dt, lib in l["evenements"]:
        lieu = "Lyon-Saint-Exupéry" if "hub" in lib else c["ville"]
        events.append({"date": dt, "libelle": lib.split(" — ")[0], "lieu": lieu, "detail": lib})
    ship = _shipment(s["suivi"], s["order_id"], f"{c['cp']} {c['ville']}", events, l["statut"], l["libelle"],
                     l["date"], l["signe_par"], l["preuve"], round(0.4 + len(s["articles"]) * 1.3, 1))
    timeline = [{"date": s["date_commande"] + " 10:14", "texte": f"Commande passée sur la boutique en ligne par {c['prenom']} {c['nom']}."},
                {"date": s["date_commande"] + " 10:14", "texte": f"Paiement de {s['montant']:.2f} € accepté (carte, via Stripe)."},
                {"date": s["date_expedition"] + " 17:40", "texte": f"Commande expédiée avec Parcelia (suivi {s['suivi']})."}]
    if l["date"]:
        timeline.append({"date": l["date"] + " 19:00", "texte": "Parcelia a confirmé la livraison."})
    if l["statut"] == "perdu":
        timeline.append({"date": s["date_expedition"] + " 09:30", "texte": "Parcelia signale une anomalie de transport."})
    if s.get("remboursement"):
        r = s["remboursement"]
        timeline.append({"date": r["date"] + " 11:02", "texte": f"Remboursement intégral de {r['montant']:.2f} € effectué (réf. {r['ref']})."})
    timeline.append({"date": (TODAY - timedelta(days=1)).isoformat() + " 08:05",
                     "texte": "Stripe : la banque du client a ouvert une contestation de paiement (litige)."})
    order = {
        "id": s["order_id"], "date": s["date_commande"], "client_email": c["email"],
        "articles": [{"nom": a["nom"], "prix": a["prix"], "qte": a["qte"], "sku": SKU.get(a["nom"], "SPV-0000")} for a in s["articles"]],
        "total": s["montant"], "tva": _tax(s["montant"]), "livraison": 0.0,
        "paiement": "Remboursé" if s.get("remboursement") else "Payé",
        "traitement": {"livre_signe": "Livrée", "boite_aux_lettres": "Livrée", "perdu": "Anomalie transport"}[l["statut"]],
        "litige": True, "transporteur": "Parcelia", "suivi": s["suivi"],
        "remboursement": s.get("remboursement"), "chronologie": sorted(timeline, key=lambda e: e["date"]),
        "adresse": f"{c['cp']} {c['ville']}", "tags": ["Litige Stripe"] + (["Remboursée"] if s.get("remboursement") else []),
    }
    tickets = [{"commande": s["order_id"], "email": c["email"], "client": f"{c['prenom']} {c['nom']}", **t} for t in s["tickets"]]
    return order, ship, tickets


TICKETS_COURANTS = [
    ("Changement d'adresse", "Bonjour, puis-je modifier l'adresse de livraison de ma commande ?", "Bonjour, c'est modifié, le colis partira à la nouvelle adresse."),
    ("Facture", "Bonjour, pourriez-vous m'envoyer la facture de ma commande ?", "Bonjour, vous la trouverez en pièce jointe. Bonne journée !"),
    ("Taille", "Bonjour, la taille est-elle conforme au guide des tailles ?", "Bonjour, oui, nos modèles taillent normalement."),
    ("Délai", "Bonjour, quand ma commande sera-t-elle expédiée ?", "Bonjour, elle part sous 24 h avec Parcelia Express 48h."),
    ("Retour produit", "Bonjour, l'article ne me convient pas, comment faire un retour ?", "Bonjour, une étiquette de retour Parcelia vous a été envoyée par e-mail."),
    ("Produit défectueux", "Bonjour, la fermeture éclair est cassée à la réception.", "Bonjour, désolés ! Nous vous remboursons l'article, inutile de le renvoyer."),
    ("Code promo", "Bonjour, mon code de bienvenue ne fonctionne pas.", "Bonjour, c'est corrigé : le code est valable jusqu'à la fin du mois."),
    ("Échange", "Bonjour, puis-je échanger contre la taille au-dessus ?", "Bonjour, oui, l'échange est lancé."),
]


def _order(r, oid, client, d, statut_force=None):
    """Une commande ordinaire (sans litige) + son colis Parcelia + éventuellement un ticket, toutes corrélées."""
    pick = lambda seq: seq[int(r.random() * len(seq))]
    prenom, nom, ville, cp, email = client["prenom"], client["nom"], client["ville"], client["cp"], client["email"]
    arts = [pick(PRODUITS) for _ in range(1 + int(r.random() * 2.2))]
    total = round(sum(p for _, p in arts), 2)
    trk = f"PRC{int(r.random() * 9_000_000_000) + 1_000_000_000}"
    age = (TODAY - d).days
    hh = f"{8 + int(r.random() * 13):02d}:{int(r.random() * 60):02d}"
    if statut_force:
        trait, code = "Livrée", statut_force
    elif age < 2:
        trait, code = "À expédier", None
    elif age < 4:
        trait, code = "Expédiée", "en_transit"
    else:
        x = r.random()
        trait, code = ("Livrée", "livre_signe") if x < 0.58 else ("Livrée", "boite_aux_lettres") if x < 0.97 else ("Anomalie transport", "perdu")
    tl = [{"date": f"{d.isoformat()} {hh}", "texte": f"Commande passée sur la boutique en ligne par {prenom} {nom}."},
          {"date": f"{d.isoformat()} {hh}", "texte": f"Paiement de {total:.2f} € accepté (carte, via Stripe)."}]
    ship = None
    if code:
        exp = d + timedelta(days=1)
        tl.append({"date": exp.isoformat() + " 17:40", "texte": f"Commande expédiée avec Parcelia (suivi {trk})."})
        ev = [{"date": exp.isoformat() + " 18:12", "libelle": "Colis pris en charge", "lieu": "Lyon-Saint-Exupéry",
               "detail": "Colis pris en charge — hub Parcelia de Lyon-Saint-Exupéry"},
              {"date": (exp + timedelta(days=1)).isoformat() + " 06:40", "libelle": "En transit", "lieu": ville,
               "detail": f"En transit — agence Parcelia de {ville}"}]
        dl, signe, label = None, None, "En transit"
        if code == "perdu":
            label = "Colis égaré — enquête ouverte"
            ev.append({"date": (exp + timedelta(days=2)).isoformat() + " 09:03", "libelle": "Anomalie", "lieu": ville,
                       "detail": "Anomalie : colis non localisé"})
            tl.append({"date": (exp + timedelta(days=2)).isoformat() + " 09:30", "texte": "Parcelia signale une anomalie de transport."})
        elif code != "en_transit":
            liv = exp + timedelta(days=2 + int(r.random() * 2))
            dl = liv.isoformat()
            signe = f"{prenom} {nom}" if code == "livre_signe" else None
            label = "Livré contre signature" if signe else "Livré sans signature (boîte aux lettres)"
            ev.append({"date": dl + " 10:20", "libelle": "En cours de livraison", "lieu": ville, "detail": "En cours de livraison"})
            ev.append({"date": dl + " 12:05", "libelle": "Livré", "lieu": ville,
                       "detail": f"Livré — remis contre signature ({signe})" if signe else "Livré — déposé en boîte aux lettres"})
            tl.append({"date": dl + " 19:00", "texte": "Parcelia a confirmé la livraison."})
        ship = _shipment(trk, oid, f"{cp} {ville}", ev, code, label, dl, signe,
                         "winning_evidence" if signe else "losing_evidence", round(0.4 + len(arts) * 1.3, 1))
    paiement, remb, tags, ticket = "Payé", None, [], None
    if code in ("livre_signe", "boite_aux_lettres") and r.random() < 0.07:  # article défectueux remboursé en partie
        a = arts[0]
        rd = date.fromisoformat(ship["date_livraison"]) + timedelta(days=3)
        if rd <= TODAY:
            remb = {"date": rd.isoformat(), "montant": a[1], "ref": f"RMB-{70000 + int(r.random() * 9000)}", "preuve": "losing_evidence",
                    "motif": f"Article défectueux : {a[0]}"}
            paiement, tags = ("Remboursé", ["Remboursée"]) if len(arts) == 1 else ("Partiellement remboursé", ["Remboursement partiel"])
            tl.append({"date": rd.isoformat() + " 11:02", "texte": f"Remboursement de {a[1]:.2f} € effectué (réf. {remb['ref']}) — article défectueux."})
            ticket = {"date": (rd - timedelta(days=1)).isoformat(), "sujet": "Produit défectueux",
                      "messages": [("client", f"Bonjour, l'article « {a[0]} » est arrivé abîmé."),
                                   ("agent", f"Désolés ! Nous vous remboursons {a[1]:.2f} € (réf. {remb['ref']}), inutile de le renvoyer."),
                                   ("client", "Merci beaucoup.")], "statut": "Résolu", "preuve": "losing_evidence"}
    if code == "perdu":
        tags = ["Enquête transporteur"]
        ticket = {"date": (d + timedelta(days=5)).isoformat(), "sujet": "Colis jamais reçu",
                  "messages": [("client", "Bonjour, mon colis n'est toujours pas arrivé."),
                               ("agent", "Le transporteur a ouvert une enquête, nous revenons vers vous sous 48 h.")],
                  "statut": "En attente", "preuve": "losing_evidence"}
    if ticket is None and r.random() < 0.28:
        sujet, q, a = pick(TICKETS_COURANTS)
        ticket = {"date": (d + timedelta(days=int(r.random() * 3))).isoformat(), "sujet": sujet,
                  "messages": [("client", q), ("agent", a)], "statut": "Résolu" if r.random() < 0.75 else "En attente",
                  "preuve": "losing_evidence"}
    if ticket and ticket["date"] > TODAY.isoformat():
        ticket["date"] = TODAY.isoformat()
    if total > 250:
        tags.append("Grosse commande")
    order = {"id": oid, "date": d.isoformat(), "client_email": email,
             "articles": [{"nom": a, "prix": p, "qte": 1, "sku": SKU[a]} for a, p in arts],
             "total": total, "tva": _tax(total), "livraison": 0.0, "paiement": paiement, "traitement": trait,
             "litige": False, "transporteur": "Parcelia", "suivi": trk if code else None, "remboursement": remb,
             "chronologie": sorted(tl, key=lambda e: e["date"]), "adresse": f"{cp} {ville}", "tags": tags}
    tickets = [{"commande": oid, "email": email, "client": f"{prenom} {nom}", **ticket}] if ticket else []
    return order, ship, tickets


def _client(r, i):
    pick = lambda seq: seq[int(r.random() * len(seq))]
    prenom, nom = pick(PRENOMS), pick(NOMS)
    ville, cp = pick(VILLES)
    email = f"{prenom.lower()}.{nom.lower()}.{i + 50}@mail.test".replace("é", "e").replace("ë", "e").replace("ï", "i").replace("è", "e")
    return {"prenom": prenom, "nom": nom, "ville": ville, "cp": cp, "email": email, "client_depuis": str(2019 + int(r.random() * 6))}


def _filler(n: int, scenarios: list, seed: int = 99) -> tuple[list, list, list, dict]:
    """Commandes ordinaires sur 90 jours + historique d'achat des clients en litige (tout est corrélé)."""
    r = random.Random(seed)
    orders, ships, tickets, clients = [], [], [], {}
    pool = []
    for i in range(n):
        if pool and r.random() < 0.3:          # client fidèle : il revient
            c = pool[int(r.random() * len(pool))]
        else:
            c = _client(r, i)
            pool.append(c)
        d = TODAY - timedelta(days=int(r.random() ** 1.3 * 90))
        o, sh, t = _order(r, f"CMD-{10203 + i * 7}", c, d)
        orders.append(o); ships += [sh] if sh else []; tickets += t
        clients[c["email"]] = {"nom": f"{c['prenom']} {c['nom']}", "ville": c["ville"], "cp": c["cp"], "depuis": c["client_depuis"]}
    k = 0
    for s in scenarios:                          # historique : anciennes commandes, livrées et signées par le vrai client
        c = dict(s["client"])
        for _ in range(int(r.random() * 3.2)):
            d = date.fromisoformat(s["date_commande"]) - timedelta(days=20 + int(r.random() * 300))
            o, sh, t = _order(r, f"CMD-{10201 + k * 7}", c, d, statut_force="livre_signe")
            orders.append(o); ships.append(sh); tickets += t
            k += 1
    return orders, ships, tickets, clients


def data() -> dict:
    orders, ships, tickets, clients = [], [], [], {}
    scenarios = generate()
    for s in scenarios:
        o, sh, t = _from_scenario(s)
        orders.append(o)
        ships.append(sh)
        tickets += t
        c = s["client"]
        clients[c["email"]] = {"nom": f"{c['prenom']} {c['nom']}", "ville": c["ville"], "cp": c["cp"], "depuis": c["client_depuis"]}
    fo, fs, ft, fc = _filler(260, scenarios)
    orders += fo
    ships += fs
    tickets += ft
    for k, v in fc.items():
        clients.setdefault(k, v)
    ids = [o["id"] for o in orders]
    assert len(ids) == len(set(ids)), "identifiants de commande en double"
    assert len({s["tracking"] for s in ships}) == len(ships), "numéros de suivi en double"
    for email, c in clients.items():               # nombre de commandes = vraies commandes visibles
        c["commandes"] = sum(1 for o in orders if o["client_email"] == email)
    orders.sort(key=lambda o: (o["date"], o["id"]), reverse=True)
    tickets.sort(key=lambda t: (t["date"], t["commande"]), reverse=True)
    for i, t in enumerate(tickets):
        t["id"] = f"#{4100 + len(tickets) - i}"
    stock = random.Random(5)
    produits = []
    for nom, prix in PRODUITS + [("Gants tactiles", 14.49)]:
        ventes = sum(a["qte"] for o in orders for a in o["articles"] if a["nom"] == nom)
        produits.append({"nom": nom, "sku": SKU[nom], "prix": prix, "stock": int(stock.random() * 140),
                         "vendus": ventes, "ca": round(ventes * prix, 2)})
    return {"orders": {o["id"]: o for o in orders}, "order_list": [o["id"] for o in orders],
            "shipments": {s["tracking"]: s for s in ships}, "tickets": tickets, "clients": clients, "produits": produits,
            "comptes": {k: {"login": v[0], "password": v[1]} for k, v in COMPTES.items() if k in ("admin", "parcelia", "care")},
            "genere_le": datetime.now().isoformat(timespec="seconds")}


def _fr_amounts(obj):
    """« 59.99 € » → « 59,99 € » dans tous les textes."""
    import re
    if isinstance(obj, str):
        return re.sub(r"(\d+)\.(\d\d) €", r"\1,\2 €", obj)
    if isinstance(obj, list):
        return [_fr_amounts(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_fr_amounts(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _fr_amounts(v) for k, v in obj.items()}
    return obj


def build() -> Path:
    APP.mkdir(exist_ok=True)
    out = APP / "data.json"
    out.write_text(json.dumps(_fr_amounts(data()), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out
