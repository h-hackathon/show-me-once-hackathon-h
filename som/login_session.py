"""Connexion une fois pour toutes, sans Docker : via le profil navigateur PAR DÉFAUT de H.

D'après la doc H : une session qui suit le profil par défaut enregistre son état (cookies) quand elle se termine.
Cette commande ouvre une session avec les 3 sites, met l'agent en pause pour que tu te connectes toi-même dans
l'« Agent View » de la session sur platform.hcompany.ai, puis termine la session pour enregistrer les connexions.
Ensuite, mets HAI_USE_DEFAULT_PROFILE=1 dans .env : l'agent réutilisera ces connexions.
"""
import time

from .config import env

SITES = [("Shopify admin", "SHOPIFY_ADMIN_URL", None), ("Stripe", None, "https://dashboard.stripe.com/test/disputes"),
         ("Freshdesk", "FRESHDESK_URL", None)]

TASK = """Ouvre ces pages, chacune dans un nouvel onglet, puis ARRÊTE-TOI et ne fais plus rien :
{pages}
Un humain va se connecter lui-même à ces sites. Ne saisis aucun identifiant, ne clique sur rien d'autre."""


def run() -> None:
    from hai_agents import Client
    pages = []
    for nom, var, url in SITES:
        u = url or (env(var) or "").rstrip("/")
        if u:
            pages.append(f"- {nom} : {u}")
    if not pages:
        raise SystemExit("❌ Renseigne au moins SHOPIFY_ADMIN_URL dans .env")
    client = Client()
    session = client.start_session(agent=env("HAI_AGENT", "h/web-surfer-pro"), messages=TASK.format(pages="\n".join(pages)),
                                   overrides={"agent.environments[kind=web].use_default_browser_profile": True},
                                   idle_timeout_s=1800)
    print(f"🟢 Session lancée : {session.id}")
    print("   L'agent ouvre les pages… (20 s)")
    time.sleep(20)
    try:
        session.pause()
        print("⏸️  Agent en pause.")
    except Exception as e:
        print(f"ℹ️  Pause impossible ({e.__class__.__name__}) : ce n'est pas grave, ne le laisse juste pas cliquer.")
    print(f"""
👉 À toi :
   1. Va sur https://platform.hcompany.ai → Sessions → ouvre la session {session.id}
   2. Ouvre son « Agent View » (le navigateur en direct) et prends la main
   3. Connecte-toi dans chaque onglet : {', '.join(n for n, _, _ in SITES)} (codes de vérification compris)
   4. Reviens ici et appuie sur Entrée — la session se termine et H enregistre les connexions
""")
    input("Appuie sur Entrée quand tu es connecté partout… ")
    for stop in ("force_answer", "cancel"):
        try:
            getattr(session, stop)()
            break
        except Exception:
            continue
    time.sleep(5)
    try:
        print(f"✅ Session terminée (statut : {session.status()}).")
    except Exception:
        print("✅ Session terminée.")
    print("   Mets HAI_USE_DEFAULT_PROFILE=1 dans .env, puis teste : python -m som test-acces shopify")
