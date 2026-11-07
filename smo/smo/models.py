"""Formats d'échange entre les étapes du pipeline (un fichier JSON par étape dans runs/<id>/)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CaptureMeta(BaseModel):
    """Ce qu'on sait de la capture avant de la traiter (meta.json)."""
    task: str                              # ex. « Saisir une facture fournisseur »
    software_kind: Literal["web", "desktop"] = "web"   # un agent H par type : navigateur ou bureau du Mac
    software_url: str                      # web : l'adresse ; bureau : le nom de l'application ouverte
    software_name: str | None = None       # nom public du logiciel (ex. « Odoo »), pour chercher sa doc (Linkup)
    owner: str = "demo"                    # ex. « catherine » : à qui appartiendra l'agent
    language: str = "fr"
    sample: str | None = None              # la pièce traitée pendant la démo (ex. « INV-001 »)
    created_at: datetime = Field(default_factory=datetime.now)


class Utterance(BaseModel):
    index: int
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    language: str
    utterances: list[Utterance]

    @property
    def text(self) -> str:
        return " ".join(u.text for u in self.utterances)


class Frame(BaseModel):
    utterance_index: int | None            # None = image de référence (ex. la facture)
    time_s: float | None
    path: str                              # relatif au dossier du run


class FrameSet(BaseModel):
    frames: list[Frame]
    references: list[Frame] = []
    final: str | None = None               # dernière image de la vidéo : le résultat attendu, pour juger les essais


class Step(BaseModel):
    index: int
    action: Literal["navigate", "click", "type", "select", "check", "read"]
    target: str                            # l'élément visé, par son libellé visible
    value_source: str | None = None        # d'où vient la valeur (ex. « facture : n° de facture »)
    why: str | None = None                 # la raison donnée par l'humain
    utterance_index: int | None = None


class ScreenReading(BaseModel):
    """Ce que Holo voit sur la capture d'une phrase (passe 1, une image par appel)."""
    screen: str | None = None              # titre ou nom de l'écran
    action: str = "none"                   # navigate, click, type, select, check, read ou none
    target: str | None = None              # libellé exact de l'élément concerné
    value: str | float | int | None = None


class ScreenNote(ScreenReading):
    utterance_index: int
    error: str | None = None               # capture illisible : la passe 2 s'appuie alors sur la phrase seule


class DocumentReading(BaseModel):
    """Ce que Holo lit sur une pièce de référence (ex. la facture de la démo)."""
    kind: str | None = None
    fields: dict[str, str | float | int | None] = {}


class DocumentNote(DocumentReading):
    path: str
    error: str | None = None               # pièce illisible : la synthèse fait sans


class Notes(BaseModel):
    """Passe 1 de la compréhension (notes.json)."""
    screens: list[ScreenNote] = []
    documents: list[DocumentNote] = []


class Rule(BaseModel):
    text: str
    kind: Literal["check", "exception", "never", "stop"]
    source: Literal["voice", "screen", "linkup"] = "voice"


class Procedure(BaseModel):
    """Ce que Holo a compris de la démo (procedure.json)."""
    task: str
    software: str
    steps: list[Step]
    rules: list[Rule]
    stop_conditions: list[str] = []
    inputs: list[str] = []                 # champs à lire sur la pièce à traiter


class RuleCheck(BaseModel):
    rule: str
    verdict: Literal["confirmed", "corrected", "unverified"]
    correction: str | None = None
    explanation: str | None = None
    sources: list[str] = []


class Context(BaseModel):
    """Ce que Linkup a vérifié ou ajouté (context.json)."""
    rule_checks: list[RuleCheck] = []
    software_notes: list[str] = []
    sources: list[str] = []


class TraceStep(BaseModel):
    index: int
    timestamp: str | None = None
    instruction: str | None = None         # la consigne de l'humain en cours
    url: str | None = None
    title: str | None = None
    reasoning: str | None = None
    actions: list[dict[str, Any]] = []     # tool_reqs bruts de l'agent H (nom + arguments)
    results: list[Any] = []
    screenshot: str | None = None          # fichier local, ou URL si le téléchargement a échoué
    page_text: str | None = None


class Trace(BaseModel):
    """Ce que l'agent H a réellement fait à l'écran (trace.json)."""
    session_id: str
    agent: str
    status: str
    steps: list[TraceStep]
    answer: Any = None
    agent_view_url: str | None = None


class CompileResult(BaseModel):
    """La session Devin qui écrit le tool (compile.json)."""
    tool_name: str
    devin_id: str
    url: str | None = None
    status: str | None = None
    pr_url: str | None = None
    mode: Literal["create", "repair"] = "create"


class Provisioned(BaseModel):
    """L'agent custom créé dans H (agent.json)."""
    agent_name: str
    skill_name: str
    tools: list[str]
    tool_ready: bool                       # False : l'agent travaille en computer use en attendant le tool
    environment: dict[str, Any]


class ScreenMap(BaseModel):
    """Un écran du logiciel, relevé par l'agent cartographe."""
    name: str                              # titre ou nom visible
    url: str | None = None
    how_to_reach: str | None = None        # menus / boutons depuis l'écran précédent
    fields: list[str] = []                 # libellés exacts des champs
    buttons: list[str] = []                # libellés exacts des boutons et liens utiles


class MapAnswer(BaseModel):
    """Format de réponse imposé à l'agent cartographe."""
    screens: list[ScreenMap]
    notes: str | None = None               # pièges vus (écran intermédiaire, fenêtre de confirmation…)


class SoftwareMap(MapAnswer):
    """La carte du logiciel pour une tâche (map.json, gardée dans runs/_maps/)."""
    software_url: str
    task: str
    session_id: str | None = None
    replay_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class Verdict(BaseModel):
    """Holo compare l'écran final de l'agent à celui de la démo : même résultat ou pas."""
    success: bool
    gap: str | None = None                 # ce qui diffère
    lesson: str | None = None              # consigne courte à ajouter à la Skill pour l'essai suivant


class Attempt(BaseModel):
    n: int
    session_id: str
    replay_url: str | None = None
    answer: Any = None
    verdict: Verdict


class Trial(BaseModel):
    """Les essais de l'agent (trial.json) : démo → essai → oui / non → nouvel essai ou Devin."""
    attempts: list[Attempt] = []
    success: bool = False


class RunReport(BaseModel):
    """Format de réponse imposé à l'agent custom."""
    status: Literal["done", "flagged", "failed"]
    mode: Literal["tool", "computer_use"]
    reference: str | None = None
    summary: str
    flags: list[str] = []
