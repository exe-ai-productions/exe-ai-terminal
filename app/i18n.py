"""Multilingual support (German + English) from day one.

Not a single string is hard-coded. Translations live as JSON under
``app/locales/<sprache>.json`` and are fetched via a dotted key:

    t("fehler.modell_nicht_erreichbar", "de", name="Mana")

If a key is missing in the requested language, we fall back to the default
language; if it is missing there too, the key itself comes back — visible in
the UI, but no crash.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LOCALES_VERZEICHNIS = Path(__file__).resolve().parent / "locales"
# English is the primary language: the program is meant
# for public release, and models work more reliably with English tool
# schemas. German remains maintained as an equal and kicks in as soon as the
# browser reports it.
STANDARDSPRACHE = "en"


@lru_cache(maxsize=8)
def _katalog(sprache: str) -> dict[str, Any]:
    datei = LOCALES_VERZEICHNIS / f"{sprache}.json"
    if not datei.exists():
        return {}
    return json.loads(datei.read_text(encoding="utf-8"))


def verfuegbare_sprachen() -> list[str]:
    return sorted(pfad.stem for pfad in LOCALES_VERZEICHNIS.glob("*.json"))


def _nachschlagen(katalog: dict[str, Any], schluessel: str) -> str | None:
    knoten: Any = katalog
    for teil in schluessel.split("."):
        if not isinstance(knoten, dict) or teil not in knoten:
            return None
        knoten = knoten[teil]
    return knoten if isinstance(knoten, str) else None


def t(schluessel: str, sprache: str | None = None, **platzhalter: Any) -> str:
    """Translates a key and fills in placeholders."""
    sprache = sprache or STANDARDSPRACHE

    text = _nachschlagen(_katalog(sprache), schluessel)
    if text is None and sprache != STANDARDSPRACHE:
        text = _nachschlagen(_katalog(STANDARDSPRACHE), schluessel)
    if text is None:
        log.warning("Übersetzung fehlt: %s (%s)", schluessel, sprache)
        return schluessel

    if not platzhalter:
        return text
    try:
        return text.format(**platzhalter)
    except KeyError as fehler:
        log.warning("Platzhalter %s fehlt für Schlüssel %s", fehler, schluessel)
        return text

