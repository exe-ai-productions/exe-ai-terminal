"""The read tool — `read_file`.

Reading a file through the shell works, but small models trip over the
quoting long before they trip over the task. A tool with a plain `path`
argument takes that whole class of mistake away, and it makes reading
switchable on its own: switch `write_file`, `edit_file` and `run_command` off
and what is left is an agent that can look but not touch.

Where it may read is decided in ``grenzen.py``, the same boundary the shell
works under.
"""

from __future__ import annotations

from typing import Any

from app.tools import grenzen
from app.tools.mcp_client import MCPWerkzeug

SERVER_NAME = "shell"
WERKZEUG_NAME = "read_file"

# As much as the shell hands back, for the same reason: a long file would
# otherwise fill the whole context.
MAX_ZEICHEN = 20_000

# How much of the start decides whether this is text at all. A null byte in
# the first block means no line-based reading will make sense of it.
PROBE_BYTES = 4096


def werkzeug_beschreibung() -> MCPWerkzeug:
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Reads a text file and returns its lines with a header saying which "
            "part of the file they are.\n"
            "Works inside the folders shared with this chat — relative paths "
            "resolve against the first one. Without a shared folder nothing is "
            "read.\n"
            "Read a long file in parts with offset and limit instead of asking "
            f"for everything: the answer is cut off at {MAX_ZEICHEN:,} characters.\n"
            "Binary files are refused — use run_command with a suitable tool for "
            "those."
        ),
        schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file to read, e.g. \"notes/todo.md\".",
                },
                "offset": {
                    "type": "integer",
                    "description": "First line to return, counting from 1. Default: the start of the file.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many lines to return. Default: as many as fit.",
                },
            },
            "required": ["path"],
        },
        server=SERVER_NAME,
    )


def aussenpfad(argumente: dict[str, Any], ordner: list[str]) -> str | None:
    return grenzen.aussenpfad(argumente, ordner)


def braucht_bestaetigung(argumente: dict[str, Any], ordner: list[str]) -> bool:
    return aussenpfad(argumente, ordner) is not None


def _zahl(wert: Any) -> int | None:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


async def ausfuehren(argumente: dict[str, Any], ordner: list[str]) -> str:
    roh = str(argumente.get("path") or "").strip()
    if not roh:
        raise grenzen.GrenzeVerletzt("No path given.")
    ziel = grenzen.ziel(roh, ordner)

    if not ziel.exists():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' does not exist.")
    if ziel.is_dir():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' is a folder — use list_dir for that.")

    try:
        with ziel.open("rb") as datei:
            probe = datei.read(PROBE_BYTES)
    except OSError as fehler:
        raise grenzen.GrenzeVerletzt(f"'{ziel}' could not be read ({fehler}).") from fehler
    if b"\0" in probe:
        raise grenzen.GrenzeVerletzt(
            f"'{ziel}' is a binary file, use run_command with a suitable tool instead."
        )

    try:
        text = ziel.read_text(encoding="utf-8", errors="replace")
    except OSError as fehler:
        raise grenzen.GrenzeVerletzt(f"'{ziel}' could not be read ({fehler}).") from fehler

    zeilen = text.splitlines()
    gesamt = len(zeilen)
    ab = max(1, _zahl(argumente.get("offset")) or 1)
    anzahl = _zahl(argumente.get("limit"))
    if anzahl is not None and anzahl < 1:
        anzahl = None
    ausschnitt = zeilen[ab - 1 :] if anzahl is None else zeilen[ab - 1 : ab - 1 + anzahl]

    if not ausschnitt:
        return f"lines {ab}–{ab} of {gesamt}\n(nothing there — the file ends earlier)"

    koerper = "\n".join(ausschnitt)
    bis = ab + len(ausschnitt) - 1
    if len(koerper) > MAX_ZEICHEN:
        # Cut on a line, not mid-word: the next call continues where this one
        # stopped, and that only works if the header tells the truth.
        gekuerzt: list[str] = []
        laenge = 0
        for zeile in ausschnitt:
            if laenge + len(zeile) + 1 > MAX_ZEICHEN and gekuerzt:
                break
            gekuerzt.append(zeile)
            laenge += len(zeile) + 1
        bis = ab + len(gekuerzt) - 1
        koerper = "\n".join(gekuerzt) + (
            f"\n… [cut off at {MAX_ZEICHEN:,} characters — continue with offset {bis + 1}]"
        )

    return f"lines {ab}–{bis} of {gesamt}\n{koerper}"
