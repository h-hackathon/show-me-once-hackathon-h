"""Données de l'app « outils internes » (dossier app/) : back-office Sportiva Admin, transporteur Parcelia Pro,
support Sportiva Care. Marques 100 % fictives.

  python -m som outils   → app/data.json (lu par app/server.py, à déployer sur Railway)

Les 24 commandes en litige viennent de som/scenarios.py ; on ajoute ~60 commandes « normales » (sans litige)
pour que le back-office ressemble à une vraie boutique. Les pages n'affichent jamais la décision attendue.
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


def _filler(n: int, seed: int = 99) -> tuple[list, list, list, dict]:
    """Commandes ordinaires (sans litige), pour le réalisme."""
    r = random.Random(seed)
    pick = lambda seq: seq[int(r.random() * len(seq))]
    orders, ships, tickets, clients = [], [], [], {}
    for i in range(n):
        prenom, nom = pick(PRENOMS), pick(NOMS)
        ville, cp = pick(VILLES)
        email = f"{prenom.lower()}.{nom.lower()}.{i + 50}@mail.test".replace("é", "e").replace("ë", "e").replace("ï", "i")
        clients[email] = {"nom": f"{prenom} {nom}", "ville": ville, "cp": cp, "depuis": str(2019 + int(r.random() * 6)),
                          "commandes": 1 + int(r.random() * 9)}
        d = TODAY - timedelta(days=int(r.random() * 40))
        arts = [pick(PRODUITS) for _ in range(1 + int(r.random() * 2.2))]
        total = round(sum(p for _, p in arts), 2)
        oid = f"CMD-{10200 + i * 7 + 3}"
        trk = f"PRC{int(r.random() * 9_000_000_000) + 1_000_000_000}"
        age = (TODAY - d).days
        if age < 2:
            trait, code, label = "À expédier", None, None
        elif age < 4:
            trait, code, label = "Expédiée", "en_transit", "En transit"
        else:
            trait, code, label = "Livrée", "livre_signe" if r.random() < 0.6 else "boite_aux_lettres", None
            label = "Livré contre signature" if code == "livre_signe" else "Livré sans signature (boîte aux lettres)"
        paid = "Payé" if r.random() > 0.06 else "Partiellement remboursé"
        tl = [{"date": d.isoformat() + " 09:20", "texte": f"Commande passée sur la boutique en ligne par {prenom} {nom}."},
              {"date": d.isoformat() + " 09:20", "texte": f"Paiement de {total:.2f} € accepté (carte, via Stripe)."}]
        if code:
            exp = d + timedelta(days=1)
            tl.append({"date": exp.isoformat() + " 17:40", "texte": f"Commande expédiée avec Parcelia (suivi {trk})."})
            ev = [{"date": exp.isoformat() + " 18:12", "libelle": "Colis pris en charge", "lieu": "Lyon-Saint-Exupéry",
                   "detail": "Colis pris en charge — hub Parcelia de Lyon-Saint-Exupéry"},
                  {"date": (exp + timedelta(days=1)).isoformat() + " 06:40", "libelle": "En transit", "lieu": ville,
                   "detail": f"En transit — agence Parcelia de {ville}"}]
            dl, signe = None, None
            if code != "en_transit":
                liv = exp + timedelta(days=2)
                dl = liv.isoformat()
                signe = f"{prenom} {nom}" if code == "livre_signe" else None
                ev.append({"date": dl + " 10:20", "libelle": "En cours de livraison", "lieu": ville, "detail": "En cours de livraison"})
                ev.append({"date": dl + " 12:05", "libelle": "Livré", "lieu": ville,
                           "detail": f"Livré — remis contre signature ({signe})" if signe else "Livré — déposé en boîte aux lettres"})
                tl.append({"date": dl + " 19:00", "texte": "Parcelia a confirmé la livraison."})
            ships.append(_shipment(trk, oid, f"{cp} {ville}", ev, code, label, dl, signe,
                                   "winning_evidence" if signe else "losing_evidence", round(0.4 + len(arts) * 1.3, 1)))
        orders.append({"id": oid, "date": d.isoformat(), "client_email": email,
                       "articles": [{"nom": a, "prix": p, "qte": 1, "sku": SKU[a]} for a, p in arts],
                       "total": total, "tva": _tax(total), "livraison": 0.0, "paiement": paid, "traitement": trait,
                       "litige": False, "transporteur": "Parcelia", "suivi": trk if code else None, "remboursement": None,
                       "chronologie": tl, "adresse": f"{cp} {ville}", "tags": []})
        if r.random() < 0.3:
            sujet, msg = pick([("Changement d'adresse", "Bonjour, puis-je modifier l'adresse de livraison de ma commande ?"),
                               ("Facture", "Bonjour, pourriez-vous m'envoyer la facture de ma commande ?"),
                               ("Taille", "Bonjour, la taille est-elle conforme au guide des tailles ?"),
                               ("Délai", "Bonjour, quand ma commande sera-t-elle expédiée ?")])
            tickets.append({"commande": oid, "email": email, "client": f"{prenom} {nom}", "date": d.isoformat(),
                            "sujet": sujet, "messages": [("client", msg), ("agent", "Bonjour, c'est noté, nous revenons vers vous rapidement.")],
                            "statut": "Résolu" if r.random() < 0.7 else "En attente", "preuve": "losing_evidence"})
    return orders, ships, tickets, clients


def data() -> dict:
    orders, ships, tickets, clients = [], [], [], {}
    for s in generate():
        o, sh, t = _from_scenario(s)
        orders.append(o)
        ships.append(sh)
        tickets += t
        c = s["client"]
        clients[c["email"]] = {"nom": f"{c['prenom']} {c['nom']}", "ville": c["ville"], "cp": c["cp"],
                               "depuis": c["client_depuis"], "commandes": c["commandes"]}
    fo, fs, ft, fc = _filler(60)
    orders += fo
    ships += fs
    tickets += ft
    clients.update(fc)
    orders.sort(key=lambda o: (o["date"], o["id"]), reverse=True)
    tickets.sort(key=lambda t: t["date"], reverse=True)
    for i, t in enumerate(tickets):
        t["id"] = f"#{4100 + len(tickets) - i}"
    return {"orders": {o["id"]: o for o in orders}, "order_list": [o["id"] for o in orders],
            "shipments": {s["tracking"]: s for s in ships}, "tickets": tickets, "clients": clients,
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
