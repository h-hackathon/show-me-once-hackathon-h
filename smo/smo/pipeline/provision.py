"""Étape 8 : l'agent custom est créé dans H, avec sa Skill, ses tools et la reprise en computer use.

Il est créé dès que la Skill est prête (il travaille alors à l'écran, c'est lui que « trial » teste), puis mis
à jour quand le tool compilé par Devin est fusionné : le même agent devient rapide et déterministe.
Une fois le tool là, la Skill de référence est celle du repo (tools/<nom>/skill.md), que Devin fait évoluer.
"""
from __future__ import annotations

from typing import Callable

from hai_agents.types.tool_definition import ToolDefinition

from ..clients import h
from ..config import Settings
from ..models import CompileResult, Provisioned, RunReport
from ..runs import Run, slug
from ..runtime.tools import definitions, h_tools, load_tools
from . import target
from .skill import skill_name, tool_name, with_common_block


INSTRUCTIONS = """Tu es l'agent « {task} » de {owner}. Tu travailles dans {where}, une pièce à la fois.
Suis ta Skill « {skill} » : sa méthode, ses règles, et sa dernière partie « Utiliser les tools ».
{dossier_rule}
Si une règle de la Skill demande l'arrêt (incohérence, cas inconnu), n'enregistre rien et explique pourquoi.
Ne clique jamais sur « Valider ». Réponds au format demandé."""


def agent_name(run: Run, s: Settings) -> str:
    meta = run.meta
    return f"{s.agent_prefix}{slug(meta.owner, max_len=12)}-{slug(meta.task, max_len=36)}-{meta.software_kind}"


def skill_description(run: Run) -> str:
    return f"À utiliser pour : {run.meta.task} dans {run.meta.software_url}."


def skill_body(run: Run, s: Settings) -> str:
    """La Skill du repo si Devin l'a écrite ou corrigée, sinon celle relue par l'humain."""
    in_repo = s.tools_dir / tool_name(run) / "skill.md"
    return (in_repo if in_repo.exists() else run.file("skill.md")).read_text(encoding="utf-8")


def create(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, tname, sname = run.meta, tool_name(run), skill_name(run)
    compiled = load_tools(s.tools_dir)
    ready = tname in compiled
    tools = h_tools({tname: compiled[tname]} if ready else {}, s, on_drift=lambda *_: None)

    client = h.client(s.hai_api_key)
    h.upsert_skill(client, sname, description=skill_description(run),
                   body=with_common_block(skill_body(run, s), tname if ready else None))
    env = target.environment(meta)   # web : navigateur (cloud, ou Chrome de cette machine en localhost) ; bureau : le Mac
    spec = dict(
        description=f"{meta.task}, appris d'une démonstration de {meta.owner} ({meta.software_kind}).",
        environments=[env],
        instructions=INSTRUCTIONS.format(task=meta.task, owner=meta.owner, where=target.where(meta), skill=sname,
                                         dossier_rule=target.DOSSIER_RULE),
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
    """Une fois la PR de Devin fusionnée (et `git pull` fait), l'agent reçoit son tool et la Skill du repo.
    Après une réparation : `smo run <id> --only upgrade --force` repousse tool et Skill dans H."""
    if tool_name(run) not in load_tools(s.tools_dir):
        pr = run.read_model("compile.json", CompileResult).pr_url if run.has("compile.json") else None
        log(f"tool pas encore là : fusionne la PR {pr or '(voir compile.json)'}, git pull, puis `smo run {run.id}`")
        return "waiting"
    return create(run, s, log)


def tool_ready(run: Run) -> bool:
    return run.has("agent.json") and run.read_model("agent.json", Provisioned).tool_ready
