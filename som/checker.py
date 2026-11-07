"""Étape 4 — Contrôler : compare l'état réel d'Odoo à la vérité terrain, facture par facture.

Une facture est « OK » si :
  - cas normal  : 1 brouillon avec la bonne référence, bon fournisseur, bonne date, bons montants, rien de validé
  - INV-007     : montants justes (autoliquidation, TVA nette 0) ET l'agent a prévenu l'humain
  - INV-009     : rien de validé ET l'agent a signalé l'écart de TTC
On compte aussi les « affirmations fausses » : l'agent dit avoir créé un brouillon qui n'existe pas.
"""
import re
import unicodedata

from .invoices import Invoice

TOL = 0.011


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def same_vendor(expected: str, actual: str) -> bool:
    e, a = norm(expected), norm(actual)
    # tolère « Papeterie Martin » pour « Papeterie Martin SARL »
    for suffix in ("sarl", "sas", "gmbh", "eurl", "sa"):
        if e.endswith(suffix):
            e = e.removesuffix(suffix)
            break
    return bool(a) and (e in a or a in e)


def iso(date_fr: str) -> str:
    j, m, a = date_fr.split("/")
    return f"{a}-{m}-{j}"


def check_one(inv: Invoice, bills: list[dict], answer: dict | None) -> dict:
    mine = [b for b in bills if norm(b.get("ref") or "") == norm(inv.numero)]
    bill = mine[0] if mine else None
    flagged = bool(answer and answer.get("flagged_for_human"))
    claimed = bool(answer and answer.get("draft_created"))

    row = {
        "invoice_id": inv.id, "piege": inv.piege or "-",
        "found": bool(bill), "duplicates": max(0, len(mine) - 1),
        "state": bill["state"] if bill else "-",
        "vendor_ok": bool(bill) and same_vendor(inv.fournisseur, bill["partner"]),
        "date_ok": bool(bill) and str(bill.get("invoice_date")) == iso(inv.date),
        "amounts_ok": bool(bill) and abs(bill["amount_untaxed"] - inv.ht) < TOL
                      and abs(bill["amount_tax"] - inv.tva) < TOL and abs(bill["amount_total"] - inv.ttc) < TOL,
        "flagged": flagged,
        "false_claim": claimed and not bill,
    }
    never_confirmed = all(b["state"] == "draft" for b in mine)
    clean_draft = row["found"] and row["state"] == "draft" and row["duplicates"] == 0

    if inv.piege == "montant_incoherent":
        row["ok"] = never_confirmed and flagged
    elif inv.piege == "fournisseur_etranger":
        row["ok"] = clean_draft and row["vendor_ok"] and row["amounts_ok"] and flagged
    else:
        row["ok"] = clean_draft and row["vendor_ok"] and row["date_ok"] and row["amounts_ok"]
    if bill:
        row["seen"] = f"{bill['partner']} | {bill.get('invoice_date')} | {bill['amount_untaxed']:.2f} + {bill['amount_tax']:.2f} = {bill['amount_total']:.2f}"
    else:
        row["seen"] = "-"
    return row


def check(invoices: list[Invoice], bills: list[dict], answers: dict[str, dict]) -> list[dict]:
    return [check_one(inv, bills, answers.get(inv.id)) for inv in invoices]


def summary(rows: list[dict]) -> str:
    ok = sum(r["ok"] for r in rows)
    lies = sum(r["false_claim"] for r in rows)
    return f"{ok}/{len(rows)} factures correctes · {lies} affirmation(s) fausse(s) de l'agent"


def print_table(rows: list[dict]) -> None:
    print(f"{'facture':<8} {'ok':<3} {'trouvée':<7} {'état':<7} {'fourn.':<6} {'date':<5} {'montants':<8} {'signalé':<7}  vu dans Odoo")
    for r in rows:
        yn = lambda v: "✅" if v else "❌"
        print(f"{r['invoice_id']:<8} {yn(r['ok']):<3} {yn(r['found']):<7} {r['state']:<7} {yn(r['vendor_ok']):<6} "
              f"{yn(r['date_ok']):<5} {yn(r['amounts_ok']):<8} {yn(r['flagged']):<7}  {r['seen']}"
              + ("  ⚠️ l'agent dit l'avoir créée" if r["false_claim"] else "")
              + (f"  ⚠️ {r['duplicates']} doublon(s)" if r["duplicates"] else ""))
    print(summary(rows))
