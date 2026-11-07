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
from ..runtime.tools import definitions, find, h_tools
from . import target
from .skill import skill_name, tool_name, with_common_block


INSTRUCTIONS = """{rule}
Tu es l'agent « {task} » de {owner}. Tu travailles dans {where}, une pièce à la fois, avec ta Skill « {skill} ».
{dossier_rule}
Si une règle de la Skill demande l'arrêt (incohérence, cas inconnu), n'enregistre rien et explique pourquoi.
Ne clique jamais sur « Valider ». Réponds au format demandé."""

RULE_WITH_TOOL = ("Règle absolue, avant tout le reste : appelle d'abord `run_{tool}` avec les valeurs lues sur la pièce. "
                  "Il fait toute la tâche sur un serveur et renvoie le résultat final : tu n'as rien à faire à l'écran. "
                  "Tu ne travailles à l'écran que s'il renvoie une erreur, puis tu appelles `report_drift`.")
RULE_WITHOUT_TOOL = "Règle absolue : pas encore de tool pour cette tâche, fais-la toi-même à l'écran en suivant ta Skill."


def agent_name(run: Run, s: Settings) -> str:
    meta = run.meta
    return f"{s.agent_prefix}{slug(meta.owner, max_len=12)}-{slug(meta.task, max_len=36)}-{meta.software_kind}"


def skill_description(run: Run) -> str:
    """Ce qui décide quand H charge la Skill : la tâche telle qu'on la demandera à l'agent."""
    meta = run.meta
    return (f"Utiliser pour toute demande de type « {meta.task.lower()} » dans {meta.software_name or meta.software_url} "
            f"(par exemple « traite la pièce {meta.sample or 'XXX'} ») : la méthode, les contrôles, quand s'arrêter.")


def skill_body(run: Run, s: Settings, tool=None) -> str:
    """La Skill d'h-tools si Devin l'a écrite ou corrigée (tools/<nom>/skill.md), sinon celle relue par l'humain."""
    return (tool.skill if tool is not None and tool.skill else None) or run.file("skill.md").read_text(encoding="utf-8")


def create(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, tname, sname = run.meta, tool_name(run), skill_name(run)
    tool = find(s, tname)   # clone local d'h-tools, sinon le service déployé
    tools = h_tools({tname: tool} if tool else {}, s, on_drift=lambda *_: None)

    client = h.client(s.hai_api_key)
    h.upsert_skill(client, sname, description=skill_description(run),
                   body=with_common_block(skill_body(run, s, tool), tname if tool else None))
    env = target.environment(meta, s)   # web : navigateur (cloud, ou Chrome de cette machine en localhost) ; bureau : le Mac
    spec = dict(
        description=f"{meta.task}, appris d'une démonstration de {meta.owner} ({meta.software_kind}).",
        environments=[env],
        instructions=INSTRUCTIONS.format(
            rule=RULE_WITH_TOOL.format(tool=tname) if tool else RULE_WITHOUT_TOOL,
            task=meta.task, owner=meta.owner, where=target.where(meta), skill=sname, dossier_rule=target.DOSSIER_RULE),
        skills=[sname],
        tools=[ToolDefinition(**d) for d in definitions(tools)],
        answer_format=RunReport.model_json_schema(),
    )
    if s.agent_model:
        spec["model"] = s.agent_model
    name = agent_name(run, s)
    h.upsert_agent(client, name, **spec)
    run.write_model("agent.json", Provisioned(agent_name=name, skill_name=sname, tools=[t.name for t in tools],
                                              tool_ready=tool is not None, environment=target.as_dict(env)))
    log(f"agent {name} : {'tool ' + tname if tool else 'computer use (tool pas encore déployé)'}")


def upgrade(run: Run, s: Settings, log: Callable[[str], None]) -> str | None:
    """Le tool est déployé par h-tools (ou présent dans le clone local) : l'agent reçoit le tool et la Skill du repo.

    Appelé tout seul quand h-tools prévient SMO (POST /hooks/tool-deployed), ou à la main :
    `smo run <id> --only upgrade --force`.
    """
    if find(s, tool_name(run)) is None:
        pr = run.read_model("compile.json", CompileResult).pr_url if run.has("compile.json") else None
        log(f"tool pas encore déployé : PR {pr or '(voir compile.json)'} → fusion dans h-tools → déploiement "
            f"automatique, qui prévient SMO")
        return "waiting"
    return create(run, s, log)


def runs_with_tool(s: Settings, tool: str) -> list[Run]:
    """Les runs dont l'agent attend (ou a déjà) ce tool : ce sont eux qu'un déploiement met à jour."""
    if not s.runs_dir.exists():
        return []
    found = []
    for folder in sorted(s.runs_dir.iterdir()):
        if (folder / "meta.json").exists() and (folder / "agent.json").exists():
            run = Run(folder)
            if tool_name(run) == tool:
                found.append(run)
    return found


def tool_ready(run: Run) -> bool:
    return run.has("agent.json") and run.read_model("agent.json", Provisioned).tool_ready
