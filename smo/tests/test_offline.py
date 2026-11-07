"""Tests sans clé ni réseau : la logique du pipeline, pas les API (pour elles : `smo doctor --probe`)."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from smo import config
from smo.clients import h, holo
from smo.models import (CaptureMeta, Context, Procedure, Rule, RuleCheck, Step, Trace, TraceStep,
                        Transcript, Utterance)
from smo.pipeline import compile as compile_stage
from smo.pipeline import orchestrator, provision, replay, skill
from smo.runs import Run, slug
from smo.runtime import tools as runtime_tools


@pytest.fixture
def s(tmp_path) -> config.Settings:
    """Réglages sans aucune clé, runs et tools dans un dossier temporaire."""
    base = config.load()
    blank = {f.name: None for f in dataclasses.fields(base)
             if f.name.endswith(("_key", "_id", "_url", "_token", "_login", "_password", "_secret", "_repo"))}
    return dataclasses.replace(base, **{**blank, "runs_dir": tmp_path / "runs", "tools_dir": tmp_path / "tools",
                                        "site_url": "https://compta.example"})


@pytest.fixture
def run(s) -> Run:
    meta = CaptureMeta(task="Saisir une facture fournisseur", software_url="https://compta.example",
                       owner="Catherine", sample="INV-001")
    r = Run.create(s.runs_dir, meta, [])
    r.write_model("transcript.json", Transcript(language="fr", utterances=[
        Utterance(index=0, start=0.0, end=3.0, text="J'ouvre une nouvelle facture."),
        Utterance(index=1, start=3.0, end=8.0, text="Je vérifie toujours que HT plus TVA égale TTC."),
    ]))
    r.write_model("procedure.json", PROCEDURE)
    return r


PROCEDURE = Procedure(
    task="Saisir une facture fournisseur", software="Site compta",
    steps=[Step(index=0, action="click", target="Nouvelle facture", utterance_index=0),
           Step(index=1, action="type", target="Référence fournisseur", value_source="facture : n° de facture")],
    rules=[Rule(text="HT + TVA = TTC", kind="check"),
           Rule(text="Fournisseur étranger : TVA 0 %", kind="exception")],
    stop_conditions=["total incohérent"], inputs=["fournisseur", "référence", "total TTC"])


def test_slug_and_names(run):
    assert slug("Saisir une facture fournisseur") == "saisir-une-facture-fournisseur"
    assert skill.tool_name(run) == "saisir_une_facture_fournisseur"
    assert skill.skill_name(run) == "smo-catherine-saisir-une-facture-fournisseur"


def test_extract_json_fenced_and_raw():
    assert holo.extract_json('Voici :\n```json\n{"a": 1}\n```') == {"a": 1}
    assert holo.extract_json('bla {"a": {"b": 2}} bla') == {"a": {"b": 2}}


def test_condense_events():
    events = [
        {"type": "UserMessageEvent", "data": {"message": "Étape 1 : clique sur « Nouvelle facture »."}},
        {"type": "AgentEvent", "timestamp": "t1", "data": {
            "kind": "observation_event", "metadata": {"url": "https://compta.example/invoices", "title": "Factures"},
            "image": {"type": "url", "source": "https://img/1.png"}}},
        {"type": "AgentEvent", "data": {"kind": "policy_event", "reasoning_content": "je clique",
                                        "tool_reqs": [{"tool_name": "click", "args": {"x": 10, "y": 20}}]}},
        {"type": "AgentEvent", "data": {"kind": "tool_result", "result": {"ok": True}}},
        {"type": "AgentEvent", "data": {"kind": "policy_event", "tool_reqs": [{"tool_name": "type"}]}},
    ]
    steps, images = h.condense(events)
    assert len(steps) == 2
    assert steps[0].url.endswith("/invoices") and steps[0].instruction.startswith("Étape 1")
    assert steps[0].actions == [{"tool_name": "click", "args": {"x": 10, "y": 20}}]
    assert steps[0].results and steps[1].actions[0]["tool_name"] == "type"
    assert images == [(0, {"type": "url", "source": "https://img/1.png"})]


def test_condense_reads_user_messages_as_h_sends_them():
    """Forme réelle (session du 7 nov.) : AgentEvent message_event, caller_id user, content = [str]."""
    steps, _ = h.condense([
        {"type": "AgentEvent", "data": {"kind": "message_event", "caller_id": "user",
                                        "content": ["Clique dans le champ « E-mail »."]}},
        {"type": "AgentEvent", "data": {"kind": "observation_event", "metadata": {"url": "http://127.0.0.1:8042/login"}}},
    ])
    assert steps[0].instruction == "Clique dans le champ « E-mail »."


def test_skill_applies_linkup_correction():
    context = Context(rule_checks=[RuleCheck(rule="Fournisseur étranger : TVA 0 %", verdict="corrected",
                                             correction="Fournisseur UE : autoliquidation (20 % EU)")])
    md = skill.render(PROCEDURE, context, "https://compta.example")
    assert "autoliquidation" in md and "dit pendant la démo" in md
    assert "Ne jamais cliquer sur « Valider »" in md
    assert "1. Cliquer sur « Nouvelle facture »" in md


def test_replay_instructions_quote_the_human(run):
    msgs = replay.instructions(PROCEDURE, run.read_model("transcript.json", Transcript))
    assert msgs[0].startswith("Étape 1/2 : clique sur « Nouvelle facture »")
    assert "J'ouvre une nouvelle facture" in msgs[0]
    assert "Ne valide rien" in msgs[-1]


def test_real_stages_wait_for_review_then_block_on_keys(run, s):
    # transcript + procedure déjà là : frames et skill tournent, enrich est sautée, la relecture attend l'humain
    assert orchestrator.run_pipeline(run, s, log=lambda _: None) == "waiting"
    assert run.has("skill.md") and run.status()["enrich"]["state"] == "skipped"
    run.write_text("skill.approved", "ok\n")
    assert orchestrator.run_pipeline(run, s, log=lambda _: None) == "blocked"
    assert run.status()["provision"]["missing"] == ["HAI_API_KEY"]
    assert orchestrator.NAMES[-4:] == ["provision", "trial", "compile", "upgrade"]


def test_skill_from_repo_wins_once_devin_wrote_it(run, s):
    run.write_text("skill.md", "# relue par l'humain\n")
    assert provision.skill_body(run, s).startswith("# relue")
    folder = s.tools_dir / skill.tool_name(run)
    folder.mkdir(parents=True)
    (folder / "skill.md").write_text("# corrigée par Devin\n")
    assert provision.skill_body(run, s).startswith("# corrigée")


def test_repair_brief_has_every_field():
    from string import Template
    Template((config.ROOT / "docs" / "DEVIN_REPAIR.md").read_text()).substitute(
        tool_name="x", repo="r", url="u", details="d", contract="{}", skill="k", trace="t")


def test_pipeline_blocks_on_missing_key(s):
    fresh = Run.create(s.runs_dir, CaptureMeta(task="Autre tâche", software_url="https://x"), [])
    assert orchestrator.run_pipeline(fresh, s, log=lambda _: None) == "blocked"
    assert fresh.status()["transcribe"]["missing"] == ["GLADIA_API_KEY"]


def test_pipeline_skips_done_stages_and_waits_for_review(run, s, monkeypatch):
    calls = []
    fake = [orchestrator.Stage("a", lambda r, s, log: calls.append("a"), (), lambda r: r.has("a.done")),
            orchestrator.Stage("opt", lambda r, s, log: calls.append("opt"), ("linkup_api_key",),
                               lambda r: False, optional=True),
            orchestrator.Stage("review", skill.review, (), lambda r: r.has("skill.approved")),
            orchestrator.Stage("b", lambda r, s, log: calls.append("b"), (), lambda r: False)]
    monkeypatch.setattr(orchestrator, "STAGES", fake)
    monkeypatch.setattr(orchestrator, "NAMES", [st.name for st in fake])
    run.write_text("a.done", "")
    assert orchestrator.run_pipeline(run, s, log=lambda _: None) == "waiting"
    assert calls == [] and run.status()["opt"]["state"] == "skipped"
    assert orchestrator.run_pipeline(run, s, auto=True, log=lambda _: None) == "done"
    assert calls == ["b"]


TOOL_SOURCE = '''
from pydantic import BaseModel, Field
NAME = "saisir_une_facture_fournisseur"
DESCRIPTION = "Saisit une facture fournisseur."
class Params(BaseModel):
    reference: str = Field(description="n° de facture")
    total_ttc: float
def precheck(page, cfg): return {"ok": True}
def run(page, params, cfg): return {"status": "draft_saved"}
'''


def test_tool_registry_and_h_definitions(s):
    (s.tools_dir / "_template").mkdir(parents=True)
    (s.tools_dir / "_template" / "tool.py").write_text("raise RuntimeError('ignoré')")
    folder = s.tools_dir / "saisir_une_facture_fournisseur"
    folder.mkdir()
    (folder / "tool.py").write_text(TOOL_SOURCE)
    compiled = runtime_tools.load_tools(s.tools_dir)
    assert list(compiled) == ["saisir_une_facture_fournisseur"]
    tools = runtime_tools.h_tools(compiled, s, on_drift=lambda *_: None)
    names = [t.name for t in tools]
    assert names == ["precheck_saisir_une_facture_fournisseur", "run_saisir_une_facture_fournisseur",
                     "report_drift", "check_supplier", "verify_entry"]
    run_def = runtime_tools.definitions(tools)[1]
    assert set(run_def["input_schema"]["required"]) == {"reference", "total_ttc"}
    drifts = []
    report = runtime_tools.h_tools({}, s, on_drift=lambda *a: drifts.append(a))[0]
    report.fn(tool="run_x", details="bouton renommé")
    assert drifts == [("run_x", "bouton renommé")]


def test_read_sends_one_image_per_call_and_survives_an_unreadable_one(run, s, monkeypatch):
    from smo.models import Frame, FrameSet, Notes, ScreenReading
    from smo.pipeline import understand
    run.write_model("frames.json", FrameSet(
        frames=[Frame(utterance_index=0, time_s=1.5, path="frames/u000.png"),
                Frame(utterance_index=1, time_s=5.5, path="frames/u001.png")],
        references=[Frame(utterance_index=None, time_s=None, path="capture/images/INV-001.pdf")]))
    calls = []

    def fake_chat_model(prompt, model_cls, api_key, model, images=()):
        calls.append(len(images))
        if "u001" in str(images[0]):
            raise RuntimeError("JSON invalide")
        if model_cls is ScreenReading:
            return ScreenReading(screen="Factures fournisseurs", action="click", target="Nouvelle facture")
        return model_cls(kind="facture", fields={"Total TTC": 298.8})

    monkeypatch.setattr(understand.holo, "chat_model", fake_chat_model)
    understand.read(run, s, log=lambda _: None)
    notes = run.read_model("notes.json", Notes)
    assert calls == [1, 1, 1]                                   # jamais plus d'une image par appel
    assert notes.screens[0].target == "Nouvelle facture" and notes.screens[1].error
    assert notes.documents[0].fields == {"Total TTC": 298.8}

    prompt = understand.synthesis_prompt(run, run.read_model("transcript.json", Transcript), notes)
    assert "vu : écran « Factures fournisseurs » · click « Nouvelle facture »" in prompt
    assert "Total TTC : 298.8" in prompt and "HT plus TVA égale TTC" in prompt   # phrase sans capture lisible gardée


def test_long_demo_keeps_the_last_screens_and_bad_document_is_tolerated(run, s, monkeypatch):
    from smo.models import Frame, FrameSet, Notes
    from smo.pipeline import understand
    assert understand.spread(list(range(100)), 5) == [0, 25, 50, 74, 99]
    run.write_model("frames.json", FrameSet(frames=[], references=[
        Frame(utterance_index=None, time_s=None, path="capture/images/illisible.pdf")]))

    def broken(*args, **kwargs):
        raise RuntimeError("PDF illisible")

    monkeypatch.setattr(understand.holo, "chat_model", broken)
    understand.read(run, s, log=lambda _: None)
    notes = run.read_model("notes.json", Notes)
    assert notes.documents[0].error
    assert "illisible.pdf" not in understand.synthesis_prompt(run, run.read_model("transcript.json", Transcript), notes)


def test_turn_stops_on_idle_event_even_if_status_flips_back():
    class FakeHandle:
        def stream(self, **kwargs):
            assert kwargs["until"] == "terminal" and kwargs["from_index"] == 3
            yield {"type": "AgentEvent", "data": {"kind": "answer_event", "answer": "ok"}}
            yield {"type": "ActiveStateChangeEvent", "data": {"state": "idle"}}
            raise AssertionError("lu au-delà de l'événement idle")   # le statut serait repassé « running »

    events = [{}, {}, {}]
    h.drain(FakeHandle(), events)
    assert len(events) == 5 and h.is_idle_event(events[-1])


def test_localhost_opens_the_browser_on_this_machine():
    assert h.session_agent("h/web-surfer-pro", "https://compta.example") == "h/web-surfer-pro"
    local = h.session_agent("h/web-surfer-pro", "http://127.0.0.1:8042", model="holo4-27b")
    assert local.environments[0].host == "user_device" and local.model == "holo4-27b"


def test_provision_environment_and_definitions():
    from hai_agents.types.tool_definition import ToolDefinition
    assert h.web_environment("http://localhost:3000").host == "user_device"
    assert h.web_environment("https://compta.example").host == "cloud"
    defs = runtime_tools.definitions(runtime_tools.h_tools({}, config.load(), on_drift=lambda *_: None))
    assert [ToolDefinition(**d).name for d in defs] == ["report_drift", "check_supplier", "verify_entry"]


def test_devin_brief_renders(run, s):
    run.write_text("skill.md", "# Skill\n- HT + TVA = TTC\n")
    trace = Trace(session_id="sess", agent="h/web-surfer-pro", status="completed", steps=[
        TraceStep(index=0, instruction="Étape 1", url="https://compta.example/invoices/new", title="Nouvelle",
                    actions=[{"tool_name": "click", "args": {"x": 1}}])])
    text = compile_stage.trace_text(trace)
    assert "> Consigne : Étape 1" in text and "click(" in text
    from string import Template
    prompt = Template((config.ROOT / "docs" / "DEVIN_BRIEF.md").read_text()).substitute(
        task="t", repo="r", tool_name="x", url="u", sample="s", skill="k", trace=text, checks="c")
    assert "tools/x/" in prompt and "$" not in prompt.replace("$tool", "")


def test_server_health_without_keys(monkeypatch):
    monkeypatch.delenv("HAI_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from smo.runtime import server
    with TestClient(server.app) as client:
        body = client.get("/health").json()
    assert body["ok"] is True and isinstance(body["tools"], list)
