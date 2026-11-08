"""Étape 8 : l'agent custom est créé dans H, avec sa Skill, ses tools et la reprise en computer use.

Il est créé dès que la Skill est prête (il travaille alors à l'écran, c'est lui que « trial » teste), puis mis
à jour quand le tool compilé par Devin est fusionné : le même agent devient rapide et déterministe.
Une fois le tool là, la Skill de référence est celle du repo (tools/<nom>/skill.md), que Devin fait évoluer.
"""
from __future__ import annotations

from typing import Callable

from hai_agents.types.tool_definition import ToolDefinition

from ..clients import h
from ..config import ROOT, Settings
from ..models import CompileResult, Provisioned, RunReport
from ..runs import Run
from ..runtime.tools import definitions, desktop_files, find, h_tools
from . import target
from .skill import NEVER_FINALIZE, skill_name, tool_name, with_common_block


INSTRUCTIONS = """{rule}
Tu es l'agent « {task} ». Tu travailles dans {where}, une pièce à la fois, avec ta Skill « {skill} ».
Les pièces jointes à la demande sont sur ta workstation : lis-les avec ta Skill « {read_skill} ».
{dossier_rule}
Si une règle de la Skill demande l'arrêt (incohérence, cas inconnu), n'enregistre rien et explique pourquoi.
""" + NEVER_FINALIZE + " Réponds au format demandé."

RULE_WITH_TOOL = ("Règle absolue, avant tout le reste : appelle d'abord `run_{tool}` avec les valeurs lues sur la pièce. "
                  "Il fait toute la tâche sur un serveur et renvoie le résultat final : tu n'as rien à faire à l'écran. "
                  "Tu ne travailles à l'écran que s'il renvoie une erreur, puis tu appelles `report_drift`.")
RULE_WITH_DESKTOP_TOOL = ("Règle absolue, avant tout le reste : lance d'abord le tool livré avec ta Skill, depuis ton shell, "
                          "dans le dossier de la Skill : `./run.sh run '<valeurs lues sur la pièce, en JSON>'`. Il fait "
                          "toute la tâche et affiche le résultat final : tu n'as rien à faire à l'écran. Tu ne travailles "
                          "à l'écran que s'il renvoie une erreur, puis tu appelles `report_drift`.")
RULE_WITHOUT_TOOL = "Règle absolue : pas encore de tool pour cette tâche, fais-la toi-même à l'écran en suivant ta Skill."


def is_desktop_tool(tool) -> bool:
    return tool is not None and tool.kind == "desktop"


def rule_for(tool, tname: str) -> str:
    if tool is None:
        return RULE_WITHOUT_TOOL
    return RULE_WITH_DESKTOP_TOOL if is_desktop_tool(tool) else RULE_WITH_TOOL.format(tool=tname)


def agent_name(run: Run, s: Settings) -> str:
    """Un agent par tâche et type de logiciel, le même nom que sa Skill."""
    return skill_name(run, s.agent_prefix)


def read_skill_name(s: Settings) -> str:
    return f"{s.agent_prefix}lire-pieces-jointes"


READ_SKILL_DESCRIPTION = ("Utiliser quand la demande arrive avec des pièces jointes (PDF, images) : où les trouver, "
                          "comment en lire les valeurs sans rien inventer, une pièce à la fois.")


def skill_description(run: Run) -> str:
    """Ce qui décide quand H charge la Skill : la tâche telle qu'on la demandera à l'agent."""
    meta = run.meta
    return (f"Utiliser pour toute demande de type « {meta.task.lower()} » dans {meta.software_name or meta.software_url} : "
            f"la méthode, les contrôles, quand s'arrêter.")


def skill_body(run: Run, s: Settings, tool=None) -> str:
    """La Skill d'h-tools si Devin l'a écrite ou corrigée (tools/<nom>/skill.md), sinon celle relue par l'humain."""
    return (tool.skill if tool is not None and tool.skill else None) or run.file("skill.md").read_text(encoding="utf-8")


def push_skill(client, run: Run, s: Settings, tool, body: str):
    """La Skill dans H, règle absolue en tête. Tool de bureau : ses fichiers sont posés dans la Skill (API Skills de H),
    l'agent le lance depuis son shell ; rien n'est installé chez l'utilisateur."""
    tname, sname = tool_name(run), skill_name(run, s.agent_prefix)
    if not is_desktop_tool(tool):
        return h.upsert_skill(client, sname, description=skill_description(run),
                              body=with_common_block(body, tname if tool else None))
    return h.upsert_skill(client, sname, description=skill_description(run),
                          body=with_common_block(body, tname, desktop_schema=tool.schema),
                          files=desktop_files(tool), executable_files=["run.sh"])


def push_read_skill(client, s: Settings):
    """La petite Skill commune à tous les agents SMO : lire les pièces jointes sur la workstation."""
    body = (ROOT / "skills" / "lire_pieces_jointes.md").read_text(encoding="utf-8")
    return h.upsert_skill(client, read_skill_name(s), description=READ_SKILL_DESCRIPTION, body=body)


def create(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, tname, sname = run.meta, tool_name(run), skill_name(run, s.agent_prefix)
    tool = find(s, tname)   # clone local d'h-tools, sinon ce qu'h-tools a déployé (service web, fichiers de bureau)
    tools = h_tools({tname: tool} if tool else {}, s, on_drift=lambda *_: None)   # déclarations seulement

    client = h.client(s.hai_api_key)
    push_skill(client, run, s, tool, skill_body(run, s, tool))
    push_read_skill(client, s)
    item = target.vault_item(meta, s, client)
    # web : navigateur cloud avec le vault de l'utilisateur (ou Chrome de cette machine en localhost) ; bureau : H ou le PC
    env = target.environment(meta, s, item.vault_id if item else None)
    spec = dict(
        description=f"{meta.task}, appris d'une démonstration ({meta.software_kind}).",
        environments=[env, target.WORKSTATION],
        instructions=INSTRUCTIONS.format(
            rule=rule_for(tool, tname), task=meta.task, where=target.where(meta), skill=sname,
            read_skill=read_skill_name(s), dossier_rule=target.DOSSIER_RULE),
        skills=[sname, read_skill_name(s)],
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
