"""The name setting: checked on the way in, one line on the way out."""

from app import anrede


def test_pruefer_behaelt_nur_bekanntes():
    sauber = anrede.schalter_pruefen({"name": "  Chris  ", "an": 1, "x": "y"})
    assert sauber == {"name": "Chris", "an": True}


def test_pruefer_verwirft_unbrauchbares():
    assert anrede.schalter_pruefen("Chris") == {}
    assert anrede.schalter_pruefen(None) == {}


def test_pruefer_begrenzt_die_laenge():
    lang = anrede.schalter_pruefen({"name": "x" * 200})
    assert len(lang["name"]) == anrede.NAME_HOECHSTLAENGE


def test_anhaengen_mit_namen():
    ergebnis = anrede.anhaengen("Grund.", {"name": "Chris", "an": True})
    assert ergebnis.startswith("Grund.")
    assert '"Chris"' in ergebnis


def test_anhaengen_aus_oder_leer_aendert_nichts():
    assert anrede.anhaengen("Grund.", {"name": "Chris", "an": False}) == "Grund."
    assert anrede.anhaengen("Grund.", {"name": "", "an": True}) == "Grund."


def test_anhaengen_ohne_grundprompt():
    ergebnis = anrede.anhaengen("", {"name": "Chris", "an": True})
    assert ergebnis.startswith("The person at this terminal")
