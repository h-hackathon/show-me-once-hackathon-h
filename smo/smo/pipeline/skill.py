"""Étape 5 : la Skill H (markdown), écrite sans LLM à partir de la procédure et des vérifications.

L'humain la relit et la corrige avant la suite (« l'agent apprend votre méthode, vous gardez la main »).
"""
from __future__ import annotations

from typing import Callable

from ..config import Settings
from ..models import Context, Procedure
from ..runs import Run, slug


VERB = {"navigate": "Aller sur", "click": "Cliquer sur", "type": "Remplir", "select": "Choisir dans",
        "check": "Vérifier", "read": "Lire"}


def skill_name(run: Run) -> str:
    meta = run.meta
    return f"smo-{slug(meta.owner, max_len=12)}-{slug(meta.task, max_len=40)}"


def tool_name(run: Run) -> str:
    """Nom du tool compilé : lettres, chiffres et _ (format imposé par H), aussi nom du dossier tools/<nom>."""
    return slug(run.meta.task, sep="_", max_len=40)


def render(procedure: Procedure, context: Context, url: str) -> str:
    corrections = {c.rule: c for c in context.rule_checks if c.verdict == "corrected" and c.correction}
    lines = [f"# {procedure.task}", "", f"Logiciel : {procedure.software} ({url})", "", "## Étapes"]
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
    return "\n".join(lines) + "\n"


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    procedure = run.read_model("procedure.json", Procedure)
    context = run.read_model("context.json", Context) if run.has("context.json") else Context()
    run.write_text("skill.md", render(procedure, context, run.meta.software_url))
    log(f"Skill écrite : {run.file('skill.md')}")


def review(run: Run, s: Settings, log: Callable[[str], None], auto: bool = False) -> str | None:
    """Point de contrôle humain. Renvoie "waiting" tant que la Skill n'est pas approuvée."""
    if auto or run.has("skill.approved"):
        run.write_text("skill.approved", "auto\n" if auto else "ok\n")
        return None
    log(f"À relire / corriger : {run.file('skill.md')}  puis  smo approve {run.id}")
    return "waiting"
