"""Request and response formats of the API.

Separate from the database's data objects: what goes to the outside should
be able to evolve independently of the internals.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agenten import Agent
from app.db.models import Auftrag, AuftragSchritt, Chat, Document, Message


class ChatAnlegen(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    endpoint_id: str | None = None


class ChatAendern(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    # Suspends the system prompt for this one chat. The prompt itself lives
    # in a file and is not touched here.
    prompt_aus: bool | None = None
    endpoint_id: str | None = None
    pinned: bool | None = None
    # The working folders (shell tool): absolute paths to existing
    # folders — checked in the handler, four at most. An empty list deselects.
    working_dirs: list[str] | None = None


class ChatAntwort(BaseModel):
    id: str
    user_id: str
    title: str
    prompt_aus: bool
    endpoint_id: str | None
    pinned: bool
    working_dirs: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    @classmethod
    def aus(cls, chat: Chat) -> "ChatAntwort":
        return cls(**chat.__dict__)


class NachrichtAnlegen(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    reasoning: str | None = None
    stats: dict[str, Any] | None = None


class NachrichtAntwort(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    reasoning: str | None
    stats: dict[str, Any]
    created_at: str
    # File name of the attached image (vision) — the UI fetches it via
    # GET /api/v1/images/{name}.
    bild: str | None = None
    # Meta card of the attached document (4.1) — built by the server from
    # the documents row; the message itself carries only the id.
    dokument: dict[str, Any] | None = None

    @classmethod
    def aus(cls, nachricht: Message, dokument: dict[str, Any] | None = None) -> "NachrichtAntwort":
        daten = dict(nachricht.__dict__)
        daten["dokument"] = dokument
        return cls(**daten)


class DokumentAntwort(BaseModel):
    id: str
    chat_id: str
    filename: str
    mime_type: str | None
    size_bytes: int | None
    created_at: str

    @classmethod
    def aus(cls, dokument: Document) -> "DokumentAntwort":
        daten = dict(dokument.__dict__)
        daten.pop("extracted_text", None)
        return cls(**daten)


class ModellAntwort(BaseModel):
    id: str
    name: str
    # Which provider this model sits behind, and what it is called there.
    # The id is built from both (see app/modellkennung.py); these two fields
    # spare the frontend from taking it apart again.
    anbieter: str = ""
    anbieter_name: str = ""
    modell: str | None = None
    # Named by the configuration — picked without anyone having to tick it.
    angeheftet: bool = False
    # Second line in the picker menu. Derived, not maintained.
    quelle: str = ""
    provider: str
    dialekt: str = "openai"
    reasoning_format: str
    erreichbar: bool
    zuletzt_geprueft: str | None
    context_tokens: int | None = None
    capabilities: dict[str, bool]
    # local | cloud | extra - the model picker groups by this so it is
    # visible at a glance whether a request leaves the machine.
    group: str = "local"
    # Name of the environment variable holding the access key, and whether it
    # is filled. Never the key itself.
    schluessel_env: str | None = None
    schluessel_gesetzt: bool = False
    parameter: list[dict[str, Any]] = Field(default_factory=list)


class GenerierungAnfrage(BaseModel):
    """Request to the streaming proxy."""

    chat_id: str
    endpoint_id: str | None = None
    content: str | None = Field(
        default=None,
        description="Neue Benutzernachricht. Fehlt sie, wird auf dem "
        "vorhandenen Verlauf weitergearbeitet (z. B. beim Neu-Erzeugen).",
    )
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    parameter: dict[str, float] | None = None
    # Vision: file name of an image previously uploaded via POST /images.
    # Only allowed if the endpoint has capabilities.vision.
    bild: str | None = None
    # Document (4.1): the id from POST /documents. The server checks that it
    # belongs to this chat and builds the meta card itself from the database.
    dokument: str | None = None
    # The thinking switch (interface close-out A): true/false toggles
    # thinking, None leaves the server at its default. Only passed through
    # if the endpoint demonstrably supports switching.
    thinking: bool | None = None
    # A skill the user picked from the slash list. Its instruction rides along
    # with THIS request and is not stored — what should outlast the request is
    # the answer, not the instruction that produced it. An unknown name is
    # ignored rather than refused: the message itself was still meant.
    skill: str | None = None


class AbbruchAnfrage(BaseModel):
    generation_id: str | None = None
    chat_id: str | None = None


class AbbruchAntwort(BaseModel):
    abgebrochen: int


class BestaetigungAnfrage(BaseModel):
    """The user's answer to the confirmation prompt before a tool."""

    generation_id: str
    aufruf_id: str
    erlaubt: bool


