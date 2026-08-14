"""The edit tool — `edit_file`.

Changing one passage without rewriting the whole file. The old text has to
match exactly once: no match means the model is looking at something it has
not read, several matches mean it does not know which one it is changing.
Both are refused, and the answer says which of the two it was — that is the
difference between a model that fixes its call and one that guesses again.
"""

from __future__ import annotations

from typing import Any

from app.tools import grenzen
from app.tools.mcp_client import MCPWerkzeug

SERVER_NAME = "shell"
WERKZEUG_NAME = "edit_file"


def werkzeug_beschreibung() -> MCPWerkzeug:
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Replaces one passage in a text file. old_text has to appear exactly "
            "once, so give enough surrounding lines to make it unique — the call "
            "is refused if it appears twice.\n"
            "Read the file first: the text has to match the file character for "
            "character, indentation included.\n"
            "Works inside the folders shared with this chat — relative paths "
            "resolve against the first one. Without a shared folder nothing is "
            "changed."
        ),
        schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file to change, e.g. \"notes/todo.md\".",
                },
                "old_text": {
                    "type": "string",
                    "description": "The passage as it stands in the file right now.",
                },
                "new_text": {
                    "type": "string",
                    "description": "What it should say instead. An empty text deletes the passage.",
                },
            },
            "required": ["path", "old_text", "new_text"],
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
    alt = argumente.get("old_text")
    if not alt:
        raise grenzen.GrenzeVerletzt("No old_text given — there is nothing to look for.")
    alt = str(alt)
    neu = str(argumente.get("new_text") or "")

    ziel = grenzen.ziel(roh, ordner)
    if not ziel.exists():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' does not exist.")
    if ziel.is_dir():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' is a folder, not a file.")

    try:
        text = ziel.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as fehler:
        raise grenzen.GrenzeVerletzt(f"'{ziel}' could not be read ({fehler}).") from fehler

    treffer = text.count(alt)
    if treffer == 0:
        raise grenzen.GrenzeVerletzt(
            f"old_text was not found in '{ziel}'. Read the file and copy the "
            "passage as it stands there, whitespace included."
        )
    if treffer > 1:
        raise grenzen.GrenzeVerletzt(
            f"old_text appears {treffer} times in '{ziel}'. Give more of the "
            "surrounding lines so it points at exactly one place."
        )

    zeile = text[: text.index(alt)].count("\n") + 1
    try:
        ziel.write_text(text.replace(alt, neu, 1), encoding="utf-8")
    except OSError as fehler:
        raise grenzen.GrenzeVerletzt(f"'{ziel}' could not be written ({fehler}).") from fehler

    return f"Changed {ziel} at line {zeile}."
