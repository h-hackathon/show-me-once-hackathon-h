"""Étape 3 — Exécuter : l'agent H saisit N factures en parallèle dans Odoo et s'arrête en brouillon.

Conditions du benchmark :
  A = agent seul, consigne classique
  B = même consigne + Skill apprise de la démo
"""
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .config import RUNS, env
from .invoices import Invoice, to_text


class InvoiceResult(BaseModel):
    draft_created: bool        # l'agent dit avoir enregistré un brouillon
    vendor: str
    invoice_number: str
    invoice_date: str
    total_untaxed: float
    total_tax: float
    total_incl_tax: float
    flagged_for_human: bool    # l'agent demande une vérification humaine
    flag_reason: str
    blockers: list[str]


BASE_TASK = """Tu es comptable fournisseurs. Saisis la facture fournisseur ci-dessous dans Odoo.

Odoo : {odoo_url}
Identifiant : {login}
Mot de passe : {password}

{invoice}

Laisse la facture en brouillon : ne clique jamais sur « Confirmer ».
Si quelque chose te semble anormal, n'invente rien : mets flagged_for_human à true et explique dans flag_reason.
Réponds avec ce qui est réellement enregistré dans Odoo."""

SKILL_BLOCK = """

Voici la procédure et les règles de l'équipe, apprises en regardant un comptable faire la tâche.
Suis-les à la lettre :

{skill}"""


def invoice_block(inv: Invoice) -> str:
    base_url = env("INVOICE_BASE_URL")
    if base_url:
        return (f"La facture à saisir est ici (ouvre-la dans un nouvel onglet et lis-la) : "
                f"{base_url.rstrip('/')}/{inv.id}.png")
    return f"Contenu de la facture à saisir :\n---\n{to_text(inv.id)}\n---"


def build_task(inv: Invoice, skill: str | None) -> str:
    task = BASE_TASK.format(odoo_url=env("ODOO_URL", required=True), login=env("ODOO_LOGIN", required=True),
                            password=env("ODOO_PASSWORD", required=True), invoice=invoice_block(inv))
    return task + (SKILL_BLOCK.format(skill=skill) if skill else "")


def run_one(inv: Invoice, condition: str, skill: str | None, run_id: int) -> dict:
    from hai_agents import Client
    t0 = time.time()
    status, answer, events, session, error = "error", None, 0, "", ""
    try:
        result = Client().run_session(agent=env("HAI_AGENT", "h/web-surfer-pro"),
                                      messages=build_task(inv, skill), answer_schema=InvoiceResult)
        status = str(getattr(result, "status", ""))
        events = len(result.events) if getattr(result, "events", None) else 0
        session = str(getattr(result, "id", "") or getattr(result, "session_id", "") or "")
        raw = getattr(result, "answer", None)
        if isinstance(raw, BaseModel):
            answer = raw.model_dump()
        elif isinstance(raw, dict):
            answer = raw
        elif isinstance(raw, str):
            try:
                answer = json.loads(raw)
            except json.JSONDecodeError:
                error = f"réponse non structurée : {raw[:200]}"
    except Exception as e:  # une session qui plante ne doit pas arrêter le lot
        error = f"{e.__class__.__name__}: {e}"

    blockers = (answer or {}).get("blockers") or ([error] if error else [])
    if answer and answer.get("draft_created"):
        verdict = "reached"
    elif blockers:
        verdict = "blocked"
    else:
        verdict = "gave_up"
    return {
        "run_id": run_id, "condition": condition, "invoice_id": inv.id,
        "task": "Saisir la facture dans Odoo et s'arrêter avant validation",
        "steps": events, "time_s": round(time.time() - t0, 1), "result": verdict,
        "blockers": " | ".join(blockers), "proof_screenshot": session,
        "notes": json.dumps({"status": status, "answer": answer, "error": error}, ensure_ascii=False),
        "_answer": answer,
    }


def run_batch(invoices: list[Invoice], condition: str, skill: str | None, run_id: int,
              concurrency: int, out_dir: Path) -> list[dict]:
    label = "A_prompt_only" if condition == "A" else "B_with_skill"
    print(f"🚀 Run {run_id} · {label} · {len(invoices)} facture(s) · {concurrency} en parallèle")
    rows = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(run_one, inv, label, skill if condition == "B" else None, run_id): inv
                   for inv in invoices}
        for f in as_completed(futures):
            row = f.result()
            rows.append(row)
            flag = " 🚩" if (row["_answer"] or {}).get("flagged_for_human") else ""
            print(f"   {row['invoice_id']} → {row['result']:<8} {row['steps']:>3} étapes {row['time_s']:>6}s{flag}"
                  + (f"  ({row['blockers'][:80]})" if row["blockers"] else ""))
    rows.sort(key=lambda r: r["invoice_id"])
    _append_csv(out_dir / "log.csv", rows)
    return rows


def _append_csv(path: Path, rows: list[dict]) -> None:
    fields = [k for k in rows[0] if not k.startswith("_")]
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def new_run_dir() -> Path:
    d = RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    return d
