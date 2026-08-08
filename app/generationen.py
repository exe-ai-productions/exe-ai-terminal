"""Manage running answers — and, since 6.1, own them too.

An answer used to run *inside* the request: the loop sat in the generator of
the ``StreamingResponse``, and when the browser closed, it was over. For a
chat that is right — nobody should heat up the GPU while no one is watching.
For an agent it would be exactly wrong.

So now **the run** owns the loop, not the request. It runs as its own
background task, writes its events into a memory and passes them on to
everyone currently watching. A request is merely one of those watchers.

Two kinds of run:

* ``an_verbindung_gebunden=True`` — a chat. If the *owning* request goes
  away, the run is cancelled. A second watcher saying goodbye changes
  nothing.
* ``an_verbindung_gebunden=False`` — a job. Keeps running no matter who is
  watching.

**On the name:** This is still called ``Generierung`` because so far there is
only one kind. As soon as agents exist (6.3), the word no longer fits and the
rename to ``Lauf`` comes along with them — doing it now would just be noise.

The confirmation prompt before a tool (1.6) also runs via the same id: the
stream only goes one way, so the user's answer comes in via
``/api/v1/chat/confirm`` and is delivered here to the waiting answer.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable

log = logging.getLogger(__name__)

# How many finished runs stay in memory. This lets someone who only looks
# shortly after the end still see the transcript. Keep it small: what lasts
# lives in the database, this here is only the display window.
VERGANGENE_LAEUFE = 50


@dataclass
class Generierung:
    id: str
    chat_id: str
    endpoint_id: str
    # Chat or job — see module header.
    an_verbindung_gebunden: bool = True
    signal: asyncio.Event = field(default_factory=asyncio.Event)
    # Open confirmation prompts: tool-call id -> decision.
    bestaetigungen: dict[str, "asyncio.Future[bool]"] = field(default_factory=dict)

    # --- Memory and watchers (6.1) --------------------------------------
    # Every reported line, in order of occurrence. Whoever joins later
    # catches up here on what they missed.
    ereignisse: list[str] = field(default_factory=list)
    _zuschauer: set[asyncio.Queue] = field(default_factory=set)
    fertig: asyncio.Event = field(default_factory=asyncio.Event)
    aufgabe: asyncio.Task | None = None

    @property
    def soll_abbrechen(self) -> bool:
        return self.signal.is_set()

    # --- Confirmation prompts --------------------------------------------

    def bestaetigung_erwarten(self, aufruf_id: str) -> "asyncio.Future[bool]":
        zukunft: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.bestaetigungen[aufruf_id] = zukunft
        return zukunft

    def bestaetigung_ablegen(self, aufruf_id: str) -> None:
        self.bestaetigungen.pop(aufruf_id, None)

    # --- Events ----------------------------------------------------------

    def melden(self, zeile: str) -> None:
        """One line into memory and to everyone currently watching."""
        self.ereignisse.append(zeile)
        for schlange in self._zuschauer:
            schlange.put_nowait(zeile)

    def beenden(self) -> None:
        """The run is done. Watchers get the end marker."""
        if self.fertig.is_set():
            return
        self.fertig.set()
        for schlange in self._zuschauer:
            schlange.put_nowait(None)

    async def zuschauen(self, ab: int = 0) -> AsyncIterator[str]:
        """First catch up on what happened, then continue live.

        ``ab`` is the counter position to read from — this lets a watcher
        whose connection was torn down reattach exactly where they left off.

        **Between catch-up and live, nothing may fall through and nothing may
        arrive twice.** That is why the queue is registered *first* and the
        counter taken *afterwards*: everything up to ``stand`` is already in
        memory, everything from ``stand`` on lands in the queue. There is no
        waiting in between, and without an ``await`` nothing in asyncio can
        butt in.
        """
        schlange: asyncio.Queue = asyncio.Queue()
        self._zuschauer.add(schlange)
        stand = len(self.ereignisse)
        war_fertig = self.fertig.is_set()
        try:
            for zeile in self.ereignisse[ab:stand]:
                yield zeile
            # The run was already over when we arrived — then there is no live part.
            if war_fertig:
                return
            while True:
                zeile = await schlange.get()
                if zeile is None:
                    return
                yield zeile
        finally:
            self._zuschauer.discard(schlange)


class Generierungsverwaltung:
    def __init__(self) -> None:
        self._laufende: dict[str, Generierung] = {}
        # Finished ones, so a late watcher can still find the transcript.
        self._vergangene: deque[Generierung] = deque(maxlen=VERGANGENE_LAEUFE)

    # --- Creating and starting -------------------------------------------

    def anmelden(
        self, *, chat_id: str, endpoint_id: str, an_verbindung_gebunden: bool = True
    ) -> Generierung:
        generierung = Generierung(
            id=uuid.uuid4().hex,
            chat_id=chat_id,
            endpoint_id=endpoint_id,
            an_verbindung_gebunden=an_verbindung_gebunden,
        )
        self._laufende[generierung.id] = generierung
        return generierung

    def starten(
        self,
        *,
        chat_id: str,
        endpoint_id: str,
        arbeit: Callable[[Generierung], Awaitable[None]],
        an_verbindung_gebunden: bool = True,
    ) -> Generierung:
        """Creates the run and sends the work into the background.

        From here on the work depends on nothing coming from outside. Whoever
        wants to watch calls ``zuschauen()``; whoever wants to cancel,
        ``abbrechen()``.
        """
        generierung = self.anmelden(
            chat_id=chat_id,
            endpoint_id=endpoint_id,
            an_verbindung_gebunden=an_verbindung_gebunden,
        )

        async def huelle() -> None:
            try:
                await arbeit(generierung)
            except asyncio.CancelledError:
                # Cancellation from outside is not a malfunction, it is the stop button.
                raise
            except Exception:  # noqa: BLE001 - a run must not drag the service down with it
                log.exception("Lauf %s ist unerwartet gescheitert", generierung.id)
            finally:
                generierung.beenden()

        generierung.aufgabe = asyncio.create_task(huelle(), name=f"lauf-{generierung.id}")
        return generierung

    # --- Lookup -----------------------------------------------------------

    def holen(self, generierung_id: str) -> Generierung | None:
        """A run, whether it is still running or just finished."""
        treffer = self._laufende.get(generierung_id)
        if treffer is not None:
            return treffer
        for vergangen in self._vergangene:
            if vergangen.id == generierung_id:
                return vergangen
        return None

    def laufende(self) -> list[Generierung]:
        return list(self._laufende.values())

    # --- Finishing --------------------------------------------------------

    def abmelden(self, generierung_id: str) -> None:
        generierung = self._laufende.pop(generierung_id, None)
        if generierung is None:
            return
        # Whoever is still waiting for an answer is no longer waiting on anyone.
        for zukunft in generierung.bestaetigungen.values():
            if not zukunft.done():
                zukunft.cancel()
        generierung.bestaetigungen.clear()
        self._vergangene.append(generierung)

    def abbrechen(self, generierung_id: str) -> bool:
        """True if this answer existed and is now being cancelled."""
        generierung = self._laufende.get(generierung_id)
        if generierung is None:
            return False
        generierung.signal.set()
        return True

    def alle_im_chat_abbrechen(self, chat_id: str) -> int:
        anzahl = 0
        for generierung in self._laufende.values():
            if generierung.chat_id == chat_id:
                generierung.signal.set()
                anzahl += 1
        return anzahl

    def bestaetigen(self, generierung_id: str, aufruf_id: str, erlaubt: bool) -> bool:
        """Deliver the user's decision.

        False here does not mean "denied" but "nobody is waiting for this
        answer" — the answer is over, or the click already happened.
        """
        generierung = self._laufende.get(generierung_id)
        if generierung is None:
            return False
        zukunft = generierung.bestaetigungen.get(aufruf_id)
        if zukunft is None or zukunft.done():
            return False
        zukunft.set_result(erlaubt)
        return True
