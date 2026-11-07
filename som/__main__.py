"""Show me once — ligne de commande.

  python -m som doctor                 vérifie que tout est prêt (clés, Odoo, tunnels, outils)
  python -m som factures-png           convertit les factures en PNG (servies à l'agent par tunnel-files)
  python -m som capture demo.mov       vidéo commentée → phrases horodatées + captures
  python -m som skill --demo runs/demo/demo/demo.json      → skills/odoo-factures.md
  python -m som skill --transcript data/demo/demo_narration.txt   (sans vidéo, pour tester)
  python -m som run -c B -i INV-001    l'agent saisit 1 facture avec la Skill, puis vérification
  python -m som bench                  benchmark A/B sur les 10 factures
  python -m som check                  compare l'état réel d'Odoo à la vérité terrain
  python -m som reset                  supprime les brouillons de factures fournisseurs
"""
import argparse
import csv
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

from .config import FACTURES, ROOT, SKILLS, env

DEFAULT_SKILL = SKILLS / "odoo-factures.md"


# ---------- doctor ----------
def _ok(label, good, hint=""):
    print(f"{'✅' if good else '❌'} {label}" + ("" if good or not hint else f"\n     → {hint}"))
    return good


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "show-me-once"}), timeout=10) as r:
            return r.status < 400
    except Exception:
        return False


def cmd_doctor(a):
    good = True
    print("— Paquets Python")
    for mod, pip in [("hai_agents", "hai-agents[cli]"), ("pydantic", "pydantic"), ("httpx", "httpx"),
                     ("dotenv", "python-dotenv"), ("imageio_ffmpeg", "imageio-ffmpeg"), ("fitz", "pymupdf")]:
        good &= _ok(mod, importlib.util.find_spec(mod) is not None, f"pip install -r requirements.txt  ({pip})")

    print("— Fichier .env")
    good &= _ok(".env présent", (ROOT / ".env").exists(), "cp .env.example .env puis remplir")
    for key, hint in [("HAI_API_KEY", "platform.hcompany.ai/settings/api-keys"), ("GLADIA_API_KEY", "app.gladia.io > API Keys"),
                      ("ODOO_LOGIN", "cd odoo && ./setup_odoo.sh"), ("ODOO_PASSWORD", "cd odoo && ./setup_odoo.sh"),
                      ("ODOO_URL", "cd odoo && docker compose up -d tunnel && docker compose logs tunnel | grep trycloudflare")]:
        good &= _ok(key, bool(env(key)), hint)

    print("— Données")
    n = len(list(FACTURES.glob("INV-*.pdf")))
    good &= _ok(f"{n}/10 factures PDF + vérité terrain", n == 10 and (FACTURES / "verite_terrain.csv").exists())
    try:
        from .capture import ffmpeg
        good &= _ok(f"ffmpeg ({Path(ffmpeg()).name})", True)
    except SystemExit as e:
        good &= _ok("ffmpeg", False, str(e))

    print("— Odoo")
    try:
        from .odoo import Odoo
        o = Odoo()
        bills = o.vendor_bills()
        good &= _ok(f"connexion locale {o.url} (base {o.db}) · {len(bills)} facture(s) fournisseur", True)
    except (SystemExit, Exception) as e:
        good &= _ok("connexion locale Odoo", False, f"{e} — Docker lancé ? cd odoo && docker compose up -d db odoo")
    if env("ODOO_URL"):
        good &= _ok(f"adresse publique {env('ODOO_URL')}", _reachable(env("ODOO_URL").rstrip("/") + "/web/login"),
                    "le tunnel a changé d'adresse ? docker compose logs tunnel | grep trycloudflare")
    base = env("INVOICE_BASE_URL")
    if base:
        _ok(f"factures publiques {base}", _reachable(base.rstrip("/") + "/INV-001.png"),
            "python -m som factures-png, puis docker compose up -d files tunnel-files")
    else:
        print("ℹ️  INVOICE_BASE_URL vide → l'agent reçoit le texte de la facture dans sa consigne")

    if a.online:
        print("— APIs (appels réels, quelques centimes)")
        try:
            from .skill_builder import holo
            rep, s = holo([{"type": "text", "text": "Réponds juste OK."}], env("HOLO_MODEL", "holo3-1-35b-a3b"))
            good &= _ok(f"Holo {env('HOLO_MODEL', 'holo3-1-35b-a3b')} répond en {s:.1f}s ({rep.strip()[:20]})", True)
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


# ---------- autres commandes ----------
def cmd_png(a):
    from .invoices import load_truth, to_png
    for inv_id in load_truth():
        print(f"🖼️  {to_png(inv_id)}")
    print("→ pour les rendre publiques : cd odoo && docker compose up -d files tunnel-files && "
          "docker compose logs tunnel-files | grep trycloudflare   (à copier dans INVOICE_BASE_URL)")


def cmd_capture(a):
    from .capture import capture
    capture(Path(a.media), a.name)


def cmd_skill(a):
    from .skill_builder import from_sources
    from_sources(Path(a.demo) if a.demo else None, Path(a.transcript) if a.transcript else None,
                 a.document, a.name, a.model, a.max_frames)


