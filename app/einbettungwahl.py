"""Whether a large document is cut up instead of sent whole.

Shipped on, like everything in this house that can act by itself. The
reason is that the alternative is not "nothing happens" — it is a document
that quietly overruns the context and an answer that is confidently wrong
about it. Between a selection that might miss a paragraph and a truncation
that silently drops half the conversation, the selection is the honest one.

Off means exactly what it did before: the whole extracted text travels with
every request, and whoever switches it off is choosing the old behaviour
knowingly. That is worth a switch, because on a model with a very large
context the old way IS better — nothing beats having the whole document.

In the settings cascade (default → global → model → chat), so it can be off
on the model with room and on everywhere else.
"""

from __future__ import annotations

from typing import Any

SCHLUESSEL = "einbettung"

VORGABE: dict[str, bool] = {"an": True}


def schalter_pruefen(wert: Any) -> dict[str, bool]:
    """``einbettung``: the switch, checked before it is stored."""
    if not isinstance(wert, dict) or "an" not in wert:
        return {}
    return {"an": bool(wert["an"])}


def zerlegt(repositories, *, modell: str | None = None, chat: str | None = None) -> bool:
    """Whether a document past the threshold is cut up in this scope."""
    stand = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, vorgabe=dict(VORGABE), modell=modell, chat=chat
    )
    if not isinstance(stand, dict):
        return VORGABE["an"]
    return bool(stand.get("an", VORGABE["an"]))