class SystemPromptAntwort(BaseModel):
    """The system prompt and whether one is stored at all."""

    text: str
    datei: str


class SystemPromptAnfrage(BaseModel):
    text: str = Field(max_length=100_000)


class GedaechtnisAntwort(BaseModel):
    """The memory file and where it lives."""

    text: str
    datei: str


class GedaechtnisAnfrage(BaseModel):
    text: str = Field(max_length=100_000)


class BestaetigungAntwort(BaseModel):
    zugestellt: bool = Field(
        description="False, wenn niemand mehr auf diese Antwort wartet — "
        "die Generierung ist vorbei oder es wurde schon entschieden."
    )


# --- Agents and jobs (phase 6.3) --------------------------------------------
# Field names in English like the other API shapes; the state values
# themselves are fixed German keys ('laeuft', 'wartet', …) — the
# UI translates them via the catalog.


class AgentAntwort(BaseModel):
    name: str
    model: str | None
    tools: list[str]
    max_rounds: int
    max_minutes: float
    # The scheduler (6.7): "HH:MM" or null. ``schedule_paused`` says the
    # scheduler is currently suspended due to repeated failures — the UI
    # makes that visible.
    schedule: str | None = None
    schedule_paused: bool = False

    @classmethod
    def aus(cls, agent: Agent, *, pausiert: bool = False) -> "AgentAntwort":
        return cls(
            name=agent.name,
            model=agent.modell,
            tools=agent.werkzeuge,
            max_rounds=agent.runden,
            max_minutes=agent.minuten,
            schedule=agent.zeitplan,
            schedule_paused=pausiert,
        )


class AgentDatei(BaseModel):
    """The raw agent file for the editor window (6.6).

    ``kaputt`` carries the reason if the front matter is no good — the file
    is saved anyway (it is the user's file), but the agent is out of play,
    and the window should be able to say so.
    """

    name: str
    content: str
    kaputt: str | None = None


class AgentDateiSchreiben(BaseModel):
    content: str = Field(max_length=100_000)


class AgentDateiEintrag(BaseModel):
    """One entry of the file list for the editor window — the broken ones too.

    ``GET /agents`` only shows what is playable. The window needs more:
    a broken file that shows up nowhere could never be repaired.
    """

    name: str
    kaputt: str | None = None


class AuftragAnlegen(BaseModel):
    agent: str = Field(min_length=1, max_length=200)
    task: str = Field(min_length=1, max_length=50_000)
    # Overrides the model from the agent's front matter, if set.
    endpoint_id: str | None = None


class SchrittAntwort(BaseModel):
    nummer: int
    typ: str
    inhalt: str
    created_at: str

    @classmethod
    def aus(cls, schritt: AuftragSchritt) -> "SchrittAntwort":
        return cls(
            nummer=schritt.nummer,
            typ=schritt.typ,
            inhalt=schritt.inhalt,
            created_at=schritt.created_at,
        )


class AuftragAntwort(BaseModel):
    id: str
    agent: str
    task: str
    state: str
    end_reason: str | None
    result: str | None
    endpoint_id: str | None
    generation_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def aus(cls, auftrag: Auftrag) -> "AuftragAntwort":
        return cls(
            id=auftrag.id,
            agent=auftrag.agent,
            task=auftrag.auftrag,
            state=auftrag.zustand,
            end_reason=auftrag.ende_grund,
            result=auftrag.ergebnis,
            endpoint_id=auftrag.endpoint_id,
            generation_id=auftrag.generation_id,
            created_at=auftrag.created_at,
            updated_at=auftrag.updated_at,
        )


class AuftragDetail(AuftragAntwort):
    schritte: list[SchrittAntwort] = Field(default_factory=list)

    @classmethod
    def aus_mit_schritten(
        cls, auftrag: Auftrag, schritte: list[AuftragSchritt]
    ) -> "AuftragDetail":
        detail = cls(**AuftragAntwort.aus(auftrag).__dict__)
        detail.schritte = [SchrittAntwort.aus(schritt) for schritt in schritte]
        return detail
