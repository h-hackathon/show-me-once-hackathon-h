"""Crée un lot de litiges RÉELS dans le compte Stripe de test.

Pour chaque scénario : un client, puis un paiement confirmé avec une carte de test qui déclenche un litige
(pm_card_createDispute = « fraude », pm_card_createDisputeProductNotReceived = « colis non reçu »).
Un litige ne se remet pas à zéro : chaque run du benchmark utilise donc son propre lot (--batch).

Sortie : runs/stripe/<batch>.json  [{order_id, dispute_id, payment_intent, customer, montant, …}]
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

from . import stripe_api as st
from .config import RUNS
from .scenarios import generate

CARTES = {"fraudulent": "pm_card_createDispute", "product_not_received": "pm_card_createDisputeProductNotReceived"}


def _one(s: dict, batch: str) -> dict:
    c = s["client"]
    cus = st.post("/customers", name=f"{c['prenom']} {c['nom']}", email=c["email"],
                  metadata={"order_id": s["order_id"], "batch": batch})
    articles = ", ".join(a["nom"] for a in s["articles"])
    pi = st.post("/payment_intents", amount=round(s["montant"] * 100), currency="eur", customer=cus["id"],
                 payment_method=CARTES[s["motif"]], payment_method_types=["card"], confirm=True,
                 description=f"Commande {s['order_id']} — {articles}",
                 metadata={"order_id": s["order_id"], "batch": batch, "marketplace": "Sportiva"})
    return {"order_id": s["order_id"], "customer": cus["id"], "payment_intent": pi["id"],
            "charge": pi.get("latest_charge"), "montant": s["montant"], "motif": s["motif"], "dispute_id": None}


def seed(batch: str, limit: int | None = None, wait_s: int = 90) -> list[dict]:
    out_dir = RUNS / "stripe"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{batch}.json"
    if path.exists():
        raise SystemExit(f"❌ Le lot « {batch} » existe déjà ({path}). Choisis un autre nom : --batch {batch}b")
    scenarios = generate()[:limit] if limit else generate()
    print(f"💳 Création de {len(scenarios)} paiements litigieux dans Stripe (mode test), lot « {batch} »…")
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda s: _one(s, batch), scenarios))

    print("⏳ Attente des litiges (Stripe les crée quelques secondes après le paiement)…")
    t0 = time.time()
    while time.time() - t0 < wait_s and any(r["dispute_id"] is None for r in rows):
        for r in rows:
            if r["dispute_id"] is None:
                found = st.get("/disputes", payment_intent=r["payment_intent"], limit=1).get("data", [])
                if found:
                    d = found[0]
                    r.update(dispute_id=d["id"], due_by=(d.get("evidence_details") or {}).get("due_by"),
                             reason=d.get("reason"), url=st.dashboard_url("disputes", d["id"]))
        missing = sum(r["dispute_id"] is None for r in rows)
        print(f"   {len(rows) - missing}/{len(rows)} litiges créés")
        if missing:
            time.sleep(4)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(r["dispute_id"] is None for r in rows):
        print("⚠️  Certains litiges ne sont pas encore apparus : relance `python -m som stripe-sync --batch "
              f"{batch}` dans une minute.")
    print(f"✅ {path}")
    return rows


def sync(batch: str) -> list[dict]:
    """Complète les litiges manquants d'un lot déjà créé."""
    path = RUNS / "stripe" / f"{batch}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for r in rows:
        if not r.get("dispute_id"):
            found = st.get("/disputes", payment_intent=r["payment_intent"], limit=1).get("data", [])
            if found:
                d = found[0]
                r.update(dispute_id=d["id"], due_by=(d.get("evidence_details") or {}).get("due_by"),
                         reason=d.get("reason"), url=st.dashboard_url("disputes", d["id"]))
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {sum(bool(r.get('dispute_id')) for r in rows)}/{len(rows)} litiges dans {path}")
    return rows


def load(batch: str) -> list[dict]:
    path = RUNS / "stripe" / f"{batch}.json"
    if not path.exists():
        raise SystemExit(f"❌ Lot inconnu : {batch} → python -m som stripe-seed --batch {batch}")
    return [r for r in json.loads(path.read_text(encoding="utf-8")) if r.get("dispute_id")]
