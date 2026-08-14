"""The engine levers, remembered between runs.

``app/feineinstellungen.py`` says what the levers ARE and what command line
they produce. This says where the chosen ones live when nothing is running.

Both are needed, and the second one is the part that was missing: the values
only ever existed in the form. Reloading the window put every lever back to
its default while the server kept running with the ones it was given, so the
drawer said `f16` about a server holding `q4_0` — and the next start went out
without the settings that were the only reason the model fitted at all.

The running server answers first: what is actually in force beats what was
once chosen. This is the fallback for every other moment — before the first
start, after a stop, after a restart of the whole program.

Global scope only, deliberately. These are facts about the machine's memory,
not about a conversation; a KV cache that changes with the open chat would be
a setting nobody could reason about.
"""

from __future__ import annotations

from typing import Any

from app.feineinstellungen import Feineinstellungen

SCHLUESSEL = "feineinstellungen"

VORGABE: dict[str, Any] = Feineinstellungen().als_daten()


def wahl_pruefen(wert: Any) -> dict[str, Any]:
    """``feineinstellungen``: the levers, checked before they are stored.

    Checked by building the real thing and reading it back, rather than by
    checking field by field here. ``aus_daten`` already clamps every value
    into range and refuses a cache type the engine does not know — writing
    those rules a second time is how the two drift apart.
    """
    if not isinstance(wert, dict):
        return {}
    return Feineinstellungen.aus_daten(wert).als_daten()


def gewaehlt(repositories) -> Feineinstellungen:
    """The levers that apply when no server is running."""
    stand = repositories.einstellungen.zusammengefuehrt(SCHLUESSEL, vorgabe=dict(VORGABE))
    if not isinstance(stand, dict):
        return Feineinstellungen()
    return Feineinstellungen.aus_daten(stand)
