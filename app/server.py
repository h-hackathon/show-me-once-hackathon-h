"""Outils internes de la marketplace fictive Sportiva — une seule app, zéro dépendance (Python 3.10+).

  /admin      Sportiva Admin   back-office : commandes, clients, remboursements
  /parcelia   Parcelia Pro     portail transporteur : suivi, preuve de livraison (POD)
  /care       Sportiva Care    support client : tickets

Données : data.json (généré par `python -m som outils`). Marques et données 100 % fictives.
Lancer en local : python app/server.py   →   http://localhost:8080
Railway : Procfile « web: python server.py » (le port vient de $PORT).
"""
import hashlib
import hmac
import html
import json
import math
import os
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
SECRET = (os.environ.get("SECRET_KEY") or "sportiva-demo-" + DATA.get("genere_le", "")).encode()
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
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
    s = f"{x:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def fdate(d: str, heure: bool = True) -> str:
    if not d:
        return "—"
    y, m, j = d[:10].split("-")
    out = f"{int(j)} {MOIS[int(m) - 1]} {y}"
    if heure and len(d) > 10:
        out += f" à {d[11:16]}"
    return out


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


# ============================================================================ composants communs
BASE_CSS = """
*{box-sizing:border-box}html,body{margin:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}a{color:inherit}button,input,select{font:inherit}
.badge{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.badge::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.8}
.b-green{background:#e7f6ec;color:#17733a}.b-grey{background:#eef0f3;color:#4b5563}.b-amber{background:#fff4dc;color:#946200}
.b-red{background:#fde8e8;color:#b42318}.b-blue{background:#e6effd;color:#1d4ed8}.b-violet{background:#efecfe;color:#5b21b6}
code.ref{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f3f4f6;border:1px solid #e5e7eb;padding:2px 8px;border-radius:6px;font-size:13px}
"""


def page(title: str, body: str, css: str = "", favicon_color: str = "#4f46e5") -> str:
    fav = (f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' "
           f"rx='8' fill='{quote(favicon_color)}'/%3E%3C/svg%3E")
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><link rel="icon" href="{fav}"><style>{BASE_CSS}{css}</style></head><body>{body}</body></html>')


def login_page(app: str, err: str = "") -> str:
    styles = {
        "admin": ("#f6f7fb", "#4f46e5", "Sportiva Admin", "Back-office de la boutique", "Adresse e-mail"),
        "parcelia": ("#0c1b33", "#14b8a6", "Parcelia Pro", "Espace expéditeurs professionnels", "Numéro de compte"),
        "care": ("#ecf7f4", "#0f766e", "Sportiva Care", "Support client", "E-mail agent"),
    }
    bg, accent, brand, sub, ulabel = styles[app]
    dark = app == "parcelia"
    css = f"""body{{background:{bg};min-height:100vh;display:grid;place-items:center;color:#111827}}
.box{{width:400px;max-width:92vw;background:#fff;border-radius:16px;padding:36px;box-shadow:0 10px 40px rgba(15,23,42,.12)}}
.logo{{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px}}.logo i{{width:34px;height:34px;border-radius:9px;
background:{accent};display:inline-grid;place-items:center;color:#fff;font-style:normal}}.sub{{color:#6b7280;margin:6px 0 24px}}
label{{display:block;font-weight:600;font-size:13px;margin:14px 0 6px}}input{{width:100%;padding:11px 12px;border:1px solid #d1d5db;border-radius:9px}}
input:focus{{outline:2px solid {accent};border-color:{accent}}}button{{width:100%;margin-top:22px;padding:12px;border:0;border-radius:9px;
background:{accent};color:#fff;font-weight:700;cursor:pointer}}.err{{color:#b42318;margin-top:12px;min-height:20px}}
.foot{{margin-top:18px;color:{'#94a3b8' if dark else '#9ca3af'};font-size:12px;text-align:center}}"""
    body = f"""<div><form class="box" method="post" action="/{app}/login">
<div class="logo"><i>{brand[0]}</i>{brand}</div><div class="sub">{sub}</div>
<label for="u">{ulabel}</label><input id="u" name="username" autocomplete="username" autofocus>
<label for="p">Mot de passe</label><input id="p" name="password" type="password" autocomplete="current-password">
<button type="submit">Se connecter</button><div class="err">{e(err)}</div></form>
<div class="foot">Environnement de démonstration — données fictives</div></div>"""
    return page(f"Connexion · {brand}", body, css, accent)


