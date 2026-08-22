"""Whether the guardian may speak up after a failed step.

It is shipped switched on, and that is the easy call to make here: the
guardian does not act. It writes a suggestion into a panel and waits for a
click. Something that only ever offers cannot do damage by being on, and a
feature nobody finds is worth nothing.

What it does cost is one short request to the model after a step that
failed — a few seconds on a local machine. That is the reason the switch
exists at all, and the reason it sits in the settings cascade
(default → global → model → chat): on the model one works with, off on the
small one where the suggestion would be worse than the failure.

Stored as an object rather than a bare boolean, like the other switches in
the house: the settings route reads a falsy value as "nothing set" and lets
the scope above take over, so a plain ``False`` could never switch anything
OFF.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "waechter"

VORGABE: dict[str, Any] = {"an": True}

# The model file name is stored beside the switch. Bounded like every other
# stored string: this is a file name in the model folder, and the settings
# column holds JSON and cannot check anything by itself.
MODELL_HOECHSTLAENGE = 200


def schalter_pruefen(wert: Any) -> dict[str, Any]:
    """``waechter``: the switch and the chosen model, before they are stored.

    Two keys survive, and each only when it was sent. The model used to be
    thrown away here — the window has been sending it along with the switch
    ever since the model can be picked, so the choice was written, silently
    dropped, and gone again after a restart with nothing anywhere saying so.

    An empty name IS a choice: "no model of its own" is one of the entries
    the picker offers, and dropping it would let the server's default walk
    back in on the next load — the setting has to be able to say "nothing"
    as clearly as it says a file name.
    """
    if not isinstance(wert, dict):
        return {}
    sauber: dict[str, Any] = {}
    if "an" in wert:
        sauber["an"] = bool(wert["an"])
    if "modell" in wert:
        sauber["modell"] = str(wert["modell"] or "").strip()[:MODELL_HOECHSTLAENGE]
    return sauber


def wacht(repositories, *, modell: str | None = None, chat: str | None = None) -> bool:
    """Whether a failed step earns a suggestion in this scope."""
    stand = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, vorgabe=dict(VORGABE), modell=modell, chat=chat
    )
    if not isinstance(stand, dict):
        return VORGABE["an"]
    return bool(stand.get("an", VORGABE["an"]))
