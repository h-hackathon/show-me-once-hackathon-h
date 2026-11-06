"""Test de prise en main de l'Agents API H (préparation, pas le code du produit).

Usage :
    export HAI_API_KEY=hk-...
    python 01_test_agents_api.py "Ta tâche en langage naturel"
Mesure le temps et récupère une réponse structurée.
"""
import sys
import time

from dotenv import load_dotenv
from pydantic import BaseModel
from hai_agents import Client


load_dotenv()  # lit HAI_API_KEY dans .env


class Result(BaseModel):
    success: bool
    summary: str
    blockers: list[str]


TASK = sys.argv[1] if len(sys.argv) > 1 else (
    "Go to news.ycombinator.com and return the title of the top story. "
    "Report any blocker you met (pop-ups, logins, errors)."
)

client = Client()
start = time.time()
result = client.run_session(
    agent="h/web-surfer-pro",
    messages=TASK,
    answer_schema=Result,
)
elapsed = time.time() - start

print(f"status   : {result.status}")
print(f"time     : {elapsed:.1f}s")
print(f"events   : {len(result.events) if result.events else 0}")
print(f"answer   : {result.answer}")