# ============================================================================ Sportiva Admin
ADMIN_CSS = """
body{background:#f6f7fb;color:#111827}
.top{position:fixed;top:0;left:0;right:0;height:56px;background:#fff;border-bottom:1px solid #e5e7eb;display:flex;align-items:center;
padding:0 18px;gap:18px;z-index:5}.brand{display:flex;align-items:center;gap:10px;font-weight:800;width:214px}
.brand i{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#4338ca);display:inline-grid;place-items:center;color:#fff;font-style:normal}
.top form{flex:1;max-width:560px}.top input{width:100%;padding:8px 12px 8px 34px;border:1px solid #e5e7eb;border-radius:9px;background:#f9fafb
url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%239ca3af' stroke-width='2'%3E%3Ccircle cx='7' cy='7' r='5'/%3E%3Cpath d='m11 11 4 4'/%3E%3C/svg%3E") 11px center no-repeat}
.me{margin-left:auto;display:flex;align-items:center;gap:10px;color:#4b5563}.me b{width:30px;height:30px;border-radius:50%;background:#eef2ff;color:#4338ca;display:grid;place-items:center;font-size:12px}
.side{position:fixed;top:56px;bottom:0;left:0;width:232px;background:#fff;border-right:1px solid #e5e7eb;padding:14px 10px}
.side a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;text-decoration:none;color:#374151;font-weight:500}
.side a:hover{background:#f3f4f6}.side a.on{background:#eef2ff;color:#3730a3;font-weight:700}.side .sep{height:1px;background:#f0f0f0;margin:12px 6px}
.side small{display:block;color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:6px 10px}
.side .cnt{margin-left:auto;background:#fde8e8;color:#b42318;border-radius:999px;font-size:11px;padding:1px 8px;font-weight:700}
main{margin:56px 0 0 232px;padding:26px 32px 60px;max-width:1240px}
h1{font-size:22px;margin:0}.head{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}
.muted{color:#6b7280}.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.card h2{font-size:14px;margin:0;padding:14px 18px;border-bottom:1px solid #f0f0f0;display:flex;align-items:center;gap:8px}
.card .in{padding:16px 18px}.tabs{display:flex;gap:4px;padding:10px 12px;border-bottom:1px solid #f0f0f0;flex-wrap:wrap}
.tabs a{padding:6px 12px;border-radius:8px;text-decoration:none;color:#4b5563;font-weight:600}.tabs a.on{background:#111827;color:#fff}
.tools{display:flex;gap:8px;padding:12px;border-bottom:1px solid #f0f0f0}.tools input{flex:1;padding:8px 12px;border:1px solid #e5e7eb;border-radius:8px}
.tools button{padding:8px 14px;border:1px solid #d1d5db;background:#fff;border-radius:8px;font-weight:600;cursor:pointer}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:12px;color:#6b7280;font-weight:600;padding:10px 14px;background:#fafafa;border-bottom:1px solid #f0f0f0}
td{padding:11px 14px;border-bottom:1px solid #f3f4f6;vertical-align:middle}tr.r:hover td{background:#fafaff}tr.r td a.o{font-weight:700;text-decoration:none}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;align-items:start}.stack{display:grid;gap:18px}
.item{display:flex;gap:14px;align-items:center;padding:12px 18px;border-bottom:1px solid #f3f4f6}.thumb{width:46px;height:46px;border-radius:9px;
background:linear-gradient(135deg,#eef2ff,#e0e7ff);display:grid;place-items:center;font-weight:800;color:#4338ca;flex:none}
.sum{display:grid;grid-template-columns:1fr auto;gap:8px 16px;padding:16px 18px}.sum .tot{font-weight:800;border-top:1px solid #f0f0f0;padding-top:10px}
.tl{padding:6px 18px 16px}.ev{display:grid;grid-template-columns:14px 1fr;gap:12px;padding:10px 0;position:relative}
.ev::before{content:"";position:absolute;left:6px;top:24px;bottom:-8px;width:2px;background:#eef0f3}.ev:last-child::before{display:none}
.dot{width:14px;height:14px;border-radius:50%;background:#c7d2fe;border:3px solid #fff;box-shadow:0 0 0 1px #c7d2fe;margin-top:3px}
.ev.alert .dot{background:#fca5a5;box-shadow:0 0 0 1px #fca5a5}.kv{display:grid;gap:4px}.kv b{font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-top:8px}
.refund{background:#fff7f7;border:1px solid #fde2e2;border-radius:10px;padding:14px;margin:0 18px 16px}
.dispute{background:#fff8eb;border:1px solid #fde7b0;border-radius:10px;padding:14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}.kpi{padding:16px 18px}.kpi .v{font-size:24px;font-weight:800;margin-top:4px}
.tag{display:inline-block;background:#f3f4f6;border-radius:6px;padding:2px 8px;font-size:12px;margin:2px 4px 2px 0}
.note{width:100%;min-height:70px;border:1px solid #e5e7eb;border-radius:8px;padding:10px}
"""


def pay_badge(p: str) -> str:
    return f'<span class="badge {"b-green" if p == "Payé" else "b-red" if p == "Remboursé" else "b-amber"}">{e(p)}</span>'


def ful_badge(t: str) -> str:
    cls = {"Livrée": "b-grey", "Expédiée": "b-blue", "À expédier": "b-amber", "Anomalie transport": "b-red"}.get(t, "b-grey")
    return f'<span class="badge {cls}">{e(t)}</span>'


def admin_shell(active: str, inner: str, q: str = "") -> str:
    n_lit = sum(1 for o in DATA["orders"].values() if o["litige"])
    nav = [("home", "/admin", "🏠", "Accueil"), ("orders", "/admin/orders", "🧾", "Commandes"),
           ("customers", "/admin/customers", "👤", "Clients"), ("products", "/admin/products", "🏷️", "Produits"),
           ("analytics", "/admin/analytics", "📊", "Analyses")]
    links = "".join(f'<a class="{"on" if k == active else ""}" href="{h}">{ic} {lbl}'
                    f'{f"<span class=cnt>{n_lit}</span>" if k == "orders" else ""}</a>' for k, h, ic, lbl in nav)
    body = f"""<div class="top"><div class="brand"><i>S</i>Sportiva Admin</div>
<form action="/admin/orders"><input name="q" value="{e(q)}" placeholder="Rechercher une commande, un client, un e-mail…"></form>
<div class="me">ops@sportiva.test <b>OP</b> <a href="/admin/logout" class="muted">Déconnexion</a></div></div>
<nav class="side">{links}<div class="sep"></div><small>Canaux de vente</small><a href="#">🛒 Boutique en ligne</a>
<a href="#">📱 Application mobile</a><div class="sep"></div><a href="#">⚙️ Paramètres</a></nav><main>{inner}</main>"""
    return page("Sportiva Admin", body, ADMIN_CSS, "#4f46e5")


