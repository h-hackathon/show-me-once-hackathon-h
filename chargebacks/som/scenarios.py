"""Les 60 litiges de la démo (24 historiques + 36 ajoutés) et la vérité terrain (ce qu'un analyste expérimenté ferait).

Marketplace fictive « Sportiva ». Chaque litige Stripe est rattaché à une commande (métadonnée order_id).
Les preuves sont dispersées dans 3 outils internes : back-office commandes, portail transporteur, support client.

Règles de l'équipe (dans cet ordre) — c'est ce que la Skill doit apprendre de la démo :
  1. montant < 15 €                          → accepter (se défendre coûte plus cher que le litige : ~15 € de frais)
  2. carte volée confirmée par le titulaire  → accepter ET bloquer le client dans Stripe (métadonnée bloque = oui)
  3. client déjà remboursé (back-office)     → contester avec la preuve de remboursement (sinon on paie deux fois)
  4. livré contre signature (transporteur)   → contester avec la preuve de livraison
  5. réception confirmée par le client (support) → contester avec l'export du ticket
  6. sinon (perdu, sans signature, rien)     → accepter (aucune preuve à faire valoir)

Chaque document affiche une « référence de preuve à transmettre ». Mode test Stripe : une preuve contenant
« winning_evidence » fait gagner le litige, « losing_evidence » le fait perdre. Un document qui ne prouve rien
(livraison sans signature, ticket sans aveu de réception) porte donc « losing_evidence ».
"""
import random
from datetime import date, timedelta

SEED = 7
SEUIL_MONTANT = 15.0

PRENOMS = ["Camille", "Lucas", "Emma", "Hugo", "Léa", "Louis", "Chloé", "Nathan", "Manon", "Jules", "Inès", "Gabriel",
           "Sarah", "Arthur", "Zoé", "Raphaël", "Lina", "Tom", "Jade", "Adam", "Alice", "Paul", "Eva", "Noé", "Clara"]
NOMS = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau", "Simon",
        "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morel", "Girard"]
VILLES = [("Lyon", "69003"), ("Lille", "59000"), ("Nantes", "44000"), ("Bordeaux", "33000"), ("Toulouse", "31000"),
          ("Marseille", "13006"), ("Rennes", "35000"), ("Strasbourg", "67000"), ("Montpellier", "34000"), ("Paris", "75011")]
PRODUITS = [("Chaussures de trail homme", 89.99), ("Veste coupe-vent running", 59.99), ("Tente 3 places", 149.99),
            ("Sac à dos randonnée 30 L", 49.99), ("Vélo de ville 28\"", 329.00), ("Raquette de tennis adulte", 79.99),
            ("Montre GPS cardio", 199.99), ("Doudoune légère", 69.99), ("Combinaison néoprène 3 mm", 129.99),
            ("Tapis de yoga 8 mm", 29.99), ("Ballon de football taille 5", 19.99), ("Lampe frontale 400 lm", 34.99),
            ("Gourde inox 750 ml", 12.99), ("Chaussettes de ski x2", 9.99), ("Bandeau running", 6.99),
            ("Bâtons de marche nordique", 44.99), ("Casque vélo urbain", 39.99), ("Planche de surf 7'", 279.00)]
PETITS = [("Bandeau running", 6.99), ("Chaussettes de ski x2", 9.99), ("Gourde inox 750 ml", 12.99), ("Gants tactiles", 14.49)]

# 24 premiers litiges (inchangés : le lot « essai » et le script vidéo s'appuient dessus)
FAMILLES = [
    ("livre_signe", "product_not_received", 5),   # contester avec la preuve de livraison (signée par le client)
    ("livre_signe", "fraudulent", 3),             # « fraude » mais livré et signé par le titulaire → contester
    ("recu_confirme", "product_not_received", 3), # sans signature, MAIS le client a écrit « bien reçu » → contester avec le ticket
    ("deja_rembourse", "product_not_received", 3),# colis égaré, MAIS déjà remboursé → contester avec la preuve de remboursement
    ("petit_montant", "product_not_received", 3), # piège : livré signé, mais < 15 € → accepter
    ("carte_volee", "fraudulent", 3),             # piège : signé par un tiers, titulaire confirme le vol → accepter + bloquer
    ("perdu", "product_not_received", 2),         # accepter : colis égaré, rien d'autre
    ("sans_signature", "product_not_received", 2),# accepter : boîte aux lettres, rien d'autre
]
# 36 litiges ajoutés (mêmes 6 règles, deux pièges de plus qui obligent à croiser les outils)
FAMILLES_EXTRA = [
    ("livre_signe", "product_not_received", 8),
    ("livre_signe", "fraudulent", 4),
    ("recu_confirme", "product_not_received", 4),
    ("deja_rembourse", "product_not_received", 4),
    ("petit_montant", "product_not_received", 4),
    ("carte_volee", "fraudulent", 3),
    ("carte_volee_petit", "fraudulent", 2),       # piège : carte volée MAIS < 15 € → la règle 1 passe avant : accepter, PAS de blocage
    ("perdu_puis_recu", "product_not_received", 3),# piège : Parcelia dit « égaré », mais le client a écrit au support qu'il l'a finalement reçu → contester (ticket)
    ("perdu", "product_not_received", 2),
    ("sans_signature", "product_not_received", 2),
]


