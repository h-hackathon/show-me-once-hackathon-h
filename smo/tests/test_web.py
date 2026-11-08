"""Page d'enregistrement : l'API vue par le navigateur, sans lancer le vrai pipeline."""
from __future__ import annotations

import dataclasses
import subprocess

import imageio_ffmpeg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from smo import config
from smo.models import CaptureMeta, FrameSet, Transcript, Utterance
from smo.pipeline import capture
from smo.pipeline.orchestrator import NAMES
from smo.runs import Run
from smo.runtime.web import router_for


@pytest.fixture
def s(tmp_path) -> config.Settings:
    return dataclasses.replace(config.load(), runs_dir=tmp_path / "runs", server_token=None, gladia_api_key=None)


@pytest.fixture
def client(s, monkeypatch):
    router, runner = router_for(s)
    started: list[str] = []
    monkeypatch.setattr(runner, "start", lambda run: started.append(run.id) or True)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        c.started = started
        yield c


def test_config_lists_every_stage_with_a_label(client):
    body = client.get("/api/config").json()
    assert [st["name"] for st in body["stages"]] == NAMES
    assert all(st["label"] for st in body["stages"]) and body["live"] is False


def test_capture_review_and_approve(client, s):
    r = client.post("/api/captures", files={"video": ("capture.webm", b"\x1a\x45\xdf\xa3webm", "video/webm")},
                    data={"task": "Saisir une facture fournisseur", "url": "http://127.0.0.1:8042"})
    run_id = r.json()["run_id"]
    run = Run.open(s.runs_dir, run_id)
    assert run.video().name == "capture.webm" and run.meta.task == "Saisir une facture fournisseur"
    assert client.started == [run_id]

    run.write_text("skill.md", "# Skill\n- HT + TVA = TTC\n")
    run.set_status("review", "waiting")
    state = client.get(f"/api/runs/{run_id}").json()
    assert state["state"] == "waiting" and state["skill"].startswith("# Skill") and not state["approved"]

    client.put(f"/api/runs/{run_id}/skill", json={"skill": "# Skill corrigée\n"})
    assert run.file("skill.md").read_text() == "# Skill corrigée\n"
    assert state["trial_request"] == {"message": "Saisir une facture fournisseur.", "files": []}
    r = client.put(f"/api/runs/{run_id}/trial-request", data={"message": "Saisis la facture jointe"},
                   files=[("files", ("../INV-002.pdf", b"%PDF-1.4", "application/pdf"))])
    assert r.json()["files"] == ["INV-002.pdf"] and run.file("trial_files/INV-002.pdf").read_bytes() == b"%PDF-1.4"
    client.put(f"/api/runs/{run_id}/trial-request", data={"message": "Rentre ces factures"})   # sans fichier : gardé
    assert client.get(f"/api/runs/{run_id}").json()["trial_request"] == {"message": "Rentre ces factures",
                                                                        "files": ["INV-002.pdf"]}
    client.post(f"/api/runs/{run_id}/approve")
    assert run.has("skill.approved") and client.started == [run_id, run_id]


def test_stop_cancels_the_h_session_and_the_pipeline_stops(s, monkeypatch):
    from smo.pipeline import orchestrator
    from smo.runtime import web
    s = dataclasses.replace(s, hai_api_key="hai-test")   # sans clé H, rien à annuler (CI, Devin)
    client = TestClient(_app(router_for(s)[0]))
    run = Run.create(s.runs_dir, CaptureMeta(task="Saisir", software_url="https://qonta.example"), [])
    run.write_text("session.active", "sess-42")
    cancelled = []
    fake = type("C", (), {"sessions": type("S", (), {"cancel_session": lambda self, sid: cancelled.append(sid)})()})()
    monkeypatch.setattr(web.h, "client", lambda key: fake)
    assert client.post(f"/api/runs/{run.id}/stop").json() == {"stopped": True, "session": "sess-42"}
    assert cancelled == ["sess-42"] and run.has("stop")
    assert orchestrator.run_pipeline(run, s, log=lambda _: None) == "failed"   # plus aucune étape lancée
    assert run.status() == {}