def admin_home() -> str:
    orders = list(DATA["orders"].values())
    ca = sum(o["total"] for o in orders)
    lit = [o for o in orders if o["litige"]]
    kpis = [("Ventes (30 j)", eur(ca)), ("Commandes", len(orders)), ("Panier moyen", eur(ca / len(orders))),
            ("Litiges ouverts", len(lit))]
    k = "".join(f'<div class="card kpi"><div class="muted">{a}</div><div class="v">{b}</div></div>' for a, b in kpis)
    rows = "".join(f'<tr class="r"><td><a class="o" href="/admin/orders/{o["id"]}">{o["id"]}</a></td><td>{fdate(o["date"], False)}</td>'
                   f'<td>{e(DATA["clients"][o["client_email"]]["nom"])}</td><td>{eur(o["total"])}</td><td>{pay_badge(o["paiement"])}</td></tr>'
                   for o in lit[:8])
    inner = f"""<div class="head"><h1>Bonjour 👋</h1><span class="muted">Voici l'activité de la boutique.</span></div>
<div class="kpis">{k}</div><div class="card"><h2>⚠️ Commandes avec une contestation de paiement</h2>
<table><tr><th>Commande</th><th>Date</th><th>Client</th><th>Total</th><th>Paiement</th></tr>{rows}</table>
<div class="in"><a href="/admin/orders?vue=litiges">Voir tous les litiges →</a></div></div>"""
    return admin_shell("home", inner)


def admin_orders(q: str, vue: str) -> str:
    ql = q.lower().strip()
    out = []
    for oid in DATA["order_list"]:
        o = DATA["orders"][oid]
        c = DATA["clients"][o["client_email"]]
        if vue == "litiges" and not o["litige"]:
            continue
        if vue == "a_traiter" and o["traitement"] != "À expédier":
            continue
        if vue == "remboursees" and o["paiement"] == "Payé":
            continue
        if ql and ql not in f'{o["id"]} {o["client_email"]} {c["nom"]} {o.get("suivi") or ""}'.lower():
            continue
        out.append(o)
    tabs = "".join(f'<a class="{"on" if vue == k else ""}" href="/admin/orders?vue={k}{"&q=" + quote(q) if q else ""}">{lbl}</a>'
                   for k, lbl in [("toutes", "Toutes"), ("a_traiter", "À expédier"), ("litiges", "Litiges"), ("remboursees", "Remboursées")])
    rows = "".join(f"""<tr class="r"><td><a class="o" href="/admin/orders/{o['id']}">{o['id']}</a>{' <span class="badge b-violet">Litige</span>' if o['litige'] else ''}</td>
<td>{fdate(o['date'], False)}</td><td>{e(DATA['clients'][o['client_email']]['nom'])}</td><td>{eur(o['total'])}</td>
<td>{pay_badge(o['paiement'])}</td><td>{ful_badge(o['traitement'])}</td><td class="muted">{sum(a['qte'] for a in o['articles'])} article(s)</td></tr>"""
                   for o in out[:60])
    empty = '<tr><td colspan="7" class="muted" style="padding:28px;text-align:center">Aucune commande ne correspond à cette recherche.</td></tr>'
    inner = f"""<div class="head"><h1>Commandes</h1><span class="muted">{len(out)} commande(s)</span></div>
<div class="card"><div class="tabs">{tabs}</div><form class="tools" action="/admin/orders"><input type="hidden" name="vue" value="{e(vue)}">
<input name="q" value="{e(q)}" placeholder="Filtrer par n° de commande, client, e-mail ou n° de suivi"><button>Rechercher</button></form>
<table><tr><th>Commande</th><th>Date</th><th>Client</th><th>Total</th><th>Paiement</th><th>Traitement</th><th>Articles</th></tr>
{rows or empty}</table></div>"""
    return admin_shell("orders", inner, q)


