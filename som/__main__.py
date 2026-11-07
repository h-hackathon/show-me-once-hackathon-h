"""Show me once — ligne de commande.

  python -m som doctor                  vérifie que tout est prêt (clés, Sheet, Databricks, outils)
  python -m som notebooks               (re)génère databricks/01_setup_crm.py à importer dans Databricks
  python -m som truth -p FR,IT          affiche ce que l'onglet doit contenir (vérité terrain)
  python -m som sheet-reset             remet le Sheet à l'état « semaine précédente »
  python -m som capture demo.mov        vidéo commentée → phrases horodatées + captures
  python -m som skill --demo runs/demo/demo/demo.json      → skills/crm-dashboard.md
  python -m som skill --transcript data/demo/demo_narration.txt   (sans vidéo, pour tester)
  python -m som run -c B -p FR          l'agent met à jour 1 pays avec la Skill, puis vérification
  python -m som bench                   benchmark A/B sur les 10 pays
  python -m som check                   compare le Sheet à la vérité terrain
"""
import argparse
import csv
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

from .config import ROOT, SKILLS, env
from .crm_data import PAYS

DEFAULT_SKILL = SKILLS / "crm-dashboard.md"


def _pays(arg: str | None) -> list[str]:
    if not arg or arg == "all":
        return list(PAYS)
    wanted = [p.strip().upper() for p in arg.split(",")]
    if bad := [p for p in wanted if p not in PAYS]:
        raise SystemExit(f"❌ Pays inconnus : {', '.join(bad)} (choix : {', '.join(PAYS)})")
    return wanted


# ---------- doctor ----------
def _ok(label, good, hint=""):
    print(f"{'✅' if good else '❌'} {label}" + ("" if good or not hint else f"\n     → {hint}"))
    return good


