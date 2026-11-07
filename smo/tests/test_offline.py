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
    assert skill.tool_name(run) == "saisir_une_facture_fournisseur_web"
    assert skill.skill_name(run) == "smo-catherine-saisir-une-facture-fournisseur-web"


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
    (folder / "tool.py").write_text(TOOL_SOURCE.replace('"saisir_une_facture_fournisseur"', f'"{folder.name}"'))
    (folder / "skill.md").write_text("# corrigée par Devin\n")
    tool = runtime_tools.find(s, folder.name)
    assert tool is not None and provision.skill_body(run, s, tool).startswith("# corrigée")


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


def _trial_setup(run, monkeypatch, verdicts):
    """Essais simulés : chaque essai renvoie une trace, le juge rend les verdicts donnés, dans l'ordre."""
    from smo.models import Provisioned, Verdict
    from smo.pipeline import trial
    run.write_text("skill.md", "# Skill\n- HT + TVA = TTC\n")
    run.write_model("agent.json", Provisioned(agent_name="smo-catherine-x", skill_name="smo-catherine-x",
                                              tools=[], tool_ready=False, environment={}))
    pushed, queue = [], [Verdict(**v) for v in verdicts]
    monkeypatch.setattr(trial.h, "client", lambda key: None)
    monkeypatch.setattr(trial.h, "upsert_skill", lambda client, name, description, body: pushed.append(body))
    monkeypatch.setattr(trial, "attempt", lambda run, s, n, agent, task, log: Trace(
        session_id=f"sess-{n}", agent="smo-catherine-x", status="idle", steps=[], answer=f"essai {n}"))
    monkeypatch.setattr(trial, "judge", lambda run, s, trace, piece: queue.pop(0))
    return trial, pushed


def test_trial_retries_with_the_lesson_then_hands_the_good_attempt_to_devin(run, s, monkeypatch):
    from smo.models import Trial
    trial, pushed = _trial_setup(run, monkeypatch, [
        {"success": False, "gap": "dossier non ouvert", "lesson": "Ouvrir d'abord le dossier 00417"},
        {"success": True}])
    assert trial.run(run, s, log=lambda _: None) is None
    result = run.read_model("trial.json", Trial)
    assert result.success and [a.verdict.success for a in result.attempts] == [False, True]
    assert run.read_model("trace.json", Trace).session_id == "sess-2"          # Devin reçoit l'essai réussi
    skill_md = run.file("skill.md").read_text()
    assert "## Leçons des essais" in skill_md and "Essai 1 : Ouvrir d'abord le dossier 00417" in skill_md
    assert len(pushed) == 2 and "Ouvrir d'abord" in pushed[1]                  # la Skill corrigée est poussée dans H


def test_trial_waits_for_the_human_after_three_failures(run, s, monkeypatch):
    trial, _ = _trial_setup(run, monkeypatch, [{"success": False, "gap": "raté"}] * 3)
    assert trial.run(run, s, log=lambda _: None) == "waiting"
    assert not run.has("trace.json")


MAP = {"screens": [{"name": "Nouvelle facture", "url": "/factures/nouvelle", "how_to_reach": "Saisie > Factures fournisseurs",
                     "fields": ["Fournisseur", "Référence fournisseur"], "buttons": ["Enregistrer le brouillon"]}],
       "notes": "écran « Choix du dossier » après la connexion"}


def test_map_is_reused_from_cache_and_forgotten_when_the_ui_changes(run, s, monkeypatch):
    from smo.models import SoftwareMap
    from smo.pipeline import mapping
    cached = mapping.cache_path(s, run.meta.software_url, run.meta.task)
    cached.parent.mkdir(parents=True)
    cached.write_text(SoftwareMap(**MAP, software_url=run.meta.software_url, task=run.meta.task).model_dump_json())
    monkeypatch.setattr(mapping.h, "client", lambda key: (_ for _ in ()).throw(AssertionError("pas d'appel H")))
    mapping.run(run, s, log=lambda _: None)
    assert mapping.load(run).screens[0].name == "Nouvelle facture"
    assert mapping.forget(s, run.meta.software_url) == 1 and not cached.exists()


def test_map_feeds_the_synthesis_and_the_skill(run, s):
    from smo.models import Notes, SoftwareMap
    from smo.pipeline import understand
    run.write_model("map.json", SoftwareMap(**MAP, software_url=run.meta.software_url, task=run.meta.task))
    prompt = understand.synthesis_prompt(run, run.read_model("transcript.json", Transcript), Notes())
    assert "Carte du logiciel" in prompt and "Saisie > Factures fournisseurs" in prompt
    skill.run(run, s, log=lambda _: None)
    md = run.file("skill.md").read_text()
    assert "## Carte du logiciel" in md and "Boutons : Enregistrer le brouillon" in md and "Choix du dossier" in md


def test_background_stage_runs_in_parallel_and_is_awaited(run, s, monkeypatch):
    import time as _time
    order = []

    def slow_map(r, s, log):
        _time.sleep(0.3)
        r.write_text("bg.done", "")
        order.append("map")

    fake = [orchestrator.Stage("map", slow_map, (), lambda r: r.has("bg.done"), optional=True, join_before="b"),
            orchestrator.Stage("a", lambda r, s, log: order.append("a"), (), lambda r: False),
            orchestrator.Stage("b", lambda r, s, log: order.append("b" if r.has("bg.done") else "b-trop-tôt"), (),
                               lambda r: False)]
    monkeypatch.setattr(orchestrator, "STAGES", fake)
    monkeypatch.setattr(orchestrator, "NAMES", [st.name for st in fake])
    assert orchestrator.run_pipeline(run, s, log=lambda _: None) == "done"
    assert order == ["a", "map", "b"]                 # a n'attend pas la carte, b l'attend


