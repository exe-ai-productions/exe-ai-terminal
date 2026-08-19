"""Guards that the UI stays bilingual.

The catalog was once fully in place and yet the frontend never used it —
around ninety German texts were hard-coded. To keep that from coming back,
these tests check on every run:

  * does every ``t('…')`` call point to a key that actually exists?
  * has a German text been hard-coded into a display attribute again?

Both are cheap to check and would otherwise only show up once the spot
appears on screen — a mistyped key even only at the user's end.
"""

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
QUELLEN = WURZEL / "frontend" / "src"

# The brand name is the same in every language and must not be translated.
# The long form stays listed: it is still the name of the program folder and
# of the user's data directory, even though the surface now reads the short one.
ERLAUBT = {"Exe AI", "Exe AI Terminal"}


def _dateien():
    return sorted(QUELLEN.rglob("*.svelte")) + sorted(QUELLEN.rglob("*.js"))


def _flach(objekt, praefix=""):
    for schluessel, wert in objekt.items():
        if isinstance(wert, dict):
            yield from _flach(wert, f"{praefix}{schluessel}.")
        else:
            yield praefix + schluessel


@pytest.fixture(scope="module")
def bekannte_schluessel():
    katalog = json.loads((WURZEL / "app" / "locales" / "de.json").read_text())
    return set(_flach(katalog))


@pytest.mark.skipif(not QUELLEN.is_dir(), reason="Frontend-Quellen nicht vorhanden")
def test_jeder_benutzte_schluessel_steht_im_katalog(bekannte_schluessel):
    """A typo in the key would otherwise show the key itself on screen."""
    fehlend = {}
    for datei in _dateien():
        for schluessel in re.findall(r"\bt\(\s*'([a-z_]+(?:\.[a-z_]+)+)'", datei.read_text()):
            if schluessel not in bekannte_schluessel:
                fehlend.setdefault(schluessel, []).append(datei.name)
    assert not fehlend, f"Schlüssel ohne Eintrag im Katalog: {fehlend}"


@pytest.mark.skipif(not QUELLEN.is_dir(), reason="Frontend-Quellen nicht vorhanden")
def test_keine_festen_deutschen_texte_in_anzeige_attributen():
    """title, aria-label, placeholder and alt belong to the user, not the code."""
    umlaut = re.compile(r"[äöüÄÖÜß]")
    attribut = re.compile(r'\b(title|aria-label|placeholder|alt)="([^"{][^"]*)"')

    gefunden = []
    for datei in _dateien():
        inhalt = datei.read_text()
        ohne_stil = re.sub(r"<style>.*?</style>", "", inhalt, flags=re.S)
        ohne_kommentar = re.sub(r"/\*.*?\*/|<!--.*?-->", "", ohne_stil, flags=re.S)
        for art, wert in attribut.findall(ohne_kommentar):
            if wert.strip() in ERLAUBT:
                continue
            if umlaut.search(wert) or " " in wert.strip():
                gefunden.append(f"{datei.name}: {art}={wert!r}")

    assert not gefunden, "Fester Text statt t(…): " + "; ".join(gefunden)
