"""What the picture window opens with.

The picture panel sets these and the picture window reads them. Only the
STARTING values live here — a default never narrows a control, it decides
where the control stands when the window opens.

Every value is checked against the same limits the route uses, from
``bildwahlen``: a stored default that the generator would refuse is worse
than no default at all, because it fails at drawing time and looks like the
picture is broken rather than the setting.

Unknown keys are dropped rather than kept. The settings column is JSON and
cannot check itself, so whatever passes here is what the window will later
trust.
"""

from __future__ import annotations

from typing import Any

from app.bildwahlen import (
    SAMPLER,
    SCHEDULER,
    kante_pruefen,
    schritte_pruefen,
)

SCHLUESSEL = "bild_vorgaben"

VORGABE: dict[str, Any] = {
    "breite": 512,
    "hoehe": 512,
    "schritte": 12,
    "sampler": "",
    "scheduler": "",
}


def wahl_pruefen(wert: Any) -> dict[str, Any]:
    """``bild_vorgaben``: the starting values, checked before they are stored."""
    if not isinstance(wert, dict):
        return {}

    geprueft: dict[str, Any] = {}

    for kante in ("breite", "hoehe"):
        if kante in wert:
            zahl = kante_pruefen(wert[kante])
            if zahl is not None:
                geprueft[kante] = zahl

    if "schritte" in wert:
        zahl = schritte_pruefen(wert["schritte"])
        if zahl is not None:
            geprueft["schritte"] = zahl

    # The empty string is a real answer here: it means "whatever the model
    # brings", which is not the same as "the house default". Anything else
    # has to be a name this build actually knows.
    for name, liste in (("sampler", SAMPLER), ("scheduler", SCHEDULER)):
        if name in wert:
            text = wert[name]
            if text == "" or text in liste:
                geprueft[name] = text

    return geprueft


def vorgaben(repositories, *, modell: str | None = None, chat: str | None = None) -> dict[str, Any]:
    """The starting values that apply in this scope."""
    stand = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, vorgabe=dict(VORGABE), modell=modell, chat=chat
    )
    if not isinstance(stand, dict):
        return dict(VORGABE)
    return {**VORGABE, **stand}
