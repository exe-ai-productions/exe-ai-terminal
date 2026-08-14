"""The starting values of the picture window.

The panel writes them and the window reads them, and between the two sits the
settings route, which only lets through what a checker vouches for. This key
had no checker: the panel showed the new numbers, the write came back 400,
and reopening the window brought back the old ones — silently, because the
panel swallowed the error.

So the first test here is not about clamping at all. It is about the key
being allowed through the route in the first place.
"""

from __future__ import annotations

import pytest

from app import bildvorgabenwahl
from app.api.v1.einstellungen import PRUEFER
from app.bildwahlen import MAX_KANTE, MAX_SCHRITTE, MIN_KANTE, RASTER


# --- The route lets it through --------------------------------------------


def test_die_bildvorgaben_stehen_im_pruefer():
    """The regression: without this entry the route answers 400."""
    assert bildvorgabenwahl.SCHLUESSEL in PRUEFER
    assert PRUEFER[bildvorgabenwahl.SCHLUESSEL] is bildvorgabenwahl.wahl_pruefen


def test_was_die_tafel_schickt_kommt_auch_an():
    """Exactly the shape Bildserver.svelte sends."""
    geschickt = {
        "breite": 768,
        "hoehe": 768,
        "schritte": 30,
        "sampler": "euler",
        "scheduler": "karras",
    }
    assert bildvorgabenwahl.wahl_pruefen(geschickt) == geschickt


# --- What comes back out --------------------------------------------------


def test_eine_kante_kommt_aufs_raster():
    geprueft = bildvorgabenwahl.wahl_pruefen({"breite": 700})
    assert geprueft["breite"] % RASTER == 0
    assert geprueft["breite"] <= 700


@pytest.mark.parametrize("wert,erwartet", [(99999, MAX_KANTE), (-5, MIN_KANTE), (0, MIN_KANTE)])
def test_eine_kante_ausserhalb_wird_geklemmt(wert, erwartet):
    assert bildvorgabenwahl.wahl_pruefen({"breite": wert})["breite"] == erwartet


def test_schritte_ausserhalb_werden_geklemmt():
    assert bildvorgabenwahl.wahl_pruefen({"schritte": 9999})["schritte"] == MAX_SCHRITTE
    assert bildvorgabenwahl.wahl_pruefen({"schritte": 0})["schritte"] == 1


def test_ein_sampler_den_der_bau_nicht_kennt_faellt_weg():
    assert "sampler" not in bildvorgabenwahl.wahl_pruefen({"sampler": "erfunden"})


def test_leer_heisst_was_das_modell_mitbringt():
    """Not the same as the house default, and a real answer."""
    assert bildvorgabenwahl.wahl_pruefen({"sampler": ""})["sampler"] == ""


def test_fremde_schluessel_kommen_nicht_durch():
    geprueft = bildvorgabenwahl.wahl_pruefen({"breite": 512, "eingeschmuggelt": "x"})
    assert geprueft == {"breite": 512}


@pytest.mark.parametrize("wert", [None, "nein", 5, [], ["breite"]])
def test_was_kein_satz_von_werten_ist_kommt_leer_zurueck(wert):
    assert bildvorgabenwahl.wahl_pruefen(wert) == {}


def test_worte_statt_zahlen_fallen_weg_statt_umzufallen():
    assert bildvorgabenwahl.wahl_pruefen({"breite": "gross", "hoehe": 512}) == {"hoehe": 512}


# --- The defaults themselves ----------------------------------------------


def test_die_vorgabe_haelt_ihre_eigenen_grenzen_ein():
    """A default the route would refuse fails at drawing time, not here."""
    assert bildvorgabenwahl.wahl_pruefen(dict(bildvorgabenwahl.VORGABE)) == {
        k: v for k, v in bildvorgabenwahl.VORGABE.items()
    }
