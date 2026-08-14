"""Whether the program makes a sound, and how loud.

Its own module for the same reason the skill switch has one: the settings
route only writes what somebody vouches for, and a JSON column cannot vouch
for anything by itself. Without an entry here the window would appear to
save and the value would be gone on the next start — which is exactly what
happened.

Stored as an object, not as two bare values: the route reads a falsy value
as "nothing set" and lets the scope above take over, so a plain ``False``
could never switch the sounds OFF, and a volume of 0 would silently jump
back to the default.

It sits in the cascade (default → global → model → chat), which makes it a
per-chat setting for free — a chat that runs long jobs may be allowed to
knock while a quiet one stays silent.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "klaenge"

# Shipped switched on, at a level that carries across a room without making
# anybody jump.
VORGABE: dict[str, Any] = {"an": True, "pegel": 70}


def wahl_pruefen(wert: Any) -> dict[str, Any] | None:
    """Keeps what is usable, drops the rest. ``None`` deletes the entry."""
    if not isinstance(wert, dict):
        return None
    sauber: dict[str, Any] = {}
    if isinstance(wert.get("an"), bool):
        sauber["an"] = wert["an"]
    pegel = wert.get("pegel")
    if isinstance(pegel, (int, float)) and not isinstance(pegel, bool):
        sauber["pegel"] = max(0, min(100, int(round(pegel))))
    return sauber or None


def aufgeloest(wert: Any) -> dict[str, Any]:
    """The stored value with the defaults behind it."""
    return {**VORGABE, **(wahl_pruefen(wert) or {})}
