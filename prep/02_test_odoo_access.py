"""Vérifie que l'agent H atteint notre Odoo et trouve l'écran des factures fournisseurs.

Prérequis dans .env : ODOO_URL, ODOO_LOGIN, ODOO_PASSWORD (compte de test, jamais un vrai mot de passe perso).
Usage :
    .venv/bin/python 02_test_odoo_access.py
Ne crée rien dans Odoo : l'agent regarde seulement.
"""
import os
import time

from dotenv import load_dotenv
from pydantic import BaseModel
from hai_agents import Client


load_dotenv()


class Result(BaseModel):
    logged_in: bool
    vendor_bills_page_found: bool
    path_taken: str
    blockers: list[str]


TASK = f"""Go to {os.environ['ODOO_URL']} and log in with
email: {os.environ['ODOO_LOGIN']}
password: {os.environ['ODOO_PASSWORD']}
Then open the list of vendor bills (Accounting or Invoicing app > Vendors > Bills).
Do NOT create, edit or delete anything. Describe the menu path you used and any blocker."""

client = Client()
start = time.time()
result = client.run_session(agent="h/web-surfer-pro", messages=TASK, answer_schema=Result)
elapsed = time.time() - start

print(f"status   : {result.status}")
print(f"time     : {elapsed:.1f}s")
print(f"events   : {len(result.events) if result.events else 0}")
print(f"answer   : {result.answer}")
