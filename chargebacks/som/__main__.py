"""Sportiva — outils factices + litiges Stripe de démonstration. Ligne de commande.

  python -m som outils                          (re)génère app/data.json (commandes, colis, tickets, clients)
  python -m som stripe-seed --batch demo        crée les 400 litiges dans Stripe (mode test)
  python -m som stripe-seed --batch plus --offset 60     seulement les litiges n° 61 à 400
  python -m som stripe-seed --batch essai --limit 5      seulement les 5 premiers
  python -m som stripe-sync --batch demo        récupère les litiges que Stripe n'avait pas encore créés
  python -m som truth                           affiche la décision attendue pour chaque litige
  python -m som doctor                          vérifie la clé Stripe et l'adresse des outils
"""
import argparse
import sys
import urllib.request

from .config import ROOT, RUNS, env


def _ok(label, good, hint=""):
    print(f"{'✅' if good else '❌'} {label}" + ("" if good or not hint else f"\n     → {hint}"))
    return good


def cmd_doctor(a):
    good = _ok(".env présent", (ROOT / ".env").exists(), "cp .env.example .env puis remplir")
    good &= _ok("STRIPE_SECRET_KEY", bool(env("STRIPE_SECRET_KEY")), "Dashboard Stripe (mode test) > Développeurs > Clés API")
    if env("STRIPE_SECRET_KEY"):
        try:
            from . import stripe_api as st
            bal = st.get("/balance")
            good &= _ok(f"API Stripe joignable (livemode = {bal.get('livemode')})", bal.get("livemode") is False, "la clé doit être une clé de TEST")
        except (SystemExit, Exception) as e:
            good &= _ok("API Stripe", False, str(e)[:200])
    lots = sorted(p.stem for p in (RUNS / "stripe").glob("*.json")) if (RUNS / "stripe").exists() else []
    print(f"ℹ️  lots de litiges créés : {', '.join(lots) if lots else 'aucun'}")
    if env("OUTILS_URL"):
        from .stripe_api import SSL
        base = env("OUTILS_URL").rstrip("/")
        for page in ("healthz", "admin/login", "parcelia/login", "care/login"):
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{base}/{page}", headers={"User-Agent": "Mozilla/5.0"}), timeout=15, context=SSL) as r:
                    ok = r.status < 400
            except Exception:
                ok = False
            good &= _ok(f"{base}/{page}", ok, "redéploie le dossier app/ sur Railway")
    print("\n" + ("🎉 Tout est prêt." if good else "Corrige les ❌ ci-dessus."))
    return 0 if good else 1


def cmd_outils(a):
    from .tools_site import build
    out = build()
    print(f"🧰 {out} généré. Tester en local : python app/server.py → http://localhost:8080 ; déployer : git push (Railway)")


def cmd_seed(a):
    from .seed import seed
    seed(a.batch, a.limit, a.offset)


def cmd_sync(a):
    from .seed import sync
    sync(a.batch)


def cmd_truth(a):
    from .scenarios import generate
    for s in generate():
        t = s["attendu"]
        print(f"{s['order_id']}  {s['montant']:>8.2f} €  {s['motif']:<21} → {t['decision']:<9}{' + bloquer' if t['bloquer'] else '':<10}  ({t['regle']})")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m som", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="vérifie la configuration").set_defaults(fn=cmd_doctor)
    sub.add_parser("outils", help="génère app/data.json").set_defaults(fn=cmd_outils)
    s = sub.add_parser("stripe-seed", help="crée les litiges dans Stripe (mode test)")
    s.add_argument("--batch", required=True, help="nom du lot (un litige ne se remet pas à zéro : un nom par lot)")
    s.add_argument("--limit", type=int, help="nombre de litiges à créer (défaut : tous)")
    s.add_argument("--offset", type=int, default=0, help="ignorer les N premiers litiges (ex. 60 = déjà créés)")
    s.set_defaults(fn=cmd_seed)
    y = sub.add_parser("stripe-sync", help="complète les litiges manquants d'un lot")
    y.add_argument("--batch", required=True)
    y.set_defaults(fn=cmd_sync)
    sub.add_parser("truth", help="décision attendue pour chaque litige").set_defaults(fn=cmd_truth)
    a = p.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
