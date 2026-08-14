"""The write tool — `write_file`.

Writing a file through the shell means a here-document or an `echo` with
quoting that survives the model, the shell and the file system. Small models
lose that fight often enough that the content arrives mangled. A tool that
takes the text as an argument cannot mangle it.

Overwriting is allowed. The share is the permission — the same rule the shell
works under, and a write tool that refuses to overwrite is a write tool
nobody can use twice.
"""

from __future__ import annotations

from typing import Any

from app.tools import grenzen
from app.tools.mcp_client import MCPWerkzeug

SERVER_NAME = "shell"
WERKZEUG_NAME = "write_file"


def werkzeug_beschreibung() -> MCPWerkzeug:
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Writes text to a file, creating it and any missing parent folders. "
            "An existing file is replaced as a whole, so read it first if the "
            "old content matters.\n"
            "Works inside the folders shared with this chat — relative paths "
            "resolve against the first one. Without a shared folder nothing is "
            "written.\n"
            "To change a part of a file, use edit_file instead of writing the "
            "whole thing back."
        ),
        schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file to write, e.g. \"notes/todo.md\".",
                },
                "content": {
                    "type": "string",
                    "description": "The full text the file should hold afterwards.",
                },
            },
            "required": ["path", "content"],
        },
        server=SERVER_NAME,
    )


def aussenpfad(argumente: dict[str, Any], ordner: list[str]) -> str | None:
    return grenzen.aussenpfad(argumente, ordner)


def braucht_bestaetigung(argumente: dict[str, Any], ordner: list[str]) -> bool:
    return aussenpfad(argumente, ordner) is not None


async def ausfuehren(argumente: dict[str, Any], ordner: list[str]) -> str:
    roh = str(argumente.get("path") or "").strip()
    if not roh:
        raise grenzen.GrenzeVerletzt("No path given.")
    inhalt = argumente.get("content")
    if inhalt is None:
        raise grenzen.GrenzeVerletzt("No content given.")
    inhalt = str(inhalt)

    ziel = grenzen.ziel(roh, ordner)
    if ziel.is_dir():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' is a folder, not a file.")

    gab_es_schon = ziel.exists()
    try:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt, encoding="utf-8")
    except OSError as fehler:
        raise grenzen.GrenzeVerletzt(f"'{ziel}' could not be written ({fehler}).") from fehler

    zeilen = len(inhalt.splitlines())
    was = "Overwrote" if gab_es_schon else "Created"
    return f"{was} {ziel} — {zeilen} lines, {len(inhalt):,} characters."
