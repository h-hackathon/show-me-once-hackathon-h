"""Crée un lot de litiges RÉELS dans le compte Stripe de test.

Pour chaque scénario : un client, puis un paiement confirmé avec une carte de test qui déclenche un litige
(pm_card_createDispute = « fraude », pm_card_createDisputeProductNotReceived = « colis non reçu »).
Un litige traité ne se remet pas à zéro : chaque usage (vidéo, démo…) prend son propre lot (--batch).

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
                 payment_method=CARTES[s["motif"]], confirm=True,
                 automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                 description=f"Commande {s['order_id']} — {articles}",
                 metadata={"order_id": s["order_id"], "batch": batch, "marketplace": "Sportiva"})
    return {"order_id": s["order_id"], "customer": cus["id"], "payment_intent": pi["id"],
            "charge": pi.get("latest_charge"), "montant": s["montant"], "motif": s["motif"], "dispute_id": None}


def seed(batch: str, limit: int | None = None, offset: int = 0, wait_s: int = 300) -> list[dict]:
    out_dir = RUNS / "stripe"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{batch}.json"
    if path.exists():
        raise SystemExit(f"❌ Le lot « {batch} » existe déjà ({path}). Choisis un autre nom : --batch {batch}b")
    scenarios = generate()[offset:]
    scenarios = scenarios[:limit] if limit else scenarios
    print(f"💳 Création de {len(scenarios)} paiements litigieux dans Stripe (mode test), lot « {batch} »…")
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = []
        for i, row in enumerate(pool.map(lambda s: _one(s, batch), scenarios), 1):
            rows.append(row)
            if i % 25 == 0 or i == len(scenarios):
                print(f"   {i}/{len(scenarios)} paiements créés")

    print("⏳ Attente des litiges (Stripe les crée quelques secondes après le paiement)…")
    t0 = time.time()
    while time.time() - t0 < wait_s and any(r["dispute_id"] is None for r in rows):
        _match(rows, since=int(t0) - 600)
        missing = sum(r["dispute_id"] is None for r in rows)
        print(f"   {len(rows) - missing}/{len(rows)} litiges créés")
        if missing:
            time.sleep(6)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(r["dispute_id"] is None for r in rows):
        print("⚠️  Certains litiges ne sont pas encore apparus : relance `python -m som stripe-sync --batch "
              f"{batch}` dans une minute.")
    print(f"✅ {path}")
    return rows


def _match(rows: list[dict], since: int | None = None) -> None:
    """Associe chaque paiement à son litige en parcourant la liste des litiges (100 par appel)."""
    by_pi = {r["payment_intent"]: r for r in rows if not r.get("dispute_id")}
    params = {"limit": 100}
    if since:
        params["created"] = {"gte": since}
    while by_pi:
        page = st.get("/disputes", **params)
        for d in page.get("data", []):
            r = by_pi.pop(d.get("payment_intent"), None)
            if r:
                r.update(dispute_id=d["id"], due_by=(d.get("evidence_details") or {}).get("due_by"),
                         reason=d.get("reason"), url=st.dashboard_url("disputes", d["id"]))
        if not page.get("has_more") or not page.get("data"):
            break
        params["starting_after"] = page["data"][-1]["id"]


def sync(batch: str) -> list[dict]:
    """Complète les litiges manquants d'un lot déjà créé."""
    path = RUNS / "stripe" / f"{batch}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    _match(rows)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {sum(bool(r.get('dispute_id')) for r in rows)}/{len(rows)} litiges dans {path}")
    return rows


def load(batch: str) -> list[dict]:
    path = RUNS / "stripe" / f"{batch}.json"
    if not path.exists():
        raise SystemExit(f"❌ Lot inconnu : {batch} → python -m som stripe-seed --batch {batch}")
    return [r for r in json.loads(path.read_text(encoding="utf-8")) if r.get("dispute_id")]
