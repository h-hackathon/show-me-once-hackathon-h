"""Mini client de l'API Stripe (bibliothèque standard), réservé au MODE TEST.

Sert à : créer les litiges de la démo (seed), lire leurs vrais statuts (vérificateur, écran € récupérés).
L'agent, lui, ne passe jamais par l'API : il travaille dans le Dashboard Stripe, comme un humain.
"""
import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .config import env

API = "https://api.stripe.com/v1"


def _ssl_context():
    """Python installé depuis python.org sur Mac n'a pas de certificats : on prend ceux de certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL = _ssl_context()


def _key() -> str:
    key = env("STRIPE_SECRET_KEY", required=True)
    if not (key.startswith("sk_test_") or key.startswith("rk_test_")):
        raise SystemExit("❌ STRIPE_SECRET_KEY doit être une clé de TEST (sk_test_…). Jamais de clé live ici.")
    return key


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """{'metadata': {'a': 1}, 'expand': ['x']} → [('metadata[a]', '1'), ('expand[0]', 'x')] (format Stripe)."""
    out = []
    for k, v in data.items():
        key = f"{prefix}[{k}]" if prefix else k
        if isinstance(v, dict):
            out += _flatten(v, key)
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    out += _flatten(item, f"{key}[{i}]")
                else:
                    out.append((f"{key}[{i}]", str(item)))
        elif isinstance(v, bool):
            out.append((key, "true" if v else "false"))
        elif v is not None:
            out.append((key, str(v)))
    return out


def call(method: str, path: str, params: dict | None = None) -> dict:
    base = env("STRIPE_API_BASE") or API  # surchargé uniquement par les tests
    body = urllib.parse.urlencode(_flatten(params or {})).encode()
    url = f"{base}{path}"
    if method == "GET" and params:
        url, body = f"{url}?{body.decode()}", None
    req = urllib.request.Request(url, data=body if method != "GET" else None, method=method, headers={
        "Authorization": "Basic " + base64.b64encode(f"{_key()}:".encode()).decode(),
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=60, context=SSL) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"Stripe {method} {path} → HTTP {e.code} {msg}") from None


def get(path, **params):
    return call("GET", path, params)


def post(path, **params):
    return call("POST", path, params)


def dashboard_url(kind: str, obj_id: str) -> str:
    """Lien Dashboard en mode test (ex. dashboard_url('disputes', 'dp_…'))."""
    return f"https://dashboard.stripe.com/test/{kind}/{obj_id}"
