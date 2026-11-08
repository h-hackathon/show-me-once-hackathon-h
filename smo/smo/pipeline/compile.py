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
from ..clients import h, vault
from ..config import ROOT, Settings
from ..models import CompileResult, Context, DevinReport, Trace
from ..runs import Run
from . import docs, mapping
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


# Les règles fixes vivent dans h-tools, à côté du code, comme skill Devin (ce compte Devin n'a plus de playbooks)
METHOD = ("Applique la skill Devin `smo-tool` du repo h-tools : lis `.agents/skills/smo-tool/SKILL.md` en entier "
          "avant de commencer (procédure, règles du tool, interdits, sortie structurée obligatoire).")
REPORT_SCHEMA = DevinReport.model_json_schema()


def session_secrets(s: Settings, site_url: str | None, log: Callable[[str], None] = print) -> dict[str, str]:
    """L'accès au logiciel pour Devin, lu dans le vault H au lancement de sa session : SITE_URL, SITE_USERNAME,
    SITE_PASSWORD (ce que lit h_tools.config.Context.from_env). Le code TOTP expire en 30 s : pas transmis."""
    if not site_url:
        return {}
    secrets = {"SITE_URL": site_url}
    item = vault.find_item(h.client(s.hai_api_key), site_url, s.h_vault_id) if s.hai_api_key else None
    if item is None:
        log(f"{vault.host(site_url) or site_url} absent du vault H : Devin code sans pouvoir se connecter")
        return secrets
    found = vault.reveal(h.client(s.hai_api_key), item)
    return {**secrets, "SITE_USERNAME": found.username, "SITE_PASSWORD": found.password}


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
            method=METHOD, task=meta.task, repo=s.devin_repo or "ce repo", tool_name=name, url=meta.software_url,
            sample=meta.sample or "voir la trace", skill=run.file("skill.md").read_text(encoding="utf-8"),
            trace=trace_text(trace), checks=checks_text(context),
            map=mapping.summary(soft_map) if (soft_map := mapping.load(run)) else "Pas de carte.",
            docs=docs.summary(run) or "Pas de documentation publique trouvée.", kind=meta.software_kind)
        run.write_text("devin_prompt.md", prompt)
        # les sorties JSON complètes de chaque étape (rien n'est perdu par le résumé du brief), puis des captures
        outputs = [run.file(n) for n in ("trace.json", "trial.json", "procedure.json", "notes.json", "map.json",
                                         "docs.json") if run.has(n)]
        shots = sorted(run.file("trace").glob("step-*.png"))
        urls = _attachments(api, [*outputs, *shots[:max(0, MAX_ATTACHMENTS - len(outputs))]])
        secrets = {} if meta.software_kind == "desktop" else session_secrets(s, meta.software_url, log)
        session = api.create_session(prompt, tags=["smo", run.id], max_acu=s.devin_max_acu, attachment_urls=urls,
                                     output_schema=REPORT_SCHEMA, secrets=secrets)
        result = CompileResult(tool_name=name, devin_id=devin_api.session_id(session), url=session.get("url"))
        run.write_model("compile.json", result)
        log(f"session Devin {result.devin_id} ({len(urls)} pièces jointes) : {result.url or ''}")

    def update(session: dict) -> None:
        result.status, result.pr_url = session.get("status"), devin_api.pr_url(session) or result.pr_url
        result.report = session.get("structured_output") or result.report
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


def _site_of_session(client, session_id: str) -> str | None:
    """Le logiciel de l'agent qui a repris à l'écran : la start_url de son navigateur."""
    from ..runtime.worker import site_of
    try:
        agent = client.sessions.get_session(session_id).request.agent
        return site_of(client.agents.get_agent(agent) if isinstance(agent, str) else agent)
    except Exception:
        return None


def repair(tool: str, session_id: str, details: str, s: Settings, log: Callable[[str], None] = print) -> CompileResult:
    """Le tool a échoué et l'agent a repris en computer use : sa session devient la nouvelle démo pour Devin,
    qui corrige le tool et la Skill dans une même PR."""
    s.require("hai_api_key", "devin_api_key", "devin_org_id")
    out = s.runs_dir / "_repairs" / f"{datetime.now():%Y%m%d-%H%M%S}-{tool}"
    client = h.client(s.hai_api_key)
    trace = h.build_trace(client, session_id, out / "trace", s.hai_api_key)
    site = _site_of_session(client, session_id) or s.site_url
    (out / "trace.json").write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    # Clone local d'h-tools si on en a un (Mac) ; sinon (Railway) Devin les lit dans le repo
    contract, skill_md = s.tools_dir / tool / "ui_contract.json", s.tools_dir / tool / "skill.md"
    in_repo = f"(à lire dans tools/{tool}/ du repo h-tools)"
    prompt = Template((ROOT / "docs" / "DEVIN_REPAIR.md").read_text(encoding="utf-8")).substitute(
        method=METHOD, tool_name=tool, repo=s.devin_repo or "ce repo", url=site or "le logiciel", details=details,
        contract=contract.read_text(encoding="utf-8") if contract.exists() else in_repo,
        skill=skill_md.read_text(encoding="utf-8") if skill_md.exists() else in_repo,
        trace=trace_text(trace))
    (out / "devin_prompt.md").write_text(prompt, encoding="utf-8")
    api = devin_api.Devin(s.devin_api_key, s.devin_org_id)
    secrets = {} if tool.endswith("_desktop") else session_secrets(s, site, log)
    session = api.create_session(prompt, tags=["smo", "repair", tool], max_acu=s.devin_max_acu,
                                 attachment_urls=_attachments(api, [out / "trace.json"]),
                                 output_schema=REPORT_SCHEMA, secrets=secrets)
    result = CompileResult(tool_name=tool, devin_id=devin_api.session_id(session), url=session.get("url"),
                           mode="repair")
    (out / "compile.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    log(f"réparation lancée : Devin {result.devin_id} {result.url or ''}")
    return result
