"""Étape 4 (obligatoire) : Linkup vérifie les règles dites par l'humain (la doc du logiciel est cherchée à l'étape docs).

Recherche « standard » (1 à 3 s, ≈0,006 $ par règle), toutes les règles en parallèle ; « deep » coûte 10 fois plus
et prend ~35 s par règle pour un verdict équivalent sur nos cas. La réponse est bornée au schéma ci-dessous + sources.
Exemple vécu en préparation : « fournisseur étranger → TVA 0 % » est faux, la bonne saisie est l'autoliquidation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..clients import linkup
from ..config import Settings
from ..models import Context, Procedure, RuleCheck
from ..runs import Run


RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirmed", "corrected", "unverified"]},
        "correction": {"type": "string", "description": "si la règle est fausse ou incomplète : la règle correcte en une "
                                                        "phrase courte, à appliquer telle quelle pendant la saisie ; sinon vide"},
        "explanation": {"type": "string", "description": "le raisonnement et les cas particuliers"},
    },
    "required": ["verdict", "explanation"],
}

QUESTION = ("Règle appliquée en France pendant la tâche « {task} » : « {rule} ». "
            "Est-elle correcte au regard de la réglementation et des pratiques comptables ? "
            "Si elle est fausse ou incomplète, donne la règle correcte.")


def check(task: str, rule: str, api_key: str) -> RuleCheck:
    answer = linkup.search(QUESTION.format(task=task, rule=rule), api_key, schema=RULE_SCHEMA)
    data = answer.get("data", answer) if isinstance(answer.get("data"), dict) else answer
    return RuleCheck(rule=rule, verdict=data.get("verdict", "unverified"), correction=data.get("correction") or None,
                     explanation=data.get("explanation"), sources=linkup.source_urls(answer))


def run(run: Run, s: Settings, log: Callable[[str], None]) -> None:
    meta, procedure = run.meta, run.read_model("procedure.json", Procedure)
    rules = [rule.text for rule in procedure.rules if rule.kind in ("check", "exception")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(lambda rule: check(meta.task, rule, s.linkup_api_key), rules))
    for c in checks:
        log(f"{c.verdict:>11} : {c.rule}" + (f" → {c.correction}" if c.correction else ""))
    run.write_model("context.json", Context(rule_checks=checks))
