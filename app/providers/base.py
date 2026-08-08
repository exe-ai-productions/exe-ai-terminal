"""Common interface of all model providers.

Adding a new provider means: write one file that implements ``Provider`` and
register it in the registry. The rest of the application — routes, database,
frontend — remains untouched. That is exactly why cloud models later are an
addition, not a rework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from app.config import EndpointConfig

StueckSorte = Literal["content", "reasoning", "stats", "error", "tool_call"]


@dataclass
class Werkzeugaufruf:
    """A tool the model wants executed."""

    id: str
    name: str
    argumente: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatNachricht:
    role: str
    content: str
    # Only with role='assistant': which tools the model requested.
    werkzeugaufrufe: list[Werkzeugaufruf] = field(default_factory=list)
    # Only with role='tool': which call the result belongs to.
    werkzeugaufruf_id: str | None = None
    # Only with role='user': an image as a data URL (vision). The provider
    # builds the OpenAI image format from it; endpoints without vision never
    # get one.
    bild_url: str | None = None


@dataclass
class Generierungsanfrage:
    nachrichten: list[ChatNachricht]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    modell: str | None = None
    # Further parameters under our own names (see app/parameter.py).
    # The provider translates them into its backend's names.
    parameter: dict[str, Any] = field(default_factory=dict)
    # Tools in OpenAI format. Empty = the model is offered none.
    werkzeuge: list[dict[str, Any]] = field(default_factory=list)
    zusatz: dict[str, Any] = field(default_factory=dict)


@dataclass
class Stueck:
    """One chunk from the answer stream."""

    sorte: StueckSorte
    text: str = ""
    daten: dict[str, Any] = field(default_factory=dict)
    # Only filled with sorte='tool_call'.
    werkzeugaufrufe: list[Werkzeugaufruf] = field(default_factory=list)


class ProviderFehler(Exception):
    """Error while talking to a model server."""


class Provider(ABC):
    """What every provider must be able to do."""

    def __init__(self, endpunkt: EndpointConfig) -> None:
        self.endpunkt = endpunkt

    @property
    def id(self) -> str:
        return self.endpunkt.id

    @property
    def name(self) -> str:
        """What the endpoint is called in error messages."""
        return self.endpunkt.name or self.endpunkt.id

    @property
    def faehigkeiten(self) -> dict[str, bool]:
        """What the provider can do — the frontend arranges its controls accordingly."""
        return self.endpunkt.capabilities.model_dump()

    @abstractmethod
    async def erreichbar(self, timeout: float = 3.0) -> bool:
        """Quick check whether the server answers."""

    async def modellname(self, timeout: float = 3.0) -> str | None:
        """What the model is called on the server.

        By default there is none — whoever can answer it overrides this.
        """
        return None

    async def kontextgroesse(self, timeout: float = 3.0) -> int | None:
        """How many tokens fit into the context — asked of the server.

        Not every server answers this. Whoever cannot returns None; then the
        value from the configuration applies, if there is one.
        """
        return self.endpunkt.context_tokens

    async def modelle_auflisten(self, timeout: float = 3.0) -> list[str]:
        """Every model this provider offers.

        A local server has exactly one loaded and reports that; a provider in
        the cloud has a catalogue. Whoever cannot answer returns an empty list
        — then the endpoint stands for itself, the way it always did.

        Asking rather than maintaining: what a provider offers changes without
        us, and a list kept by hand is wrong the day after it is written.
        """
        return []

    @abstractmethod
    def streamen(self, anfrage: Generierungsanfrage) -> AsyncIterator[Stueck]:
        """Produces the answer chunk by chunk.

        If the call is aborted (``aclose``), the connection to the model
        server must be closed — the stop button depends on this.
        """
