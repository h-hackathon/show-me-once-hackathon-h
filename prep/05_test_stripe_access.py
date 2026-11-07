"""Test go/no-go : l'agent H arrive-t-il à se connecter au Dashboard Stripe (sandbox) ?

Risque principal : Stripe demande souvent un code par e-mail quand on se connecte depuis un nouvel appareil,
et le navigateur de l'agent H est un nouvel appareil à chaque session.
Prérequis dans .env : STRIPE_LOGIN, STRIPE_PASSWORD (compte Stripe créé pour le hackathon, jamais un compte perso).
Usage :
    .venv/bin/python 05_test_stripe_access.py
Ne crée rien dans Stripe : l'agent regarde seulement.
"""
import os
import time

from dotenv import load_dotenv
from pydantic import BaseModel
from hai_agents import Client


load_dotenv()


class Result(BaseModel):
    logged_in: bool
    verification_asked: bool  # Stripe a-t-il demandé un code (e-mail, SMS, 2FA) ou un captcha ?
    payments_page_found: bool
    path_taken: str
    blockers: list[str]


TASK = f"""Go to https://dashboard.stripe.com/login and log in with
email: {os.environ['STRIPE_LOGIN']}
password: {os.environ['STRIPE_PASSWORD']}
If Stripe asks for a verification code, a captcha or 2FA, stop there and report it.
Otherwise make sure you are in the sandbox / test mode, then open the Payments list.
Do NOT create, edit, refund or delete anything. Describe the menu path you used and any blocker."""

client = Client()
start = time.time()
result = client.run_session(agent="h/web-surfer-pro", messages=TASK, answer_schema=Result)
elapsed = time.time() - start

print(f"status   : {result.status}")
print(f"time     : {elapsed:.1f}s")
print(f"events   : {len(result.events) if result.events else 0}")
print(f"answer   : {result.answer}")