def admin_order(oid: str) -> str | None:
    o = DATA["orders"].get(oid)
    if not o:
        return None
    c = DATA["clients"][o["client_email"]]
    items = "".join(f"""<div class="item"><div class="thumb">{e(a['nom'][0])}</div><div style="flex:1"><div style="font-weight:600">{e(a['nom'])}</div>
<div class="muted">SKU : {e(a['sku'])}</div></div><div class="muted">{eur(a['prix'])} × {a['qte']}</div><div style="width:90px;text-align:right;font-weight:600">{eur(a['prix'] * a['qte'])}</div></div>"""
                    for a in o["articles"])
    rb = o.get("remboursement")
    paid_line = f"<span>Payé par le client</span><span>{eur(o['total'])}</span>"
    if rb:
        paid_line += f"<span style='color:#b42318'>Remboursé</span><span style='color:#b42318'>− {eur(rb['montant'])}</span><span class='tot'>Montant net</span><span class='tot'>{eur(o['total'] - rb['montant'])}</span>"
    refund = (f"""<div class="refund"><b>💸 Remboursement effectué le {fdate(rb['date'], False)}</b> — {eur(rb['montant'])} (réf. {e(rb['ref'])})<br>
<span class="muted">Justificatif de remboursement — référence de preuve à transmettre :</span> <code class="ref">{e(rb['preuve'])}</code></div>""" if rb else "")
    ship = ""
    if o.get("suivi"):
        sh = DATA["shipments"].get(o["suivi"], {})
        ship = f"""<div class="card"><h2>🚚 Expédition {ful_badge(o['traitement'])}</h2><div class="in kv">
<div>Transporteur : <b style="text-transform:none;font-size:14px;color:#111827">Parcelia — {e(sh.get('service', ''))}</b></div>
<div>Numéro de suivi : <code class="ref">{e(o['suivi'])}</code></div>
<div class="muted">Le suivi détaillé et la preuve de livraison sont disponibles sur le portail Parcelia Pro.</div></div></div>"""
    tl = "".join(f'<div class="ev {"alert" if ("contestation" in ev["texte"] or "anomalie" in ev["texte"]) else ""}"><div class="dot"></div>'
                 f'<div><div>{e(ev["texte"])}</div><div class="muted">{fdate(ev["date"])}</div></div></div>'
                 for ev in reversed(o["chronologie"]))
    dispute = ("""<div class="card"><h2>⚖️ Litige</h2><div class="in"><div class="dispute"><b>Contestation de paiement ouverte</b><br>
<span class="muted">La banque du client conteste ce paiement. Le litige se traite dans le Dashboard Stripe.</span></div></div></div>""" if o["litige"] else "")
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in o["tags"]) or '<span class="muted">Aucune étiquette</span>'
    inner = f"""<div class="head"><a href="/admin/orders" class="muted" style="text-decoration:none">← Commandes</a></div>
<div class="head"><h1>{o['id']}</h1>{pay_badge(o['paiement'])}{ful_badge(o['traitement'])}<span class="muted">{fdate(o['chronologie'][0]['date'])} · Boutique en ligne</span></div>
<div class="grid"><div class="stack">
<div class="card"><h2>📦 Articles</h2>{items}</div>
<div class="card"><h2>💳 Paiement {pay_badge(o['paiement'])}</h2><div class="sum"><span>Sous-total</span><span>{eur(o['total'])}</span>
<span>Livraison</span><span>Offerte</span><span class="muted">dont TVA (20 %)</span><span class="muted">{eur(o['tva'])}</span>
<span class="tot">Total</span><span class="tot">{eur(o['total'])}</span>{paid_line}</div>{refund}</div>
{ship}<div class="card"><h2>🕒 Chronologie</h2><div class="tl">{tl}</div></div></div>
<div class="stack"><div class="card"><h2>👤 Client</h2><div class="in kv"><a href="/admin/customers/{quote(o['client_email'])}" style="font-weight:700">{e(c['nom'])}</a>
<div class="muted">{c['commandes']} commande(s) · client depuis {e(c['depuis'])}</div><b>Coordonnées</b><div>{e(o['client_email'])}</div>
<b>Adresse de livraison</b><div>{e(c['nom'])}<br>{e(o['adresse'])}<br>France</div></div></div>
{dispute}<div class="card"><h2>🏷️ Étiquettes</h2><div class="in">{tags}</div></div>
<div class="card"><h2>📝 Notes</h2><div class="in"><textarea class="note" placeholder="Ajouter une note interne…"></textarea></div></div></div></div>"""
    return admin_shell("orders", inner)


def admin_customers(q: str) -> str:
    ql = q.lower().strip()
    rows = []
    for email, c in sorted(DATA["clients"].items(), key=lambda kv: kv[1]["nom"]):
        if ql and ql not in f"{email} {c['nom']}".lower():
            continue
        n = [o for o in DATA["orders"].values() if o["client_email"] == email]
        rows.append(f'<tr class="r"><td><a class="o" href="/admin/customers/{quote(email)}">{e(c["nom"])}</a></td><td class="muted">{e(email)}</td>'
                    f'<td>{e(c["cp"])} {e(c["ville"])}</td><td>{c["commandes"]}</td><td>{eur(sum(o["total"] for o in n))}</td></tr>')
    inner = f"""<div class="head"><h1>Clients</h1><span class="muted">{len(rows)} client(s)</span></div><div class="card">
<form class="tools" action="/admin/customers"><input name="q" value="{e(q)}" placeholder="Rechercher un client"><button>Rechercher</button></form>
<table><tr><th>Client</th><th>E-mail</th><th>Ville</th><th>Commandes</th><th>Dépensé (boutique)</th></tr>{''.join(rows)}</table></div>"""
    return admin_shell("customers", inner)


def admin_customer(email: str) -> str | None:
    c = DATA["clients"].get(email)
    if not c:
        return None
    orders = [o for o in DATA["orders"].values() if o["client_email"] == email]
    rows = "".join(f'<tr class="r"><td><a class="o" href="/admin/orders/{o["id"]}">{o["id"]}</a></td><td>{fdate(o["date"], False)}</td>'
                   f'<td>{eur(o["total"])}</td><td>{pay_badge(o["paiement"])}</td><td>{ful_badge(o["traitement"])}</td></tr>' for o in orders)
    inner = f"""<div class="head"><a href="/admin/customers" class="muted" style="text-decoration:none">← Clients</a></div>
<div class="head"><h1>{e(c['nom'])}</h1><span class="muted">{e(c['ville'])} · client depuis {e(c['depuis'])}</span></div>
<div class="grid"><div class="card"><h2>Commandes</h2><table><tr><th>Commande</th><th>Date</th><th>Total</th><th>Paiement</th><th>Traitement</th></tr>{rows}</table></div>
<div class="card"><h2>Coordonnées</h2><div class="in kv"><div>{e(email)}</div><b>Adresse</b><div>{e(c['cp'])} {e(c['ville'])}, France</div>
<b>Historique</b><div>{c['commandes']} commande(s) au total</div></div></div></div>"""
    return admin_shell("customers", inner)


