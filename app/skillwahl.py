"""Whether the model may reach for a skill on its own.

Two ways lead into a skill, and only one of them costs anything:

* typed — the user writes ``/name``. The program puts the instruction in
  front of the request. Nothing stands in the prompt, no extra round trip,
  and it works with a model too small to choose for itself. There is no
  reason to ever switch that off, so there is no switch for it.
* automatic — every skill marked ``auto`` spends one line of the system
  prompt on EVERY request, so the model knows it exists. That is the half
  this switch governs.

It lives in the settings cascade (default → global → model → chat), which
makes it a per-model setting for free: off on the small local model that
would only be slowed down and would pick badly, on for a model that can use
it well.

That is a different axis from the memory's ``lokal``/``cloud`` pair, and
deliberately so. The memory splits along confidentiality — sending a profile
to a foreign server is a different act from keeping it here. Skills split
along what a model can do and how long it takes, and that runs through the
individual model, not through where it is hosted.

Stored as an object rather than a bare boolean: the settings route reads a
falsy value as "nothing set" and lets the scope above take over, so a plain
``False`` could never switch anything OFF.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "skills_auto"

# On by default. A handful of shipped skills is about sixty tokens — on the
# local model roughly two seconds, and the feature shows itself. It is at
# twenty-odd skills that this starts to hurt, and by then whoever collected
# them knows the switch is there.
VORGABE: dict[str, bool] = {"an": True}


def schalter_pruefen(wert: Any) -> dict[str, bool]:
    """``skills_auto``: the switch, checked before it is stored."""
    if not isinstance(wert, dict) or "an" not in wert:
        return {}
    return {"an": bool(wert["an"])}


def selbst_waehlen(repositories, *, modell: str | None = None, chat: str | None = None) -> bool:
    """Whether the catalogue travels with a request in this scope."""
    stand = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, vorgabe=dict(VORGABE), modell=modell, chat=chat
    )
    if not isinstance(stand, dict):
        return VORGABE["an"]
    return bool(stand.get("an", VORGABE["an"]))
