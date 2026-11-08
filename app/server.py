"""Outils internes de la marketplace fictive Sportiva — une seule app, zéro dépendance (Python 3.10+).

  /admin      Sportiva Admin   back-office : commandes, clients, remboursements
  /parcelia   Parcelia Pro     portail transporteur : suivi, étiquette, preuve de livraison (POD)
  /care       Sportiva Care    support client : tickets

Données : data.json (généré par `python -m som outils`). Marques et données 100 % fictives.
Lancer en local : python app/server.py   →   http://localhost:8080
Railway : `python main.py` (le port vient de $PORT).
"""
import hashlib
import hmac
import html
import json
import os
import random
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
BY_CLIENT: dict = {}
for _o in DATA["orders"].values():
    BY_CLIENT.setdefault(_o["client_email"], []).append(_o)
N_LITIGES = sum(1 for _o in DATA["orders"].values() if _o["litige"])
SECRET = (os.environ.get("SECRET_KEY") or "sportiva-demo-" + DATA.get("genere_le", "")).encode()
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
TODAY = date(2026, 11, 7)
GEO = {"Lyon": (45.76, 4.84), "Lille": (50.63, 3.06), "Nantes": (47.22, -1.55), "Bordeaux": (44.84, -0.58),
       "Toulouse": (43.60, 1.44), "Marseille": (43.30, 5.37), "Rennes": (48.11, -1.68), "Strasbourg": (48.57, 7.75),
       "Montpellier": (43.61, 3.88), "Paris": (48.86, 2.35), "Lyon-Saint-Exupéry": (45.72, 5.08)}
FRANCE = [(-4.8, 48.4), (-3.0, 48.8), (-1.6, 48.7), (-1.6, 49.65), (0.1, 49.5), (1.6, 50.1), (1.6, 50.9), (2.6, 51.05),
          (4.2, 50.0), (4.9, 49.8), (5.9, 49.5), (8.2, 49.0), (7.6, 47.6), (7.0, 47.4), (6.1, 46.3), (7.0, 45.9),
          (6.7, 45.1), (7.0, 44.2), (7.5, 43.8), (6.2, 43.1), (4.6, 43.4), (3.1, 43.1), (3.2, 42.4), (1.7, 42.5),
          (-0.5, 42.8), (-1.8, 43.4), (-1.2, 44.6), (-1.2, 46.2), (-2.2, 47.1), (-4.2, 47.8)]


def e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def eur(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " €"


def fdate(d: str, heure: bool = True) -> str:
    if not d:
        return "—"
    y, m, j = d[:10].split("-")
    out = f"{int(j)} {MOIS[int(m) - 1]} {y}"
    if heure and len(d) > 10:
        out += f" à {d[11:16]}"
    return out


def initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def hue(seed: str) -> int:
    return int(hashlib.md5(seed.encode()).hexdigest()[:4], 16) % 360


# ============================================================================ icônes (traits fins, 24×24)
_IC = {
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "orders": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.7.8 2.7 2.6 3 5.2"/>',
    "tag": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "bell": '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "truck": '<path d="M2 6h12v10H2zM14 9h4l4 4v3h-8z"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    "box": '<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5 12 12l9-4.5M12 12v9"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "card": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 10h19M6 15h4"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    "note": '<path d="M5 3h10l4 4v14H5z"/><path d="M15 3v4h4M8 12h8M8 16h5"/>',
    "out": '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "check": '<path d="m4 12.5 5 5L20 6.5"/>',
    "msg": '<path d="M4 5h16v11H9l-5 4z"/>',
    "inbox": '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    "file": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "refund": '<path d="M4 8h12a4 4 0 0 1 0 8H8"/><path d="m8 4-4 4 4 4"/>',
    "scale": '<path d="M12 3v18M5 21h14M4 7h16M7 7l-3 7a3 3 0 0 0 6 0zM17 7l-3 7a3 3 0 0 0 6 0z"/>',
    "store": '<path d="M3 9 5 4h14l2 5M3 9h18v11H3zM3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18h2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "ext": '<path d="M14 4h6v6M20 4 11 13M18 14v6H4V6h6"/>',
    "dot": '<circle cx="12" cy="12" r="4"/>',
    "route": '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5"/>',
    "pen": '<path d="m4 20 4-1L20 7l-3-3L5 16z"/>',
    "attach": '<path d="M20 11.5 12 19.5a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L10 17a1.7 1.7 0 0 1-2.4-2.4L15 7.3"/>',
}


def ic(name: str, size: int = 18, cls: str = "ic") -> str:
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_IC[name]}</svg>')


# ============================================================================ authentification (cookie signé)
APPS = {"admin": "Sportiva Admin", "parcelia": "Parcelia Pro", "care": "Sportiva Care"}


def token(app: str) -> str:
    return hmac.new(SECRET, app.encode(), hashlib.sha256).hexdigest()[:32]


