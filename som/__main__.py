"""Show me once — litiges Stripe (chargebacks). Ligne de commande.

  python -m som doctor [--online]          vérifie l'installation (clés, Stripe test, outils en ligne)
  python -m som connexion                  te connecter une fois (Shopify, Stripe, Freshdesk) dans le profil H par défaut
  python -m som test-acces shopify         l'agent H ouvre-t-il l'admin Shopify sans blocage ?
  python -m som outils                     (re)génère le site des 3 outils internes (dossier outils/)
  python -m som stripe-seed --batch demo   crée 24 litiges réels dans Stripe (mode test)
  python -m som truth                      affiche la décision attendue pour chaque commande
  python -m som capture demo.mov           vidéo commentée → phrases horodatées + captures
  python -m som skill --transcript data/demo/demo_narration.txt    → skills/litiges.md
  python -m som run -c B --batch demo -o CMD-10247      l'agent traite 1 litige avec la Skill
  python -m som watch --batch demo         écran de démo « € récupérés » en direct (localhost:8787)
  python -m som check --batch demo         lit les statuts réels dans Stripe et note chaque litige
  python -m som bench --batch-a runA --batch-b runB     benchmark A (sans Skill) / B (avec Skill)
"""
import argparse
import csv
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

from .config import ROOT, RUNS, SKILLS, env

DEFAULT_SKILL = SKILLS / "litiges.md"


def _ok(label, good, hint=""):
    print(f"{'✅' if good else '❌'} {label}" + ("" if good or not hint else f"\n     → {hint}"))
    return good


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 show-me-once"}), timeout=15) as r:
            return r.status < 400
    except Exception:
        return False


def cmd_doctor(a):
    good = True
    print("— Paquets Python")
    for mod, pip in [("hai_agents", "hai-agents[all]"), ("pydantic", "pydantic"), ("httpx", "httpx"),
                     ("dotenv", "python-dotenv"), ("imageio_ffmpeg", "imageio-ffmpeg")]:
        good &= _ok(mod, importlib.util.find_spec(mod) is not None, f"pip install -r requirements.txt  ({pip})")

    print("— Fichier .env")
    good &= _ok(".env présent", (ROOT / ".env").exists(), "cp .env.example .env puis remplir")
    for key, hint in [("HAI_API_KEY", "platform.hcompany.ai/settings/api-keys"), ("GLADIA_API_KEY", "app.gladia.io > API Keys"),
                      ("STRIPE_SECRET_KEY", "Dashboard Stripe (mode test) > Développeurs > Clés API > clé secrète sk_test_…"),
                      ("OUTILS_URL", "adresse publique de l'app des outils (déployée sur Railway)")]:
        good &= _ok(key, bool(env(key)), hint)

    print("— Stripe (mode test)")
    if env("STRIPE_SECRET_KEY"):
        try:
            from . import stripe_api as st
            bal = st.get("/balance")
            good &= _ok(f"API Stripe joignable (livemode = {bal.get('livemode')})", bal.get("livemode") is False,
                        "la clé doit être une clé de TEST")
        except (SystemExit, Exception) as e:
            good &= _ok("API Stripe", False, str(e)[:200])
    if env("HAI_BROWSER_PROFILE_ID"):
        print(f"✅ profil navigateur H pour le Dashboard Stripe : {env('HAI_BROWSER_PROFILE_ID')}")
    else:
        print("⚠️  pas de HAI_BROWSER_PROFILE_ID : l'agent devra se connecter à Stripe (code e-mail « nouvel appareil »)")
    lots = sorted(p.stem for p in (RUNS / "stripe").glob("*.json")) if (RUNS / "stripe").exists() else []
    print(f"ℹ️  lots de litiges créés : {', '.join(lots) if lots else 'aucun → python -m som stripe-seed --batch demo'}")

    print("— Outils internes")
    if env("OUTILS_URL"):
        base = env("OUTILS_URL").rstrip("/")
        for page in ("healthz", "admin/login", "parcelia/login", "care/login"):
            good &= _ok(f"{base}/{page}", _reachable(f"{base}/{page}"), "python -m som outils, puis redéployer le dossier app/ sur Railway")

    print("— Outils")
    try:
        from .capture import ffmpeg
        good &= _ok(f"ffmpeg ({Path(ffmpeg()).name})", True)
    except SystemExit as e:
        good &= _ok("ffmpeg", False, str(e))

    if a.online:
        print("— APIs H et Gladia (appels réels, quelques centimes)")
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


