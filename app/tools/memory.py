"""The memory tool — ``memory_save``.

Built in rather than an MCP server, for the same reason as the shell tool:
the file belongs to the program, and an outside process would have to be told
where it is on every call — and anything passed as an argument can be forged
by the model.

What it can do is deliberately narrow. It appends ONE entry under one of two
headings, or replaces ONE existing entry with a new one. It cannot hand over
whole file contents, and it cannot delete: a model that can write the file in
one go can also wipe it in one go, and clearing the memory is the user's move,
one button away in the settings window.

The two kinds are not decoration:

  * A **rule** changes behaviour and applies always.
  * A **fact** is knowledge and applies where it fits.

Neither asks before it is stored. There is exactly one prompt in the whole
program — the shell reaching outside the shared folders — and it is worth
something only because it is rare. A prompt that comes ten times a session
gets clicked away without reading, and then it protects nothing.

What carries that here is that the memory is **visible and reversible**: it
is one file, it stands open in the settings window, and any line can be
deleted in a click. Looking at it does everything a prompt would have done,
and it does it after the fact instead of in the way.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.gedaechtnis import UEBERSCHRIFT_FAKTEN, UEBERSCHRIFT_REGELN
from app.tools.mcp_client import MCPWerkzeug

log = logging.getLogger(__name__)

SERVER_NAME = "memory"
WERKZEUG_NAME = "memory_save"

# Long enough for a rule with its reasoning, short enough that nobody parks a
# whole document in the file that travels with every single request.
MAX_LAENGE = 600

REGEL = "rule"
FAKTUM = "fact"

# One writer at a time. A chat and a job running overnight can hit this in the
# same second, and both do read-modify-write — without the gate one of them
# writes over what the other just added.
_schleuse = asyncio.Lock()


class MemoryVerboten(Exception):
    """The call was refused — nothing was written."""


def werkzeug_beschreibung() -> MCPWerkzeug:
    """The tool as the model sees it."""
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Remembers one thing about this user across conversations: how "
            "they want to be worked with, what they prefer, who they are, how "
            "their project is put together.\n"
            "Kind 'rule' is an instruction that changes how you work and "
            "always applies. Kind 'fact' is knowledge that applies where it "
            "fits. Both are stored without asking, so save a rule only when "
            "the user actually asked for one — it will be in front of you in "
            "every conversation from now on.\n"
            "One entry per call, one sentence, at most "
            f"{MAX_LAENGE} characters. It cannot delete and it cannot take "
            "whole file contents — to correct something, pass the exact text "
            "of the existing entry as 'replaces'.\n"
            "The answer says what happened: saved, replaced, or already known."
        ),
        schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "The entry, one sentence, phrased so it still makes "
                        'sense on its own in a year. E.g. "Prefers being told '
                        'the measured number over an estimate."'
                    ),
                },
                "kind": {
                    "type": "string",
                    "enum": [REGEL, FAKTUM],
                    "description": "'rule' changes behaviour, 'fact' is knowledge.",
                },
                "replaces": {
                    "type": "string",
                    "description": (
                        "The exact text of an existing entry this one "
                        "supersedes. Leave out when adding something new."
                    ),
                },
            },
            "required": ["text", "kind"],
        },
        server=SERVER_NAME,
    )


def _text_von(argumente: dict[str, Any]) -> str:
    return str(argumente.get("text") or "").strip()


def _art_von(argumente: dict[str, Any]) -> str:
    art = str(argumente.get("kind") or "").strip().lower()
    return art if art in (REGEL, FAKTUM) else FAKTUM


def braucht_bestaetigung(argumente: dict[str, Any]) -> bool:
    """Nothing here asks.

    One prompt in the whole program, and it is the shell reaching outside the
    shared folders. Everything else runs through. The reason is what a prompt
    costs when it comes often: someone who has clicked Accept ten times in a
    session stops reading it, and then the one prompt that matters is clicked
    away with the rest.

    What makes that affordable here is that a memory entry is visible and
    reversible — it stands in the settings window and can be deleted in a
    click. A prompt buys nothing that looking does not.
    """
    return False


def _zeilen_teilen(inhalt: str) -> tuple[list[str], list[str]]:
    """Splits the file into the two lists of entries.

    Anything outside the two headings is dropped on purpose: the file is
    hand-editable, and whatever a person writes above the first heading is
    theirs to keep — so it is preserved separately by the caller, not here.
    """
    regeln: list[str] = []
    fakten: list[str] = []
    ziel: list[str] | None = None
    for zeile in inhalt.splitlines():
        kopf = zeile.strip()
        if kopf == UEBERSCHRIFT_REGELN:
            ziel = regeln
            continue
        if kopf == UEBERSCHRIFT_FAKTEN:
            ziel = fakten
            continue
        if ziel is None or not kopf:
            continue
        ziel.append(kopf.removeprefix("-").strip() if kopf.startswith("-") else kopf)
    return regeln, fakten


def _zusammensetzen(regeln: list[str], fakten: list[str]) -> str:
    teile: list[str] = []
    if regeln:
        teile.append(UEBERSCHRIFT_REGELN + "\n" + "\n".join(f"- {z}" for z in regeln))
    if fakten:
        teile.append(UEBERSCHRIFT_FAKTEN + "\n" + "\n".join(f"- {z}" for z in fakten))
    return "\n\n".join(teile)


def eintragen(inhalt: str, text: str, art: str, ersetzt: str = "") -> str:
    """The new file content — pure text in, pure text out, nothing on disk.

    Kept free of the filesystem so the rules of the game can be tested
    without one: replacing hits the entry no matter which heading it sits
    under, and an entry that is already there is not written twice.
    """
    regeln, fakten = _zeilen_teilen(inhalt)
    ersetzt = ersetzt.strip().removeprefix("-").strip()

    if ersetzt:
        for liste in (regeln, fakten):
            for stelle, vorhanden in enumerate(liste):
                if vorhanden == ersetzt:
                    liste.pop(stelle)
                    break

    ziel = regeln if art == REGEL else fakten
    if text not in ziel:
        ziel.append(text)
    return _zusammensetzen(regeln, fakten)


async def ausfuehren(argumente: dict[str, Any], pfad: Path) -> str:
    """Writes one entry. Returns what the model is told about it."""
    text = _text_von(argumente)
    if not text:
        raise MemoryVerboten("No text given — nothing was saved.")
    if len(text) > MAX_LAENGE:
        raise MemoryVerboten(
            f"Too long ({len(text)} characters, at most {MAX_LAENGE}). "
            "A memory entry is one sentence, not a document."
        )

    art = _art_von(argumente)
    ersetzt = str(argumente.get("replaces") or "").strip()

    async with _schleuse:
        alt = pfad.read_text(encoding="utf-8") if pfad.exists() else ""
        neu = eintragen(alt, text, art, ersetzt)
        if neu.strip() == alt.strip():
            return "Already known — nothing changed."
        pfad.parent.mkdir(parents=True, exist_ok=True)
        # Side file, then rename: an interrupted write would otherwise leave
        # the program having forgotten half of what it knew.
        neben = pfad.with_suffix(pfad.suffix + ".neu")
        neben.write_text(neu + "\n", encoding="utf-8")
        neben.replace(pfad)

    log.info("Gedächtnis ergänzt (%s): %s", art, text)
    return "Replaced." if ersetzt else "Saved."