def logged(handler, app: str) -> bool:
    for part in (handler.headers.get("Cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == f"s_{app}" and hmac.compare_digest(v, token(app)):
            return True
    return False


# ============================================================================ page
FONTS = {
    "admin": "family=Inter:wght@400;500;550;600;650;700&family=Roboto+Mono:wght@400;600",
    "parcelia": "family=Roboto:wght@400;500;700;900&family=Roboto+Mono:wght@400;700",
    "care": "family=Inter:wght@400;500;600;650;700&family=Roboto+Mono:wght@400;600",
}
BASE_CSS = """
*{box-sizing:border-box}html,body{margin:0}body{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit}button,input,select,textarea{font:inherit;color:inherit}.ic{flex:none;display:inline-block;vertical-align:-3px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px 3px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap;line-height:18px}
.pill i{width:7px;height:7px;border-radius:50%;background:currentColor}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.rise{animation:rise .45s cubic-bezier(.2,.7,.2,1) both}.d1{animation-delay:.04s}.d2{animation-delay:.08s}.d3{animation-delay:.12s}.d4{animation-delay:.16s}.d5{animation-delay:.2s}
"""


def page(title: str, body: str, css: str, app: str, fav: str) -> str:
    favicon = (f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' "
               f"rx='9' fill='{quote(fav)}'/%3E%3C/svg%3E")
    fonts = (f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             f'<link href="https://fonts.googleapis.com/css2?{FONTS[app]}&display=swap" rel="stylesheet">') if app in FONTS else ""
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><link rel="icon" href="{favicon}">{fonts}<style>{BASE_CSS}{css}</style></head><body>{body}</body></html>')


# ============================================================================ connexion
LOGIN = {
    "admin": dict(panel="#1a1a1a", ink="#e3e3e3", accent="#005bd3", btn="#303030", btnt="#fff", brand="Sportiva <b>Admin</b>",
                  tag="Le back-office de la boutique.", sub="Commandes, clients, remboursements : tout au même endroit.", ulabel="Adresse e-mail", fav="#303030",
                  font="Inter,-apple-system,sans-serif", mark="#fff", markt="#1a1a1a", r="10px"),
    "parcelia": dict(panel="#330000", ink="#f5e6c8", accent="#0662bb", btn="#ffc400", btnt="#121212", brand="parcelia <b>PRO</b>",
                     tag="Vos envois, suivis au scan près.", sub="Espace expéditeurs professionnels : suivi, étiquettes, preuves de livraison.",
                     ulabel="Numéro de compte", fav="#ffc400", font="Roboto,Arial,sans-serif", mark="#ffc400", markt="#351c15", r="999px"),
    "care": dict(panel="#1a1a1a", ink="#e6e6e6", accent="#1f73e8", btn="#1f73e8", btnt="#fff", brand="Sportiva <b>Care</b>",
                 tag="Chaque client mérite une vraie réponse.", sub="Le support client de Sportiva.", ulabel="E-mail agent", fav="#1f73e8",
                 font="Inter,-apple-system,sans-serif", mark="#1f73e8", markt="#fff", r="6px"),
}


def login_page(app: str, err: str = "") -> str:
    s = LOGIN[app]
    css = """
body{font-family:FONT;background:#fff;color:#1a1a1a;min-height:100vh;display:grid;grid-template-columns:1.05fr 1fr}
.panel{background:PANEL;color:INK;padding:48px 56px;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden}
.brand{font-size:20px;display:flex;align-items:center;gap:12px;font-weight:600}.brand span.m{width:34px;height:34px;border-radius:9px;background:MARK;color:MARKT;display:grid;place-items:center;font-weight:800}
.brand b{font-weight:800}.tag{font-size:42px;line-height:1.1;font-weight:700;max-width:520px;letter-spacing:-.02em}
.sub{opacity:.75;max-width:440px;margin-top:16px;font-size:16px}.foot{font-size:12.5px;border:1px solid #ffffff33;border-radius:8px;padding:10px 12px;max-width:460px;line-height:1.45}
.form{display:grid;place-items:center;padding:40px}form{width:380px;max-width:100%}h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em}
.muted{color:#616161}label{display:block;font-weight:600;font-size:13px;margin:20px 0 7px}
input{width:100%;padding:11px 12px;border:1px solid #8a8a8a;border-radius:8px;font-size:15px;background:#fff}
input:focus{outline:2px solid ACCENT;outline-offset:1px}
button{width:100%;margin-top:26px;padding:13px;border:0;border-radius:RAD;background:BTN;color:BTNT;font-weight:700;font-size:15px;cursor:pointer}
button:hover{filter:brightness(.95)}.err{color:#8e0b21;margin-top:14px;min-height:20px;font-weight:600}
.note{margin-top:22px;font-size:12px;color:#616161;border-top:1px solid #e3e3e3;padding-top:12px}
@media(max-width:860px){body{grid-template-columns:1fr}.panel{display:none}}"""
    for k, v in (("FONT", s["font"]), ("PANEL", s["panel"]), ("ACCENT", s["accent"]), ("INK", s["ink"]), ("MARKT", s["markt"]), ("MARK", s["mark"]),
                 ("BTNT", s["btnt"]), ("BTN", s["btn"]), ("RAD", s["r"])):
        css = css.replace(k, v)
    body = f"""<section class="panel"><div class="brand"><span class="m">{'S' if app != 'parcelia' else 'P'}</span><span>{s['brand']}</span></div>
<div><div class="tag rise">{s['tag']}</div><div class="sub rise d1">{s['sub']}</div></div>
<div class="foot">Environnement de démonstration indépendant, développé pour un hackathon. Non affilié à un service existant ; marques et données fictives.</div></section>
<section class="form"><form class="rise d2" method="post" action="/{app}/login"><h1>Connexion</h1><div class="muted">Accède à ton espace {APPS[app]} (démo).</div>
<label for="u">{s['ulabel']}</label><input id="u" name="username" autocomplete="username" autofocus>
<label for="p">Mot de passe</label><input id="p" name="password" type="password" autocomplete="current-password">
<button type="submit">Se connecter</button><div class="err">{e(err)}</div>
<div class="note">Démo indépendante · n'utilise jamais ici le mot de passe d'un autre service.</div></form></section>"""
    return page(f"Connexion · {APPS[app]} (démo)", body, css, app, s["fav"])



# ============================================================================ Sportiva Admin
# Palette et conventions d'un back-office e-commerce de référence (cadre sombre, canevas clair, cartes à biseau).
ADMIN_CSS = """
:root{--frame:#1a1a1a;--canvas:#f1f1f1;--card:#fff;--ink:#303030;--mute:#616161;--line:#e3e3e3;--hover:#f7f7f7;--acc:#303030;--focus:#005bd3}
body{font-family:Inter,-apple-system,'Segoe UI',sans-serif;font-size:13px;background:var(--frame);color:var(--ink);letter-spacing:-.003em}
.mono{font-family:'Roboto Mono',ui-monospace,Menlo,monospace}
.side{position:fixed;inset:0 auto 0 0;width:240px;background:var(--frame);color:#e3e3e3;display:flex;flex-direction:column;padding:12px 10px}
.logo{display:flex;align-items:center;justify-content:space-between;padding:4px 6px 12px}.logo b{display:flex;align-items:center;gap:9px;color:#fff;font-size:14px;font-weight:650}
.logo b i{width:28px;height:28px;border-radius:8px;background:#fff;color:#1a1a1a;display:grid;place-items:center;font-style:normal;font-weight:800}
.ssearch{display:flex;align-items:center;gap:8px;background:#303030;border:1px solid #4a4a4a;border-radius:10px;padding:7px 10px;color:#b5b5b5;margin-bottom:14px}
.ssearch input{background:none;border:0;outline:none;color:#fff;flex:1;min-width:0;font-size:13px}.ssearch input::placeholder{color:#b5b5b5}
.ssearch kbd{font:11px Inter;color:#b5b5b5}
.side a{display:flex;align-items:center;gap:10px;padding:7px 9px;border-radius:8px;text-decoration:none;font-weight:550;margin:1px 0;color:#e3e3e3;font-size:13.5px}
.side a .ic{color:#b5b5b5}.side a:hover{background:#262626}.side a.on{background:#303030;color:#fff;box-shadow:inset 0 0 0 1px #3d3d3d}.side a.on .ic{color:#fff}
.side .cnt{margin-left:auto;background:#3d3d3d;color:#fff;font-size:11px;font-weight:600;border-radius:6px;padding:1px 7px}
.side small.sec{display:flex;align-items:center;gap:4px;font-size:12.5px;color:#b5b5b5;padding:16px 9px 5px;font-weight:550}
.store{margin-top:auto;display:flex;align-items:center;gap:10px;padding:8px 9px;color:#fff;font-weight:550}
.store b{width:24px;height:24px;border-radius:6px;background:#2c6ecb;color:#fff;display:grid;place-items:center;font-size:9px}
.store span.dev{background:#3d3d3d;color:#e3e3e3;border-radius:6px;padding:1px 7px;font-size:12px;font-weight:500}
.main{margin:8px 8px 8px 248px;min-height:calc(100vh - 16px);background:var(--canvas);border-radius:12px;overflow:hidden}
.top{height:52px;display:flex;align-items:center;gap:16px;padding:0 24px;background:#fff;border-bottom:1px solid var(--line)}
.ready{display:flex;align-items:center;gap:8px;font-size:13.5px;font-weight:500}.ready i{width:9px;height:9px;border-radius:50%;background:#29845a;box-shadow:0 0 0 3px #cdfee1}
.me{margin-left:auto;display:flex;align-items:center;gap:14px;color:var(--mute)}.av{width:32px;height:32px;border-radius:50%;display:grid;place-items:center;
font-weight:650;font-size:11.5px;color:#fff;flex:none}.me a{color:var(--mute);display:flex}
.wrap{padding:24px 32px 64px;max-width:1240px;margin:0 auto}.crumb{color:var(--mute);text-decoration:none;display:inline-flex;align-items:center;gap:6px;font-weight:550}
.crumb:hover{color:var(--ink)}.title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0 18px}
.title h1{font-size:20px;font-weight:700;margin:0;letter-spacing:-.01em}.title .meta{color:var(--mute)}
.title .act{margin-left:auto;display:flex;gap:8px}
.btn{border:0;background:#fff;padding:6px 12px;border-radius:8px;font-weight:600;font-size:12.5px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;text-decoration:none;color:var(--ink);
box-shadow:0 1px 0 0 #e3e3e3 inset,1px 0 0 0 #e3e3e3 inset,-1px 0 0 0 #e3e3e3 inset,0 -1px 0 0 #b5b5b5 inset}.btn:hover{background:#fafafa}
.btn.dark{background:linear-gradient(180deg,#303030 63.53%,#1a1a1a);color:#fff;box-shadow:0 -1px 0 1px rgba(0,0,0,.8) inset,0 0 0 1px #303030 inset,0 .5px 0 1.5px rgba(255,255,255,.25) inset}
.card{background:var(--card);border-radius:12px;box-shadow:0 1px 0 0 rgba(26,26,26,.07),0 1px 0 0 rgba(204,204,204,.5) inset,0 -1px 0 0 rgba(0,0,0,.17) inset,-1px 0 0 0 rgba(0,0,0,.13) inset,1px 0 0 0 rgba(0,0,0,.13) inset;overflow:hidden}
.card>h2{font-size:13.5px;font-weight:650;margin:0;padding:14px 16px 6px;display:flex;align-items:center;gap:8px}
.card>h2 .ic{color:var(--mute)}.card>h2 .r{margin-left:auto;font-weight:500;font-size:12.5px;color:var(--mute)}.in{padding:10px 16px 16px}
.p-green{background:#cdfee1;color:#0c5132}.p-grey{background:#e3e3e3;color:#303030}.p-amber{background:#ffeb78;color:#4f4700}
.p-red{background:#fedad9;color:#8e0b21}.p-blue{background:#eaf4ff;color:#00527c}.p-acc{background:#ffd6a4;color:#5e4200}
.pill{border-radius:8px;padding:2px 8px 2px 6px;font-weight:550;font-size:12px}.pill i{width:6px;height:6px;border:1.5px solid currentColor;background:none}
.p-green i{background:currentColor}
.tabs{display:flex;gap:4px;padding:8px 8px;border-bottom:1px solid var(--line)}.tabs a{padding:5px 11px;text-decoration:none;color:var(--mute);font-weight:550;border-radius:8px;display:flex;gap:7px;align-items:center}
.tabs a span{font-size:11.5px;color:var(--mute)}.tabs a:hover{background:var(--hover)}.tabs a.on{background:#e3e3e3;color:var(--ink)}
.tools{display:flex;gap:8px;padding:8px}.tools .f{flex:1;position:relative}.tools .f .ic{position:absolute;left:10px;top:8px;color:var(--mute)}
.tools input{width:100%;padding:6px 10px 6px 34px;border:1px solid #8a8a8a;border-radius:8px;background:#fdfdfd}.tools input:focus{outline:2px solid var(--focus);outline-offset:1px}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:12px;color:var(--mute);font-weight:550;padding:7px 12px;background:#f7f7f7;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid #ebebeb;vertical-align:middle}tr.r:hover td{background:var(--hover)}
.oid{font-weight:650;text-decoration:none}.oid:hover{text-decoration:underline}.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.who{display:flex;align-items:center;gap:9px}.flag{color:#8e0b21;display:inline-flex;margin-left:6px;vertical-align:-2px}.tfoot{padding:10px 12px;color:var(--mute);font-size:12.5px;background:#f7f7f7}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px;align-items:start}.stack{display:grid;gap:16px}
.item{display:grid;grid-template-columns:44px 1fr auto auto;gap:14px;align-items:center;padding:10px 16px;border-top:1px solid #ebebeb}
.thumb{width:44px;height:44px;border-radius:8px;display:grid;place-items:center;color:#fff;font-weight:700;font-size:16px;border:1px solid #e3e3e3}
.sum{display:grid;grid-template-columns:1fr auto;gap:8px 20px;padding:6px 16px 14px;margin:0 16px 14px;border:1px solid var(--line);border-radius:10px;padding-top:12px}
.sum .tot{font-weight:650;border-top:1px solid var(--line);padding-top:9px}
.receipt{margin:0 16px 16px;border:1px solid #e3e3e3;background:#f7f7f7;border-radius:10px;padding:12px 14px;display:grid;gap:5px}
.receipt b{display:flex;gap:8px;align-items:center}code.ref{font-family:'Roboto Mono',ui-monospace,monospace;background:#303030;color:#fff;padding:2px 8px;border-radius:6px;font-size:12px}
.ship{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:6px 16px 12px}.kv small{display:block;font-size:12px;color:var(--mute);font-weight:550;margin-bottom:2px}
.track{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:0 16px 14px}.track span{font-size:11.5px;color:var(--mute);font-weight:550}
.track span::before{content:"";display:block;height:4px;border-radius:9px;background:#e3e3e3;margin-bottom:6px}.track span.ok{color:var(--ink)}
.track span.ok::before{background:#29845a}.track span.ko{color:#8e0b21}.track span.ko::before{background:#e51c00}
.tl{padding:4px 16px 14px}.ev{display:grid;grid-template-columns:28px 1fr;gap:10px;padding:8px 0;position:relative}
.ev::before{content:"";position:absolute;left:13px;top:34px;bottom:-6px;width:2px;background:#e3e3e3}.ev:last-child::before{display:none}
.ev .b{width:28px;height:28px;border-radius:8px;background:#f1f1f1;display:grid;place-items:center;color:var(--mute)}
.ev.alert .b{background:#fedad9;color:#8e0b21}.ev .t{color:var(--mute);font-size:12px;margin-top:2px}
.comment{display:flex;gap:10px;align-items:center;margin:4px 16px 10px;border:1px solid var(--line);border-radius:10px;padding:8px 10px;color:var(--mute);background:#fff}
.banner{display:flex;gap:12px;align-items:flex-start;background:#fff;border-radius:12px;margin-bottom:16px;overflow:hidden;box-shadow:0 0 0 1px #e3e3e3}
.banner .ic{color:#fff}.banner .bh{background:#e51c00;color:#fff;padding:12px;align-self:stretch;display:grid;place-items:center}
.banner div.t{padding:10px 0}.banner span{color:var(--mute)}
.cust{display:flex;gap:12px;align-items:center;padding:6px 16px 6px}.cust a{font-weight:650;color:#005bd3;text-decoration:none}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#e3e3e3;margin:10px 16px;border-radius:8px;overflow:hidden}
.stats div{background:#fafafa;padding:8px 10px}.stats b{display:block;font-size:13.5px}.stats small{color:var(--mute);font-size:11.5px}
.tag{display:inline-flex;align-items:center;gap:5px;background:#e3e3e3;border-radius:8px;padding:2px 8px;font-size:12px;margin:3px 6px 3px 0;font-weight:550}
textarea.note{width:100%;min-height:72px;border:1px solid #8a8a8a;border-radius:8px;padding:8px 10px;resize:vertical}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.kpi{padding:14px 16px;position:relative}
.kpi small{color:var(--mute);font-weight:550;font-size:12.5px;text-decoration:underline dotted #b5b5b5;text-underline-offset:3px}.kpi .v{font-size:22px;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.kpi svg.sp{position:absolute;right:14px;bottom:14px}.kpi.hot .v{color:#8e0b21}
.cols{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;align-items:start}
.ask{max-width:780px;margin:6px auto 26px;background:#fff;border-radius:18px;padding:14px 18px 10px;box-shadow:0 0 0 1px #e3e3e3,0 6px 18px -10px rgba(0,0,0,.25)}
.ask .q{color:#8a8a8a;font-size:15px;padding:4px 2px 22px}.ask .bar{display:flex;align-items:center;gap:14px;color:var(--ink);font-weight:550}
.ask .bar .sp{margin-left:auto}.hello{text-align:center;font-size:30px;font-weight:650;letter-spacing:-.02em;margin:18px 0 18px;line-height:1.15}
"""

PALETTE = ["#303030", "#2c6ecb", "#29845a", "#8051ff", "#c4290c", "#0a7ea4", "#b28500", "#e0005a"]


def avatar(name: str, size: int = 32) -> str:
    return f'<span class="av" style="width:{size}px;height:{size}px;background:hsl({hue(name)} 45% 46%)">{e(initials(name))}</span>'


def pay_pill(p: str) -> str:
    return f'<span class="pill {"p-grey" if p == "Payé" else "p-amber" if p == "Remboursé" else "p-acc"}"><i></i>{e(p)}</span>'


def ful_pill(t: str) -> str:
    cls = {"Livrée": "p-green", "Expédiée": "p-blue", "À expédier": "p-amber", "Anomalie transport": "p-red"}.get(t, "p-grey")
    return f'<span class="pill {cls}"><i></i>{e(t)}</span>'


def admin_shell(active: str, inner: str, q: str = "") -> str:
    n_lit = N_LITIGES
    nav = [("home", "/admin", "home", "Accueil"), ("orders", "/admin/orders", "orders", "Commandes"),
           ("products", "/admin/products", "tag", "Produits"), ("customers", "/admin/customers", "users", "Clients"),
           ("analytics", "/admin/analytics", "chart", "Analyses de données")]
    links = "".join(f'<a class="{"on" if k == active else ""}" href="{h}">{ic(i)} {lbl}'
                    f'{f"<span class=cnt>{n_lit}</span>" if k == "orders" else ""}</a>' for k, h, i, lbl in nav)
    body = f"""<aside class="side"><div class="logo"><b><i>S</i>Sportiva Admin</b></div>
<form class="ssearch" action="/admin/orders">{ic('search', 16)}<input name="q" value="{e(q)}" placeholder="Rechercher"><kbd>⌘K</kbd></form>{links}
<small class="sec">Canaux de vente ›</small><a href="#">{ic('store')} Boutique en ligne</a><a href="#">{ic('phone')} Application mobile</a>
<a href="#" style="margin-top:auto">{ic('settings')} Paramètres</a>
<div class="store" style="margin-top:0"><b>SPO</b>Sportiva <span class="dev">démo</span><span style="margin-left:auto;color:#b5b5b5">{ic('bell', 16)}</span></div></aside>
<div class="main"><header class="top"><span class="ready"><i></i>Environnement de démonstration indépendant · données fictives</span>
<div class="me"><span>ops@sportiva.test</span>{avatar('Opérations Sportiva', 28)}<a href="/admin/logout" title="Déconnexion">{ic('out')}</a></div></header>
<div class="wrap">{inner}</div></div>"""
    return page("Sportiva Admin", body, ADMIN_CSS, "admin", "#303030")


def spark(seed: str, w: int = 92, h: int = 30, color: str = "#29845a") -> str:
    r = random.Random(seed)
    pts, v = [], 0.5
    for i in range(14):
        v = min(.95, max(.08, v + (r.random() - .45) * .3))
        pts.append(f"{i * w / 13:.1f},{h - v * h:.1f}")
    return (f'<svg class="sp" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline points="{" ".join(pts)}" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def admin_home() -> str:
    allo = list(DATA["orders"].values())
    orders = [o for o in allo if o["date"] >= (TODAY - timedelta(days=30)).isoformat()]
    ca = sum(o["total"] for o in orders)
    lit = [o for o in allo if o["litige"]]
    kpis = [("Ventes · 30 jours", eur(ca), "a"), ("Commandes · 30 jours", str(len(orders)), "b"), ("Panier moyen", eur(ca / max(len(orders), 1)), "c")]
    k = "".join(f'<div class="card kpi rise d{i + 1}"><small>{a}</small><div class="v">{b}</div>{spark(s)}</div>' for i, (a, b, s) in enumerate(kpis))
    k += (f'<div class="card kpi hot rise d4"><small>Litiges ouverts</small><div class="v">{len(lit)}</div>'
          f'<div style="color:#616161;font-size:12.5px;margin-top:4px">{eur(sum(o["total"] for o in lit))} contestés</div></div>')
    per_day = {}
    for o in allo:
        per_day[o["date"]] = per_day.get(o["date"], 0) + 1
    days = [(TODAY - timedelta(days=i)).isoformat() for i in range(20, -1, -1)]
    mx = max(per_day.get(d, 0) for d in days) or 1
    bars = "".join(f'<rect x="{i * 26 + 4}" y="{150 - per_day.get(d, 0) / mx * 120:.0f}" width="16" height="{per_day.get(d, 0) / mx * 120 + 2:.0f}" rx="4" '
                   f'fill="{"#303030" if i == len(days) - 1 else "#8a8a8a"}" opacity="{1 if i == len(days) - 1 else .82}"><title>{fdate(d, False)} : {per_day.get(d, 0)}</title></rect>'
                   for i, d in enumerate(days))
    chart = f'<svg viewBox="0 0 {len(days) * 26} 160" width="100%" height="190" preserveAspectRatio="none">{bars}</svg>'
    rows = "".join(f'<tr class="r"><td><a class="oid" href="/admin/orders/{o["id"]}">{o["id"]}</a></td>'
                   f'<td><div class="who">{avatar(DATA["clients"][o["client_email"]]["nom"], 26)}{e(DATA["clients"][o["client_email"]]["nom"])}</div></td>'
                   f'<td class="num">{eur(o["total"])}</td><td>{pay_pill(o["paiement"])}</td></tr>' for o in lit[:7])
    wd = JOURS[TODAY.weekday()]
    inner = f"""<div class="hello rise">Bonjour !<br>Voici l'activité de la boutique</div>
<div class="ask rise d1"><div class="q">Que voulez-vous savoir sur vos commandes ? <span style="color:#b5b5b5">({wd} {fdate(TODAY.isoformat(), False)})</span></div>
<div class="bar">{ic('dot', 16)}<span class="sp"></span>{ic('clock', 17)} Récents<span style="color:#e3e3e3">|</span>{ic('plus', 17)}{ic('msg', 17)}</div></div>
<div class="kpis">{k}</div><div class="cols"><div class="card rise d3"><h2>{ic('chart')} Commandes par jour<span class="r">21 derniers jours</span></h2><div class="in">{chart}</div></div>
<div class="card rise d4"><h2>{ic('scale')} Contestations de paiement<span class="r"><a href="/admin/orders?vue=litiges">Tout voir</a></span></h2>
<table><tr><th>Commande</th><th>Client</th><th style="text-align:right">Total</th><th>Paiement</th></tr>{rows}</table></div></div>"""
    return admin_shell("home", inner)


def admin_orders(q: str, vue: str, pg: int = 1) -> str:
    ql = q.lower().strip()
    def keep(o, v):
        if v == "litiges":
            return o["litige"]
        if v == "a_traiter":
            return o["traitement"] == "À expédier"
        if v == "remboursees":
            return o["paiement"] != "Payé"
        return True
    allo = [DATA["orders"][i] for i in DATA["order_list"]]
    out = [o for o in allo if keep(o, vue) and (not ql or ql in f'{o["id"]} {o["client_email"]} {DATA["clients"][o["client_email"]]["nom"]} {o.get("suivi") or ""}'.lower())]
    tabs = "".join(f'<a class="{"on" if vue == k else ""}" href="/admin/orders?vue={k}{"&q=" + quote(q) if q else ""}">{lbl}<span>{sum(1 for o in allo if keep(o, k))}</span></a>'
                   for k, lbl in [("toutes", "Toutes"), ("a_traiter", "À expédier"), ("litiges", "Litiges"), ("remboursees", "Remboursées")])
    rows = "".join(f"""<tr class="r"><td><a class="oid" href="/admin/orders/{o['id']}">{o['id']}</a>{f'<span class="flag" title="Litige ouvert">{ic("alert", 15)}</span>' if o['litige'] else ''}</td>
<td style="color:var(--mute)">{fdate(o['date'], False)}</td><td><div class="who">{avatar(DATA['clients'][o['client_email']]['nom'], 28)}{e(DATA['clients'][o['client_email']]['nom'])}</div></td>
<td style="color:var(--mute)">Boutique en ligne</td><td class="num">{eur(o['total'])}</td><td>{pay_pill(o['paiement'])}</td><td>{ful_pill(o['traitement'])}</td>
<td style="color:var(--mute)">{sum(a['qte'] for a in o['articles'])} article{'s' if sum(a['qte'] for a in o['articles']) > 1 else ''}</td></tr>""" for o in out[(pg - 1) * 50:pg * 50])
    empty = '<tr><td colspan="8" style="padding:40px;text-align:center;color:var(--mute)">Aucune commande ne correspond à cette recherche.</td></tr>'
    inner = f"""<div class="title"><h1>Commandes</h1><span class="meta">{len(out)} commande{'s' if len(out) > 1 else ''}</span>
<div class="act"><span class="btn">{ic('file', 16)} Exporter</span><span class="btn dark">{ic('plus', 16)} Créer une commande</span></div></div>
<div class="card rise"><div class="tabs">{tabs}</div><form class="tools" action="/admin/orders"><input type="hidden" name="vue" value="{e(vue)}">
<div class="f">{ic('search', 17)}<input name="q" value="{e(q)}" placeholder="Filtrer par n° de commande, client, e-mail ou n° de suivi"></div><button class="btn">Rechercher</button></form>
<table><tr><th>Commande</th><th>Date</th><th>Client</th><th>Canal</th><th style="text-align:right">Total</th><th>Paiement</th><th>Traitement</th><th>Articles</th></tr>
{rows or empty}</table><div class="tfoot" style="display:flex;align-items:center;gap:10px">Affichage de {min(len(out), (pg - 1) * 50 + 1)}–{min(len(out), pg * 50)} sur {len(out)}
<span style="margin-left:auto"></span>{f'<a class="btn" href="/admin/orders?vue={vue}&q={quote(q)}&page={pg - 1}">← Précédent</a>' if pg > 1 else ''}
{f'<a class="btn" href="/admin/orders?vue={vue}&q={quote(q)}&page={pg + 1}">Suivant →</a>' if pg * 50 < len(out) else ''}</div></div>"""
    return admin_shell("orders", inner, q)


def admin_order(oid: str) -> str | None:
    o = DATA["orders"].get(oid)
    if not o:
        return None
    c = DATA["clients"][o["client_email"]]
    items = "".join(f"""<div class="item"><div class="thumb" style="background:{PALETTE[hue(a['nom']) % len(PALETTE)]}">{e(a['nom'][0])}</div>
<div><div style="font-weight:600">{e(a['nom'])}</div><div class="mono" style="color:var(--mute);font-size:12.5px">SKU {e(a['sku'])}</div></div>
<div class="mono" style="color:var(--mute)">{eur(a['prix'])} × {a['qte']}</div><div class="num" style="font-weight:600;min-width:90px">{eur(a['prix'] * a['qte'])}</div></div>"""
                    for a in o["articles"])
    rb = o.get("remboursement")
    paid = f"<span>Payé par le client</span><span class='num'>{eur(o['total'])}</span>"
    if rb:
        paid += (f"<span style='color:#b3261e'>Remboursé</span><span class='num' style='color:#b3261e'>− {eur(rb['montant'])}</span>"
                 f"<span class='tot'>Montant net</span><span class='num tot'>{eur(o['total'] - rb['montant'])}</span>")
    receipt = (f"""<div class="receipt"><b>{ic('refund', 17)} {'Remboursement intégral' if rb['montant'] >= o['total'] else 'Remboursement partiel'} · {fdate(rb['date'], False)}</b>{f"<div>{e(rb['motif'])}</div>" if rb.get('motif') else ''}
<div>{eur(rb['montant'])} remboursés sur la carte d'origine · réf. <span class="mono">{e(rb['ref'])}</span></div>
<div style="color:var(--mute)">Justificatif de remboursement — référence de preuve à transmettre : <code class="ref">{e(rb['preuve'])}</code></div></div>""" if rb else "")
    ship = ""
    if o.get("suivi"):
        sh = DATA["shipments"].get(o["suivi"], {})
        code = sh.get("code")
        reached = {"en_transit": 2, "perdu": 2, "livre_signe": 4, "boite_aux_lettres": 4}.get(code, 1)
        steps = "".join(f'<span class="{"ko" if code == "perdu" and i == 2 else "ok" if i < reached else ""}">{s}</span>'
                        for i, s in enumerate(["Préparée", "Prise en charge", "En livraison", "Livrée"]))
        ship = f"""<div class="card rise d3"><h2>{ic('truck')} Expédition {ful_pill(o['traitement'])}<span class="r">Parcelia</span></h2>
<div class="ship"><div class="kv"><small>Service</small>{e(sh.get('service', ''))}</div><div class="kv"><small>Numéro de suivi</small><span class="mono" style="font-weight:600">{e(o['suivi'])}</span></div></div>
<div class="track">{steps}</div><div style="padding:0 20px 18px;color:var(--mute);font-size:13px">Suivi scan par scan et preuve de livraison sur le portail Parcelia Pro.</div></div>"""
    def ev_icon(t):
        t = t.lower()
        return ("alert" if ("contestation" in t or "anomalie" in t) else "refund" if "rembours" in t else "truck" if ("expédiée" in t or "parcelia" in t)
                else "card" if "paiement" in t else "orders")
    tl = "".join(f'<div class="ev {"alert" if ev_icon(ev["texte"]) == "alert" else ""}"><div class="b">{ic(ev_icon(ev["texte"]), 15)}</div>'
                 f'<div><div>{e(ev["texte"])}</div><div class="t">{fdate(ev["date"])}</div></div></div>' for ev in reversed(o["chronologie"]))
    banner = (f'<div class="banner rise"><div class="bh">{ic("alert", 20)}</div><div class="t"><b>Contestation de paiement ouverte</b><br>'
              f'<span>La banque du client conteste ce paiement. Le litige se traite dans le Dashboard Stripe.</span></div></div>' if o["litige"] else "")
    spent = sum(x["total"] for x in BY_CLIENT.get(o["client_email"], []))
    tags = "".join(f'<span class="tag">{ic("tag", 13)}{e(t)}</span>' for t in o["tags"]) or '<span style="color:var(--mute)">Aucune étiquette</span>'
    inner = f"""<a class="crumb" href="/admin/orders">← Commandes</a>
<div class="title"><h1 class="mono" style="font-family:'Roboto Mono',monospace;font-weight:600;font-size:26px">{o['id']}</h1>{pay_pill(o['paiement'])}{ful_pill(o['traitement'])}
<span class="meta">{fdate(o['chronologie'][0]['date'])} · Boutique en ligne</span><div class="act"><span class="btn">{ic('refund', 16)} Rembourser</span><span class="btn">Plus ▾</span></div></div>
{banner}<div class="grid"><div class="stack"><div class="card rise d1"><h2>{ic('box')} Articles<span class="r">{len(o['articles'])} ligne(s)</span></h2>{items}</div>
<div class="card rise d2"><h2>{ic('card')} Paiement {pay_pill(o['paiement'])}<span class="r">Carte · Stripe</span></h2><div class="sum"><span>Sous-total</span><span class="num">{eur(o['total'])}</span>
<span>Livraison</span><span class="num">Offerte</span><span style="color:var(--mute)">dont TVA 20 %</span><span class="num" style="color:var(--mute)">{eur(o['tva'])}</span>
<span class="tot">Total</span><span class="num tot">{eur(o['total'])}</span>{paid}</div>{receipt}</div>
{ship}<div class="card rise d4"><h2>{ic('clock')} Chronologie</h2><div class="comment">{avatar('Opérations Sportiva', 26)} Laisser un commentaire…</div><div class="tl">{tl}</div></div></div>
<div class="stack"><div class="card rise d1"><h2>{ic('users')} Client</h2><div class="cust">{avatar(c['nom'], 46)}<div><a href="/admin/customers/{quote(o['client_email'])}">{e(c['nom'])}</a>
<div style="color:var(--mute);font-size:13px">{e(o['client_email'])}</div></div></div>
<div class="stats"><div><b>{c['commandes']}</b><small>commandes</small></div><div><b>{e(c['depuis'])}</b><small>client depuis</small></div><div><b>{eur(spent).replace(',00', '')}</b><small>sur cette période</small></div></div>
<div class="in kv" style="padding-top:6px"><small>Adresse de livraison</small>{e(c['nom'])}<br>{e(o['adresse'])}<br>France</div></div>
<div class="card rise d2"><h2>{ic('tag')} Étiquettes</h2><div class="in">{tags}</div></div>
<div class="card rise d3"><h2>{ic('note')} Notes internes</h2><div class="in"><textarea class="note" placeholder="Ajouter une note pour l'équipe…"></textarea></div></div></div></div>"""
    return admin_shell("orders", inner)


def admin_customers(q: str) -> str:
    ql = q.lower().strip()
    rows = []
    for email, c in sorted(DATA["clients"].items(), key=lambda kv: kv[1]["nom"]):
        if ql and ql not in f"{email} {c['nom']}".lower():
            continue
        n = BY_CLIENT.get(email, [])
        rows.append(f'<tr class="r"><td><div class="who">{avatar(c["nom"], 28)}<a class="oid" style="font-family:inherit" href="/admin/customers/{quote(email)}">{e(c["nom"])}</a></div></td>'
                    f'<td style="color:var(--mute)">{e(email)}</td><td>{e(c["ville"])}</td><td class="num">{c["commandes"]}</td><td class="num">{eur(sum(o["total"] for o in n))}</td></tr>')
    inner = f"""<div class="title"><h1>Clients</h1><span class="meta">{len(rows)} client(s)</span></div><div class="card rise">
<form class="tools" action="/admin/customers"><div class="f">{ic('search', 17)}<input name="q" value="{e(q)}" placeholder="Rechercher un client par nom ou e-mail"></div><button class="btn">Rechercher</button></form>
<table><tr><th>Client</th><th>E-mail</th><th>Ville</th><th style="text-align:right">Commandes</th><th style="text-align:right">Dépensé</th></tr>{''.join(rows[:100])}</table>{f'<div class="tfoot">100 premiers affichés sur {len(rows)} · utilise la recherche</div>' if len(rows) > 100 else ''}</div>"""
    return admin_shell("customers", inner)


def admin_customer(email: str) -> str | None:
    c = DATA["clients"].get(email)
    if not c:
        return None
    orders = BY_CLIENT.get(email, [])
    rows = "".join(f'<tr class="r"><td><a class="oid" href="/admin/orders/{o["id"]}">{o["id"]}</a></td><td>{fdate(o["date"], False)}</td>'
                   f'<td class="num">{eur(o["total"])}</td><td>{pay_pill(o["paiement"])}</td><td>{ful_pill(o["traitement"])}</td></tr>' for o in orders)
    inner = f"""<a class="crumb" href="/admin/customers">← Clients</a><div class="title">{avatar(c['nom'], 44)}<h1>{e(c['nom'])}</h1>
<span class="meta">{e(c['ville'])} · client depuis {e(c['depuis'])}</span></div><div class="grid"><div class="card rise"><h2>{ic('orders')} Commandes</h2>
<table><tr><th>Commande</th><th>Date</th><th style="text-align:right">Total</th><th>Paiement</th><th>Traitement</th></tr>{rows}</table></div>
<div class="card rise d1"><h2>{ic('users')} Coordonnées</h2><div class="in kv"><small>E-mail</small>{e(email)}<br><br><small>Adresse</small>{e(c['cp'])} {e(c['ville'])}, France
<br><br><small>Historique</small>{c['commandes']} commande(s) au total</div></div></div>"""
    return admin_shell("customers", inner)


def admin_products() -> str:
    ps = sorted(DATA.get("produits", []), key=lambda p: -p["ca"])
    rows = "".join(f"""<tr class="r"><td><div class="who"><div class="thumb" style="width:36px;height:36px;border-radius:9px;font-size:15px;background:{PALETTE[hue(p['nom']) % len(PALETTE)]}">{e(p['nom'][0])}</div>
<b style="font-weight:600">{e(p['nom'])}</b></div></td><td class="mono" style="color:var(--mute)">{e(p['sku'])}</td><td class="num">{eur(p['prix'])}</td>
<td>{'<span class="pill p-red"><i></i>Rupture</span>' if p['stock'] == 0 else f'<span class="pill p-amber"><i></i>{p["stock"]} en stock</span>' if p['stock'] < 15 else f'<span class="pill p-green"><i></i>{p["stock"]} en stock</span>'}</td>
<td class="num">{p['vendus']}</td><td class="num">{eur(p['ca'])}</td></tr>""" for p in ps)
    inner = f"""<div class="title"><h1>Produits</h1><span class="meta">{len(ps)} produits actifs</span><div class="act"><span class="btn dark">{ic('plus', 16)} Ajouter un produit</span></div></div>
<div class="card rise"><table><tr><th>Produit</th><th>SKU</th><th style="text-align:right">Prix</th><th>Stock</th><th style="text-align:right">Vendus</th><th style="text-align:right">Chiffre d'affaires</th></tr>{rows}</table></div>"""
    return admin_shell("products", inner)


def admin_analytics() -> str:
    allo = [o for o in DATA["orders"].values() if o["date"] >= (TODAY - timedelta(days=90)).isoformat()]
    weeks = {}
    for o in allo:
        d = date.fromisoformat(o["date"])
        k = (d - timedelta(days=d.weekday())).isoformat()
        weeks[k] = weeks.get(k, 0) + o["total"]
    ks = sorted(weeks)[-13:]
    mx = max(weeks[k] for k in ks) or 1
    bars = "".join(f'<rect x="{i * 46 + 8}" y="{170 - weeks[k] / mx * 150:.0f}" width="30" height="{weeks[k] / mx * 150:.0f}" rx="5" fill="#303030"><title>{eur(weeks[k])}</title></rect>'
                   f'<text x="{i * 46 + 23}" y="190" font-size="10" text-anchor="middle" fill="#6b6f78">{int(k[8:])} {MOIS[int(k[5:7]) - 1]}</text>' for i, k in enumerate(ks))
    lit = [o for o in allo if o["litige"]]
    remb = sum((o["remboursement"] or {}).get("montant", 0) for o in allo)
    villes = {}
    for o in allo:
        v = o["adresse"].split(" ", 1)[1]
        villes[v] = villes.get(v, 0) + o["total"]
    top = sorted(villes.items(), key=lambda kv: -kv[1])[:6]
    vm = top[0][1] if top else 1
    vrows = "".join(f'<div style="display:grid;grid-template-columns:110px 1fr 90px;gap:10px;align-items:center;margin:9px 0"><span>{e(v)}</span>'
                    f'<span style="height:8px;border-radius:9px;background:#29845a;width:{x / vm * 100:.0f}%"></span><span class="num">{eur(x)}</span></div>' for v, x in top)
    k = [("Chiffre d'affaires · 90 jours", eur(sum(o["total"] for o in allo))), ("Commandes", str(len(allo))),
         ("Taux de litige", f"{len(lit) / len(allo) * 100:.1f} %".replace(".", ",")), ("Remboursé", eur(remb))]
    kk = "".join(f'<div class="card kpi rise d{i + 1}"><small>{a}</small><div class="v">{b}</div></div>' for i, (a, b) in enumerate(k))
    inner = f"""<div class="title"><h1>Analyses</h1><span class="meta">90 derniers jours</span></div><div class="kpis">{kk}</div>
<div class="cols"><div class="card rise"><h2>{ic('chart')} Ventes par semaine</h2><div class="in"><svg viewBox="0 0 {len(ks) * 46 + 8} 200" width="100%" height="230">{bars}</svg></div></div>
<div class="card rise d1"><h2>{ic('pin')} Ventes par ville</h2><div class="in">{vrows}</div></div></div>"""
    return admin_shell("analytics", inner)


def admin_stub(active: str, title: str) -> str:
    return admin_shell(active, f'<div class="title"><h1>{title}</h1></div><div class="card"><div class="in" style="color:var(--mute)">Cette section n\'est pas utilisée dans la démo.</div></div>')


# ============================================================================ Parcelia Pro
# Palette et conventions d'un portail transporteur de référence (bordeaux profond, vague rouge, jaune d'action, liens bleus).
PARCELIA_CSS = """
:root{--brown:#351c15;--deep:#330000;--red:#c8102e;--gold:#ffc400;--gold-h:#ffb500;--link:#0662bb;--ink:#121212;--mute:#5f5753;--line:#dfdbd7;--bg:#f2f1ef}
body{font-family:Roboto,Arial,sans-serif;font-size:15px;background:var(--bg);color:var(--ink)}.mono{font-family:'Roboto Mono',ui-monospace,monospace}
.demo{background:var(--brown);color:#f5e6c8;font-size:12.5px;text-align:center;padding:5px 12px}
.bar{background:#fff;height:88px;display:flex;align-items:center;padding:0 48px;gap:40px;position:sticky;top:0;z-index:5;box-shadow:0 1px 0 #e7e3df}
.lg{display:flex;align-items:center;gap:10px;font-weight:900;font-size:24px;color:var(--brown);letter-spacing:-.02em;text-decoration:none}
.lg svg{color:var(--gold)}.lg small{font-size:12px;font-weight:700;color:var(--mute);letter-spacing:.06em;margin-left:2px}
.bar nav{display:flex;gap:30px}.bar nav a{color:var(--ink);text-decoration:none;font-size:17px;font-weight:500;padding:6px 0;border-bottom:3px solid transparent}
.bar nav a.on{border-color:var(--gold)}.bar nav a:hover{color:var(--link)}
.acc{margin-left:auto;display:flex;align-items:center;gap:18px;font-size:14px;color:var(--mute)}.acc b{color:var(--ink)}
.gold{background:var(--gold);color:var(--ink);border:0;border-radius:999px;padding:12px 26px;font-weight:700;font-size:16px;cursor:pointer;text-decoration:none;
display:inline-flex;align-items:center;gap:6px;white-space:nowrap}.gold:hover{background:var(--gold-h)}
.hero{position:relative;background:var(--deep);padding:70px 48px 60px;overflow:hidden}
.hero svg.wave{position:absolute;left:0;right:0;bottom:0;width:100%;height:78%}
.hgrid{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;max-width:1240px;margin:0 auto}
.tcard{background:#fff;border-radius:24px;box-shadow:0 10px 30px -10px rgba(0,0,0,.35);padding:56px 64px 46px;text-align:center}
.tcard h1{font-size:54px;font-weight:400;margin:0 0 26px;display:flex;align-items:center;justify-content:center;gap:16px}
.tcard h1 svg{color:var(--gold)}.tcard form{display:flex;gap:18px;align-items:center;max-width:780px;margin:0 auto}
.tcard input{flex:1;padding:18px 14px;border:1px solid #6e6e6e;border-radius:2px;font-size:17px;font-family:inherit}.tcard input:focus{outline:2px solid var(--link)}
.links{display:flex;gap:44px;justify-content:center;margin-top:20px}.links a{color:var(--link);text-decoration:none;font-size:17px;font-weight:500;display:flex;gap:8px;align-items:center}
.scard{background:#fff;border-radius:24px;padding:26px 28px;margin-bottom:24px;box-shadow:0 10px 30px -14px rgba(0,0,0,.3);min-height:188px;display:flex;flex-direction:column;justify-content:space-between}
.scard .ill{width:56px;height:56px;border-radius:16px;background:#fff4cc;color:var(--brown);display:grid;place-items:center}.scard b{font-size:24px;font-weight:400;line-height:1.25}
.scard .chips{display:flex;gap:6px;flex-wrap:wrap;font-size:13px;color:var(--mute)}
.wrap{max-width:1240px;margin:0 auto;padding:30px 48px 70px}
.box{background:#fff;border-radius:16px;margin-bottom:22px;overflow:hidden;box-shadow:0 2px 12px -6px rgba(0,0,0,.18)}
.box>h2{font-size:20px;margin:0;padding:20px 24px 12px;font-weight:500;display:flex;align-items:center;gap:10px;color:var(--ink)}
.box>h2 .ic{color:var(--brown)}.box>h2 .r{margin-left:auto;font-size:14px;color:var(--mute);font-weight:400}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:13px;color:var(--mute);padding:10px 24px;font-weight:500;border-bottom:2px solid var(--ink)}
td{padding:14px 24px;border-bottom:1px solid #ece8e4}td a.trk{font-weight:700;color:var(--link);text-decoration:none}td a.trk:hover{text-decoration:underline}
tr:hover td{background:#fbfaf9}.pill{border-radius:4px;font-weight:700;font-size:12.5px}
.p-ok{background:#e1f3e6;color:#0a6b2e}.p-mid{background:#fff4cc;color:#6b4e00}.p-ko{background:#fde2e4;color:#a30d24}.p-blue{background:#e5eff9;color:#0a4f99}
.back{color:var(--link);font-weight:500;text-decoration:none;display:inline-block;margin-bottom:16px}
.head{display:grid;grid-template-columns:1fr auto;gap:20px;padding:30px 32px 10px}.head small{color:var(--mute);font-size:13px}
.trkbig{font-size:16px;margin:4px 0 16px;color:var(--mute)}.trkbig b{color:var(--ink);font-family:'Roboto Mono',monospace;font-weight:700;letter-spacing:.04em}
.st{display:flex;align-items:center;gap:12px;font-size:40px;font-weight:400}
.ok{color:#0a6b2e}.ko{color:#a30d24}.mid{color:#8a6100}.blue{color:#0a4f99}.st.ok .ic,.st.mid .ic{color:inherit}
.eta{text-align:right}.eta small{display:block;font-size:13px;color:var(--mute)}.eta b{display:block;font-size:26px;font-weight:500}
.steps{display:grid;grid-template-columns:repeat(4,1fr);padding:22px 32px 34px;gap:0}.step{position:relative;font-size:14px;font-weight:500;color:#8b827d}
.step .n{display:flex;align-items:center;gap:0;flex-direction:column;align-items:flex-start}.step .n i{width:22px;height:22px;border-radius:50%;background:#fff;border:3px solid #cfc8c2;
display:grid;place-items:center;font-style:normal;font-size:11px;position:relative;z-index:1;color:#fff;margin-bottom:10px}
.step::after{content:"";position:absolute;left:22px;right:0;top:9px;height:5px;background:#e5e0db;z-index:0}.step:last-child::after{display:none}
.step .n span{background:none;padding:0}.step.done{color:var(--ink)}.step.done .n i{background:var(--brown);border-color:var(--brown)}.step.done::after{background:var(--brown)}
.step.bad{color:#a30d24}.step.bad .n i{background:#a30d24;border-color:#a30d24}
.step em{display:block;font-style:normal;font-weight:400;color:var(--mute);margin-top:4px;font-size:13px}
.two{display:grid;grid-template-columns:1.2fr 1fr;gap:22px;align-items:start}
.evs{padding:4px 24px 18px}.ev{display:grid;grid-template-columns:104px 20px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid #f0ece8}.ev:last-child{border:0}
.ev .d{font-size:13px;color:var(--mute);text-align:right;line-height:1.4}.ev .d b{color:var(--ink);display:block;font-weight:500}
.ev .m{width:12px;height:12px;border-radius:50%;background:#cfc8c2;margin:4px auto 0}.ev:first-child .m{background:var(--gold);box-shadow:0 0 0 4px #fff4cc}
.ev .l{font-weight:500}.ev .l small{display:block;color:var(--mute);font-weight:400;font-size:13px;margin-top:2px}
.label{margin:10px 24px 22px;border:2px solid var(--ink);font-size:12.5px}.label .row{display:grid;grid-template-columns:1fr 1fr;border-bottom:2px solid var(--ink)}
.label .row>div{padding:10px 12px}.label .row>div+div{border-left:2px solid var(--ink)}.label small{display:block;font-weight:700;font-size:10px;color:var(--mute)}
.label .svc{background:var(--ink);color:#fff;font-weight:900;font-size:22px;padding:10px 12px;display:flex;justify-content:space-between}
.label .bc{padding:12px 12px 8px;text-align:center;font-family:'Roboto Mono',monospace;font-weight:700;letter-spacing:.2em}
.pod{padding:6px 24px 24px;position:relative}.paper{background:#fffdf6;border:1px solid #ebe3cf;border-radius:8px;padding:10px;margin:10px 0;position:relative}
.stamp{position:absolute;right:14px;top:10px;transform:rotate(-12deg);border:3px solid #0a6b2e;color:#0a6b2e;font-weight:900;letter-spacing:.12em;
padding:3px 10px;border-radius:6px;font-size:18px;opacity:.85;text-transform:uppercase}.stamp.warn{border-color:#8a6100;color:#8a6100}
code.ref{font-family:'Roboto Mono',monospace;background:var(--brown);color:var(--gold);padding:3px 10px;border-radius:4px;font-size:13px}
.alert{background:#fde2e4;border-left:5px solid #a30d24;color:#5c0613;padding:14px 16px;margin:10px 24px 16px;display:flex;gap:10px}
.warnb{background:#fff4cc;border-left:5px solid var(--gold);color:#4d3800;padding:12px 14px;margin:10px 24px 0;display:flex;gap:10px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px;padding:14px 0}.grid2 small{display:block;color:var(--mute);font-size:12.5px}
.map{background:#f7f5f3}.btn{background:var(--gold);color:var(--ink);border:0;border-radius:999px;padding:12px 22px;font-weight:700;cursor:pointer;
text-decoration:none;display:inline-flex;align-items:center;gap:8px;font-size:15px}.btn:hover{background:var(--gold-h)}
"""

PARCELIA_LOGO = ('<svg width="34" height="34" viewBox="0 0 32 32" fill="none"><rect x="3" y="7" width="26" height="20" rx="3" fill="#351c15"/>'
                 '<path d="M3 13h26" stroke="currentColor" stroke-width="3"/><path d="M13 7v6M19 7v6" stroke="currentColor" stroke-width="2"/></svg>')
WAVE = ('<svg class="wave" viewBox="0 0 1440 400" preserveAspectRatio="none"><defs><linearGradient id="wv" x1="0" x2="1">'
        '<stop offset="0" stop-color="#c8102e"/><stop offset=".55" stop-color="#7a0a12"/><stop offset="1" stop-color="#4a0508"/></linearGradient></defs>'
        '<path d="M0 400V170C260 60 520 40 760 110s470 120 680 40V400z" fill="url(#wv)"/>'
        '<path d="M0 400V330C360 190 760 180 1080 220c150 18 260 30 360 20V400z" fill="#f2f1ef"/></svg>')


def parcelia_shell(inner: str, hero: str = "") -> str:
    body = f"""<div class="demo">Parcelia Pro — environnement de démonstration indépendant, non affilié à un transporteur réel · données fictives</div>
<div class="bar"><a class="lg" href="/parcelia">{PARCELIA_LOGO}parcelia<small>PRO</small></a>
<nav><a href="#">Expédition</a><a class="on" href="/parcelia">Suivi</a><a href="#">Solutions professionnelles</a><a href="#">Aide</a></nav>
<div class="acc">{ic('search', 22)}<span>Compte <b class="mono">SPORTIVA-PRO</b></span><a class="gold" href="/parcelia/logout">Déconnexion ›</a></div></div>
{hero}<div class="wrap">{inner}</div>"""
    return page("Parcelia Pro", body, PARCELIA_CSS, "parcelia", "#ffc400")


def ship_pill(s: dict) -> str:
    cls = {"livre_signe": "p-ok", "boite_aux_lettres": "p-mid", "perdu": "p-ko", "en_transit": "p-blue"}.get(s["code"], "p-blue")
    return f'<span class="pill {cls}"><i></i>{e(s["statut"])}</span>'


def parcelia_home(q: str):
    ql = q.strip().upper()
    allv = list(DATA["shipments"].values())
    items = allv
    if ql:
        items = [s for s in allv if ql in s["tracking"] or ql in s["order_id"]]
        if len(items) == 1:
            return None
    items.sort(key=lambda s: s["evenements"][-1]["date"], reverse=True)
    rows = "".join(f'<tr><td><a class="trk" href="/parcelia/shipments/{s["tracking"]}">{s["tracking"]}</a></td><td class="mono">{e(s["order_id"])}</td>'
                   f'<td>{e(s["destination"])}</td><td>{ship_pill(s)}</td><td style="color:var(--mute)">{fdate(s["evenements"][-1]["date"])}</td></tr>' for s in items[:50])
    empty = f'<tr><td colspan="5" style="padding:30px;text-align:center;color:var(--mute)">Aucun envoi trouvé pour « {e(q)} ».</td></tr>'
    n = lambda c: sum(1 for s in allv if s["code"] == c)
    pinic = ('<svg width="58" height="58" viewBox="0 0 24 24"><path d="M12 22s-7-6.2-7-11.5A7 7 0 0 1 19 10.5C19 15.8 12 22 12 22z" fill="#ffc400" stroke="#351c15" stroke-width=".8"/>'
             '<circle cx="12" cy="10.5" r="2.6" fill="#351c15"/></svg>')
    hero = f"""<section class="hero">{WAVE}<div class="hgrid"><div class="tcard rise"><h1>{pinic}Suivi</h1>
<form action="/parcelia"><input name="q" value="{e(q)}" placeholder="Numéro de suivi Parcelia ou référence client (CMD-…)"><button class="gold">Suivi ›</button></form>
<div class="links"><a href="#">{ic('bell', 20)} Configurer les alertes</a><a href="#">{ic('truck', 20)} Modifier la livraison</a><a href="#">{ic('msg', 20)} Obtenir de l'aide</a></div></div>
<div><div class="scard rise d1"><span class="ill">{ic('box', 30)}</span><b>Expédition</b><div class="chips"><span>{n('en_transit')} en transit</span>·<span>{n('livre_signe') + n('boite_aux_lettres')} livrés</span></div></div>
<div class="scard rise d2" style="margin:0"><span class="ill">{ic('alert', 30)}</span><b>Anomalies à traiter</b><div class="chips"><span>{n('perdu')} colis non localisés</span></div></div></div></div></section>"""
    inner = f"""<div class="box rise d2"><h2>{ic('box', 22)} {'Résultats de recherche' if q else 'Envois récents du compte'}<span class="r">{len(items)} envoi(s)</span></h2>
<table><tr><th>N° de suivi</th><th>Référence client</th><th>Destination</th><th>Statut</th><th>Dernier scan</th></tr>{rows or empty}</table></div>"""
    return parcelia_shell(inner, hero)


def _xy(lat, lon, w=320, h=300):
    return (lon + 5.3) / 13.9 * w, (51.4 - lat) / 9.2 * h


def france_map(dest_city: str, perdu: bool) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (_xy(lat, lon) for lon, lat in FRANCE))
    hx, hy = _xy(*GEO["Lyon-Saint-Exupéry"])
    dx, dy = _xy(*GEO.get(dest_city, GEO["Paris"]))
    mx, my = (hx + dx) / 2 + (dy - hy) * 0.18, (hy + dy) / 2 - (dx - hx) * 0.18
    color = "#ef4444" if perdu else "#351c15"
    end = (f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="9" fill="#ffc400" opacity=".25"/><circle cx="{dx:.1f}" cy="{dy:.1f}" r="5.5" fill="#351c15"/>' if not perdu
           else f'<circle cx="{(hx + dx) / 2:.0f}" cy="{(hy + dy) / 2:.0f}" r="12" fill="#fde4e1"/><text x="{(hx + dx) / 2:.0f}" y="{(hy + dy) / 2 + 5:.0f}" font-size="14" font-weight="900" text-anchor="middle" fill="#b42318">?</text>')
    return f"""<svg viewBox="0 0 320 300" width="100%" style="display:block"><polygon points="{pts}" fill="#fff" stroke="#b9aea7" stroke-width="1.4"/>
<path d="M{hx:.1f},{hy:.1f} Q{mx:.1f},{my:.1f} {dx:.1f},{dy:.1f}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-dasharray="{'5 7' if perdu else '0'}"/>
<rect x="{hx - 6:.1f}" y="{hy - 6:.1f}" width="12" height="12" rx="2" fill="#351c15"/><text x="{hx + 10:.0f}" y="{hy + 4:.0f}" font-size="10.5" font-weight="800" fill="#351c15" font-family="Roboto">HUB LYON</text>
{end}<text x="{dx + 11:.0f}" y="{dy - 9:.0f}" font-size="11.5" font-weight="800" fill="#121212" font-family="Roboto">{e(dest_city).upper()}</text></svg>"""


def barcode(code: str, w: int = 300, h: int = 54) -> str:
    r = random.Random(code)
    x, bars = 0.0, []
    while x < w - 4:
        bw = r.choice([1.2, 1.2, 2.4, 3.6])
        if r.random() < 0.55:
            bars.append(f'<rect x="{x:.1f}" y="0" width="{bw}" height="{h}"/>')
        x += bw + r.choice([1.2, 2.4])
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" fill="#121212" preserveAspectRatio="none">{"".join(bars)}</svg>'


def signature(name: str) -> str:
    r = random.Random(name)
    x, y = 18.0, 52.0
    d = f"M{x:.0f},{y:.0f}"
    for _ in range(9):
        x += 22 + r.random() * 14
        d += f" C{x - 18:.0f},{y - 34 * r.random():.0f} {x - 6:.0f},{y + 30 * r.random():.0f} {x:.0f},{y + (r.random() - .5) * 18:.0f}"
    d += f" M{24 + r.random() * 30:.0f},{72 + r.random() * 6:.0f} L{x - 10:.0f},{64 + r.random() * 8:.0f}"
    return (f'<svg viewBox="0 0 320 92" width="100%" height="92"><path d="{d}" fill="none" stroke="#1e3a8a" stroke-width="2.3" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def gps(s: dict) -> str:
    lat, lon = GEO.get(s["destination"].split(" ", 1)[1], GEO["Paris"])
    r = random.Random(s["tracking"])
    return f"{lat + (r.random() - .5) * .04:.5f}, {lon + (r.random() - .5) * .04:.5f}"


def parcelia_shipment(trk: str):
    s = DATA["shipments"].get(trk)
    if not s:
        return None
    city = s["destination"].split(" ", 1)[1]
    code = s["code"]
    evs = s["evenements"]
    first = {0: evs[0]["date"], 1: evs[1]["date"] if len(evs) > 1 else None}
    reached = {"en_transit": 2, "perdu": 2, "livre_signe": 4, "boite_aux_lettres": 4}.get(code, 1)
    labels = ["Pris en charge", "En transit", "En livraison", "Livré"]
    stamps = [evs[0]["date"], evs[1]["date"] if len(evs) > 1 else "", evs[-2]["date"] if reached == 4 and len(evs) > 2 else "",
              evs[-1]["date"] if reached == 4 else ""]
    steps = "".join(f'<div class="step {"bad" if code == "perdu" and i == 2 else "done" if i < reached else ""}"><div class="n"><i>'
                    f'{"!" if code == "perdu" and i == 2 else "✓" if i < reached else i + 1}</i><span>{lbl}</span></div>'
                    f'<em>{fdate(stamps[i]) if i < reached and stamps[i] else ("Anomalie" if code == "perdu" and i == 2 else "—")}</em></div>'
                    for i, lbl in enumerate(labels))
    cls = {"livre_signe": "ok", "boite_aux_lettres": "mid", "perdu": "ko", "en_transit": "blue"}[code]
    icon = {"livre_signe": "check", "boite_aux_lettres": "inbox", "perdu": "alert", "en_transit": "truck"}[code]
    eta = (f'<small>LIVRÉ LE</small><b>{fdate(s["date_livraison"], False)}</b>' if s.get("date_livraison") else
           ('<small>ÉTAT</small><b class="ko">ENQUÊTE OUVERTE</b>' if code == "perdu" else '<small>LIVRAISON PRÉVUE</small><b>sous 48 h</b>'))
    ev = "".join(f'<div class="ev"><div class="d"><b>{fdate(x["date"], False)}</b>{x["date"][11:16]}</div><div class="m"></div>'
                 f'<div class="l">{e(x["libelle"])}<small>{e(x["detail"])} · {e(x["lieu"])}</small></div></div>' for x in reversed(evs))
    if code == "livre_signe":
        pod = f"""<div class="pod"><div style="font-weight:800">{ic('pen', 16)} Remis en main propre contre signature</div>
<div class="paper"><span class="stamp">Livré</span>{signature(s['signe_par'])}</div>
<div class="grid2" style="padding:6px 0 10px"><div><small>Signé par</small><b>{e(s['signe_par'])}</b></div><div><small>Date et heure</small>{fdate(evs[-1]['date'])}</div>
<div><small>Position GPS livreur</small><span class="mono">{gps(s)}</span></div><div><small>Livreur</small>Tournée {e(city[:3].upper())}-{int(hashlib.md5(trk.encode()).hexdigest()[:2], 16) % 40 + 10}</div></div>
<div>Référence de preuve à transmettre : <code class="ref">{e(s['preuve'])}</code></div>
<div style="margin-top:16px"><a class="btn" href="/parcelia/shipments/{trk}/pod">{ic('file', 16)} Ouvrir la preuve de livraison (POD)</a></div></div>"""
    elif code == "boite_aux_lettres":
        pod = f"""<div class="warnb">{ic('inbox', 18)}<div>Livré <b>sans signature</b> : colis déposé dans la boîte aux lettres du destinataire.</div></div>
<div class="pod"><div class="paper" style="text-align:center;padding:18px;color:var(--mute)"><span class="stamp warn">Déposé</span>Aucune signature recueillie pour ce service.</div>
<div class="grid2" style="padding:6px 0 10px"><div><small>Date et heure</small>{fdate(evs[-1]['date'])}</div><div><small>Position GPS livreur</small><span class="mono">{gps(s)}</span></div></div>
<div>Référence de preuve : <code class="ref">{e(s['preuve'])}</code></div>
<div style="margin-top:16px"><a class="btn" href="/parcelia/shipments/{trk}/pod">{ic('file', 16)} Ouvrir l'attestation de dépôt</a></div></div>"""
    elif code == "perdu":
        pod = f"""<div class="alert">{ic('alert', 18)}<div><b>Anomalie : colis non localisé.</b> Une enquête a été ouverte auprès du réseau. Aucune preuve de livraison n'existe pour cet envoi.</div></div>
<div class="pod" style="padding-top:0">Référence de preuve : <code class="ref">{e(s['preuve'])}</code></div>"""
    else:
        pod = '<div class="pod" style="color:var(--mute)">Le colis est en cours d\'acheminement. La preuve de livraison sera disponible après la remise.</div>'
    label = f"""<div class="label"><div class="svc"><span>Express 48h</span><span>{e(s['poids_kg'])} kg</span></div>
<div class="row"><div><small>DE</small>SPORTIVA SAS<br>Plateforme e-commerce<br>69125 Lyon</div><div><small>À</small>{e(s['destination'])}<br>France<br><span class="mono">Réf. {e(s['order_id'])}</span></div></div>
<div class="bc">{barcode(trk)}<div style="margin-top:6px">{e(trk)}</div></div></div>"""
    inner = f"""<div style="margin-bottom:14px"><a class="back" href="/parcelia">‹ Tous les envois</a></div>
<div class="box rise"><div class="head"><div><small>ENVOI · RÉF. CLIENT <span class="mono">{e(s['order_id'])}</span> · {e(s['destination']).upper()}</small>
<div class="trkbig">Numéro de suivi : <b>{e(trk)}</b></div><div class="st {cls}">{ic(icon, 22)} {e(s['statut'])}</div></div><div class="eta">{eta}</div></div><div class="steps">{steps}</div></div>
<div class="two"><div><div class="box rise d1"><h2>{ic('clock', 16)} Historique des scans<span class="r">{len(evs)} événements</span></h2><div class="evs">{ev}</div></div>
<div class="box rise d2"><h2>{ic('file', 16)} Étiquette d'expédition</h2>{label}</div></div>
<div><div class="box rise d1"><h2>{ic('check', 16)} Preuve de livraison</h2>{pod}</div>
<div class="box rise d2"><h2>{ic('route', 16)} Trajet<span class="r">Hub Lyon → {e(city)}</span></h2><div class="map">{france_map(city, code == 'perdu')}</div></div></div></div>"""
    return parcelia_shell(inner)


def parcelia_pod(trk: str):
    s = DATA["shipments"].get(trk)
    if not s or s["code"] not in ("livre_signe", "boite_aux_lettres"):
        return None
    signed = s["code"] == "livre_signe"
    css = PARCELIA_CSS + """body{padding:34px}.doc{max-width:780px;margin:0 auto;background:#fff;box-shadow:0 18px 50px -20px #351c1555;border-radius:6px;overflow:hidden}
.dh{background:var(--brown);color:#fff;padding:22px 34px;display:flex;justify-content:space-between;align-items:center}.dh .lg{color:#fff}
.dh span{font-weight:900;font-stretch:80%;letter-spacing:.1em;text-transform:uppercase;color:var(--gold)}.db{padding:26px 34px 34px;position:relative}
table{margin-top:4px}td{padding:11px 0;border-top:1px solid #edf1f6}td:first-child{color:var(--mute);width:40%;font-weight:600}
.sig{border:1px solid #ece4cf;background:#fffdf7;border-radius:8px}.big{position:absolute;right:40px;top:30px;transform:rotate(-12deg);border:4px solid #0a6b2e;color:#0a6b2e;
font-weight:900;font-stretch:80%;font-size:26px;letter-spacing:.14em;padding:4px 14px;border-radius:8px;opacity:.8;text-transform:uppercase}.big.w{border-color:#a16207;color:#a16207}
.pr{margin-top:24px;display:flex;gap:14px;align-items:center}@media print{body{background:#fff;padding:0}.pr{display:none}.doc{box-shadow:none}}"""
    sig = f'<tr><td>Signature</td><td><div class="sig">{signature(s["signe_par"])}</div></td></tr>' if signed else ""
    body = f"""<div class="doc"><div class="dh"><div class="lg">{PARCELIA_LOGO}parcelia <b>PRO</b></div><span>{'Preuve de livraison · POD' if signed else 'Attestation de dépôt'}</span></div>
<div class="db"><div class="big {'' if signed else 'w'}">{'Livré' if signed else 'Déposé'}</div><div style="width:300px;margin-bottom:18px">{barcode(trk, 300, 46)}<div class="mono" style="font-weight:700;letter-spacing:.18em;margin-top:4px">{e(trk)}</div></div>
<table><tr><td>Numéro de suivi</td><td class="mono"><b>{e(trk)}</b></td></tr><tr><td>Référence client</td><td class="mono">{e(s['order_id'])}</td></tr>
<tr><td>Expéditeur</td><td>Sportiva SAS — Lyon</td></tr><tr><td>Destination</td><td>{e(s['destination'])}, France</td></tr>
<tr><td>Date et heure de remise</td><td>{fdate(s['evenements'][-1]['date'])}</td></tr>
<tr><td>Mode de remise</td><td>{'Remis en main propre contre signature' if signed else 'Déposé en boîte aux lettres, sans signature'}</td></tr>
<tr><td>Réceptionnaire</td><td>{e(s['signe_par']) if signed else '—'}</td></tr><tr><td>Position GPS</td><td class="mono">{gps(s)}</td></tr>{sig}
<tr><td>Référence de preuve à transmettre</td><td><code class="ref">{e(s['preuve'])}</code></td></tr></table>
<p style="color:var(--mute);font-size:12px;margin-top:20px">Document généré par le portail Parcelia Pro. Données fictives de démonstration.</p>
<div class="pr"><button class="btn" onclick="window.print()">{ic('file', 16)} Imprimer / Enregistrer en PDF</button>
<a href="/parcelia/shipments/{e(trk)}" style="color:var(--link);font-weight:800">← Retour à l'envoi</a></div></div></div>"""
    return page(f"POD {trk} · Parcelia Pro", body, css, "parcelia", "#ffc400")


# ============================================================================ Sportiva Care
# Palette et conventions d'une boîte de réception support de référence (rail d'icônes, 4 colonnes, bleu d'action).
CARE_CSS = """
:root{--ink:#1a1a1a;--mute:#737376;--line:#e6e6e6;--soft:#f5f5f5;--rail:#f0f0f0;--blue:#1f73e8;--blue-s:#e5eefd;--bub:#f1f1f1}
body{font-family:Inter,-apple-system,'Segoe UI',sans-serif;font-size:14px;background:#fff;color:var(--ink)}
.demo{height:26px;line-height:26px;background:#1a1a1a;color:#d9d9d9;font-size:12px;text-align:center}
.app{display:grid;grid-template-columns:52px 210px 290px minmax(0,1fr) 270px;height:calc(100vh - 26px)}
.rail{background:var(--rail);display:flex;flex-direction:column;align-items:center;padding:12px 0;gap:6px;border-right:1px solid var(--line)}
.rail .lg{width:30px;height:30px;border-radius:8px;background:#1a1a1a;color:#fff;display:grid;place-items:center;font-weight:800;margin-bottom:12px;font-size:14px}
.rail a{width:36px;height:36px;border-radius:8px;display:grid;place-items:center;color:#5c5c5f;text-decoration:none}.rail a.on{color:var(--blue);background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.rail a:hover{background:#e6e6e6}.rail .bot{margin-top:auto}
.folders{background:#fafafa;border-right:1px solid var(--line);padding:14px 10px;overflow:auto}.folders h1{font-size:16px;white-space:nowrap;align-items:center;margin:2px 8px 16px;font-weight:700;display:flex;justify-content:space-between}
.folders small{display:block;font-weight:600;color:var(--ink);font-size:13px;margin:4px 8px 6px}
.folders a{display:flex;align-items:center;gap:9px;padding:6px 8px;border-radius:6px;text-decoration:none;color:#3b3b3d;font-size:13.5px}
.folders a span{margin-left:auto;color:var(--mute);font-size:12.5px}.folders a.on{color:var(--blue);font-weight:600;background:var(--blue-s)}.folders a.on span{color:var(--blue)}
.list{border-right:1px solid var(--line);overflow:auto;display:flex;flex-direction:column}
.lh{padding:14px 14px 10px;position:sticky;top:0;background:#fff;z-index:2;border-bottom:1px solid var(--line)}
.lh h2{font-size:17px;margin:0 0 10px;font-weight:700;display:flex;align-items:center;gap:8px}.lh .sub{display:flex;justify-content:space-between;font-weight:600;font-size:13px;margin-top:10px}
.lh form{position:relative}.lh form .ic{position:absolute;left:10px;top:8px;color:var(--mute)}
.lh input{width:100%;padding:7px 10px 7px 34px;border:1px solid var(--line);border-radius:8px;background:var(--soft);font-size:13px}.lh input:focus{outline:2px solid var(--blue);background:#fff}
.t{display:grid;grid-template-columns:34px 1fr;gap:10px;padding:13px 14px;text-decoration:none;border-bottom:1px solid #efefef}
.t:hover{background:#fafafa}.t.on{background:var(--blue-s)}.t .s{font-size:13.5px;color:#3b3b3d;margin:4px 0 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.t .top{display:flex;justify-content:space-between;gap:8px;font-weight:650}.t .top span+span{font-weight:400;color:var(--mute);font-size:12px;white-space:nowrap}
.t small{color:var(--mute);font-size:12px;display:flex;justify-content:space-between;align-items:center}
.av{border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:600;font-size:12.5px;flex:none}
.pill{font-size:11.5px;padding:1px 8px 1px 6px}.p-ok{background:#e3f5ea;color:#1b7a43}.p-wait{background:#fff1e0;color:#a35a00}
.conv{display:flex;flex-direction:column;min-width:0;background:#fff}.ch{padding:14px 26px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
.ch h2{font-size:18px;margin:0;font-weight:700}.ch .meta{color:var(--mute);font-size:12.5px;margin-top:3px}
.ch .acts{margin-left:auto;display:flex;align-items:center;gap:14px;color:#3b3b3d}.ch .acts .rin{white-space:nowrap;border:1px solid var(--line);border-radius:6px;padding:3px 8px;font-size:12.5px;display:flex;gap:5px;align-items:center}
.msgs{flex:1;overflow:auto;padding:22px 26px}.m{display:flex;gap:12px;margin:14px 0;max-width:620px;align-items:flex-start}
.m .bub{background:var(--bub);border-radius:10px;padding:11px 14px;line-height:1.5}.m .who{font-size:12px;color:var(--mute);margin-top:6px}
.m.agent{margin-left:auto;flex-direction:row-reverse}.m.agent .who{text-align:right}
.sys{text-align:center;color:var(--mute);font-size:12.5px;margin:18px 0}
.exp{display:flex;gap:12px;align-items:center;max-width:620px;margin:18px 0 6px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:#fafafa}
.exp .fi{width:36px;height:36px;border-radius:8px;background:var(--blue-s);display:grid;place-items:center;color:var(--blue)}
code.ref{font-family:'Roboto Mono',ui-monospace,Menlo,monospace;background:#1a1a1a;color:#fff;padding:2px 8px;border-radius:5px;font-size:12px}
.composer{margin:0 26px 18px;border-radius:12px;box-shadow:0 0 0 1px var(--line),0 6px 20px -10px rgba(0,0,0,.25);background:#fff}
.composer .tb{display:flex;gap:18px;padding:10px 16px 0;border-bottom:1px solid #f0f0f0;font-weight:600;font-size:13.5px;color:var(--mute)}
.composer .tb span{padding-bottom:8px}.composer .tb span.on{color:var(--blue);border-bottom:2px solid var(--blue)}
.composer .ph{padding:14px 16px 26px;color:#a3a3a6}.composer .ft{display:flex;align-items:center;gap:16px;padding:8px 12px 10px 16px;color:#5c5c5f}
.composer .send{margin-left:auto;background:var(--blue);color:#fff;border-radius:6px;padding:7px 18px;font-weight:600}
.ctx{background:#fafafa;border-left:1px solid var(--line);overflow:auto;padding:16px 14px}
.ctx h3{font-size:14px;margin:0 0 12px;font-weight:650;display:flex;justify-content:space-between}.ctx h3 span{color:var(--mute);font-weight:500}
.kv{display:grid;grid-template-columns:96px 1fr;gap:9px 8px;font-size:13px;margin-bottom:20px}.kv span:nth-child(odd){color:var(--mute)}
.rel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:12px}
.cp{display:flex;gap:10px;align-items:center;font-weight:650;margin-bottom:10px}
.ri{display:flex;gap:10px;align-items:center;color:#3b3b3d;font-size:12.5px;margin:7px 0}.ri .ic{color:var(--mute)}
.oc{border-top:1px solid #f0f0f0;padding:8px 0;display:flex;justify-content:space-between;align-items:center;font-size:12.5px}
.oc .mono{font-family:'Roboto Mono',ui-monospace,monospace;font-weight:600}.empty{flex:1;display:grid;place-items:center;color:var(--mute);text-align:center;padding:40px}
.empty h2{color:var(--ink);font-weight:650}
"""


def care_avatar(name: str, size: int = 34) -> str:
    return f'<span class="av" style="width:{size}px;height:{size}px;background:hsl({hue(name)} 55% 58%)">{e(initials(name))}</span>'


def _ago(d: str) -> str:
    n = (TODAY - date.fromisoformat(d[:10])).days
    return "aujourd'hui" if n == 0 else "hier" if n == 1 else f"{n} j"


def care_page(q: str, tid: str | None) -> str:
    ql = q.lower().strip()
    ts = [t for t in DATA["tickets"] if not ql or ql in f'{t["email"]} {t["client"]} {t["commande"]} {t["id"]} {t["sujet"]}'.lower()]
    allt = DATA["tickets"]
    att = sum(1 for t in allt if t["statut"] != "Résolu")
    items = "".join(f"""<a class="t {'on' if t['id'] == tid else ''}" href="/care/tickets/{quote(t['id'][1:])}{'?q=' + quote(q) if q else ''}">{care_avatar(t['client'])}
<div style="min-width:0"><div class="top"><span>{e(t['client'])}</span><span>{_ago(t['date'])}</span></div><div class="s">{e(t['sujet'])} — {e(t['messages'][0][1])}</div>
<small><span>{e(t['id'])} · {e(t['commande'])}</span><span class="pill {'p-ok' if t['statut'] == 'Résolu' else 'p-wait'}"><i></i>{e(t['statut'])}</span></small></div></a>""" for t in ts[:150])
    t = next((x for x in allt if x["id"] == tid), None)
    if t:
        r = random.Random(t["id"])
        h0 = 9 + int(r.random() * 7)
        msgs = "".join(f"""<div class="m {m[0]}">{care_avatar(t['client'] if m[0] == 'client' else 'Agent Care', 32)}<div>
<div class="bub">{e(m[1])}</div><div class="who">{e(t['client']) if m[0] == 'client' else 'Agent Sportiva Care'} · {fdate(t['date'], False)}, {h0 + i}:{int(r.random() * 50) + 10:02d} · Vu</div></div></div>"""
                       for i, m in enumerate(t["messages"]))
        conv = f"""<div class="ch">{care_avatar(t['client'], 36)}<div><h2>{e(t['client'])}</h2><div class="meta">{e(t['sujet'])} · {e(t['email'])}</div></div>
<div class="acts"><span class="rin">{ic('clock', 14)} Répondre sous 2 h</span>{ic('users', 18)}<span>Vous</span>{ic('check', 18)}</div></div>
<div class="msgs"><div class="sys">Conversation ouverte le {fdate(t['date'], False)} · ticket {e(t['id'])} · commande {e(t['commande'])}</div>{msgs}
<div class="exp"><div class="fi">{ic('attach')}</div><div>📎 Export de la conversation (pièce justificative) — référence de preuve : <code class="ref">{e(t['preuve'])}</code>
<br><span style="color:var(--mute);font-size:12.5px">PDF généré automatiquement à partir du fil</span></div></div>
<div class="sys">Statut : {e(t['statut'])}</div></div>
<div class="composer"><div class="tb"><span class="on">Répondre</span><span>Note interne</span></div><div class="ph">Répondre à {e(t['client'].split()[0])}…</div>
<div class="ft">{ic('file', 17)}{ic('note', 17)}{ic('tag', 17)}{ic('attach', 17)}<span class="send">Envoyer</span></div></div>"""
        c = DATA["clients"].get(t["email"], {"nom": t["client"], "ville": "", "cp": "", "depuis": "", "commandes": 0})
        orders = sorted(BY_CLIENT.get(t["email"], []), key=lambda o: o["date"], reverse=True)
        oc = "".join(f'<div class="oc"><div><span class="mono">{o["id"]}</span><br><small style="color:var(--mute)">{fdate(o["date"], False)}</small></div>'
                     f'<div style="text-align:right"><b>{eur(o["total"])}</b><br><small style="color:var(--mute)">{e(o["traitement"])}</small></div></div>' for o in orders)
        others = [x for x in allt if x["email"] == t["email"] and x["id"] != t["id"]]
        oth = "".join(f'<div class="ri">{care_avatar(x["client"], 20)}<a href="/care/tickets/{quote(x["id"][1:])}" style="color:inherit">{e(x["sujet"])}</a>'
                      f'<span style="margin-left:auto;color:var(--mute)">{_ago(x["date"])}</span></div>' for x in others) or '<div class="ri" style="color:var(--mute)">Aucune autre conversation</div>'
        urg = "Haute" if any(k in t["sujet"].lower() for k in ("jamais", "introuvable", "reçu")) else "Normale"
        ctx = f"""<aside class="ctx"><h3>Détails de la conversation {ic('settings', 16)}</h3><div class="kv"><span>Urgence</span><span>{urg}</span>
<span>Catégorie</span><span>{e(t['sujet'])}</span><span>Commande</span><span class="mono" style="font-family:'Roboto Mono',monospace">{e(t['commande'])}</span><span>Statut</span><span>{e(t['statut'])}</span><span>ID</span><span>{e(t['id'][1:])}</span></div>
<h3>Lié <span>Personnaliser</span></h3><div class="rel"><div class="cp">{care_avatar(c['nom'], 30)}{e(c['nom'])}</div>
<div class="ri">{ic('msg', 15)} {e(t['email'])}</div><div class="ri">{ic('pin', 15)} {e(c['cp'])} {e(c['ville'])}</div>
<div class="ri">{ic('clock', 15)} Client depuis {e(c['depuis'])}</div><div class="ri">{ic('orders', 15)} {c['commandes']} commande(s) au total</div>{oc}</div>
<h3>Dernières conversations</h3><div class="rel">{oth}</div></aside>"""
    else:
        conv = f'<div class="empty"><div>{ic("inbox", 40)}<h2>Aucune conversation sélectionnée</h2>Choisis un ticket dans la liste, ou recherche un client, un e-mail ou un numéro de commande.</div></div>'
        ctx = '<aside class="ctx"></aside>'
    body = f"""<div class="demo">Sportiva Care — environnement de démonstration indépendant, non affilié à un éditeur réel · données fictives</div>
<div class="app"><nav class="rail"><div class="lg">c</div><a class="on" href="/care" title="Boîte de réception">{ic('inbox', 20)}</a><a href="#" title="Envois">{ic('ext', 20)}</a>
<a href="#" title="Contacts">{ic('users', 20)}</a><a href="#" title="Base de connaissances">{ic('note', 20)}</a><a href="#" title="Rapports">{ic('chart', 20)}</a>
<a class="bot" href="/care/logout" title="Déconnexion">{ic('out', 20)}</a></nav>
<section class="folders"><h1>Boîte de réception {ic('search', 17)}</h1><small>Conversations ▾</small>
<a href="/care" class="{'' if ql else 'on'}">{ic('users', 16)} Toutes<span>{len(allt)}</span></a><a href="#">{ic('dot', 16)} Vous<span>{att}</span></a>
<a href="#">{ic('msg', 16)} Mentions<span>0</span></a><a href="/care?q=jamais">{ic('alert', 16)} Litiges & colis<span>{sum(1 for x in allt if 'jamais' in x['sujet'].lower() or 'introuvable' in x['sujet'].lower())}</span></a>
<a href="#">{ic('clock', 16)} En attente<span>{att}</span></a></section>
<section class="list"><div class="lh"><h2>{ic('inbox', 18)} Tickets</h2><form action="/care">{ic('search', 16)}
<input name="q" value="{e(q)}" placeholder="Rechercher : e-mail, nom, n° de commande"></form><div class="sub"><span>Ouverts {len(ts)} ▾</span><span>Plus récents ▾</span></div></div>
{items or '<div style="padding:24px;color:var(--mute)">Aucun ticket trouvé.</div>'}{f'<div style="padding:14px;color:var(--mute);font-size:12.5px">150 plus récents affichés sur {len(ts)} · utilise la recherche pour retrouver un ticket</div>' if len(ts) > 150 else ''}</section>
<main class="conv">{conv}</main>{ctx}</div>"""
    return page("Sportiva Care", body, CARE_CSS, "care", "#1f73e8")


# ============================================================================ serveur
INDEX_CSS = """body{font-family:Inter,sans-serif;background:#16171a;color:#f6f5f2;min-height:100vh;display:grid;place-items:center}
.w{max-width:760px;padding:40px 24px}h1{font-family:Inter;font-size:44px;margin:0;letter-spacing:-.02em}p{color:#a9abb3}
.g{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:28px}.g a{display:block;padding:22px;border-radius:16px;text-decoration:none;border:1px solid #2a2b31;background:#1c1d22;transition:.15s}
.g a:hover{transform:translateY(-2px);border-color:#8a8a8a}.g b{display:block;font-family:Inter;font-size:18px;margin:10px 0 4px}.g small{color:#a9abb3}"""
INDEX = page("Sportiva — outils internes", f"""<div class="w"><h1>Sportiva — outils internes</h1><p>Environnement de démonstration indépendant, développé pour un hackathon · non affilié à un service existant · marques et données fictives.</p>
<div class="g"><a href="/admin">{ic('orders', 26)}<b>Sportiva Admin</b><small>Commandes, clients, remboursements</small></a>
<a href="/parcelia">{ic('truck', 26)}<b>Parcelia Pro</b><small>Suivi, étiquettes, preuves de livraison</small></a>
<a href="/care">{ic('msg', 26)}<b>Sportiva Care</b><small>Tickets et échanges clients</small></a></div></div>""", INDEX_CSS, "admin", "#303030")


class H(BaseHTTPRequestHandler):
    server_version = "Sportiva/1.1"

    def log_message(self, fmt, *args):
        pass

    def send_html(self, body: str, code: int = 200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, to: str, cookie: str | None = None):
        self.send_response(303)
        self.send_header("Location", to)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def not_found(self):
        self.send_html(page("Introuvable", '<div style="padding:80px;text-align:center;font-family:sans-serif"><h1>Page introuvable</h1><a href="/">Accueil</a></div>',
                            "", "", "#999"), 404)

    def do_POST(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] in APPS and parts[1] == "login":
            app = parts[0]
            n = int(self.headers.get("Content-Length") or 0)
            f = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf-8")).items()}
            c = DATA["comptes"][app]
            if f.get("username", "").strip().lower() == c["login"].lower() and f.get("password", "") == c["password"]:
                return self.redirect(f"/{app}", f"s_{app}={token(app)}; Path=/; HttpOnly; SameSite=Lax")
            return self.send_html(login_page(app, "Identifiant ou mot de passe incorrect."), 401)
        self.not_found()

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        parts = [p for p in u.path.split("/") if p]
        if not parts:
            return self.send_html(INDEX)
        if parts == ["healthz"]:
            return self.send_html("ok")
        app = parts[0]
        if app not in APPS:
            return self.not_found()
        if parts[1:] == ["logout"]:
            return self.redirect(f"/{app}/login", f"s_{app}=; Path=/; Max-Age=0")
        if parts[1:] == ["login"]:
            return self.send_html(login_page(app))
        if not logged(self, app):
            return self.redirect(f"/{app}/login")
        rest, out = parts[1:], None
        if app == "admin":
            if not rest:
                out = admin_home()
            elif rest == ["orders"]:
                out = admin_orders(q.get("q", ""), q.get("vue", "toutes"), max(1, int(q.get("page", "1")) if q.get("page", "1").isdigit() else 1))
            elif len(rest) == 2 and rest[0] == "orders":
                out = admin_order(rest[1])
            elif rest == ["customers"]:
                out = admin_customers(q.get("q", ""))
            elif len(rest) == 2 and rest[0] == "customers":
                out = admin_customer(unquote(rest[1]))
            elif rest == ["products"]:
                out = admin_products()
            elif rest == ["analytics"]:
                out = admin_analytics()
        elif app == "parcelia":
            if not rest:
                out = parcelia_home(q.get("q", ""))
                if out is None:
                    ql = q["q"].strip().upper()
                    s = next(s for s in DATA["shipments"].values() if ql in s["tracking"] or ql in s["order_id"])
                    return self.redirect(f"/parcelia/shipments/{s['tracking']}")
            elif len(rest) == 2 and rest[0] == "shipments":
                out = parcelia_shipment(rest[1])
            elif len(rest) == 3 and rest[0] == "shipments" and rest[2] == "pod":
                out = parcelia_pod(rest[1])
        elif app == "care":
            if not rest:
                out = care_page(q.get("q", ""), None)
            elif len(rest) == 2 and rest[0] == "tickets":
                out = care_page(q.get("q", ""), "#" + rest[1])
        return self.send_html(out) if out else self.not_found()


def main():
    port = int(os.environ.get("PORT", "8080"))
    print(f"Sportiva — outils internes sur http://0.0.0.0:{port}  (admin · parcelia · care)")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()
