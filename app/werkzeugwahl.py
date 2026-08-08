"""What the user switched off among the tools — checked before it is stored.

Two things decide whether a tool reaches the model, and they are deliberately
kept apart because they answer different questions:

``allowed_tools`` in ``mcp_servers.json``
    WHICH of a server's tools exist for us at all. One server reports
    nineteen, most of which nobody ordered. This is the pick, it belongs to
    the server entry, and the registry holds that line while it is starting —
    long before anyone has opened a window.

``werkzeuge_aus`` in the settings cascade
    Which of the picked tools are switched OFF right now. Stored as the
    negative, for the same reason as with the models: a tool a server newly
    offers is then simply there, instead of staying invisible until somebody
    remembers to allow it.

Keeping them apart is what lets a tool be silenced for an afternoon without
losing the pick behind it — the same shape the model window already has, where
the checkbox picks and the switch mutes.

The list is checked, not trusted. A tool name is the identifier the model
calls with; anything that is not a non-empty string has no business in there.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "werkzeuge_aus"

# A tool name is an identifier, not prose. Far above anything real — this is a
# stop against a runaway value, not a rule about names.
MAX_LAENGE = 200


def aus_pruefen(werte: Any) -> list[str]:
    """``werkzeuge_aus``: a flat list of tool names, cleaned.

    Strings only, trimmed, no duplicates, order kept — the same treatment the
    model ids get, because it is the same kind of value.
    """
    if not isinstance(werte, list):
        return []
    sauber: list[str] = []
    for wert in werte:
        if not isinstance(wert, str):
            continue
        name = wert.strip()
        if name and len(name) <= MAX_LAENGE and name not in sauber:
            sauber.append(name)
    return sauber


def abgeschaltete(repositories, *, modell: str | None = None,
                  chat: str | None = None) -> set[str]:
    """The tools switched off where we are — global, model, or chat.

    A list cannot be merged key by key, so it travels whole from the most
    specific scope that set one. A chat that switches something off therefore
    decides for itself and does not silently inherit half of the global list.
    """
    wert = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, modell=modell, chat=chat
    )
    return set(aus_pruefen(wert))


def anwenden(registry, repositories, *, modell: str | None = None,
             chat: str | None = None) -> None:
    """Hands the registry the off-list that applies for this run.

    Read fresh per run rather than pushed on save: the registry restarts
    whenever a server entry changes, and anything pushed into it once would be
    gone afterwards without anybody noticing. Reading costs one query and
    cannot fall out of step.

    The registry enforces it — both where tools are offered and where they are
    executed. A switch that only greys out a row in a window is a lie: the
    model never sees that window.
    """
    if registry is None:
        return
    registry.abgeschaltet = abgeschaltete(repositories, modell=modell, chat=chat)
