"""Dummy for tests.

Behaves like a real provider but needs no running model server. This lets
the integration tests of the whole chain (request → proxy → answer →
database) run on any machine, including CI.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.config import Capabilities, EndpointConfig
from app.providers.base import (
    Generierungsanfrage,
    Provider,
    ProviderFehler,
    Stueck,
    Werkzeugaufruf,
)
from app.reasoning import ReasoningParser


def mock_endpunkt(
    kennung: str = "mock",
    reasoning_format: str = "none",
    **felder,
) -> EndpointConfig:
    return EndpointConfig.model_validate(
        {
            "id": kennung,
            "name": f"Attrappe ({kennung})",
            "provider": "mock",
            "base_url": "http://mock.invalid/v1",
            "reasoning_format": reasoning_format,
            "capabilities": Capabilities(streaming=True, tool_calls=True).model_dump(),
            **felder,
        }
    )


class MockProvider(Provider):
    """Emits predefined chunks, with configurable behavior."""

    def __init__(
        self,
        endpunkt: EndpointConfig | None = None,
        *,
        haeppchen: list[str] | None = None,
        ist_erreichbar: bool = True,
        verzoegerung: float = 0.0,
        fehler: str | None = None,
        werkzeugaufrufe: list[Werkzeugaufruf] | None = None,
        modelle: list[str] | None = None,
    ) -> None:
        super().__init__(endpunkt or mock_endpunkt())
        self.haeppchen = haeppchen if haeppchen is not None else ["Hallo ", "Welt"]
        self.ist_erreichbar = ist_erreichbar
        self.verzoegerung = verzoegerung
        self.fehler = fehler
        # Tool calls for the first pass. After that the dummy answers with
        # text — otherwise the loop would never end.
        self.werkzeugaufrufe = werkzeugaufrufe or []
        # The catalogue this dummy claims to offer. Empty means: one address,
        # one model — the way a local server behaves.
        self.modelle = modelle or []
        # Inspectable by tests: was the stream closed prematurely?
        self.abgebrochen = False
        self.ausgegebene_haeppchen = 0
        self.durchlaeufe = 0
        self.letzte_anfrage: Generierungsanfrage | None = None
        self.alle_anfragen: list[Generierungsanfrage] = []

    async def erreichbar(self, timeout: float = 3.0) -> bool:
        return self.ist_erreichbar

    async def modelle_auflisten(self, timeout: float = 3.0) -> list[str]:
        return list(self.modelle)

    async def streamen(self, anfrage: Generierungsanfrage) -> AsyncIterator[Stueck]:
        self.letzte_anfrage = anfrage
        self.alle_anfragen.append(anfrage)
        self.durchlaeufe += 1
        if self.fehler:
            raise ProviderFehler(self.fehler)

        # Request tools on the first pass, answer normally afterwards.
        if self.werkzeugaufrufe and self.durchlaeufe == 1:
            yield Stueck("tool_call", werkzeugaufrufe=list(self.werkzeugaufrufe))
            return

        parser = ReasoningParser(self.endpunkt.reasoning_format)
        try:
            for haeppchen in self.haeppchen:
                if self.verzoegerung:
                    await asyncio.sleep(self.verzoegerung)
                self.ausgegebene_haeppchen += 1
                for sorte, text in parser.feed(haeppchen):
                    yield Stueck(sorte, text)
            for sorte, text in parser.finish():
                yield Stueck(sorte, text)
            yield Stueck(
                "stats",
                daten={
                    "dauer_sekunden": 0.0,
                    "haeppchen": self.ausgegebene_haeppchen,
                    "endpunkt": self.id,
                },
            )
        except GeneratorExit:
            # The consumer closed the stream — that is the stop button.
            self.abgebrochen = True
            raise