def test_online_desktop_capture_needs_the_h_desktop_environment(s, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    data = {"task": "t", "url": "QONTA Cabinet 6.2", "software_kind": "desktop"}
    s = dataclasses.replace(s, h_desktop_env=None, h_desktop_bridge=None)
    bridge = "3f2c1a9e-8b7d-4c6e-9f10-2a3b4c5d6e7f"
    cases = ((None, None, 422), ("qonta-desktop", None, 200), (None, bridge, 200))
    for i, (desktop_env, desktop_bridge, expected) in enumerate(cases):
        data["task"] = f"t{i}"   # un run par cas : même seconde, même tâche → même dossier
        router, runner = router_for(dataclasses.replace(s, h_desktop_env=desktop_env, h_desktop_bridge=desktop_bridge))
        monkeypatch.setattr(runner, "start", lambda run: True)
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            r = c.post("/api/captures", files={"video": ("capture.webm", b"x", "video/webm")}, data=data)
        assert r.status_code == expected
    detail = TestClient(_app(router_for(s)[0])).post(
        "/api/captures", files={"video": ("c.webm", b"x", "video/webm")}, data=data).json()["detail"]
    assert "H_DESKTOP_BRIDGE" in detail and "H_DESKTOP_ENV" in detail


def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def test_unknown_run_and_token(client, s):
    assert client.get("/api/runs/inconnu").status_code == 404
    router, _ = router_for(dataclasses.replace(s, server_token="secret"))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        assert c.get("/api/config").status_code == 401
        assert c.get("/api/config", headers={"X-SMO-Token": "secret"}).status_code == 200


def test_online_server_refuses_to_start_without_a_real_token(s, monkeypatch):
    from smo.runtime.auth import require_safe_deployment
    require_safe_deployment(s)                                   # en local sans jeton : ouvert
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    for weak in (None, "court"):
        with pytest.raises(RuntimeError, match="SMO_SERVER_TOKEN"):
            require_safe_deployment(dataclasses.replace(s, server_token=weak))
    require_safe_deployment(dataclasses.replace(s, server_token="x" * 16))


def test_upload_too_big_is_refused(client, s, monkeypatch):
    from smo.runtime import web
    monkeypatch.setattr(web, "MAX_UPLOAD_MB", 0)
    r = client.post("/api/captures", files={"video": ("capture.webm", b"0123456789", "video/webm")},
                    data={"task": "t", "url": "http://x"})
    assert r.status_code == 413 and client.started == [] and not s.runs_dir.exists()


def test_frames_from_a_recorded_webm(s):
    """Les .webm de MediaRecorder n'ont pas d'index : l'extraction passe par un seul passage à 1 image/s."""
    run = Run.create(s.runs_dir, CaptureMeta(task="t", software_url="http://x"), [])
    video = run.file("capture/capture.webm")
    made = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
                           "-i", "testsrc=duration=4:size=320x240:rate=15", "-c:v", "libvpx", str(video)])
    if made.returncode:
        pytest.skip("ffmpeg sans encodeur libvpx")
    run.write_model("transcript.json", Transcript(language="fr", utterances=[
        Utterance(index=0, start=0.0, end=1.0, text="un"), Utterance(index=1, start=2.0, end=3.8, text="deux")]))
    capture.frames(run, s, log=lambda _: None)
    frameset = run.read_model("frames.json", FrameSet)
    assert [f.utterance_index for f in frameset.frames] == [0, 1]
    assert all(run.file(f.path).exists() for f in frameset.frames) and not run.file("frames/all").exists()
    assert frameset.final == "frames/final.png" and run.file(frameset.final).exists()   # référence du juge
