"""Command runs: what is running, what it wrote, and who is watching.

Every ``run_command`` becomes a run here, foreground and background alike.
Three jobs in one place, because they are the same data seen from three
sides:

* **Live output.** A build that takes two minutes used to be two minutes of
  nothing. Each line is announced the moment it arrives, and the terminal
  window shows it.
* **Background runs.** A call may return at once and keep working. When it
  finishes, the result goes into the chat by itself — the alternative, a
  second tool for looking it up, was rejected: small models never look.
* **The kill switch.** Nothing outlives the program. Whatever is still
  running when the service stops is killed, so no process keeps writing into
  a folder while the chat that started it is gone.

The buffer is capped and keeps both ends: the start says what was being done,
the end says how it went, and the middle is the part nobody reads.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

log = logging.getLogger(__name__)

# How much of one run's output is kept. Enough for a long build log, far from
# enough to eat the memory of a machine that also runs a model.
MAX_PUFFER_ZEICHEN = 200_000

# How long a background run may take before it is stopped. The foreground has
# two minutes; a background run is meant for the long things, but not for
# forever.
HINTERGRUND_GRENZE_SEKUNDEN = 30 * 60

LAEUFT = "laeuft"
FERTIG = "fertig"
FEHLER = "fehler"
# Asked for, not gone wrong. Its own state because the colour rules treat a
# failure and a change of mind differently, and a stopped run should not
# leave a red mark in the history.
ABGEBROCHEN = "abgebrochen"

# What kind of work a run is. The list carries both because they are the same
# thing seen by the same eye: something started in this chat, and it ended.
ART_BEFEHL = "befehl"
ART_BILD = "bild"


@dataclass
class Lauf:
    """One command, from its first line to its exit code."""

    nummer: int
    chat_id: str
    befehl: str
    hintergrund: bool = False
    zustand: str = LAEUFT
    code: int | None = None
    zeilen: list[str] = field(default_factory=list)
    prozess: Any = None
    # What was run. A command writes lines and has an exit code; a picture
    # writes nothing and has a duration — one list, two shapes of entry.
    art: str = ART_BEFEHL
    # Monotonic, so a clock the user drags around cannot make a run last
    # minus two seconds.
    _begonnen: float = field(default_factory=time.monotonic)
    dauer_sekunden: float | None = None
    _zeichen: int = 0

    @property
    def ausgabe(self) -> str:
        return "\n".join(self.zeilen)

    def anhaengen(self, text: str) -> None:
        self.zeilen.append(text)
        self._zeichen += len(text) + 1
        if self._zeichen <= MAX_PUFFER_ZEICHEN:
            return
        # Keep both ends: the first lines say what was started, the last ones
        # say how it ended. What goes is the middle, and it says so.
        haelfte = MAX_PUFFER_ZEICHEN // 2
        kopf: list[str] = []
        laenge = 0
        for zeile in self.zeilen:
            if laenge + len(zeile) + 1 > haelfte:
                break
            kopf.append(zeile)
            laenge += len(zeile) + 1
        fuss: list[str] = []
        laenge = 0
        for zeile in reversed(self.zeilen):
            if laenge + len(zeile) + 1 > haelfte:
                break
            fuss.append(zeile)
            laenge += len(zeile) + 1
        fuss.reverse()
        weg = len(self.zeilen) - len(kopf) - len(fuss)
        if weg <= 0:
            return
        self.zeilen = [*kopf, f"… [{weg} lines cut out of the middle]", *fuss]
        self._zeichen = sum(len(z) + 1 for z in self.zeilen)


class Laufverwaltung:
    """All runs of all chats, and everyone watching them.

    In memory on purpose: a run belongs to a program that is running. What is
    worth keeping lands in the chat as a message.
    """

    def __init__(self) -> None:
        self._laeufe: dict[str, list[Lauf]] = {}
        self._zuschauer: dict[str, set[asyncio.Queue]] = {}
        # What to do with a finished background run. The tool cannot write to
        # the database; the service hangs its own handler in here at startup.
        self.abschluss: Callable[[Lauf, str], Any] | None = None

    # --- The runs --------------------------------------------------------

    def anlegen(
        self,
        chat_id: str,
        befehl: str,
        hintergrund: bool = False,
        art: str = ART_BEFEHL,
    ) -> Lauf:
        liste = self._laeufe.setdefault(chat_id, [])
        lauf = Lauf(
            nummer=len(liste) + 1,
            chat_id=chat_id,
            befehl=befehl,
            hintergrund=hintergrund,
            art=art,
        )
        liste.append(lauf)
        self.melden(
            chat_id,
            typ="lauf_start",
            lauf=lauf.nummer,
            befehl=befehl,
            hintergrund=hintergrund,
            art=art,
        )
        return lauf

    def zeile(self, lauf: Lauf, text: str, strom: str = "stdout") -> None:
        lauf.anhaengen(text)
        self.melden(
            lauf.chat_id, typ="lauf_zeile", lauf=lauf.nummer, text=text, strom=strom
        )

    def beenden(self, lauf: Lauf, code: int | None, zustand: str | None = None) -> None:
        """Closes a run. `zustand` overrides the exit-code reading.

        A picture has no exit code, and a stopped one is not a failure — both
        say for themselves how they ended.
        """
        lauf.code = code
        lauf.zustand = zustand or (FERTIG if code == 0 else FEHLER)
        lauf.prozess = None
        lauf.dauer_sekunden = round(time.monotonic() - lauf._begonnen, 1)
        self.melden(
            lauf.chat_id,
            typ="lauf_ende",
            lauf=lauf.nummer,
            code=code,
            zustand=lauf.zustand,
            hintergrund=lauf.hintergrund,
            dauer_sekunden=lauf.dauer_sekunden,
        )

    def laeufe(self, chat_id: str) -> list[Lauf]:
        return list(self._laeufe.get(chat_id, []))

    def holen(self, chat_id: str, nummer: int) -> Lauf | None:
        for lauf in self._laeufe.get(chat_id, []):
            if lauf.nummer == nummer:
                return lauf
        return None

    # --- Watchers --------------------------------------------------------

    def melden(self, chat_id: str, **daten: Any) -> None:
        for schlange in self._zuschauer.get(chat_id, set()):
            schlange.put_nowait(daten)

    async def zuschauen(self, chat_id: str) -> AsyncIterator[dict[str, Any]]:
        """Live events of this chat. What already happened is not repeated —
        the window asks for the runs so far through the ordinary route."""
        schlange: asyncio.Queue = asyncio.Queue()
        self._zuschauer.setdefault(chat_id, set()).add(schlange)
        try:
            while True:
                yield await schlange.get()
        finally:
            self._zuschauer.get(chat_id, set()).discard(schlange)

    # --- The kill switch --------------------------------------------------

    def alle_toeten(self) -> int:
        """Stops everything still running. Called when the service goes down."""
        getoetet = 0
        for laeufe in self._laeufe.values():
            for lauf in laeufe:
                if lauf.zustand != LAEUFT or lauf.prozess is None:
                    continue
                try:
                    lauf.prozess.kill()
                    getoetet += 1
                except (ProcessLookupError, OSError):
                    pass
                lauf.zustand = FEHLER
                lauf.prozess = None
        return getoetet

    def vergessen(self, chat_id: str) -> None:
        self._laeufe.pop(chat_id, None)


# Process-wide, like the event bus: one program, one set of runs.
laeufe = Laufverwaltung()