def cmd_outils(a):
    from .tools_site import build
    out = build()
    print(f"🧰 {out} généré. Tester en local : python app/server.py → http://localhost:8080 ; déployer : dossier app/ sur Railway")


def cmd_seed(a):
    from .seed import seed
    seed(a.batch, a.limit)


def cmd_sync(a):
    from .seed import sync
    sync(a.batch)


def cmd_truth(a):
    from .scenarios import generate
    for s in generate():
        t = s["attendu"]
        print(f"{s['order_id']}  {s['montant']:>8.2f} €  {s['motif']:<21} → {t['decision']:<9}{' + bloquer' if t['bloquer'] else '':<10}  ({t['regle']})")


def cmd_capture(a):
    from .capture import capture
    capture(Path(a.media), a.name)


def cmd_skill(a):
    from .skill_builder import from_sources
    from_sources(Path(a.demo) if a.demo else None, Path(a.transcript) if a.transcript else None,
                 a.name, a.model, a.max_frames)


def _skill_text(path):
    from .skill_builder import load
    p = Path(path) if path else DEFAULT_SKILL
    if not p.exists():
        raise SystemExit(f"❌ Skill introuvable : {p}\n   → python -m som skill --transcript data/demo/demo_narration.txt")
    return load(p)


def _rows(batch, orders):
    from .seed import load
    rows = load(batch)
    if orders:
        wanted = {o.strip().upper() for o in orders.split(",")}
        rows = [r for r in rows if r["order_id"] in wanted]
        if not rows:
            raise SystemExit(f"❌ Aucune de ces commandes dans le lot {batch}")
    return rows