def _reachable(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 show-me-once"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 400
    except Exception:
        return False


def cmd_doctor(a):
    good = True
    print("— Paquets Python")
    for mod, pip in [("hai_agents", "hai-agents[cli]"), ("pydantic", "pydantic"), ("httpx", "httpx"),
                     ("dotenv", "python-dotenv"), ("imageio_ffmpeg", "imageio-ffmpeg")]:
        good &= _ok(mod, importlib.util.find_spec(mod) is not None, f"pip install -r requirements.txt  ({pip})")

    print("— Fichier .env")
    good &= _ok(".env présent", (ROOT / ".env").exists(), "cp .env.example .env puis remplir")
    for key, hint in [("HAI_API_KEY", "platform.hcompany.ai/settings/api-keys"),
                      ("GLADIA_API_KEY", "app.gladia.io > API Keys"),
                      ("DATABRICKS_URL", "l'adresse de ton workspace Free Edition (https://….cloud.databricks.com)"),
                      ("SHEET_URL", "lien du Google Sheet (partagé « tous les utilisateurs disposant du lien » en éditeur)"),
                      ("SHEET_WEBAPP_URL", "Apps Script > Déployer > Application Web → URL /exec"),
                      ("SHEET_TOKEN", "même valeur que TOKEN dans sheets/dashboard.gs")]:
        good &= _ok(key, bool(env(key)), hint)

    print("— Connexion de l'agent à Databricks")
    if env("HAI_BROWSER_PROFILE_ID"):
        print(f"✅ profil navigateur H : {env('HAI_BROWSER_PROFILE_ID')}")
    elif env("DATABRICKS_EMAIL") and env("OTP_IMAP_HOST"):
        good &= _ok("e-mail + lecture du code OTP par IMAP", importlib.util.find_spec("hai_agents_tools") is not None,
                    "le module hai_agents_tools manque : pip install \"hai-agents[all]\"")
    else:
        print("⚠️  ni profil navigateur (HAI_BROWSER_PROFILE_ID) ni OTP par IMAP : l'agent risque de bloquer sur le code e-mail")

    print("— Google Sheet")
    if env("SHEET_WEBAPP_URL") and env("SHEET_TOKEN"):
        try:
            from .sheet import read
            tabs = read()
            missing = [p for p in PAYS if not tabs.get(p)]
            good &= _ok(f"API du Sheet : {len(PAYS) - len(missing)}/10 onglets pays", not missing,
                        f"onglets manquants : {', '.join(missing)} → lance la fonction setup dans Apps Script")
            filled = sum(1 for p in PAYS if tabs.get(p) and len(tabs[p]) > 1)
            print(f"ℹ️  {filled}/10 onglets contiennent des données" + ("" if filled else " → python -m som sheet-reset"))
        except (SystemExit, Exception) as e:
            good &= _ok("API du Sheet", False, str(e)[:200])
    if env("DATABRICKS_URL"):
        good &= _ok(f"Databricks joignable ({env('DATABRICKS_URL')})", _reachable(env("DATABRICKS_URL")))

    print("— Outils")
    try:
        from .capture import ffmpeg
        good &= _ok(f"ffmpeg ({Path(ffmpeg()).name})", True)
    except SystemExit as e:
        good &= _ok("ffmpeg", False, str(e))
    setup = ROOT / "databricks" / "01_setup_crm.py"
    good &= _ok("notebook de setup Databricks", setup.exists(), "python -m som notebooks")

    if a.online:
        print("— APIs (appels réels, quelques centimes)")
        try:
            from .skill_builder import holo
            model = env("HOLO_MODEL", "holo3-1-35b-a3b")
            rep, s = holo([{"type": "text", "text": "Réponds juste OK."}], model)
            good &= _ok(f"Holo {model} répond en {s:.1f}s ({rep.strip()[:20]})", True)
        except Exception as e:
            good &= _ok("Holo (Models API)", False, str(e)[:200])
        try:
            import httpx
            r = httpx.get("https://api.gladia.io/v2/pre-recorded", headers={"x-gladia-key": env("GLADIA_API_KEY") or ""}, timeout=15)
            good &= _ok("clé Gladia acceptée", r.status_code < 400, f"HTTP {r.status_code}")
        except Exception as e:
            good &= _ok("Gladia", False, str(e)[:200])

    print("\n" + ("🎉 Tout est prêt." if good else "Corrige les ❌ ci-dessus, puis relance : python -m som doctor"))
    return 0 if good else 1


# ---------- commandes ----------
def cmd_notebooks(a):
    from .notebooks import build
    print(f"📓 {build()}\n→ Databricks : Workspace > (ton dossier) > ⋮ > Import > ce fichier, puis « Run all »")


def cmd_truth(a):
    from .crm_data import COLONNES_RAPPORT, expected, generate, previous
    t = generate()
    for p in _pays(a.pays):
        rows, flag, why = expected(t, p)
        print(f"\n=== {p} · avant : {len(previous(t, p))} ligne(s) · après : {len(rows)} ligne(s)"
              + (f" · 🚩 alerte attendue : {why}" if flag else ""))
        print("\t".join(COLONNES_RAPPORT))
        for r in rows:
            print("\t".join(str(r[c]) for c in COLONNES_RAPPORT))


def cmd_sheet_reset(a):
    from .sheet import reset
    print(f"🧹 {reset()} onglet(s) remis à la semaine précédente")


def cmd_capture(a):
    from .capture import capture
    capture(Path(a.media), a.name)


def cmd_skill(a):
    from .skill_builder import from_sources
    from_sources(Path(a.demo) if a.demo else None, Path(a.transcript) if a.transcript else None,
                 a.name, a.model, a.max_frames)


def _skill_text(path: str | None):
    from .skill_builder import load
    p = Path(path) if path else DEFAULT_SKILL
    if not p.exists():
        raise SystemExit(f"❌ Skill introuvable : {p}\n   → python -m som skill --transcript data/demo/demo_narration.txt")
    return load(p)


def _check_and_log(tables, pays_list, answers, out_dir, run_id, condition):
    from .checker import check, print_table
    from .sheet import read
    rows = check(tables, pays_list, read(), answers)
    print_table(rows)
    path = out_dir / "scores.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["run_id", "condition", *rows[0].keys()])
        if new:
            w.writeheader()
        w.writerows({"run_id": run_id, "condition": condition, **r} for r in rows)
    return rows


def _execute(conditions, a):
    from .crm_data import generate
    from .runner import new_run_dir, run_batch
    from .sheet import reset
    pays_list = _pays(a.pays)
    skill = _skill_text(a.skill) if "B" in conditions else None
    tables = generate()
    out = new_run_dir()
    totals = {}
    for run_id in range(1, a.runs + 1):
        for cond in conditions:
            if not a.no_reset:
                print(f"🧹 Sheet remis à la semaine précédente ({reset(tables)} onglets)")
            rows = run_batch(pays_list, cond, skill, run_id, a.concurrency, out)
            answers = {r["pays"]: r["_answer"] for r in rows if r["_answer"]}
            (out / f"answers_run{run_id}_{cond}.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
            scored = _check_and_log(tables, pays_list, answers, out, run_id, cond)
            totals.setdefault(cond, []).append((sum(r["ok"] for r in scored), sum(r["steps"] for r in rows),
                                                sum(r["fausse_affirmation"] for r in scored)))
    print(f"\n📁 Résultats : {out}")
    n = len(pays_list)
    for cond, vals in totals.items():
        k = len(vals)
        print(f"   {cond} : {sum(v[0] for v in vals) / k:.1f}/{n} pays corrects · "
              f"{sum(v[1] for v in vals) / k / n:.0f} étapes/pays · {sum(v[2] for v in vals)} affirmation(s) fausse(s) · {k} run(s)")


def cmd_run(a):
    _execute(["A", "B"] if a.condition == "AB" else [a.condition], a)


def cmd_bench(a):
    _execute(["A", "B"], a)


def cmd_check(a):
    from .checker import check, print_table
    from .crm_data import generate
    from .sheet import read
    answers = json.loads(Path(a.answers).read_text(encoding="utf-8")) if a.answers else {}
    print_table(check(generate(), _pays(a.pays), read(), answers))


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m som", description="Show me once — Databricks → Google Sheet")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="vérifie l'installation")
    d.add_argument("--online", action="store_true", help="teste aussi Holo et Gladia (appels réels)")
    d.set_defaults(fn=cmd_doctor)

    sub.add_parser("notebooks", help="génère le notebook de setup Databricks").set_defaults(fn=cmd_notebooks)

    t = sub.add_parser("truth", help="vérité terrain par pays")
    t.add_argument("-p", "--pays", default="all")
    t.set_defaults(fn=cmd_truth)

    sub.add_parser("sheet-reset", help="Sheet → semaine précédente").set_defaults(fn=cmd_sheet_reset)

    c = sub.add_parser("capture", help="vidéo de démo → phrases + captures")
    c.add_argument("media", help="vidéo .mov/.mp4 (ou audio .wav)")
    c.add_argument("--name", help="nom du dossier de sortie (défaut : nom du fichier)")
    c.set_defaults(fn=cmd_capture)

    s = sub.add_parser("skill", help="démo → Skill (Holo)")
    s.add_argument("--demo", help="demo.json produit par `capture`")
    s.add_argument("--transcript", help="ou un simple texte de narration")
    s.add_argument("--name", default="crm-dashboard")
    s.add_argument("--model", help="défaut : HOLO_MODEL du .env")
    s.add_argument("--max-frames", type=int, default=8)
    s.set_defaults(fn=cmd_skill)

    for name, fn, helptext in [("run", cmd_run, "l'agent met à jour des pays"), ("bench", cmd_bench, "benchmark A/B")]:
        r = sub.add_parser(name, help=helptext)
        if name == "run":
            r.add_argument("-c", "--condition", choices=["A", "B", "AB"], default="B")
        r.add_argument("-p", "--pays", default="FR" if name == "run" else "all", help="FR,IT ou all")
        r.add_argument("--runs", type=int, default=1 if name == "run" else 2)
        r.add_argument("--concurrency", type=int, default=3)
        r.add_argument("--skill", help=f"défaut : {DEFAULT_SKILL.relative_to(ROOT)}")
        r.add_argument("--no-reset", action="store_true", help="ne pas remettre le Sheet à zéro avant chaque lot")
        r.set_defaults(fn=fn)

    k = sub.add_parser("check", help="Sheet vs vérité terrain")
    k.add_argument("-p", "--pays", default="all")
    k.add_argument("--answers", help="answers_*.json d'un run (pour les alertes de l'agent)")
    k.set_defaults(fn=cmd_check)

    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
