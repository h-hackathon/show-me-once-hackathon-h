"""Les étapes nommées d'un tool : une panne dit où elle a eu lieu (« saisie du fournisseur »), pas seulement quoi.

Sans Playwright : utilisable par les tools web et de bureau, et dans les tests hors ligne.

    with step("saisie du fournisseur"):
        locate(page, {"label": "Fournisseur"}).fill(params.fournisseur)
"""
from __future__ import annotations

from contextlib import contextmanager


class StepError(Exception):
    def __init__(self, step: str, cause: Exception):
        super().__init__(f"{step} : {type(cause).__name__}: {cause}")
        self.step, self.cause = step, cause


@contextmanager
def step(name: str):
    try:
        yield
    except StepError:
        raise                          # étape imbriquée : on garde la plus précise
    except Exception as err:
        raise StepError(name, err) from err