def _execute(plan, a):
    """plan = [(condition, batch)] — chaque condition sur son propre lot (un litige traité ne se rejoue pas)."""
    from .checker import check, print_table, summary
    from .runner import new_run_dir, run_batch
    skill = _skill_text(a.skill) if any(c == "B" for c, _ in plan) else None
    out = new_run_dir()
    results = {}
    for cond, batch in plan:
        rows = _rows(batch, getattr(a, "orders", None))
        done = run_batch(rows, cond, skill, 1, a.concurrency, out)
        answers = {r["order_id"]: r["_answer"] for r in done if r["_answer"]}
        (out / f"answers_{cond}_{batch}.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
        scored = check(rows, answers)
        print_table(scored)
        with open(out / "scores.csv", "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["condition", "batch", *scored[0].keys()])
            if fh.tell() == 0:
                w.writeheader()
            w.writerows({"condition": cond, "batch": batch, **r} for r in scored)
        results[cond] = (summary(scored), sum(r["steps"] for r in done) / max(1, len(done)))
    print(f"\n📁 Résultats : {out}")
    from .checker import eur
    for cond, (s, steps) in results.items():
        print(f"   {cond} : {s['ok']}/{s['n']} litiges bien traités · {eur(s['recupere'])} récupérés · "
              f"{eur(s['conteste_a_tort'])} contestés à tort · {s['fraudeurs']}/{s['fraudeurs_total']} fraudeurs bloqués · "
              f"{steps:.0f} étapes/litige · {s['faux']} affirmation(s) fausse(s)")


def cmd_run(a):
    if a.condition == "AB":
        raise SystemExit("❌ Un litige traité ne se rejoue pas : utilise `bench --batch-a … --batch-b …` (2 lots).")
    _execute([(a.condition, a.batch)], a)


def cmd_bench(a):
    if a.batch_a == a.batch_b:
        raise SystemExit("❌ Il faut 2 lots différents (un litige traité ne se rejoue pas).")
    _execute([("A", a.batch_a), ("B", a.batch_b)], a)


def cmd_check(a):
    from .checker import check, print_table
    answers = json.loads(Path(a.answers).read_text(encoding="utf-8")) if a.answers else {}
    print_table(check(_rows(a.batch, a.orders), answers))


def cmd_connexion(a):
    from .login_session import run
    run()


def cmd_test_acces(a):
    from .access_test import run
    run(a.cible, not a.sans_profil)


def cmd_watch(a):
    from .watch import serve
    serve(a.batch, a.port, not a.no_browser)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m som", description="Show me once — litiges Stripe")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="vérifie l'installation")
    d.add_argument("--online", action="store_true", help="teste aussi Holo et Gladia (appels réels)")
    d.set_defaults(fn=cmd_doctor)

    sub.add_parser("outils", help="génère le site des 3 outils internes").set_defaults(fn=cmd_outils)

    s = sub.add_parser("stripe-seed", help="crée les litiges dans Stripe (mode test)")
    s.add_argument("--batch", required=True, help="nom du lot (ex. demo, runA, runB)")
    s.add_argument("--limit", type=int, help="ne créer que les N premiers litiges")
    s.set_defaults(fn=cmd_seed)
    s = sub.add_parser("stripe-sync", help="récupère les litiges pas encore apparus")
    s.add_argument("--batch", required=True)
    s.set_defaults(fn=cmd_sync)

    sub.add_parser("truth", help="décision attendue par commande").set_defaults(fn=cmd_truth)

    c = sub.add_parser("capture", help="vidéo de démo → phrases + captures")
    c.add_argument("media", help="vidéo .mov/.mp4 (ou audio .wav)")
    c.add_argument("--name", help="nom du dossier de sortie")
    c.set_defaults(fn=cmd_capture)

    k = sub.add_parser("skill", help="démo → Skill (Holo)")
    k.add_argument("--demo", help="demo.json produit par `capture`")
    k.add_argument("--transcript", help="ou un simple texte de narration")
    k.add_argument("--name", default="litiges")
    k.add_argument("--model", help="défaut : HOLO_MODEL du .env")
    k.add_argument("--max-frames", type=int, default=8)
    k.set_defaults(fn=cmd_skill)

    r = sub.add_parser("run", help="l'agent traite des litiges")
    r.add_argument("-c", "--condition", choices=["A", "B", "AB"], default="B")
    r.add_argument("--batch", required=True)
    r.add_argument("-o", "--orders", help="CMD-10247,CMD-10254 (défaut : tout le lot)")
    r.add_argument("--concurrency", type=int, default=3)
    r.add_argument("--skill", help=f"défaut : {DEFAULT_SKILL.relative_to(ROOT)}")
    r.set_defaults(fn=cmd_run)

    b = sub.add_parser("bench", help="benchmark A/B sur 2 lots")
    b.add_argument("--batch-a", required=True)
    b.add_argument("--batch-b", required=True)
    b.add_argument("--concurrency", type=int, default=3)
    b.add_argument("--skill")
    b.set_defaults(fn=cmd_bench)

    k = sub.add_parser("check", help="statuts réels dans Stripe vs vérité terrain")
    k.add_argument("--batch", required=True)
    k.add_argument("-o", "--orders")
    k.add_argument("--answers", help="answers_*.json d'un run")
    k.set_defaults(fn=cmd_check)

    sub.add_parser("connexion", help="te connecter une fois aux sites dans le profil H par défaut").set_defaults(fn=cmd_connexion)

    t = sub.add_parser("test-acces", help="l'agent H ouvre-t-il l'outil sans blocage ?")
    t.add_argument("cible", choices=["shopify", "freshdesk", "stripe"])
    t.add_argument("--sans-profil", action="store_true", help="sans profil navigateur, pour comparer")
    t.set_defaults(fn=cmd_test_acces)

    w = sub.add_parser("watch", help="écran de démo € récupérés")
    w.add_argument("--batch", required=True)
    w.add_argument("--port", type=int, default=8787)
    w.add_argument("--no-browser", action="store_true")
    w.set_defaults(fn=cmd_watch)

    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
