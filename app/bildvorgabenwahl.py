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
    klasse_aus_name,
    schritte_pruefen,
    vorgabe_fuer_klasse,
)

SCHLUESSEL = "bild_vorgaben"

# The class-free base — sampler and scheduler stay empty, meaning "whatever
# the model brings". Resolution and steps come from the model's class (see
# `vorgaben`); the numbers here are only the last resort when no model is
# named, and they match the SD-1.5 class rather than the old 512/12 that
# starved every SDXL picture.
VORGABE: dict[str, Any] = {
    "breite": 512,
    "hoehe": 512,
    "schritte": 22,
    "sampler": "",
    "scheduler": "",
}


def _basis(modell: str | None) -> dict[str, Any]:
    """The starting values before any stored override — class-aware when a
    model is named, so an SDXL model opens at 1024/28 and an SD-1.5 at
    512/22 instead of one number for both."""
    if not modell:
        return dict(VORGABE)
    return {**VORGABE, **vorgabe_fuer_klasse(klasse_aus_name(modell))}


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


# Resolution and steps belong to the model's class, not to a global switch:
# a single number in the global scope cannot be right for both classes — 512
# starves an SDXL picture, 1024 doubles an SD-1.5 one. So these three come
# from the class base and may only be overridden by an INTENTIONAL per-model
# or per-chat choice, never by the one global default left over from the days
# before classes existed. Everything else (sampler, scheduler) cascades
# normally, because those ARE class-independent.
KLASSEN_EIGEN = ("breite", "hoehe", "schritte")


def vorgaben(repositories, *, modell: str | None = None, chat: str | None = None) -> dict[str, Any]:
    """The starting values that apply in this scope.

    The class default is the base. A stored sampler or scheduler wins at any
    scope; resolution and steps, though, are the class's own and only a
    per-model or per-chat override speaks for a specific model — the leftover
    global default from before classes existed is deliberately ignored, so an
    SDXL model opens at 1024 even on an installation that once stored 512.
    """
    e = repositories.einstellungen
    basis = _basis(modell)
    voll = e.zusammengefuehrt(SCHLUESSEL, vorgabe=basis, modell=modell, chat=chat)
    if not isinstance(voll, dict):
        return basis
    ergebnis = {**basis, **voll}
    # Take resolution and steps only from the scopes ABOVE global — the class
    # base holds otherwise.
    spezifisch: dict[str, Any] = {}
    for bereich in e.kette(SCHLUESSEL, modell=modell, chat=chat)[1:]:
        stand = e.holen(bereich, SCHLUESSEL)
        if isinstance(stand, dict):
            spezifisch.update(stand)
    for schluessel in KLASSEN_EIGEN:
        ergebnis[schluessel] = spezifisch.get(schluessel, basis[schluessel])
    return ergebnis
