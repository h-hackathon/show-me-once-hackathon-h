"""Accès direct à Odoo (XML-RPC, adresse locale) : lire ce qui est VRAIMENT saisi, et remettre à zéro.

On ne croit jamais l'agent sur parole : le score vient de la base, pas de son résumé.
"""
import xmlrpc.client

from .config import env

FIELDS = ["id", "ref", "partner_id", "invoice_date", "amount_untaxed", "amount_tax", "amount_total", "state"]


class Odoo:
    def __init__(self):
        self.url = env("ODOO_LOCAL_URL", "http://localhost:8069").rstrip("/")
        self.db = env("ODOO_DB", "hackathon")
        self.login = env("ODOO_LOGIN", required=True)
        self.password = env("ODOO_PASSWORD", required=True)
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, self.login, self.password, {})
        if not self.uid:
            raise SystemExit(f"❌ Connexion Odoo refusée ({self.login} sur {self.url}, base {self.db})")
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def _call(self, model, method, *args, **kw):
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)

    def vendor_bills(self) -> list[dict]:
        bills = self._call("account.move", "search_read", [("move_type", "=", "in_invoice")], fields=FIELDS)
        for b in bills:  # partner_id = [id, "Nom"] ou False
            b["partner"] = b["partner_id"][1] if b.get("partner_id") else ""
        return bills

    def reset_drafts(self) -> int:
        """Supprime les factures fournisseurs en brouillon (entre 2 runs du benchmark). Ne touche pas aux validées."""
        ids = self._call("account.move", "search", [("move_type", "=", "in_invoice"), ("state", "=", "draft")])
        if ids:
            self._call("account.move", "unlink", ids)
        return len(ids)
