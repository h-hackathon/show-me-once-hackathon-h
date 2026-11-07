"""Écran de démo « € récupérés » : http://localhost:8787 — lit Stripe en direct pendant que les agents travaillent.

La clé Stripe reste sur ton ordinateur (le serveur est local) : rien n'est publié.
"""
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .checker import check, summary
from .seed import load

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Show me once · litiges en direct</title>
<style>
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e8ecff}
header{padding:22px 36px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e2748}
h1{margin:0;font-size:22px}.live{color:#4ade80;font-weight:700}.live::before{content:'● ';animation:b 1.2s infinite}
@keyframes b{50%{opacity:.2}}
.kpis{display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr;gap:16px;padding:24px 36px}
.k{background:#141b34;border-radius:16px;padding:20px}.k .l{color:#8b95c9;font-size:13px;text-transform:uppercase;letter-spacing:.06em}
.k .v{font-size:40px;font-weight:800;margin-top:8px}.big .v{font-size:64px;color:#4ade80}.k .s{color:#8b95c9;margin-top:4px}
.bar{height:10px;background:#1e2748;border-radius:99px;margin-top:14px;overflow:hidden}.bar div{height:100%;background:#4ade80;transition:width .8s}
table{width:calc(100% - 72px);margin:0 36px 36px;border-collapse:collapse}td,th{padding:9px 10px;border-bottom:1px solid #1e2748;text-align:left;font-size:14px}
th{color:#8b95c9;font-weight:600}.chip{padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700}
.won{background:#14532d;color:#86efac}.lost{background:#3f1d1d;color:#fca5a5}.under_review,.warning_under_review{background:#3b3414;color:#fde68a}
.needs_response,.warning_needs_response{background:#1e2748;color:#8b95c9}.accepted{background:#1e2748;color:#c7d2fe}.ok{color:#4ade80}.ko{color:#f87171}
</style></head><body>
<header><h1>⚔️ Cellule litiges — agent Show me once</h1><span class="live">EN DIRECT DEPUIS STRIPE</span></header>
<div class="kpis">
  <div class="k big"><div class="l">€ récupérés</div><div class="v" id="rec">0 €</div><div class="s" id="recs"></div><div class="bar"><div id="recb" style="width:0"></div></div></div>
  <div class="k"><div class="l">Litiges traités</div><div class="v" id="done">0</div><div class="s" id="dones"></div></div>
  <div class="k"><div class="l">Bonnes décisions</div><div class="v" id="ok">0</div><div class="s">contester ou accepter à raison</div></div>
  <div class="k"><div class="l">Fraudeurs bloqués</div><div class="v" id="fr">0</div><div class="s" id="frs"></div></div>
  <div class="k"><div class="l">Contestés à tort</div><div class="v" id="bad">0 €</div><div class="s">litiges qu'il fallait accepter</div></div>
</div>
<table><thead><tr><th>Commande</th><th>Montant</th><th>Statut Stripe</th><th>Décision prise</th><th>Décision attendue</th><th></th></tr></thead><tbody id="rows"></tbody></table>
<script>
const eur = x => x.toLocaleString('fr-FR', {style:'currency', currency:'EUR'});
const LABEL = {won: 'gagné', lost: 'perdu', under_review: 'en examen', warning_under_review: 'en examen',
               needs_response: 'à traiter', warning_needs_response: 'à traiter', accepted: 'accepté'};
const cls = r => (r.statut_stripe === 'lost' && r.fait.startsWith('accepter')) ? 'accepted' : r.statut_stripe;
async function tick(){
  try {
    const d = await (await fetch('/api')).json(); const s = d.summary;
    rec.textContent = eur(s.recupere); recs.textContent = 'sur ' + eur(s.a_recuperer) + ' défendables';
    recb.style.width = (s.a_recuperer ? 100 * s.recupere / s.a_recuperer : 0) + '%';
    done.textContent = (s.n - s.sans_reponse) + ' / ' + s.n; dones.textContent = s.sans_reponse + ' en attente';
    ok.textContent = s.ok + ' / ' + s.n; fr.textContent = s.fraudeurs + ' / ' + s.fraudeurs_total; bad.textContent = eur(s.conteste_a_tort);
    rows.innerHTML = d.rows.map(r => `<tr><td><b>${r.order_id}</b></td><td>${eur(r.montant)}</td>
      <td><span class="chip ${cls(r)}">${LABEL[cls(r)] || r.statut_stripe}</span></td><td>${r.fait}</td><td>${r.attendu}</td>
      <td class="${r.ok ? 'ok' : (r.fait === 'sans réponse' ? '' : 'ko')}">${r.ok ? '✅' : (r.fait === 'sans réponse' ? '⏳' : '❌')}</td></tr>`).join('');
  } catch (e) { console.error(e); }
  setTimeout(tick, 5000);
}
tick();
</script></body></html>"""


def serve(batch: str, port: int = 8787, open_browser: bool = True) -> None:
    rows = load(batch)
    cache = {"t": 0, "data": None}
    lock = threading.Lock()

    def data():
        with lock:
            if time.time() - cache["t"] > 4:
                checked = check(rows)
                cache.update(t=time.time(), data={"summary": summary(checked), "rows": checked})
            return cache["data"]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/api"):
                body, ctype = json.dumps(data(), ensure_ascii=False).encode(), "application/json"
            else:
                body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

    url = f"http://localhost:{port}"
    print(f"📺 Écran de démo : {url}  (lot « {batch} », {len(rows)} litiges) — Ctrl + C pour arrêter")
    if open_browser:
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
