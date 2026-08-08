"""What the user picked among the models — checked before it is stored.

The settings table holds JSON and cannot check anything by itself, so every
key that may be written needs someone who vouches for its shape. Two keys
belong to the models, and they mean different things:

``modelle_aus``
    Which models are switched OFF in the quick picker. Deliberately the
    negative: a model that newly appears is then visible instead of staying
    hidden until somebody remembers to allow it.

``katalog_wahl``
    Which models of a provider's CATALOGUE were picked at all, per provider.
    Here the positive is stored, and a provider starts empty: one of them
    reports 124 models, most for speech, images or embeddings, and nobody
    asked for a list they did not order.

Both are checked, not trusted. Names are ids that go into a URL and into a
request to a model server; anything that is not a non-empty string has no
business in there.
"""

from __future__ import annotations

from typing import Any

# A single id long enough to be a path and a model name together. Far above
# anything real — this is a stop against a runaway value, not a rule about
# names.
MAX_LAENGE = 400


def _namen(werte: Any) -> list[str]:
    """Cleans a list of ids: strings only, trimmed, no duplicates, in order."""
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


def aus_pruefen(werte: Any) -> list[str]:
    """``modelle_aus``: a flat list of model ids."""
    return _namen(werte)


def wahl_pruefen(werte: Any) -> dict[str, list[str]]:
    """``katalog_wahl``: per provider the models picked from its catalogue.

    Providers without a single pick are dropped rather than stored as an empty
    list — an empty entry says nothing that its absence does not.
    """
    if not isinstance(werte, dict):
        return {}
    sauber: dict[str, list[str]] = {}
    for anbieter, namen in werte.items():
        if not isinstance(anbieter, str) or not anbieter.strip():
            continue
        gewaehlt = _namen(namen)
        if gewaehlt:
            sauber[anbieter.strip()] = gewaehlt
    return sauber
