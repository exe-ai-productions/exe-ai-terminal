"""Internal event system (publish/subscribe).

Purpose: decouple modules. The streaming proxy does not need to know who
reacts to a finished answer — it announces ``model_response_finished``, and
whoever is interested (save chat, count tokens, update statistics) has
subscribed beforehand.

Handlers may be synchronous or asynchronous. An error in one handler does not
stop the others — it is logged and the flow continues.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

Handler = Callable[..., Any | Awaitable[Any]]


class Ereignisse:
    """Names of the known events — no loose strings in the code."""

    CHAT_ERSTELLT = "chat_created"
    CHAT_GELOESCHT = "chat_deleted"
    NACHRICHT_GESPEICHERT = "message_saved"
    ANTWORT_FERTIG = "model_response_finished"
    ANTWORT_ABGEBROCHEN = "model_response_cancelled"
    ENDPUNKT_STATUS_GEAENDERT = "endpoint_status_changed"


class EventBus:
    def __init__(self) -> None:
        self._handler: dict[str, list[Handler]] = defaultdict(list)

    def abonnieren(self, ereignis: str, handler: Handler) -> None:
        self._handler[ereignis].append(handler)

    def abbestellen(self, ereignis: str, handler: Handler) -> None:
        if handler in self._handler.get(ereignis, []):
            self._handler[ereignis].remove(handler)

    def abonnenten(self, ereignis: str) -> list[Handler]:
        return list(self._handler.get(ereignis, []))

    def alles_loeschen(self) -> None:
        """Tests only."""
        self._handler.clear()

    async def veroeffentlichen(self, ereignis: str, **daten: Any) -> None:
        """Calls all handlers of the event. Errors are logged, not raised."""
        handler_liste = self._handler.get(ereignis, [])
        if not handler_liste:
            return

        for handler in list(handler_liste):
            try:
                ergebnis = handler(**daten)
                if inspect.isawaitable(ergebnis):
                    await ergebnis
            except Exception:  # noqa: BLE001 - a broken subscriber must not block anything
                log.exception(
                    "Handler für Ereignis '%s' ist fehlgeschlagen: %r", ereignis, handler
                )

    def veroeffentlichen_ohne_warten(self, ereignis: str, **daten: Any) -> None:
        """Fires an event from synchronous code without waiting for it."""
        try:
            schleife = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.veroeffentlichen(ereignis, **daten))
            return
        schleife.create_task(self.veroeffentlichen(ereignis, **daten))


# Process-wide bus. Tests create their own when needed.
bus = EventBus()