def admin_stub(active: str, title: str) -> str:
    return admin_shell(active, f'<div class="head"><h1>{title}</h1></div><div class="card"><div class="in muted">Cette section n\'est pas utilisée dans la démo.</div></div>')


# ============================================================================ Parcelia Pro
PARCELIA_CSS = """
body{background:#f4f6f9;color:#0f172a}.bar{background:#0c1b33;color:#fff;height:62px;display:flex;align-items:center;padding:0 28px;gap:28px}
.bar .lg{display:flex;align-items:center;gap:10px;font-weight:800;font-size:19px;letter-spacing:-.01em}
.bar .lg i{width:32px;height:32px;border-radius:50%;background:conic-gradient(#14b8a6 0 70%,#5eead4 0);display:inline-block}
.bar nav a{color:#cbd5e1;text-decoration:none;margin-right:20px;font-weight:600}.bar nav a.on{color:#fff;border-bottom:2px solid #14b8a6;padding-bottom:19px}
.bar .acc{margin-left:auto;color:#94a3b8;font-size:13px}.bar .acc a{color:#5eead4;margin-left:12px}
.wrap{max-width:1120px;margin:0 auto;padding:28px}.hero{background:linear-gradient(120deg,#0f2a4f,#0c1b33);color:#fff;border-radius:16px;padding:26px 28px;margin-bottom:22px}
.hero h1{margin:0 0 14px;font-size:22px}.hero form{display:flex;gap:10px}.hero input{flex:1;padding:13px 14px;border-radius:10px;border:0;font-size:15px}
.hero button,.btn{background:#14b8a6;color:#04201d;border:0;border-radius:10px;padding:12px 20px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}
.box{background:#fff;border-radius:14px;border:1px solid #e2e8f0;margin-bottom:20px;overflow:hidden}.box h2{font-size:15px;margin:0;padding:16px 20px;border-bottom:1px solid #eef2f7}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:12px;color:#64748b;padding:10px 20px;background:#f8fafc;text-transform:uppercase;letter-spacing:.04em}
td{padding:12px 20px;border-top:1px solid #f1f5f9}td a{font-weight:700;color:#0f766e;text-decoration:none}
.status{padding:22px 24px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}.status .big{font-size:24px;font-weight:800}
.ok{color:#047857}.ko{color:#b42318}.mid{color:#b45309}.blue{color:#1d4ed8}
.steps{display:grid;grid-template-columns:repeat(4,1fr);padding:0 24px 24px;gap:8px}.step{text-align:center;font-size:12px;color:#94a3b8;font-weight:600}
.step i{display:block;height:6px;border-radius:9px;background:#e2e8f0;margin-bottom:8px}.step.done{color:#0f766e}.step.done i{background:#14b8a6}
.step.bad{color:#b42318}.step.bad i{background:#f87171}
.two{display:grid;grid-template-columns:1.25fr 1fr;gap:20px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px;padding:18px 20px}
.meta div small{display:block;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:700}
.pod{padding:18px 20px}.pod .sig{background:#fbfdff;border:1px dashed #cbd5e1;border-radius:10px;padding:8px;margin:10px 0}
.alert{background:#fef2f2;border:1px solid #fecaca;color:#991b1b;border-radius:10px;padding:14px 16px;margin:0 20px 18px}
.warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:10px;padding:14px 16px;margin:0 20px 18px}
"""


def parcelia_shell(active: str, inner: str) -> str:
    body = f"""<div class="bar"><div class="lg"><i></i>Parcelia <span style="font-weight:400;color:#5eead4">Pro</span></div>
<nav><a class="{'on' if active == 'envois' else ''}" href="/parcelia">Envois</a><a href="#">Enlèvements</a><a href="#">Facturation</a><a href="#">Réclamations</a></nav>
<div class="acc">Compte SPORTIVA-PRO · Sportiva SAS<a href="/parcelia/logout">Déconnexion</a></div></div><div class="wrap">{inner}</div>"""
    return page("Parcelia Pro", body, PARCELIA_CSS, "#14b8a6")


def ship_badge(s: dict) -> str:
    cls = {"livre_signe": "b-green", "boite_aux_lettres": "b-amber", "perdu": "b-red", "en_transit": "b-blue"}.get(s["code"], "b-grey")
    return f'<span class="badge {cls}">{e(s["statut"])}</span>'


