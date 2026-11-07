"""Étape 8 : l'agent custom est créé dans H, avec sa Skill, ses tools et la reprise en computer use.

Il est créé dès que la Skill est prête (il travaille alors à l'écran), puis mis à jour quand le tool
compilé par Devin est fusionné : le même agent devient rapide et déterministe.
"""
from __future__ import annotations

from typing import Callable

from hai_agents import Environment_Web
from hai_agents.types.tool_definition import ToolDefinition

from ..clients import h
from ..config import Settings
from ..models import CompileResult, Provisioned, RunReport
from ..runs import Run, slug
from ..runtime.tools import definitions, h_tools, load_tools
from .skill import skill_name, tool_name


INSTRUCTIONS = """Tu es l'agent « {task} » de {owner}. Tu travailles dans {url}, une pièce à la fois, \
en suivant la Skill « {skill} ».
{mode}
Dans tous les cas :
- Vérifie que la pièce est bien enregistrée en brouillon avec les bonnes valeurs (à l'écran et avec `verify_entry`).
- Si un fournisseur est inconnu ou douteux, vérifie-le avec `check_supplier`.
- Si une règle de la Skill demande l'arrêt (incohérence, cas inconnu), n'enregistre rien et explique pourquoi.
- Ne clique jamais sur « Valider ».
- Réponds au format demandé : mode = "tool" si le tool a fait la saisie, "computer_use" si tu l'as faite à l'écran."""

WITH_TOOL = """Pour chaque pièce :
1. Appelle `precheck_{tool}` : il vérifie, sans rien modifier, que l'interface n'a pas changé.
2. Si le precheck est OK : ouvre la pièce, lis ses valeurs, puis appelle `run_{tool}` avec ces valeurs.
3. Si le precheck échoue ou si `run_{tool}` renvoie une erreur : fais la saisie toi-même à l'écran \
en suivant la Skill, puis appelle `report_drift` en décrivant ce qui a changé."""

WITHOUT_TOOL = "Le tool automatique n'est pas encore prêt : fais la saisie toi-même à l'écran en suivant la Skill."


def agent_name(run: Run, s: Settings) -> str:
    meta = run.meta
    return f"{s.agent_prefix}{slug(meta.owner, max_len=12)}-{slug(meta.task, max_len=40)}"


def environment(url: str) -> Environment_Web:
    """Site en ligne → navigateur cloud H ; localhost → navigateur sur la machine qui fait tourner SMO."""
    return Environment_Web(id="web", host="user_device" if h.is_local(url) else "cloud", start_url=url)


def create(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, tname, sname = run.meta, tool_name(run), skill_name(run)
    compiled = load_tools(s.tools_dir)
    ready = tname in compiled
    tools = h_tools({tname: compiled[tname]} if ready else {}, s, on_drift=lambda *_: None)

    client = h.client(s.hai_api_key)
    h.upsert_skill(client, sname, description=f"À utiliser pour : {meta.task} dans {meta.software_url}.",
                   body=run.file("skill.md").read_text(encoding="utf-8"))
    env = environment(meta.software_url)
    spec = dict(
        description=f"{meta.task}, appris d'une démonstration de {meta.owner}.",
        environments=[env],
        instructions=INSTRUCTIONS.format(task=meta.task, owner=meta.owner, url=meta.software_url, skill=sname,
                                         mode=WITH_TOOL.format(tool=tname) if ready else WITHOUT_TOOL),
        skills=[sname],
        tools=[ToolDefinition(**d) for d in definitions(tools)],
        answer_format=RunReport.model_json_schema(),
    )
    if s.agent_model:
        spec["model"] = s.agent_model
    name = agent_name(run, s)
    h.upsert_agent(client, name, **spec)
    run.write_model("agent.json", Provisioned(agent_name=name, skill_name=sname, tools=[t.name for t in tools],
                                              tool_ready=ready, environment=env.model_dump(mode="json")))
    log(f"agent {name} : {'tool ' + tname if ready else 'computer use (tool pas encore fusionné)'}")


def upgrade(run: Run, s: Settings, log: Callable[[str], None]) -> str | None:
    """Une fois la PR de Devin fusionnée (et `git pull` fait), l'agent reçoit son tool."""
    if tool_name(run) not in load_tools(s.tools_dir):
        pr = run.read_model("compile.json", CompileResult).pr_url if run.has("compile.json") else None
        log(f"tool pas encore là : fusionne la PR {pr or '(voir compile.json)'}, git pull, puis `smo run {run.id}`")
        return "waiting"
    return create(run, s, log)


def tool_ready(run: Run) -> bool:
    return run.has("agent.json") and run.read_model("agent.json", Provisioned).tool_ready
