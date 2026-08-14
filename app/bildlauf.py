"""A drawing job, written into the chat's little history.

The terminal module shows what happened in a conversation: which commands
ran, and how they ended. A picture ordered from the plus menu belongs in that
list for exactly the same reason a command does — somebody started something
here, it took a while, and it either worked or it did not. That it reaches
the generator over a different route than a tool call is an implementation
detail of the program, not something the reader should have to know.

Its own module because the run registry next door is the shell tool's, and
this is not a shell tool: it borrows the registry the way any other kind of
work may, and keeps its own vocabulary out of it. What the registry learned
for this is one neutral word — `art` — and nothing about pictures.

The prompt is what stands in the line, shortened: a run entry is one line,
and a prompt is written to be long.
"""

from __future__ import annotations

import logging

from app.tools.hintergrund import ABGEBROCHEN, ART_BILD, FEHLER, FERTIG, Lauf, laeufe

log = logging.getLogger(__name__)

# How much of the prompt stands in the line. Long enough to recognise which
# picture this was, short enough that the line stays a line.
MAX_ZEICHEN = 80


def kurzform(prompt: str) -> str:
    """The prompt as one line, shortened at a word boundary where possible."""
    eine_zeile = " ".join(prompt.split())
    if len(eine_zeile) <= MAX_ZEICHEN:
        return eine_zeile
    schnitt = eine_zeile[:MAX_ZEICHEN]
    luecke = schnitt.rfind(" ")
    if luecke > MAX_ZEICHEN // 2:
        schnitt = schnitt[:luecke]
    return schnitt + "…"


def beginnen(chat_id: str | None, prompt: str) -> Lauf | None:
    """Opens the entry. Without a chat there is no history to write into."""
    if not chat_id:
        return None
    try:
        return laeufe.anlegen(chat_id, kurzform(prompt), art=ART_BILD)
    except Exception:  # noqa: BLE001 - a log line must never break a picture
        log.exception("Bildlauf konnte nicht angelegt werden")
        return None


def beenden(lauf: Lauf | None, *, gescheitert: bool = False, abgebrochen: bool = False) -> None:
    """Closes the entry with the outcome the caller saw.

    A picture has no exit code — the state is what says how it went, and a
    stopped one is not a failure but a decision.
    """
    if lauf is None:
        return
    zustand = ABGEBROCHEN if abgebrochen else (FEHLER if gescheitert else FERTIG)
    try:
        laeufe.beenden(lauf, code=None, zustand=zustand)
    except Exception:  # noqa: BLE001 - same reason as above
        log.exception("Bildlauf konnte nicht beendet werden")
