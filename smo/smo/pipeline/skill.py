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


# La seule règle de sécurité commune à toutes les tâches, quel que soit le logiciel : c'est un humain qui finalise.
NEVER_FINALIZE = ("Ne jamais finaliser (valider, confirmer, envoyer, payer, supprimer) : enregistrer sans finaliser, "
                  "un humain s'en charge.")

VERB = {"navigate": "Aller sur", "click": "Cliquer sur", "type": "Remplir", "select": "Choisir dans",
        "check": "Vérifier", "read": "Lire"}


def name_for(task: str, kind: str, prefix: str = "smo-") -> str:
    """Un agent, une Skill et un tool par tâche et type de logiciel (web, desktop) : le nom porte le type. Le préfixe
    est celui des agents (SMO_AGENT_PREFIX) : un SMO de test ne réécrit pas les Skills de celui de Railway."""
    return f"{prefix}{slug(task, max_len=40)}-{kind}"


def skill_name(run: Run, prefix: str = "smo-") -> str:
    return name_for(run.meta.task, run.meta.software_kind, prefix)


def tool_name(run: Run) -> str:
    """Nom du tool compilé : lettres, chiffres et _ (format imposé par H), aussi nom du dossier tools/<nom>."""
    return f"{slug(run.meta.task, sep='_', max_len=36)}_{run.meta.software_kind}"


def with_common_block(body: str, tool: str | None, desktop_schema: dict | None = None) -> str:
    """La Skill envoyée à H : le titre, puis le bloc commun SMO (skills/), puis la méthode de la tâche.

    La règle absolue (le tool fait la tâche, l'écran n'est qu'un secours) est dans les instructions de l'agent ; le
    bloc n'en donne que le détail (statuts, report_drift, mode). Il n'est ni montré à la relecture ni écrit par
    Devin : SMO l'insère à chaque envoi dans H. Tool de bureau (desktop_schema) : la règle
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
             f"{procedure.task} dans {procedure.software} ({url}), une pièce à la fois, sans jamais finaliser.", "",
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
    lines += [f"- {NEVER_FINALIZE}",
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
