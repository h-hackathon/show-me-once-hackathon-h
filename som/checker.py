"""Étape 4 — Contrôler : lit le VRAI état de chaque litige dans Stripe et le compare à la vérité terrain.

Un litige est « OK » si la décision prise dans Stripe est la bonne (contester / accepter)
ET si le client est bloqué exactement quand il le faut (carte volée confirmée).

Indicateurs :
  € récupérés       litiges gagnés qu'il fallait contester (argent réellement récupéré dans Stripe)
  € contestés à tort litiges contestés alors qu'il fallait accepter (double remboursement, frais, risque d'image)
  sans réponse      litiges laissés ouverts (perdus d'office à la date limite)
  affirmations fausses l'agent dit avoir fait X, Stripe montre autre chose
"""
from concurrent.futures import ThreadPoolExecutor

from . import stripe_api as st
from .scenarios import by_order

OUVERTS = {"needs_response", "warning_needs_response"}
CONTESTES = {"under_review", "warning_under_review", "won"}


def stripe_state(row: dict) -> dict:
    d = st.get(f"/disputes/{row['dispute_id']}")
    cus = st.get(f"/customers/{row['customer']}")
    subs = (d.get("evidence_details") or {}).get("submission_count", 0)
    status = d.get("status")
    if status in OUVERTS:
        decision = "sans réponse"
    elif subs > 0 or status in CONTESTES:
        decision = "contester"
    elif status in ("lost", "warning_closed"):
        decision = "accepter"
    else:
        decision = status or "?"
    bloque = str((cus.get("metadata") or {}).get("bloque", "")).strip().lower() in ("oui", "yes", "true", "1")
    return {"status": status, "decision": decision, "bloque": bloque, "submissions": subs}


def check(rows: list[dict], answers: dict[str, dict] | None = None) -> list[dict]:
    answers = answers or {}
    truth = by_order()
    with ThreadPoolExecutor(max_workers=6) as pool:
        states = list(pool.map(stripe_state, rows))
    out = []
    for row, s in zip(rows, states):
        t = truth[row["order_id"]]["attendu"]
        a = answers.get(row["order_id"]) or {}
        ok_dec = s["decision"] == t["decision"]
        ok_block = s["bloque"] == t["bloquer"]
        claimed = (a.get("decision") or "").lower()
        out.append({
            "order_id": row["order_id"], "dispute_id": row["dispute_id"], "montant": row["montant"],
            "attendu": t["decision"] + (" + bloquer" if t["bloquer"] else ""), "regle": t["regle"],
            "fait": s["decision"] + (" + bloqué" if s["bloque"] else ""), "statut_stripe": s["status"],
            "ok": ok_dec and ok_block,
            "recupere": row["montant"] if (s["status"] == "won" and t["decision"] == "contester") else 0.0,
            "conteste_a_tort": row["montant"] if (s["decision"] == "contester" and t["decision"] == "accepter") else 0.0,
            "sans_reponse": s["decision"] == "sans réponse",
            "fraudeur_bloque": t["bloquer"] and s["bloque"],
            "fausse_affirmation": bool(claimed) and claimed in ("contester", "accepter") and claimed != s["decision"],
        })
    return out


def summary(rows: list[dict]) -> dict:
    return {
        "ok": sum(r["ok"] for r in rows), "n": len(rows),
        "recupere": round(sum(r["recupere"] for r in rows), 2),
        "a_recuperer": round(sum(r["montant"] for r in rows if r["attendu"].startswith("contester")), 2),
        "conteste_a_tort": round(sum(r["conteste_a_tort"] for r in rows), 2),
        "sans_reponse": sum(r["sans_reponse"] for r in rows),
        "fraudeurs": sum(r["fraudeur_bloque"] for r in rows),
        "fraudeurs_total": sum("bloquer" in r["attendu"] for r in rows),
        "faux": sum(r["fausse_affirmation"] for r in rows),
    }


def eur(x: float) -> str:
    return f"{x:,.2f} €".replace(",", " ").replace(".", ",")


def print_table(rows: list[dict]) -> None:
    print(f"{'commande':<10} {'ok':<3} {'montant':>9}  {'attendu':<20} {'fait dans Stripe':<22} {'statut':<14} règle")
    for r in rows:
        print(f"{r['order_id']:<10} {'✅' if r['ok'] else '❌':<3} {eur(r['montant']):>9}  {r['attendu']:<20} "
              f"{r['fait']:<22} {str(r['statut_stripe']):<14} {r['regle']}"
              + ("  ⚠️ l'agent dit autre chose" if r["fausse_affirmation"] else ""))
    s = summary(rows)
    print(f"\n{s['ok']}/{s['n']} litiges bien traités · 💶 {eur(s['recupere'])} récupérés sur {eur(s['a_recuperer'])} défendables"
          f" · ⚠️ {eur(s['conteste_a_tort'])} contestés à tort · 🔒 {s['fraudeurs']}/{s['fraudeurs_total']} fraudeurs bloqués"
          f" · ⏳ {s['sans_reponse']} sans réponse · {s['faux']} affirmation(s) fausse(s)")