def _check_and_log(invoices, answers, out_dir, run_id, condition):
    from .checker import check, print_table
    from .odoo import Odoo
    rows = check(invoices, Odoo().vendor_bills(), answers)
    print_table(rows)
    path = out_dir / "scores.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["run_id", "condition", *rows[0].keys()])
        if new:
            w.writeheader()
        w.writerows({"run_id": run_id, "condition": condition, **r} for r in rows)
    return rows


def _skill_text(path: str | None):
    from .skill_builder import load
    p = Path(path) if path else DEFAULT_SKILL
    if not p.exists():
        raise SystemExit(f"❌ Skill introuvable : {p}\n   → python -m som skill --transcript data/demo/demo_narration.txt")
    return load(p)


def _execute(conditions, a):
    from .invoices import select
    from .odoo import Odoo
    from .runner import new_run_dir, run_batch
    invoices = select(a.invoices)
    skill = _skill_text(a.skill) if "B" in conditions else None
    out = new_run_dir()
    totals = {}
    for run_id in range(1, a.runs + 1):
        for cond in conditions:
            if not a.no_reset:
                print(f"🧹 {Odoo().reset_drafts()} brouillon(s) supprimé(s)")
            rows = run_batch(invoices, cond, skill, run_id, a.concurrency, out)
            answers = {r["invoice_id"]: r["_answer"] for r in rows if r["_answer"]}
            (out / f"answers_run{run_id}_{cond}.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
            scored = _check_and_log(invoices, answers, out, run_id, cond)
            ok = sum(r["ok"] for r in scored)
            steps = sum(r["steps"] for r in rows)
            totals.setdefault(cond, []).append((ok, steps))
    print(f"\n📁 Résultats : {out}")
    for cond, vals in totals.items():
        n = len(invoices)
        avg_ok = sum(v[0] for v in vals) / len(vals)
        avg_steps = sum(v[1] for v in vals) / len(vals) / n
        print(f"   {cond} : {avg_ok:.1f}/{n} correctes en moyenne · {avg_steps:.0f} étapes/facture · {len(vals)} run(s)")


def cmd_run(a):
    _execute(["A", "B"] if a.condition == "AB" else [a.condition], a)


def cmd_bench(a):
    a.invoices = a.invoices or "all"
    _execute(["A", "B"], a)


def cmd_check(a):
    from .checker import check, print_table
    from .invoices import select
    from .odoo import Odoo
    answers = json.loads(Path(a.answers).read_text(encoding="utf-8")) if a.answers else {}
    print_table(check(select(a.invoices), Odoo().vendor_bills(), answers))


def cmd_reset(a):
    from .odoo import Odoo
    print(f"🧹 {Odoo().reset_drafts()} brouillon(s) de facture fournisseur supprimé(s)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m som", description="Show me once")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="vérifie l'installation")
    d.add_argument("--online", action="store_true", help="teste aussi Holo et Gladia (appels réels)")
    d.set_defaults(fn=cmd_doctor)

    sub.add_parser("factures-png", help="factures PDF → PNG").set_defaults(fn=cmd_png)

    c = sub.add_parser("capture", help="vidéo de démo → phrases + captures")
    c.add_argument("media", help="vidéo .mov/.mp4 (ou audio .wav)")
    c.add_argument("--name", help="nom du dossier de sortie (défaut : nom du fichier)")
    c.set_defaults(fn=cmd_capture)

    s = sub.add_parser("skill", help="démo → Skill (Holo)")
    s.add_argument("--demo", help="demo.json produit par `capture`")
    s.add_argument("--transcript", help="ou un simple texte de narration")
    s.add_argument("--document", default="INV-001", help="facture traitée pendant la démo")
    s.add_argument("--name", default="odoo-factures")
    s.add_argument("--model", help="défaut : HOLO_MODEL du .env")
    s.add_argument("--max-frames", type=int, default=6)
    s.set_defaults(fn=cmd_skill)

    for name, fn, helptext in [("run", cmd_run, "l'agent saisit des factures"), ("bench", cmd_bench, "benchmark A/B")]:
        r = sub.add_parser(name, help=helptext)
        if name == "run":
            r.add_argument("-c", "--condition", choices=["A", "B", "AB"], default="B")
        r.add_argument("-i", "--invoices", default=None if name == "bench" else "INV-001",
                       help="INV-001,INV-009 ou all")
        r.add_argument("--runs", type=int, default=1 if name == "run" else 2)
        r.add_argument("--concurrency", type=int, default=3)
        r.add_argument("--skill", help=f"défaut : {DEFAULT_SKILL.relative_to(ROOT)}")
        r.add_argument("--no-reset", action="store_true", help="ne pas vider les brouillons avant chaque lot")
        r.set_defaults(fn=fn)

    k = sub.add_parser("check", help="état réel d'Odoo vs vérité terrain")
    k.add_argument("-i", "--invoices", default="all")
    k.add_argument("--answers", help="answers_*.json d'un run (pour les signalements de l'agent)")
    k.set_defaults(fn=cmd_check)

    sub.add_parser("reset", help="supprime les brouillons").set_defaults(fn=cmd_reset)

    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
