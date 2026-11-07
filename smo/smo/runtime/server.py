"""Serveur SMO (Railway) : répond aux tools des agents H et expose les tools compilés pour les tests.

    uv run smo serve        # http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from hai_agents.webhook_verification import WebhookVerificationError, verify_webhook

from ..config import load
from .tools import input_schema, load_tools
from .worker import Worker


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
settings = load()
worker = Worker(settings) if settings.hai_api_key else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if worker and os.environ.get("SMO_POLL", "1") == "1":
        threading.Thread(target=worker.poll_forever, daemon=True).start()
    yield


app = FastAPI(title="SMO", lifespan=lifespan)


def check_token(x_smo_token: str | None = Header(default=None)) -> None:
    if settings.server_token and x_smo_token != settings.server_token:
        raise HTTPException(401, "X-SMO-Token invalide")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "worker": worker is not None, "tools": sorted(load_tools(settings.tools_dir)),
            "serving": sorted(worker.active) if worker else []}


@app.get("/tools", dependencies=[Depends(check_token)])
def list_tools() -> list[dict]:
    return [{"name": t.name, "description": t.description, "params": input_schema(t.params)}
            for t in load_tools(settings.tools_dir).values()]


def _tool(name: str):
    tool = load_tools(settings.tools_dir).get(name)
    if tool is None:
        raise HTTPException(404, f"Tool inconnu : {name}")
    return tool


@app.post("/tools/{name}/precheck", dependencies=[Depends(check_token)])
def precheck(name: str) -> dict:
    return _tool(name).precheck(settings)


@app.post("/tools/{name}/run", dependencies=[Depends(check_token)])
def run(name: str, params: dict) -> dict:
    return _tool(name).run(settings, **params)


@app.post("/sessions/{session_id}/attach", dependencies=[Depends(check_token)])
def attach(session_id: str) -> dict:
    if worker is None:
        raise HTTPException(503, "HAI_API_KEY absente")
    return {"attached": worker.attach(session_id)}


@app.post("/webhooks/h")
async def h_webhook(request: Request) -> dict:
    if worker is None or not settings.h_webhook_secret:
        raise HTTPException(503, "worker ou H_WEBHOOK_SECRET absent")
    try:
        event = verify_webhook(await request.body(), request.headers.get("X-H-Webhook-Signature", ""),
                               request.headers.get("X-H-Webhook-Timestamp", ""), settings.h_webhook_secret)
    except WebhookVerificationError as err:
        raise HTTPException(401, str(err))
    attached = event.type.startswith("session.") and worker.on_webhook(event.data)
    return {"received": event.type, "attached": attached}
