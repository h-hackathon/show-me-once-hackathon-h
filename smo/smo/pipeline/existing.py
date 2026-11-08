"""Avant une démo : la tâche a-t-elle déjà un agent SMO dans H, du même nom ou d'un nom proche ?

La page le demande avant d'enregistrer. Même nom : améliorer l'existant, ou changer de titre (sinon la nouvelle démo
écraserait l'agent sans le dire). Nom proche : souvent la même tâche, titrée autrement, qu'il vaut mieux améliorer
que doubler.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from pydantic import BaseModel

from ..clients import h
from ..config import Settings
from ..runs import slug
from .provision import RULE_WITHOUT_TOOL
from .skill import name_for

DESCRIBED = ", appris d'une démonstration ("   # provision.create : « <tâche>, appris d'une démonstration (<type>). »
SIMILAR = 0.75                                 # ressemblance des titres, de 0 à 1
PAGE = 100


class Existing(BaseModel):
    name: str
    task: str
    exact: bool                # même nom : la démo le remplacerait
    has_tool: bool             # le tool de Devin est déjà là (sinon l'agent travaille à l'écran)


def task_of(agent) -> str | None:
    description = agent.description or ""
    return description.split(DESCRIBED)[0] if DESCRIBED in description else None


def similar(a: str, b: str) -> bool:
    words_a, words_b = ({w for w in slug(x).split("-") if len(w) > 3} for x in (a, b))
    shared = len(words_a & words_b) / max(1, len(words_a | words_b))
    return shared >= SIMILAR or SequenceMatcher(None, slug(a), slug(b)).ratio() >= SIMILAR


def agents(client, prefix: str) -> list:
    found, page = [], 1
    while True:
        items = client.agents.list_agents(page=page, size=PAGE).items
        found += [a for a in items if a.name.startswith(prefix)]
        if len(items) < PAGE:
            return found
        page += 1


def candidates(s: Settings, task: str, kind: str) -> list[Existing]:
    """Les agents SMO du même type de logiciel dont le titre est le même ou proche, le même d'abord."""
    target = name_for(task, kind, s.agent_prefix)
    out = []
    for agent in agents(h.client(s.hai_api_key), s.agent_prefix):
        known = task_of(agent)
        # agent qu'on ne saurait pas recréer sous le même nom (créé à la main, ancien format) : on ne le propose pas
        if not known or name_for(known, kind, s.agent_prefix) != agent.name:
            continue
        if agent.name == target or similar(known, task):
            out.append(Existing(name=agent.name, task=known, exact=agent.name == target,
                                has_tool=RULE_WITHOUT_TOOL not in (agent.instructions or "")))
    return sorted(out, key=lambda e: not e.exact)
