#!/usr/bin/env python3
"""Importe un fichier agent Show Me Once (*.h-agent.json) dans H Company, puis le lance (optionnel).

    export HAI_API_KEY=...
    python3 scripts/import_to_h.py smo-agent-litige-stripe-abc123.h-agent.json
    python3 scripts/import_to_h.py fichier.h-agent.json --run "Analyse le premier litige et recommande accepter/contester"

Aucune dépendance : bibliothèque standard uniquement.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("HAI_BASE_URL", "https://agp.eu.hcompany.ai/api/v2")


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {os.environ['HAI_API_KEY']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--run", metavar="TÂCHE", help="lance une session avec ce message après l'import")
    a = ap.parse_args()
    if not os.getenv("HAI_API_KEY"):
        sys.exit("HAI_API_KEY manquante (export HAI_API_KEY=...)")
    exp = json.load(open(a.file))
    skill = {k: v for k, v in exp["skill"].items() if v is not None}

    code, res = call("POST", "/skills", skill)
    print(f"skill {skill['name']}: " + {201: "créé", 409: "existe déjà"}.get(code, f"ERREUR {code} {res}"))
    if code not in (201, 409):
        sys.exit(1)
    code, res = call("POST", "/agents", exp["agent"])
    print(f"agent {exp['agent']['name']}: " + {201: "créé", 409: "existe déjà"}.get(code, f"ERREUR {code} {res}"))
    if code not in (201, 409):
        sys.exit(1)

    if a.run:
        code, s = call("POST", "/sessions", {"agent": exp["agent"]["name"], "messages": a.run, "timezone": "Europe/Paris"})
        if code >= 400:
            sys.exit(f"session: ERREUR {code} {s}")
        print("session lancée :", s.get("agent_view_url"))
        while True:
            time.sleep(5)
            _, st = call("GET", f"/sessions/{s['id']}/status")
            status = (st or {}).get("status") if isinstance(st, dict) else None
            print("  …", status)
            if status in ("completed", "failed", "timed_out", "interrupted", "idle"):
                break
        _, full = call("GET", f"/sessions/{s['id']}")
        print("\nRéponse de l'agent :\n", json.dumps(full.get("latest_answer"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
