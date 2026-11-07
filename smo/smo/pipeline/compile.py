"""Étape 7 : Devin reçoit tout ce que le pipeline a compris et écrit le tool déterministe (une PR).

Devin n'est pas déterministe ; le code qu'il produit l'est, une fois relu (PR) et testé.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Callable

from ..clients import devin as devin_api
from ..clients import h
from ..config import ROOT, Settings
from ..models import CompileResult, Context, Trace
from ..runs import Run
from . import mapping
from .skill import tool_name


MAX_TRACE_CHARS = 20_000
MAX_ATTACHMENTS = 10


def trace_text(trace: Trace) -> str:
    lines, instruction = [], None
    for st in trace.steps:
        if st.instruction and st.instruction != instruction:
            instruction = st.instruction
            lines.append(f"\n> Consigne : {instruction[:300]}")
        actions = "; ".join(f"{a['tool_name']}({json.dumps(a.get('args'), ensure_ascii=False)[:200]})"
                            for a in st.actions)
        lines.append(f"- [{st.url or '?'}] {st.title or ''} → {actions or 'observation'}")
    text = "\n".join(lines)
    return text if len(text) <= MAX_TRACE_CHARS else text[:MAX_TRACE_CHARS] + "\n[…] (trace complète en pièce jointe)"


def checks_text(context: Context) -> str:
    if not context.rule_checks:
        return "Aucune règle vérifiée."
    return "\n".join(f"- {c.verdict} : « {c.rule} »" + (f" → {c.correction}" if c.correction else "")
                     + (f" ({', '.join(c.sources[:2])})" if c.sources else "") for c in context.rule_checks)


def _attachments(api: devin_api.Devin, files: list[Path]) -> list[str]:
    return [url for f in files[:MAX_ATTACHMENTS] if f.exists() and (url := api.upload(f))]


def is_done(run: Run) -> bool:
    return run.has("compile.json") and bool(run.read_model("compile.json", CompileResult).pr_url)


def run(run: Run, s: Settings, log: Callable[[str], None], wait: bool = True) -> str | None:
    api = devin_api.Devin(s.devin_api_key, s.devin_org_id)
    if run.has("compile.json"):                       # session déjà lancée : on reprend le suivi
        result = run.read_model("compile.json", CompileResult)
    else:
        meta, trace = run.meta, run.read_model("trace.json", Trace)
        context = run.read_model("context.json", Context) if run.has("context.json") else Context()
        name = tool_name(run)
        prompt = Template((ROOT / "docs" / "DEVIN_BRIEF.md").read_text(encoding="utf-8")).substitute(
            task=meta.task, repo=s.devin_repo or "ce repo", tool_name=name, url=meta.software_url,
            sample=meta.sample or "voir la trace", skill=run.file("skill.md").read_text(encoding="utf-8"),
            trace=trace_text(trace), checks=checks_text(context),
            map=mapping.summary(soft_map) if (soft_map := mapping.load(run)) else "Pas de carte.")
        run.write_text("devin_prompt.md", prompt)
        shots = sorted(run.file("trace").glob("step-*.png"))
        urls = _attachments(api, [run.file("trace.json"), run.file("trial.json"), *shots[:MAX_ATTACHMENTS - 2]])
        session = api.create_session(prompt, tags=["smo", run.id], max_acu=s.devin_max_acu, attachment_urls=urls)
        result = CompileResult(tool_name=name, devin_id=devin_api.session_id(session), url=session.get("url"))
        run.write_model("compile.json", result)
        log(f"session Devin {result.devin_id} ({len(urls)} pièces jointes) : {result.url or ''}")

    def update(session: dict) -> None:
        result.status, result.pr_url = session.get("status"), devin_api.pr_url(session) or result.pr_url
        run.write_model("compile.json", result)

    if not wait:
        update(api.get_session(result.devin_id))
        if result.pr_url:
            return None
        log(f"Devin travaille ({result.status}) : relance `smo run {run.id}` pour suivre")
        return "waiting"
    final = api.wait(result.devin_id, on_update=update)
    if not devin_api.pr_url(final):
        raise RuntimeError(f"Devin a fini sans PR (statut {final.get('status')}) : {result.url} "
                           f"— supprime {run.file('compile.json')} pour relancer une session")
    log(f"PR : {result.pr_url}")
    return None


def repair(tool: str, session_id: str, details: str, s: Settings, log: Callable[[str], None] = print) -> CompileResult:
    """Le tool a échoué et l'agent a repris en computer use : sa session devient la nouvelle démo pour Devin,
    qui corrige le tool et la Skill dans une même PR."""
    s.require("hai_api_key", "devin_api_key", "devin_org_id")
    out = s.runs_dir / "_repairs" / f"{datetime.now():%Y%m%d-%H%M%S}-{tool}"
    trace = h.build_trace(h.client(s.hai_api_key), session_id, out / "trace", s.hai_api_key)
    (out / "trace.json").write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    contract, skill_md = s.tools_dir / tool / "ui_contract.json", s.tools_dir / tool / "skill.md"
    prompt = Template((ROOT / "docs" / "DEVIN_REPAIR.md").read_text(encoding="utf-8")).substitute(
        tool_name=tool, repo=s.devin_repo or "ce repo", url=s.site_url or "le logiciel", details=details,
        contract=contract.read_text(encoding="utf-8") if contract.exists() else "{}",
        skill=skill_md.read_text(encoding="utf-8") if skill_md.exists() else "(pas encore de skill.md : crée-la)",
        trace=trace_text(trace))
    (out / "devin_prompt.md").write_text(prompt, encoding="utf-8")
    api = devin_api.Devin(s.devin_api_key, s.devin_org_id)
    session = api.create_session(prompt, tags=["smo", "repair", tool], max_acu=s.devin_max_acu,
                                 attachment_urls=_attachments(api, [out / "trace.json"]))
    result = CompileResult(tool_name=tool, devin_id=devin_api.session_id(session), url=session.get("url"),
                           mode="repair")
    (out / "compile.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    log(f"réparation lancée : Devin {result.devin_id} {result.url or ''}")
    return result
