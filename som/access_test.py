"""Test go / no-go : l'agent H arrive-t-il à ouvrir un vrai outil (Shopify admin, Stripe, Freshdesk) ?

Il se connecte avec les comptes de test du .env et, si un code est envoyé par e-mail, te le demande dans le terminal
(ou le lit tout seul si la boîte IMAP est configurée). Il ne crée, ne modifie et ne supprime RIEN.

  python -m som test-acces shopify
"""
import time

from pydantic import BaseModel

from .auth import login_hint, session_options
from .config import env

CIBLES = {
    "shopify": ("SHOPIFY_ADMIN_URL", "/orders", "la liste des commandes de l'admin Shopify", ("shopify",)),
    "freshdesk": ("FRESHDESK_URL", "/a/tickets", "la liste des tickets Freshdesk", ()),
    "stripe": (None, "https://dashboard.stripe.com/test/disputes", "la liste des litiges du Dashboard Stripe (mode test)", ("stripe",)),
}


class AccessResult(BaseModel):
    page_reached: bool           # la page demandée est affichée, connecté
    had_to_log_in: bool          # l'agent a dû se connecter
    verification_asked: bool     # un code / une double authentification a été demandé
    verification_passed: bool    # … et l'agent l'a passé
    store_or_account_name: str
    what_i_see: str
    blockers: list[str]


TASK = """Ouvre {url} et arrive sur {what}.
{login}Ne crée, ne modifie et ne supprime rien.
Si tu restes bloqué (captcha, code refusé, accès refusé), arrête-toi et décris exactement ce qui est demandé.
Une fois sur la page : donne le nom de la boutique ou du compte, le titre de la page et le nombre d'éléments listés."""


def run(cible: str, avec_profil: bool = True) -> dict:
    from hai_agents import Client
    var, path, what, comptes = CIBLES[cible]
    url = path if var is None else env(var, required=True).rstrip("/") + path
    opts = session_options()
    if not avec_profil:
        opts.pop("overrides", None)
    client = Client()
    print(f"🔎 Test d'accès {cible} → {url}")
    if "tools" in opts and not env("OTP_IMAP_HOST"):
        print("   ✉️  Si l'outil envoie un code par e-mail, l'agent te le demandera ICI : recopie-le et appuie sur Entrée.")
    t0 = time.time()
    result = client.run_session(agent=env("HAI_AGENT", "h/web-surfer-pro"),
                                messages=TASK.format(url=url, what=what, login=login_hint(*comptes)),
                                answer_schema=AccessResult, **opts)
    a = result.answer.model_dump() if isinstance(result.answer, BaseModel) else result.answer
    share = ""
    try:
        share = client.sessions.share_session(result.id).share_url
    except Exception:
        pass
    print(f"   statut : {result.status} · {time.time() - t0:.0f}s · {len(result.events or [])} étapes")
    print(f"   réponse : {a}")
    if share:
        print(f"   replay : {share}")
    ok = bool(a and a.get("page_reached"))
    print("✅ GO : l'agent est dans l'outil." if ok else "❌ NO-GO : regarde le replay pour voir où il bloque.")
    return {"ok": ok, "answer": a, "replay": share}
