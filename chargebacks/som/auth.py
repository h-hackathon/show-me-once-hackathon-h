"""Connexion de l'agent H aux vrais outils (Shopify, Stripe…) : identifiants + code de vérification.

- Les identifiants (comptes de test du hackathon) viennent du .env : SHOPIFY_LOGIN / SHOPIFY_PASSWORD, STRIPE_LOGIN / STRIPE_PASSWORD.
- Le code de vérification envoyé par e-mail passe par l'outil OTP officiel de H (hai_agents_tools) :
    * par défaut, il te le DEMANDE DANS LE TERMINAL (tu le recopies depuis ta boîte mail) ;
    * si OTP_IMAP_HOST / OTP_IMAP_USER / OTP_IMAP_PASSWORD sont remplis, il le lit tout seul dans la boîte (IMAP).
  Dans les deux cas l'outil tourne sur ton ordinateur : ta boîte mail n'est jamais envoyée à H, seul le code l'est.
- Avec HAI_USE_DEFAULT_PROFILE=1, la session enregistre les cookies à la fin : les fois suivantes, plus besoin de code.
"""
from .config import env

COMPTES = {"shopify": ("SHOPIFY_LOGIN", "SHOPIFY_PASSWORD"), "stripe": ("STRIPE_LOGIN", "STRIPE_PASSWORD")}


def vault_hint() -> str:
    return ("Les identifiants de connexion sont dans le coffre sécurisé : sur une page de connexion, "
            "utilise le remplissage sécurisé des identifiants (fill_secret_at) au lieu de les taper.\n")


def login_hint(*cibles: str) -> str:
    if env("HAI_VAULT_ID"):
        return vault_hint()
    lines = []
    for c in cibles:
        u, p = (env(k) for k in COMPTES[c])
        if u and p:
            lines.append(f"- {c.capitalize()} : identifiant {u} / mot de passe {p}")
    if not lines:
        return ""
    return ("Si une page de connexion apparaît, connecte-toi avec ces comptes de test :\n" + "\n".join(lines) +
            ("\nSi un code de vérification ou une double authentification est demandé, appelle l'outil de code à usage "
             "unique (OTP) pour obtenir le code, puis saisis-le.\n" if otp_tools() else "\n"))


def otp_tools() -> list:
    if env("OTP") in ("0", "non", "false"):  # pas de double authentification : pas d'outil de code
        return []
    try:
        from hai_agents_tools import imap_otp_handler, otp_tool
    except ImportError:
        return []
    if env("OTP_IMAP_HOST") and env("OTP_IMAP_USER") and env("OTP_IMAP_PASSWORD"):
        return [otp_tool(imap_otp_handler(host=env("OTP_IMAP_HOST"), username=env("OTP_IMAP_USER"),
                                          password=env("OTP_IMAP_PASSWORD")))]
    return [otp_tool()]  # sans boîte configurée : le code est demandé dans le terminal


def session_options() -> dict:
    """Profil navigateur (par défaut ou nommé) + outil de code de vérification."""
    overrides = {}
    if env("HAI_USE_DEFAULT_PROFILE") in ("1", "true", "oui"):
        overrides["agent.environments[kind=web].use_default_browser_profile"] = True
    elif env("HAI_BROWSER_PROFILE_ID"):
        overrides["agent.environments[kind=web].browser_profile_id"] = env("HAI_BROWSER_PROFILE_ID")
    if env("HAI_VAULT_ID"):
        overrides["agent.environments[kind=web].vault_id"] = env("HAI_VAULT_ID")
    opts = {"overrides": overrides} if overrides else {}
    tools = otp_tools()
    if tools:
        opts["tools"] = tools
    return opts