def test_each_attempt_takes_the_next_piece():
    from smo.pipeline.trial import trial_piece
    assert [trial_piece("INV-001", n) for n in (1, 2, 3)] == ["INV-002", "INV-003", "INV-004"]
    assert "autre pièce" in trial_piece(None, 1)


def test_common_block_is_added_to_the_skill_sent_to_h():
    with_tool = skill.with_common_block("# Skill\n", "saisir_web")
    assert "## Utiliser les tools" in with_tool and "`precheck_saisir_web`" in with_tool and "`run_saisir_web`" in with_tool
    without = skill.with_common_block("# Skill\n", None)
    assert "Pas encore de tool" in without and "$" not in without


def test_desktop_gets_its_own_agent_environment_and_names(s, tmp_path):
    from smo.pipeline import target
    run = Run.create(s.runs_dir, CaptureMeta(task="Saisir une facture fournisseur", software_kind="desktop",
                                             software_url="COMPTAREX Cabinet 6.2", owner="Catherine"), [])
    assert target.environment(run.meta).kind == "desktop" and target.environment(run.meta).host == "user_device"
    assert skill.tool_name(run).endswith("_desktop") and provision.agent_name(run, s).endswith("-desktop")
    assert "application de bureau « COMPTAREX Cabinet 6.2 »" in target.where(run.meta)
    assert target.credentials(run.meta, s) == (s.desktop_login, s.desktop_password)


def test_docs_summary_feeds_holo(run):
    from smo.models import Notes
    from smo.pipeline import docs, understand
    assert docs.summary(run) == ""
    run.write_json("docs.json", {"query": "q", "answer": "Saisie > Factures fournisseurs > Nouvelle facture",
                                 "sources": ["https://doc.example/factures"], "pages": [{"url": "https://x", "text": "Connexion"}]})
    assert "Ce que dit la documentation" in docs.summary(run) and "https://doc.example/factures" in docs.summary(run)
    prompt = understand.synthesis_prompt(run, run.read_model("transcript.json", Transcript), Notes())
    assert "Documentation publique du logiciel (Linkup)" in prompt


def test_deployed_tool_is_described_and_unreachable_one_returns_an_error():
    import httpx
    from smo.runtime.remote import RemoteTool, tool_url
    assert tool_url(None, "saisir_facture_web") == "http://tool-saisir-facture-web.railway.internal:8080"

    def handler(request):
        assert request.url.path == "/saisir-facture-web/describe"
        return httpx.Response(200, json={"name": "saisir_facture_web", "description": "Saisit", "sha": "abc",
                                         "params": {"type": "object", "properties": {"reference": {"type": "string"}}},
                                         "skill": "# Skill d'h-tools"})

    tool = RemoteTool.fetch("saisir_facture_web", "http://tools.test/{name}", transport=httpx.MockTransport(handler))
    assert tool.sha == "abc" and tool.skill.startswith("# Skill") and "reference" in tool.schema["properties"]
    down = RemoteTool(name="x", description="", schema={}, skill=None, sha=None, base_url="http://127.0.0.1:9")
    assert down.precheck(None)["status"] == "error"
    assert RemoteTool.fetch("x", "http://127.0.0.1:9") is None


def test_find_prefers_the_local_clone_and_only_reaches_deployed_web_tools(s, monkeypatch):
    from smo.runtime import tools as rt
    calls = []
    monkeypatch.setattr(rt.RemoteTool, "fetch", classmethod(lambda cls, name, url=None: calls.append(name) or "remote"))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert rt.find(s, "saisir_web") is None and calls == []              # en local, sans SMO_TOOL_URL : rien à joindre
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert rt.find(s, "saisir_web") == "remote" and rt.find(s, "saisir_desktop") is None   # le bureau, jamais en ligne


def test_each_server_serves_only_its_kind_of_agent():
    from smo.config import worker_kinds
    assert worker_kinds(None, None) == ("web", "desktop")                 # Mac seul
    assert worker_kinds(None, "https://smo.up.railway.app") == ("desktop",)   # Mac + Railway : le Mac garde le bureau
    assert worker_kinds("web", None) == ("web",)


def test_tool_deployed_hook_upgrades_the_waiting_agents(monkeypatch):
    from fastapi.testclient import TestClient
    from smo.runtime import server
    upgraded = []
    monkeypatch.setattr(server, "runs_with_tool", lambda s, name: [type("R", (), {"id": f"run-{name}"})()])
    monkeypatch.setattr(server, "_upgrade", lambda run_: upgraded.append(run_.id))
    with TestClient(server.app) as client:
        body = client.post("/hooks/tool-deployed", json={"tool": "saisir_web", "sha": "abc"}).json()
    assert body["runs"] == ["run-saisir_web"]


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
        task="t", repo="r", tool_name="x", url="u", sample="s", skill="k", trace=text, checks="c", map="m",
        docs="d", kind="web")
    assert "tools/x/" in prompt and "$" not in prompt.replace("$tool", "")


def test_server_health_without_keys(monkeypatch):
    monkeypatch.delenv("HAI_API_KEY", raising=False)
    from fastapi.testclient import TestClient
    from smo.runtime import server
    with TestClient(server.app) as client:
        body = client.get("/health").json()
    assert body["ok"] is True and isinstance(body["local_tools"], list)
