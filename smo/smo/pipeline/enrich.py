"""Étape 4 : Linkup vérifie les règles dites par l'humain (et cherche la doc du logiciel s'il est public).

Exemple vécu en préparation : « fournisseur étranger → TVA 0 % » est faux, la bonne saisie est l'autoliquidation.
"""
from __future__ import annotations

from typing import Callable

from ..clients import linkup
from ..config import Settings
from ..models import Context, Procedure, RuleCheck
from ..runs import Run


RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirmed", "corrected", "unverified"]},
        "correction": {"type": "string", "description": "la règle correcte si elle est fausse ou incomplète, sinon vide"},
        "explanation": {"type": "string"},
    },
    "required": ["verdict", "explanation"],
}

QUESTION = ("Règle appliquée en France pendant la tâche « {task} » : « {rule} ». "
            "Est-elle correcte au regard de la réglementation et des pratiques comptables ? "
            "Si elle est fausse ou incomplète, donne la règle correcte.")


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, procedure = run.meta, run.read_model("procedure.json", Procedure)
    context = Context()
    for rule in procedure.rules:
        if rule.kind not in ("check", "exception"):
            continue
        answer = linkup.search(QUESTION.format(task=meta.task, rule=rule.text), s.linkup_api_key, schema=RULE_SCHEMA)
        data = answer.get("data", answer) if isinstance(answer.get("data"), dict) else answer
        check = RuleCheck(rule=rule.text, verdict=data.get("verdict", "unverified"),
                          correction=data.get("correction") or None, explanation=data.get("explanation"),
                          sources=linkup.source_urls(answer))
        context.rule_checks.append(check)
        log(f"{check.verdict:>11} : {rule.text}" + (f" → {check.correction}" if check.correction else ""))
    if meta.software_name:
        doc = linkup.search(f"Documentation {meta.software_name} : comment {meta.task.lower()}", s.linkup_api_key)
        context.software_notes.append(doc.get("answer", ""))
        context.sources += linkup.source_urls(doc)
    run.write_model("context.json", context)
