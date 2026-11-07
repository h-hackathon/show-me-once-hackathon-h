"""Étape 3 — Exécuter : une session agent H par pays, en parallèle.

Chaque session : Databricks → lancer le notebook rapport_<PAYS> → récupérer le résultat
→ le coller dans l'onglet <PAYS> du Google Sheet (le dashboard se met à jour tout seul).

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


class CountryResult(BaseModel):
    sheet_updated: bool            # l'agent dit avoir écrit dans l'onglet
    rows_written: int
    campaigns_written: list[str]   # campagne_id collés dans le Sheet
    campaigns_excluded: list[str]  # campagne_id volontairement écartés
    flagged_for_human: bool        # l'agent demande une vérification humaine
    flag_reason: str
    blockers: list[str]


TASK = """Tu mets à jour le rapport hebdomadaire des campagnes email de Decathlon pour le pays {pays}.

1. Va sur Databricks : {databricks}
{login}
2. Ouvre le notebook « rapport_{pays} » (Workspace > dossier show-me-once) et lance-le avec « Run all ». Attends la fin.
3. Le dernier bloc du notebook affiche le résultat en texte séparé par des tabulations (en-têtes compris).
4. Ouvre le Google Sheet {sheet} et va dans l'onglet « {pays} ».
   Remplace son contenu par ce résultat, à partir de la cellule A1.
5. Va dans l'onglet « Dashboard » et vérifie que la ligne {pays} a changé.

N'invente aucun chiffre. Ne touche à aucun autre onglet.
Si quelque chose te semble anormal, mets flagged_for_human à true et explique dans flag_reason.
Réponds avec ce qui est réellement écrit dans le Sheet."""

SKILL_BLOCK = """

Voici la procédure et les règles de l'équipe CRM, apprises en regardant une personne faire cette tâche.
Suis-les à la lettre :

{skill}"""


def login_block() -> str:
    if env("DATABRICKS_EMAIL"):
        otp = " Databricks t'enverra un code par e-mail : récupère-le avec l'outil de code à usage unique." \
            if env("OTP_IMAP_HOST") else ""
        return f"   Si on te demande de te connecter, utilise l'e-mail {env('DATABRICKS_EMAIL')}.{otp}"
    return "   Tu es déjà connecté (session enregistrée dans le navigateur)."


def build_task(pays: str, skill: str | None) -> str:
    task = TASK.format(pays=pays, databricks=env("DATABRICKS_URL", required=True), login=login_block(),
                       sheet=env("SHEET_URL", required=True))
    return task + (SKILL_BLOCK.format(skill=skill) if skill else "")


def session_options() -> dict:
    """Profil navigateur / coffre / lecteur de codes OTP, si configurés dans .env."""
    opts, overrides = {}, {}
    if env("HAI_BROWSER_PROFILE_ID"):
        overrides["agent.environments[kind=web].browser_profile_id"] = env("HAI_BROWSER_PROFILE_ID")
    if env("HAI_VAULT_ID"):
        overrides["agent.environments[kind=web].vault_id"] = env("HAI_VAULT_ID")
    if overrides:
        opts["overrides"] = overrides
    if env("OTP_IMAP_HOST"):
        from hai_agents_tools import imap_otp_handler, otp_tool
        opts["tools"] = [otp_tool(imap_otp_handler(host=env("OTP_IMAP_HOST"), username=env("OTP_IMAP_USER", required=True),
                                                   password=env("OTP_IMAP_PASSWORD", required=True)))]
    return opts


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


def run_one(pays: str, condition: str, skill: str | None, run_id: int) -> dict:
    from hai_agents import Client
    client = Client()
    t0 = time.time()
    status, answer, events, session, error = "error", None, 0, "", ""
    try:
        result = client.run_session(agent=env("HAI_AGENT", "h/web-surfer-pro"), messages=build_task(pays, skill),
                                    answer_schema=CountryResult, **session_options())
        status = str(getattr(result, "status", ""))
        events = len(result.events) if getattr(result, "events", None) else 0
        session = str(getattr(result, "id", "") or "")
        answer, error = _answer(result)
        if session:  # lien de replay, preuve pour le jury
            try:
                session = client.sessions.share_session(session).share_url or session
            except Exception:
                pass
    except Exception as e:  # une session qui plante ne doit pas arrêter le lot
        error = f"{e.__class__.__name__}: {e}"

    blockers = (answer or {}).get("blockers") or ([error] if error else [])
    if answer and answer.get("sheet_updated"):
        verdict = "reached"
    elif answer and answer.get("flagged_for_human"):
        verdict = "stopped_for_human"  # s'est arrêté volontairement pour prévenir un humain
    else:
        verdict = "blocked" if blockers else "gave_up"
    return {
        "run_id": run_id, "condition": condition, "pays": pays,
        "task": "Lancer rapport Databricks et mettre à jour l'onglet du Sheet",
        "steps": events, "time_s": round(time.time() - t0, 1), "result": verdict,
        "blockers": " | ".join(blockers), "proof_screenshot": session,
        "notes": json.dumps({"status": status, "answer": answer, "error": error}, ensure_ascii=False),
        "_answer": answer,
    }


def run_batch(pays_list: list[str], condition: str, skill: str | None, run_id: int,
              concurrency: int, out_dir: Path) -> list[dict]:
    label = "A_prompt_only" if condition == "A" else "B_with_skill"
    print(f"🚀 Run {run_id} · {label} · {len(pays_list)} pays · {concurrency} en parallèle")
    rows = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_one, p, label, skill if condition == "B" else None, run_id) for p in pays_list]
        for f in as_completed(futures):
            row = f.result()
            rows.append(row)
            flag = " 🚩 " + ((row["_answer"] or {}).get("flag_reason") or "")[:60] if (row["_answer"] or {}).get("flagged_for_human") else ""
            print(f"   {row['pays']} → {row['result']:<8} {row['steps']:>3} étapes {row['time_s']:>6}s{flag}"
                  + (f"  ({row['blockers'][:80]})" if row["blockers"] else ""))
    rows.sort(key=lambda r: r["pays"])
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
