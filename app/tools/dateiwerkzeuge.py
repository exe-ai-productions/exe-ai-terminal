"""The built-in file tools as one group.

Four tools that behave identically towards the registry: same source, same
boundary, same confirmation. Listing them once here keeps the registry from
growing a branch per tool, and adding a fifth stays a one-line change.

Each module carries its own tool; this file only says which ones there are.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from app.tools import datei_aendern, datei_lesen, datei_schreiben, ordner_lesen
from app.tools.mcp_client import MCPWerkzeug

# The order the model sees them in: look, write, change, list.
MODULE: tuple[ModuleType, ...] = (
    datei_lesen,
    datei_schreiben,
    datei_aendern,
    ordner_lesen,
)

NAMEN: tuple[str, ...] = tuple(m.WERKZEUG_NAME for m in MODULE)


def modul(name: str) -> ModuleType | None:
    """The module behind a tool name, or None if it is not one of ours."""
    for eintrag in MODULE:
        if eintrag.WERKZEUG_NAME == name:
            return eintrag
    return None


def beschreibungen() -> list[MCPWerkzeug]:
    return [m.werkzeug_beschreibung() for m in MODULE]


def aussenpfad(name: str, argumente: dict[str, Any], ordner: list[str]) -> str | None:
    eintrag = modul(name)
    return eintrag.aussenpfad(argumente, ordner) if eintrag else None
