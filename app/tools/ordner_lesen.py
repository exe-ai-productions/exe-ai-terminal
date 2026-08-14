"""The listing tool — `list_dir`.

What is in this folder, with a mark for folders and a size for files. `ls`
through the shell does the same, but its output changes with the platform and
the user's aliases; this one reads the same everywhere.

Hidden entries are listed. File work needs them — a dotfile is the thing
people ask about most often.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools import grenzen
from app.tools.mcp_client import MCPWerkzeug

SERVER_NAME = "shell"
WERKZEUG_NAME = "list_dir"

# How deep the listing may go. Three levels are a folder one can still read;
# below that it turns into a wall of text nobody uses.
MAX_TIEFE = 3

# Where a listing stops. A node_modules would otherwise fill the context.
MAX_EINTRAEGE = 500


def werkzeug_beschreibung() -> MCPWerkzeug:
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Lists what is in a folder: sub-folders marked with a slash, files "
            "with their size. Hidden entries are included.\n"
            "Without a path it lists the first folder shared with this chat. "
            "Relative paths resolve against that folder, and without a shared "
            "folder nothing is listed.\n"
            f"depth reaches into sub-folders, at most {MAX_TIEFE} levels. Long "
            f"listings stop after {MAX_EINTRAEGE} entries — go into a sub-folder "
            "rather than asking for everything."
        ),
        schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The folder to list. Default: the first folder shared with this chat.",
                },
                "depth": {
                    "type": "integer",
                    "description": f"How many levels to go down, 1 to {MAX_TIEFE}. Default: 1.",
                },
            },
        },
        server=SERVER_NAME,
    )


def aussenpfad(argumente: dict[str, Any], ordner: list[str]) -> str | None:
    return grenzen.aussenpfad(argumente, ordner)


def braucht_bestaetigung(argumente: dict[str, Any], ordner: list[str]) -> bool:
    return aussenpfad(argumente, ordner) is not None


def _groesse(datei: Path) -> str:
    try:
        bytes_ = datei.stat().st_size
    except OSError:
        return "?"
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def _sammeln(wurzel: Path, tiefe: int) -> tuple[list[str], bool]:
    """The listing as lines, and whether it had to stop early."""
    zeilen: list[str] = []

    def hinein(ordner: Path, ebene: int, einzug: str) -> bool:
        try:
            eintraege = sorted(ordner.iterdir(), key=lambda p: p.name.lower())
        except OSError as fehler:
            zeilen.append(f"{einzug}[not readable: {fehler.strerror or fehler}]")
            return True
        for eintrag in eintraege:
            if len(zeilen) >= MAX_EINTRAEGE:
                return False
            if eintrag.is_dir() and not eintrag.is_symlink():
                zeilen.append(f"{einzug}{eintrag.name}/")
                if ebene < tiefe and not hinein(eintrag, ebene + 1, einzug + "  "):
                    return False
            else:
                zeilen.append(f"{einzug}{eintrag.name}  {_groesse(eintrag)}")
        return True

    vollstaendig = hinein(wurzel, 1, "")
    return zeilen, not vollstaendig


async def ausfuehren(argumente: dict[str, Any], ordner: list[str]) -> str:
    roh = str(argumente.get("path") or "").strip()
    if roh:
        ziel = grenzen.ziel(roh, ordner)
    else:
        if not ordner:
            raise grenzen.GrenzeVerletzt(grenzen.OHNE_ORDNER)
        ziel = grenzen.wurzeln(ordner)[0]

    if not ziel.exists():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' does not exist.")
    if not ziel.is_dir():
        raise grenzen.GrenzeVerletzt(f"'{ziel}' is a file — use read_file for that.")

    try:
        tiefe = int(argumente.get("depth") or 1)
    except (TypeError, ValueError):
        tiefe = 1
    tiefe = max(1, min(MAX_TIEFE, tiefe))

    zeilen, abgeschnitten = _sammeln(ziel, tiefe)
    if not zeilen:
        return f"{ziel}\n(empty)"
    kopf = f"{ziel}"
    if abgeschnitten:
        zeilen.append(f"… [stopped at {MAX_EINTRAEGE} entries]")
    return "\n".join([kopf, *zeilen])
