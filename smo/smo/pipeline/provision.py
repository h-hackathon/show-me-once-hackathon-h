"""Étape 8 : l'agent custom est créé dans H, avec sa Skill, ses tools et la reprise en computer use.

Il est créé dès que la Skill est prête (il travaille alors à l'écran, c'est lui que « trial » teste), puis mis
à jour quand le tool compilé par Devin est fusionné : le même agent devient rapide et déterministe.
Une fois le tool là, la Skill de référence est celle du repo (tools/<nom>/skill.md), que Devin fait évoluer.
"""
from __future__ import annotations

import json
from pathlib import Path
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

# report_drift relance Devin : seulement pour une interface changée, jamais pour un refus métier du tool.
DRIFT_RULE = ("Tu ne travailles à l'écran que s'il renvoie une erreur. N'appelle `report_drift` que si l'interface a "
              "changé (un élément introuvable à l'écran, un écran différent de la Skill), jamais pour un cas métier "
              "(fournisseur absent ou ambigu, doublon, total incohérent).")
RULE_WITH_TOOL = ("Règle absolue, avant tout le reste : appelle d'abord `run_{tool}` avec les valeurs lues sur la pièce. "
                  "Il fait toute la tâche sur un serveur et renvoie le résultat final : tu n'as rien à faire à l'écran. "
                  + DRIFT_RULE)
RULE_WITH_DESKTOP_TOOL = ("Règle absolue, avant tout le reste : lance d'abord le tool livré avec ta Skill, depuis ton shell, "
                          "dans le dossier de la Skill : `./run.sh run '<valeurs lues sur la pièce, en JSON>'`. Il fait "
                          "toute la tâche et affiche le résultat final : tu n'as rien à faire à l'écran. " + DRIFT_RULE)
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


# Amélioration d'une tâche qui a déjà son tool : le commit de ce tool au moment de la démo. Tant qu'h-tools n'a pas
# déployé le suivant (la PR de Devin pour cette démo), la Skill de référence reste celle relue par l'humain.
BASE_TOOL = "base_tool.json"


def note_base_tool(run: Run, tool) -> None:
    """Sans commit connu (clone local d'h-tools), on ne peut pas voir arriver le suivant : rien n'est noté."""
    if run.meta.improves and getattr(tool, "sha", None) and not run.has(BASE_TOOL):
        run.write_text(BASE_TOOL, json.dumps({"sha": getattr(tool, "sha", None)}))


def awaits_new_tool(run: Run, sha: str | None) -> bool:
    """La démo améliore un tool existant, et `sha` est encore celui d'avant la démo."""
    return run.has(BASE_TOOL) and json.loads(run.file(BASE_TOOL).read_text())["sha"] == sha


def skill_body(run: Run, s: Settings, tool=None) -> str:
    """La Skill d'h-tools si Devin l'a écrite ou corrigée (tools/<nom>/skill.md), sinon celle relue par l'humain."""
    if tool is None or not tool.skill or awaits_new_tool(run, getattr(tool, "sha", None)):
        return run.file("skill.md").read_text(encoding="utf-8")
    return tool.skill


def skill_archive(s: Settings) -> Path:
    """Les versions de Skills remplacées dans H (H n'en garde pas l'historique)."""
    return s.runs_dir / "_archive" / "skills"


def push_skill(client, run: Run, s: Settings, tool, body: str):
    """La Skill dans H, règle absolue en tête. Tool de bureau : ses fichiers sont posés dans la Skill (API Skills de H),
    l'agent le lance depuis son shell ; rien n'est installé chez l'utilisateur."""
    tname, sname = tool_name(run), skill_name(run, s.agent_prefix)
    if not is_desktop_tool(tool):
        return h.upsert_skill(client, sname, description=skill_description(run),
                              body=with_common_block(body, tname if tool else None), archive_dir=skill_archive(s))
    return h.upsert_skill(client, sname, description=skill_description(run),
                          body=with_common_block(body, tname, desktop_schema=tool.schema),
                          files=desktop_files(tool), executable_files=["run.sh"], archive_dir=skill_archive(s))


def push_read_skill(client, s: Settings):
    """La petite Skill commune à tous les agents SMO : lire les pièces jointes sur la workstation."""
    body = (ROOT / "skills" / "lire_pieces_jointes.md").read_text(encoding="utf-8")
    return h.upsert_skill(client, read_skill_name(s), description=READ_SKILL_DESCRIPTION, body=body,
                          archive_dir=skill_archive(s))


def create(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, tname, sname = run.meta, tool_name(run), skill_name(run, s.agent_prefix)
    tool = find(s, tname)   # clone local d'h-tools, sinon ce qu'h-tools a déployé (service web, fichiers de bureau)
    note_base_tool(run, tool)
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
                                              tool_ready=tool is not None, environment=target.as_dict(env),
                                              tool_sha=getattr(tool, "sha", None)))
    log(f"agent {name} : {'tool ' + tname if tool else 'computer use (tool pas encore déployé)'}")


def upgrade(run: Run, s: Settings, log: Callable[[str], None]) -> str | None:
    """Le tool est déployé par h-tools (ou présent dans le clone local) : l'agent reçoit le tool et la Skill du repo.

    Appelé tout seul quand h-tools prévient SMO (POST /hooks/tool-deployed), ou à la main :
    `smo run <id> --only upgrade --force`.
    """
    tool = find(s, tool_name(run))
    if tool is None or awaits_new_tool(run, getattr(tool, "sha", None)):
        pr = run.read_model("compile.json", CompileResult).pr_url if run.has("compile.json") else None
        state = "pas encore déployé" if tool is None else "encore dans sa version d'avant la démo"
        log(f"tool {state} : PR {pr or '(voir compile.json)'} → fusion dans h-tools → déploiement "
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
    """L'agent a son tool, et pour une amélioration, celui qui suit la démo."""
    if not run.has("agent.json"):
        return False
    agent = run.read_model("agent.json", Provisioned)
    return agent.tool_ready and not awaits_new_tool(run, agent.tool_sha)