def decide(s: dict) -> tuple[str, bool, str]:
    """Vérité terrain : (decision, bloquer, règle appliquée)."""
    if s["montant"] < SEUIL_MONTANT:
        return "accepter", False, "montant < 15 € → accepter"
    if s["carte_volee"]:
        return "accepter", True, "carte volée confirmée → accepter + bloquer"
    if s["rembourse"]:
        return "contester", False, "déjà remboursé → contester (preuve de remboursement)"
    if s["livraison"]["statut"] == "livre_signe":
        return "contester", False, "livré signé → contester (preuve transporteur)"
    if any(t.get("preuve") == "winning_evidence" for t in s["tickets"]):
        return "contester", False, "réception confirmée → contester (export du ticket)"
    return "accepter", False, "aucune preuve → accepter"


def generate(seed: int = SEED) -> list[dict]:
    r = random.Random(seed)
    pick = lambda seq: seq[int(r.random() * len(seq))]
    aujourd_hui = date(2026, 11, 7)
    scenarios, n = [], 0
    file = [(f, m) for f, m, k in FAMILLES for _ in range(k)]
    random.Random(seed + 1).shuffle(file)  # pièges mélangés dans la file, comme dans la vraie vie
    extra = [(f, m) for f, m, k in FAMILLES_EXTRA for _ in range(k)]
    random.Random(seed + 2).shuffle(extra)
    file += extra  # ajoutés APRÈS : les 24 premiers litiges restent strictement identiques
    for famille, motif in file:
        if True:
            n += 1
            prenom, nom = pick(PRENOMS), pick(NOMS)
            ville, cp = pick(VILLES)
            email = f"{prenom.lower().replace('é', 'e').replace('ë', 'e').replace('ï', 'i').replace('è', 'e')}.{nom.lower()}{n}@mail.test"
            commande = aujourd_hui - timedelta(days=12 + int(r.random() * 20))
            if famille in ("petit_montant", "carte_volee_petit"):
                articles = [(*pick(PETITS), 1)]
            else:
                articles = [(*pick(PRODUITS), 1)]
                if r.random() < 0.35:
                    articles.append((*pick(PRODUITS), 1))
            montant = round(sum(p * q for _, p, q in articles), 2)
            if famille not in ("petit_montant", "carte_volee_petit") and montant < SEUIL_MONTANT:
                articles.append(("Sac à dos randonnée 30 L", 49.99, 1))
                montant = round(sum(p * q for _, p, q in articles), 2)
            expedie = commande + timedelta(days=1)
            livre = expedie + timedelta(days=2 + int(r.random() * 2))
            suivi = f"PRC{int(r.random() * 9_000_000_000) + 1_000_000_000}"
            order_id = f"CMD-{10240 + n * 7}"
            s = {
                "id": n, "famille": famille, "motif": motif, "order_id": order_id,
                "client": {"prenom": prenom, "nom": nom, "email": email, "ville": ville, "cp": cp,
                           "client_depuis": str(2019 + int(r.random() * 6)),
                           "commandes": 1 + int(r.random() * 14)},
                "articles": [{"nom": a, "prix": p, "qte": q} for a, p, q in articles],
                "montant": montant, "date_commande": commande.isoformat(), "date_expedition": expedie.isoformat(),
                "transporteur": "Parcelia", "suivi": suivi,
                "rembourse": famille == "deja_rembourse", "carte_volee": famille in ("carte_volee", "carte_volee_petit"),
                "tickets": [],
            }
            # --- livraison (portail transporteur)
            evenements = [(expedie.isoformat() + " 18:12", "Colis pris en charge — hub Parcelia de Lyon-Saint-Exupéry"),
                          ((expedie + timedelta(days=1)).isoformat() + " 06:40", f"En transit — agence Parcelia de {ville}")]
            if famille in ("perdu", "deja_rembourse", "perdu_puis_recu"):
                evenements.append(((expedie + timedelta(days=2)).isoformat() + " 09:03", "Anomalie : colis non localisé"))
                s["livraison"] = {"statut": "perdu", "date": None, "signe_par": None, "preuve": "losing_evidence",
                                  "libelle": "Colis égaré — enquête ouverte"}
            elif famille in ("sans_signature", "recu_confirme"):
                evenements.append((livre.isoformat() + " 11:27", "Livré — déposé en boîte aux lettres"))
                s["livraison"] = {"statut": "boite_aux_lettres", "date": livre.isoformat(), "signe_par": None,
                                  "preuve": "losing_evidence", "libelle": "Livré sans signature (boîte aux lettres)"}
            else:
                signe = f"{pick(PRENOMS)} {pick(NOMS)}" if famille in ("carte_volee", "carte_volee_petit") else f"{prenom} {nom}"
                evenements.append((livre.isoformat() + " 10:" + f"{int(r.random() * 50) + 10}", "En cours de livraison"))
                evenements.append((livre.isoformat() + " 12:" + f"{int(r.random() * 50) + 10}", f"Livré — remis contre signature ({signe})"))
                s["livraison"] = {"statut": "livre_signe", "date": livre.isoformat(), "signe_par": signe,
                                  "preuve": "winning_evidence", "libelle": "Livré contre signature"}
            s["livraison"]["evenements"] = evenements
            # --- support client
            if famille == "recu_confirme":
                s["tickets"].append({"date": (livre + timedelta(days=1)).isoformat(), "sujet": "Ma commande",
                                     "messages": [("client", "Bonjour, j'ai bien reçu ma commande dans ma boîte aux lettres, merci pour la rapidité !"),
                                                  ("agent", "Merci pour votre retour, bonne journée !")], "statut": "Résolu",
                                     "preuve": "winning_evidence"})
            if famille == "deja_rembourse":
                d = expedie + timedelta(days=6)
                s["remboursement"] = {"date": d.isoformat(), "montant": montant, "ref": f"RMB-{80000 + n * 13}",
                                      "preuve": "winning_evidence"}
                s["tickets"].append({"date": (d - timedelta(days=1)).isoformat(), "sujet": "Colis jamais reçu",
                                     "messages": [("client", "Bonjour, mon colis n'est jamais arrivé."),
                                                  ("agent", f"Le transporteur a perdu votre colis : nous vous avons remboursé {montant:.2f} € "
                                                            f"le {d.strftime('%d/%m/%Y')} (réf. RMB-{80000 + n * 13})."),
                                                  ("client", "Merci.")], "statut": "Résolu", "preuve": "losing_evidence"})
            if famille in ("carte_volee", "carte_volee_petit"):
                d = commande + timedelta(days=4)
                s["tickets"].append({"date": d.isoformat(), "sujet": "Commande que je n'ai jamais passée",
                                     "messages": [("client", "Bonjour, je n'ai jamais commandé chez vous. Ma carte bancaire a été volée, "
                                                             "j'ai fait opposition et porté plainte. Cette commande est frauduleuse."),
                                                  ("agent", "Nous sommes désolés. Nous transmettons au service fraude.")], "statut": "En attente",
                                     "preuve": "losing_evidence"})
            if famille in ("perdu", "sans_signature"):
                s["tickets"].append({"date": (expedie + timedelta(days=5)).isoformat(), "sujet": "Colis jamais reçu",
                                     "messages": [("client", "Bonjour, je n'ai toujours pas reçu mon colis."),
                                                  ("agent", "Nous vérifions avec le transporteur et revenons vers vous.")], "statut": "En attente",
                                     "preuve": "losing_evidence"})
            if famille == "perdu_puis_recu":
                s["tickets"].append({"date": (expedie + timedelta(days=4)).isoformat(), "sujet": "Colis introuvable",
                                     "messages": [("client", "Bonjour, le suivi Parcelia indique que mon colis est égaré, je ne l'ai pas reçu."),
                                                  ("agent", "Nous ouvrons une enquête avec le transporteur."),
                                                  ("client", "Finalement mon colis est arrivé hier, une voisine l'avait récupéré. Je l'ai bien reçu, tout est en ordre, merci !"),
                                                  ("agent", "Parfait, merci de nous avoir prévenus. Bonne journée !")], "statut": "Résolu",
                                     "preuve": "winning_evidence"})
            if famille == "livre_signe" and r.random() < 0.5:
                s["tickets"].append({"date": (expedie + timedelta(days=1)).isoformat(), "sujet": "Délai de livraison",
                                     "messages": [("client", "Bonjour, quand est-ce que mon colis arrive ?"),
                                                  ("agent", f"Votre colis est en transit, livraison prévue le {livre.strftime('%d/%m')}.")], "statut": "Résolu",
                                     "preuve": "losing_evidence"})
            s["tickets"].sort(key=lambda t: t["date"])
            s["statut_commande"] = "Remboursée" if s["rembourse"] else (
                "Livrée" if s["livraison"]["statut"] != "perdu" else "Expédiée — anomalie transport")
            decision, bloquer, regle = decide(s)
            s["attendu"] = {"decision": decision, "bloquer": bloquer, "regle": regle}
            scenarios.append(s)
    return scenarios


def by_order(scenarios=None) -> dict[str, dict]:
    return {s["order_id"]: s for s in (scenarios or generate())}