def parcelia_home(q: str) -> str:
    ql = q.strip().upper()
    items = list(DATA["shipments"].values())
    if ql:
        items = [s for s in items if ql in s["tracking"] or ql in s["order_id"]]
        if len(items) == 1:
            return None  # redirection vers le détail
    items.sort(key=lambda s: s["evenements"][0]["date"], reverse=True)
    rows = "".join(f'<tr><td><a href="/parcelia/shipments/{s["tracking"]}">{s["tracking"]}</a></td><td>{e(s["order_id"])}</td>'
                   f'<td>{e(s["destination"])}</td><td>{ship_badge(s)}</td><td>{fdate(s["evenements"][-1]["date"])}</td></tr>' for s in items[:40])
    empty = f'<tr><td colspan="5" style="padding:26px;text-align:center;color:#64748b">Aucun envoi trouvé pour « {e(q)} ».</td></tr>'
    inner = f"""<div class="hero"><h1>Suivre un envoi</h1><form action="/parcelia"><input name="q" value="{e(q)}" placeholder="Numéro de suivi (PRC…) ou référence client (CMD-…)">
<button>Suivre</button></form></div><div class="box"><h2>{'Résultats' if q else 'Envois récents'} · {len(items)}</h2>
<table><tr><th>N° de suivi</th><th>Référence client</th><th>Destination</th><th>Statut</th><th>Dernier événement</th></tr>{rows or empty}</table></div>"""
    return parcelia_shell("envois", inner)


def _xy(lat, lon, w=300, h=290):
    return (lon + 5.3) / 13.9 * w, (51.4 - lat) / 9.2 * h


def france_map(dest_city: str, perdu: bool) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (_xy(lat, lon) for lon, lat in FRANCE))
    hx, hy = _xy(*GEO["Lyon-Saint-Exupéry"])
    dx, dy = _xy(*GEO.get(dest_city, GEO["Paris"]))
    mx, my = (hx + dx) / 2 + (dy - hy) * 0.15, (hy + dy) / 2 - (dx - hx) * 0.15
    color = "#ef4444" if perdu else "#14b8a6"
    end = (f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="7" fill="#fff" stroke="{color}" stroke-width="3"/>' if not perdu else
           f'<text x="{(hx + dx) / 2:.0f}" y="{(hy + dy) / 2:.0f}" font-size="18" text-anchor="middle">❓</text>')
    return f"""<svg viewBox="0 0 300 290" width="100%" style="display:block;background:#f8fafc">
<polygon points="{pts}" fill="#e2e8f0" stroke="#cbd5e1" stroke-width="1.5"/>
<path d="M{hx:.1f},{hy:.1f} Q{mx:.1f},{my:.1f} {dx:.1f},{dy:.1f}" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{'6 6' if perdu else '0'}"/>
<circle cx="{hx:.1f}" cy="{hy:.1f}" r="6" fill="#0c1b33"/><text x="{hx + 9:.0f}" y="{hy + 4:.0f}" font-size="10" fill="#0c1b33" font-weight="700">Hub Lyon</text>
{end}<text x="{dx + 10:.0f}" y="{dy - 8:.0f}" font-size="11" fill="#0f172a" font-weight="700">{e(dest_city)}</text></svg>"""


