"""Whether a stored picture keeps anything but its pixels.

A generator writes the prompt, seed and settings into its file, and a photo
someone uploads can carry EXIF — camera, time, place. This one switch decides
whether that is stripped on the way to disk, for uploaded and generated
pictures alike, so the answer is the same wherever a picture enters.

It ships on: a picture leaves this machine without a trail unless someone
turns the switch off on purpose. Off, everything stays as the generator or
the camera wrote it.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "bildmetadaten"

# A set of one flag, stored as a dict on purpose. The settings route discards
# a falsy value as "unset" (app/api/v1/einstellungen.py), so a bare ``False``
# could never turn the switch off against a default of on — it would be read
# back as the default. A dict is always truthy, so "off" survives. This is the
# same reason the memory switches (app/gedaechtnis.py) are shaped this way.
VORGABE: dict[str, bool] = {"an": True}


def schalter_pruefen(wert: Any) -> dict[str, bool]:
    """``bildmetadaten``: the one switch, checked before it is stored.

    Only the known key survives, as a real boolean. Anything else is dropped
    rather than stored — a settings column holds JSON and cannot check itself.
    """
    if not isinstance(wert, dict):
        return {}
    return {name: bool(wert[name]) for name in VORGABE if name in wert}


def putzen_an(repositories) -> bool:
    """Whether uploaded and generated pictures get their metadata removed."""
    stand = repositories.einstellungen.zusammengefuehrt(SCHLUESSEL, vorgabe=dict(VORGABE))
    if not isinstance(stand, dict):
        stand = dict(VORGABE)
    return bool(stand.get("an", VORGABE["an"]))
