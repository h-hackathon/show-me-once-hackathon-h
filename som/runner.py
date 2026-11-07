"""Étape 3 — Exécuter : une session agent H par litige Stripe, en parallèle.

Chaque session : ouvrir le litige dans le Dashboard Stripe → enquêter dans le back-office, le portail transporteur
et le support → décider (contester / accepter, bloquer ou non) → agir dans Stripe.

Conditions du benchmark :
  A = agent seul, consigne classique (« traite le litige au mieux »)
  B = même consigne + Skill apprise de la démo (les règles de l'équipe)
"""
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .config import RUNS, env
from .tools_site import COMPTES

MOTIFS = {"fraudulent": "fraude (le titulaire dit ne pas avoir fait l'achat)",
          "product_not_received": "produit non reçu"}


class DisputeResult(BaseModel):
    order_id: str
    decision: str                 # "contester" ou "accepter"
    evidence_submitted: bool      # l'agent dit avoir soumis des preuves dans Stripe
    customer_blocked: bool        # l'agent dit avoir bloqué le client (métadonnée bloque = oui)
    evidence_found: list[str]     # éléments trouvés dans les outils (ex. « signé par X le … »)
    reason: str
    blockers: list[str]


TASK = """Tu es analyste litiges (chargebacks) pour la marketplace Sportiva. Traite ce litige Stripe de bout en bout.

Litige : {url}
Commande {order_id} · {montant} € · motif : {motif}

Outils internes pour enquêter :
- Back-office Sportiva Admin : {outils}/admin{c1}
- Portail transporteur Parcelia Pro : {outils}/parcelia{c2}
- Support client Sportiva Care : {outils}/care{c3}
{stripe_login}
Décide s'il faut contester ou accepter le litige, puis fais-le dans le Dashboard Stripe (mode test).
Ne laisse pas le litige sans réponse. N'invente aucune preuve.
Réponds avec ce que tu as réellement fait dans Stripe."""

SKILL_BLOCK = """

Voici la procédure et les règles de l'équipe litiges, apprises en regardant une analyste traiter un litige.
Suis-les à la lettre :

{skill}"""


def stripe_login() -> str:
    from .auth import login_hint
    return login_hint("stripe", "shopify")


def build_task(row: dict, skill: str | None) -> str:
    (u1, p1), (u2, p2), (u3, p3) = COMPTES["admin"], COMPTES["parcelia"], COMPTES["care"]
    cred = (lambda u, p: "") if env("HAI_VAULT_ID") else (lambda u, p: f"  (identifiant {u} / mot de passe {p})")
    task = TASK.format(url=row["url"], order_id=row["order_id"], montant=f"{row['montant']:.2f}".replace(".", ","),
                       motif=MOTIFS.get(row.get("reason") or row["motif"], row.get("reason") or row["motif"]),
                       outils=env("OUTILS_URL", required=True).rstrip("/"),
                       c1=cred(u1, p1), c2=cred(u2, p2), c3=cred(u3, p3), stripe_login=stripe_login())
    return task + (SKILL_BLOCK.format(skill=skill) if skill else "")


def session_options() -> dict:
    from .auth import session_options as opts
    return opts()


def _answer(result):
    raw = getattr(result, "answer", None)
    if raw is None and getattr(result, "final_changes", None) is not None:
        raw = getattr(result.final_changes, "answer", None)
    if isinstance(raw, BaseModel):
        return raw.model_dump(), ""
    if isinstance(raw, dict):
        return raw, ""
    if isinstance(raw, str):
        try:
            return json.loads(raw), ""
        except json.JSONDecodeError:
            return None, f"réponse non structurée : {raw[:200]}"
    return None, "pas de réponse"


def run_one(row: dict, condition: str, skill: str | None, run_id: int) -> dict:
    from hai_agents import Client
    client = Client()
    t0 = time.time()
    status, answer, events, session, error = "error", None, 0, "", ""
    try:
        result = client.run_session(agent=env("HAI_AGENT", "h/web-surfer-pro"), messages=build_task(row, skill),
                                    answer_schema=DisputeResult, **session_options())
        status = str(getattr(result, "status", ""))
        events = len(result.events) if getattr(result, "events", None) else 0
        session = str(getattr(result, "id", "") or "")
        answer, error = _answer(result)
        if session:  # lien de replay : preuve pour le jury
            try:
                session = client.sessions.share_session(session).share_url or session
            except Exception:
                pass
    except Exception as e:  # une session qui plante ne doit pas arrêter le lot
        error = f"{e.__class__.__name__}: {e}"

    blockers = (answer or {}).get("blockers") or ([error] if error else [])
    verdict = (answer or {}).get("decision") or ("blocked" if blockers else "gave_up")
    return {
        "run_id": run_id, "condition": condition, "order_id": row["order_id"], "dispute_id": row["dispute_id"],
        "task": "Traiter un litige Stripe (enquête dans 3 outils + réponse dans Stripe)",
        "steps": events, "time_s": round(time.time() - t0, 1), "result": verdict,
        "blockers": " | ".join(blockers), "proof_screenshot": session,
        "notes": json.dumps({"status": status, "answer": answer, "error": error}, ensure_ascii=False),
        "_answer": answer,
    }


def run_batch(rows: list[dict], condition: str, skill: str | None, run_id: int,
              concurrency: int, out_dir: Path) -> list[dict]:
    label = "A_prompt_only" if condition == "A" else "B_with_skill"
    from .config import env as _env
    if concurrency > 1 and "tools" in session_options() and not _env("OTP_IMAP_HOST"):
        print("ℹ️  Code e-mail demandé dans le terminal : litiges traités l'un après l'autre "
              "(remplis OTP_IMAP_* pour le parallèle).")
        concurrency = 1
    print(f"🚀 Run {run_id} · {label} · {len(rows)} litige(s) · {concurrency} en parallèle")
    done = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_one, r, label, skill if condition == "B" else None, run_id) for r in rows]
        for f in as_completed(futures):
            row = f.result()
            done.append(row)
            a = row["_answer"] or {}
            print(f"   {row['order_id']} → {row['result']:<10} {row['steps']:>3} étapes {row['time_s']:>6}s"
                  + (" 🔒 bloqué" if a.get("customer_blocked") else "")
                  + (f"  ({row['blockers'][:80]})" if row["blockers"] else ""))
    done.sort(key=lambda r: r["order_id"])
    _append_csv(out_dir / "log.csv", done)
    return done


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