def signature(name: str) -> str:
    r = random.Random(name)
    x, y, d = 18.0, 50.0, ""
    d = f"M{x:.0f},{y:.0f}"
    for _ in range(9):
        x += 22 + r.random() * 14
        d += f" C{x - 18:.0f},{y - 34 * r.random():.0f} {x - 6:.0f},{y + 30 * r.random():.0f} {x:.0f},{y + (r.random() - .5) * 18:.0f}"
    d += f" M{24 + r.random() * 30:.0f},{70 + r.random() * 6:.0f} L{x - 10:.0f},{62 + r.random() * 8:.0f}"
    return (f'<svg viewBox="0 0 320 90" width="100%" height="90"><path d="{d}" fill="none" stroke="#1e293b" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def gps(s: dict) -> str:
    city = s["destination"].split(" ", 1)[1]
    lat, lon = GEO.get(city, GEO["Paris"])
    r = random.Random(s["tracking"])
    return f"{lat + (r.random() - .5) * .04:.5f}, {lon + (r.random() - .5) * .04:.5f}"


def parcelia_shipment(trk: str) -> str | None:
    s = DATA["shipments"].get(trk)
    if not s:
        return None
    city = s["destination"].split(" ", 1)[1]
    code = s["code"]
    order = ["Pris en charge", "En transit", "En cours de livraison", "Livré"]
    reached = {"en_transit": 2, "perdu": 2, "livre_signe": 4, "boite_aux_lettres": 4}.get(code, 1)
    steps = "".join(f'<div class="step {"bad" if code == "perdu" and i == 2 else "done" if i < reached else ""}"><i></i>{lbl}</div>'
                    for i, lbl in enumerate(order))
    cls = {"livre_signe": "ok", "boite_aux_lettres": "mid", "perdu": "ko", "en_transit": "blue"}[code]
    ev = "".join(f'<tr><td>{fdate(x["date"], False)}</td><td>{x["date"][11:16]}</td><td>{e(x["lieu"])}</td><td>{e(x["detail"])}</td></tr>'
                 for x in reversed(s["evenements"]))
    if code == "livre_signe":
        pod = f"""<div class="pod"><b>✍️ Remis contre signature</b><div class="sig">{signature(s['signe_par'])}</div>
<div>Signé par : <b>{e(s['signe_par'])}</b> · {fdate(s['evenements'][-1]['date'])}</div><div style="color:#64748b">Position GPS du livreur : {gps(s)}</div>
<div style="margin-top:12px">Référence de preuve à transmettre : <code class="ref">{e(s['preuve'])}</code></div>
<div style="margin-top:14px"><a class="btn" href="/parcelia/shipments/{trk}/pod">Ouvrir la preuve de livraison (POD)</a></div></div>"""
    elif code == "boite_aux_lettres":
        pod = f"""<div class="warn">Livré <b>sans signature</b> : colis déposé dans la boîte aux lettres du destinataire.</div><div class="pod">
<div>Photo de dépôt : non disponible pour ce service.</div><div style="color:#64748b">Position GPS du livreur : {gps(s)}</div>
<div style="margin-top:12px">Référence de preuve : <code class="ref">{e(s['preuve'])}</code></div>
<div style="margin-top:14px"><a class="btn" href="/parcelia/shipments/{trk}/pod">Ouvrir l'attestation de dépôt</a></div></div>"""
    elif code == "perdu":
        pod = f"""<div class="alert"><b>Anomalie : colis non localisé.</b> Une enquête a été ouverte. Aucune preuve de livraison n'existe pour cet envoi.</div>
<div class="pod">Référence de preuve : <code class="ref">{e(s['preuve'])}</code></div>"""
    else:
        pod = '<div class="pod" style="color:#64748b">Le colis est en cours d\'acheminement. La preuve de livraison sera disponible après la remise.</div>'
    inner = f"""<div style="margin-bottom:14px"><a href="/parcelia" style="color:#0f766e;font-weight:700;text-decoration:none">← Tous les envois</a></div>
<div class="box"><div class="status"><div><div style="color:#64748b;font-size:12px;font-weight:700;letter-spacing:.05em">ENVOI {e(trk)} · RÉF. CLIENT {e(s['order_id'])}</div>
<div class="big {cls}">{e(s['statut'])}</div></div></div><div class="steps">{steps}</div></div>
<div class="two"><div><div class="box"><h2>Historique des événements</h2><table><tr><th>Date</th><th>Heure</th><th>Lieu</th><th>Événement</th></tr>{ev}</table></div>
<div class="box"><h2>Détails de l'envoi</h2><div class="meta"><div><small>Service</small>{e(s['service'])}</div><div><small>Poids</small>{s['poids_kg']} kg</div>
<div><small>Expéditeur</small>Sportiva SAS — Lyon</div><div><small>Destination</small>{e(s['destination'])}</div></div></div></div>
<div><div class="box"><h2>Preuve de livraison</h2>{pod}</div><div class="box"><h2>Trajet</h2>{france_map(city, code == 'perdu')}</div></div></div>"""
    return parcelia_shell("envois", inner)


def parcelia_pod(trk: str) -> str | None:
    s = DATA["shipments"].get(trk)
    if not s or s["code"] not in ("livre_signe", "boite_aux_lettres"):
        return None
    signed = s["code"] == "livre_signe"
    css = """body{background:#e5e7eb;padding:30px}.doc{max-width:760px;margin:0 auto;background:#fff;padding:44px 50px;box-shadow:0 8px 30px rgba(0,0,0,.12)}
.h{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #0c1b33;padding-bottom:14px}.h b{font-size:22px}
table{width:100%;border-collapse:collapse;margin-top:22px}td{padding:9px 0;border-bottom:1px solid #eee}td:first-child{color:#64748b;width:42%}
.sig{border:1px solid #cbd5e1;border-radius:8px;margin-top:8px}.pr{margin-top:26px}@media print{body{background:#fff;padding:0}.pr{display:none}.doc{box-shadow:none}}"""
    sig = f'<tr><td>Signature</td><td><div class="sig">{signature(s["signe_par"])}</div></td></tr>' if signed else ""
    body = f"""<div class="doc"><div class="h"><b>Parcelia</b><span>{'Preuve de livraison (POD)' if signed else 'Attestation de dépôt'}</span></div>
<table><tr><td>Numéro de suivi</td><td><b>{e(trk)}</b></td></tr><tr><td>Référence client</td><td>{e(s['order_id'])}</td></tr>
<tr><td>Expéditeur</td><td>Sportiva SAS — Lyon</td></tr><tr><td>Destination</td><td>{e(s['destination'])}</td></tr>
<tr><td>Date et heure de remise</td><td>{fdate(s['evenements'][-1]['date'])}</td></tr>
<tr><td>Mode de remise</td><td>{'Remis en main propre contre signature' if signed else 'Déposé en boîte aux lettres, sans signature'}</td></tr>
<tr><td>Réceptionnaire</td><td>{e(s['signe_par']) if signed else '—'}</td></tr><tr><td>Position GPS</td><td>{gps(s)}</td></tr>{sig}
<tr><td>Référence de preuve à transmettre</td><td><code class="ref">{e(s['preuve'])}</code></td></tr></table>
<p style="color:#64748b;font-size:12px;margin-top:22px">Document généré par le portail Parcelia Pro. Données fictives de démonstration.</p>
<div class="pr"><button onclick="window.print()" style="padding:10px 16px">Imprimer / Enregistrer en PDF</button>
<a href="/parcelia/shipments/{e(trk)}" style="margin-left:14px">← Retour à l'envoi</a></div></div>"""
    return page(f"POD {trk} · Parcelia", body, css, "#14b8a6")


# ============================================================================ Sportiva Care
CARE_CSS = """
body{background:#f2f7f6;color:#0f2a26}.app{display:grid;grid-template-columns:72px 380px 1fr;height:100vh}
.rail{background:#0f3d38;display:flex;flex-direction:column;align-items:center;padding:16px 0;gap:18px}
.rail i{width:40px;height:40px;border-radius:12px;background:#2dd4bf;display:grid;place-items:center;font-style:normal;font-weight:900;color:#0f3d38}
.rail a{color:#99f6e4;text-decoration:none;font-size:20px}.rail .out{margin-top:auto;font-size:12px}
.list{background:#fff;border-right:1px solid #dcebe7;overflow:auto}.list .hd{padding:18px 18px 10px}.list h1{margin:0 0 10px;font-size:18px}
.list input{width:100%;padding:9px 12px;border:1px solid #cfe3de;border-radius:10px}.t{display:block;padding:14px 18px;border-top:1px solid #eef5f3;text-decoration:none}
.t:hover{background:#f6fbfa}.t.on{background:#e6f6f2;border-left:3px solid #0f766e}.t small{color:#5b7a73}.t .s{font-weight:700;margin:2px 0}
.conv{overflow:auto;padding:26px 34px}.meta{color:#5b7a73;margin:6px 0 20px}.msg{max-width:660px;padding:12px 16px;border-radius:16px;margin:12px 0;line-height:1.5}
.msg.client{background:#fff;border:1px solid #dcebe7}.msg.agent{background:#0f766e;color:#fff;margin-left:auto}.who{font-size:12px;opacity:.7;margin-bottom:4px}
.exp{margin-top:24px;max-width:660px;background:#fff;border:1px dashed #0f766e;border-radius:12px;padding:14px 16px}
"""


def care_page(q: str, tid: str | None) -> str:
    ql = q.lower().strip()
    ts = [t for t in DATA["tickets"] if not ql or ql in f'{t["email"]} {t["client"]} {t["commande"]} {t["id"]} {t["sujet"]}'.lower()]
    items = "".join(f'<a class="t {"on" if t["id"] == tid else ""}" href="/care/tickets/{quote(t["id"][1:])}?q={quote(q)}">'
                    f'<span class="badge {"b-green" if t["statut"] == "Résolu" else "b-amber"}" style="float:right">{e(t["statut"])}</span>'
                    f'<div class="s">{e(t["sujet"])}</div><small>{e(t["client"])} · {e(t["commande"])} · {fdate(t["date"], False)}</small></a>' for t in ts)
    t = next((x for x in DATA["tickets"] if x["id"] == tid), None)
    if t:
        msgs = "".join(f'<div class="msg {m[0]}"><div class="who">{e(t["client"]) if m[0] == "client" else "Agent Sportiva Care"}</div>{e(m[1])}</div>'
                       for m in t["messages"])
        conv = f"""<h2 style="margin:0">{e(t['sujet'])}</h2><div class="meta">Ticket {e(t['id'])} · {e(t['client'])} &lt;{e(t['email'])}&gt; ·
commande {e(t['commande'])} · ouvert le {fdate(t['date'], False)} · <span class="badge {'b-green' if t['statut'] == 'Résolu' else 'b-amber'}">{e(t['statut'])}</span></div>
{msgs}<div class="exp">📎 <b>Export de la conversation</b> (pièce justificative) — référence de preuve : <code class="ref">{e(t['preuve'])}</code></div>"""
    else:
        conv = '<p style="color:#5b7a73">Sélectionne un ticket, ou recherche un client, un e-mail ou un numéro de commande.</p>'
    body = f"""<div class="app"><div class="rail"><i>C</i><a href="/care" title="Tickets">💬</a><a href="#" title="Clients">👥</a>
<a href="#" title="Rapports">📈</a><a class="out" href="/care/logout">Quitter</a></div>
<div class="list"><div class="hd"><h1>Tickets</h1><form action="/care"><input name="q" value="{e(q)}" placeholder="Rechercher : e-mail, nom, n° de commande"></form></div>
{items or '<div class="t"><small>Aucun ticket trouvé.</small></div>'}</div><div class="conv">{conv}</div></div>"""
    return page("Sportiva Care", body, CARE_CSS, "#0f766e")


# ============================================================================ serveur
INDEX = page("Sportiva — outils internes", """<div style="max-width:720px;margin:60px auto;padding:0 20px">
<h1 style="margin-bottom:4px">Sportiva — outils internes</h1><p style="color:#6b7280">Environnement de démonstration. Marques et données fictives.</p>
<p><a href="/admin">🧾 Sportiva Admin</a> — back-office (commandes, clients, remboursements)</p>
<p><a href="/parcelia">🚚 Parcelia Pro</a> — portail transporteur (suivi, preuve de livraison)</p>
<p><a href="/care">💬 Sportiva Care</a> — support client (tickets)</p></div>""")


class H(BaseHTTPRequestHandler):
    server_version = "Sportiva/1.0"

    def log_message(self, fmt, *args):
        pass

    def send_html(self, body: str, code: int = 200, headers: dict | None = None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, to: str, cookie: str | None = None):
        self.send_response(303)
        self.send_header("Location", to)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def not_found(self):
        self.send_html(page("Introuvable", '<div style="padding:60px;text-align:center"><h1>Page introuvable</h1><a href="/">Accueil</a></div>'), 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        parts = path.strip("/").split("/")
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
        rest = parts[1:]
        out = None
        if app == "admin":
            if not rest:
                out = admin_home()
            elif rest == ["orders"]:
                out = admin_orders(q.get("q", ""), q.get("vue", "toutes"))
            elif len(rest) == 2 and rest[0] == "orders":
                out = admin_order(rest[1])
            elif rest == ["customers"]:
                out = admin_customers(q.get("q", ""))
            elif len(rest) == 2 and rest[0] == "customers":
                from urllib.parse import unquote
                out = admin_customer(unquote(rest[1]))
            elif rest in (["products"], ["analytics"]):
                out = admin_stub(rest[0], "Produits" if rest[0] == "products" else "Analyses")
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
