"""Étape 5 : la Skill H (markdown), écrite sans LLM à partir de la procédure et des vérifications.

L'humain la relit et la corrige avant la suite (« l'agent apprend votre méthode, vous gardez la main »).
"""
from __future__ import annotations

import json
from string import Template
from typing import Callable

from ..config import ROOT, Settings
from ..models import Context, Procedure, SoftwareMap
from ..runs import Run, slug
from . import mapping


VERB = {"navigate": "Aller sur", "click": "Cliquer sur", "type": "Remplir", "select": "Choisir dans",
        "check": "Vérifier", "read": "Lire"}


def skill_name(run: Run) -> str:
    """Un agent, une Skill et un tool par type de logiciel (web, desktop) : le nom porte le type."""
    meta = run.meta
    return f"smo-{slug(meta.owner, max_len=12)}-{slug(meta.task, max_len=36)}-{meta.software_kind}"


def tool_name(run: Run) -> str:
    """Nom du tool compilé : lettres, chiffres et _ (format imposé par H), aussi nom du dossier tools/<nom>."""
    return f"{slug(run.meta.task, sep='_', max_len=36)}_{run.meta.software_kind}"


def with_common_block(body: str, tool: str | None, desktop_schema: dict | None = None) -> str:
    """La Skill envoyée à H : le titre, puis la règle absolue SMO (skills/), puis la méthode de la tâche.

    La règle vient en premier : le tool fait la tâche, l'écran n'est qu'un secours. Elle n'est ni montrée à la
    relecture ni écrite par Devin : SMO l'insère à chaque envoi dans H. Tool de bureau (desktop_schema) : la règle
    dit de le lancer depuis le shell de l'agent (./run.sh), avec le schéma de ses valeurs.
    """
    if desktop_schema is not None:
        name = "bloc_commun_bureau.md"
    else:
        name = "bloc_commun.md" if tool else "bloc_commun_sans_tool.md"
    block = Template((ROOT / "skills" / name).read_text(encoding="utf-8"))
    rule = block.substitute(precheck=f"precheck_{tool}", run=f"run_{tool}",
                            schema=json.dumps(desktop_schema or {}, ensure_ascii=False)).strip()
    title, _, rest = body.strip().partition("\n")
    if not title.startswith("# "):                     # pas de titre : la règle tout en haut
        title, rest = "", body.strip()
    return "\n\n".join(part for part in (title, rule, rest.strip()) if part) + "\n"


def render(procedure: Procedure, context: Context, url: str, soft_map: SoftwareMap | None = None) -> str:
    corrections = {c.rule: c for c in context.rule_checks if c.verdict == "corrected" and c.correction}
    lines = [f"# {procedure.task}", "",
             "## Objectif",
             f"{procedure.task} dans {procedure.software} ({url}), une pièce à la fois, en s'arrêtant en brouillon.", "",
             "## Prérequis",
             "- Être connecté au logiciel.",
             "- S'il faut choisir un dossier ou une société : celui du client indiqué sur la pièce.", "",
             "## Étapes"]
    for st in procedure.steps:
        line = f"{st.index + 1}. {VERB[st.action]} « {st.target} »"
        if st.value_source:
            line += f" : {st.value_source}"
        if st.why:
            line += f" ({st.why})"
        lines.append(line)
    lines += ["", "## Règles"]
    for rule in procedure.rules:
        fix = corrections.get(rule.text)
        if fix:
            lines.append(f"- {fix.correction} (corrigé par vérification ; dit pendant la démo : « {rule.text} »)")
        else:
            lines.append(f"- {rule.text}")
    lines += ["- Ne jamais cliquer sur « Valider » ou « Confirmer » : la pièce reste en brouillon.",
              "", "## S'arrêter et prévenir un humain si"]
    lines += [f"- {c}" for c in procedure.stop_conditions] or ["- une valeur est illisible ou incohérente"]
    if procedure.inputs:
        lines += ["", "## À lire sur la pièce"] + [f"- {i}" for i in procedure.inputs]
    if soft_map and soft_map.screens:
        lines += ["", "## Carte du logiciel", mapping.summary(soft_map)]
    return "\n".join(lines) + "\n"


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    procedure = run.read_model("procedure.json", Procedure)
    context = run.read_model("context.json", Context) if run.has("context.json") else Context()
    run.write_text("skill.md", render(procedure, context, run.meta.software_url, mapping.load(run)))
    log(f"Skill écrite : {run.file('skill.md')}")


def review(run: Run, s: Settings, log: Callable[[str], None], auto: bool = False) -> str | None:
    """Point de contrôle humain. Renvoie "waiting" tant que la Skill n'est pas approuvée."""
    if auto or run.has("skill.approved"):
        run.write_text("skill.approved", "auto\n" if auto else "ok\n")
        return None
    log(f"À relire / corriger : {run.file('skill.md')}  puis  smo approve {run.id}")
    return "waiting"
