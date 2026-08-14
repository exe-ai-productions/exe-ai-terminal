"""The engine levers, remembered between runs.

The bug: they lived only in the form. Reloading the window put every lever
back to its default while the server kept running with what it was given —
the drawer said `f16` about a server holding `q4_0`, and the next start went
out without the settings that were the only reason the model fitted.

Two halves are tested here. That the route lets the key through at all, and
that what comes back out is a set of levers the engine would actually accept.
"""

from __future__ import annotations

import pytest

from app import feineinstellungenwahl as wahl
from app.api.v1.einstellungen import PRUEFER
from app.feineinstellungen import FA_VORGABE, KV_TYPEN, KV_VORGABE, MAX_FAEDEN


# --- The route lets it through --------------------------------------------


def test_die_feineinstellungen_stehen_im_pruefer():
    """Without this entry the route answers 400 and the panel loses them."""
    assert wahl.SCHLUESSEL in PRUEFER
    assert PRUEFER[wahl.SCHLUESSEL] is wahl.wahl_pruefen


def test_was_die_schublade_schickt_kommt_auch_an():
    geschickt = {
        "kv_cache": "q4_0",
        "flash_attention": "on",
        "faeden": 8,
        "moe_auf_cpu": True,
        "moe_schichten": 12,
        "festnageln": True,
    }
    assert wahl.wahl_pruefen(geschickt) == geschickt


# --- What comes back out --------------------------------------------------


def test_ein_cache_typ_den_die_maschine_nicht_kennt_faellt_auf_die_vorgabe():
    """It must never reach the command line — the engine refuses to start."""
    geprueft = wahl.wahl_pruefen({"kv_cache": "erfunden"})
    assert geprueft["kv_cache"] == KV_VORGABE
    assert geprueft["kv_cache"] in KV_TYPEN


def test_eine_unsinnige_fadenzahl_wird_in_den_bereich_geholt():
    assert wahl.wahl_pruefen({"faeden": 99999})["faeden"] == MAX_FAEDEN
    assert wahl.wahl_pruefen({"faeden": -4})["faeden"] == 1
    # Zero means "let the engine decide" and travels as nothing.
    assert wahl.wahl_pruefen({"faeden": 0})["faeden"] is None


def test_worte_statt_zahlen_kippen_nichts_um():
    assert wahl.wahl_pruefen({"faeden": "acht"})["faeden"] is None
    assert wahl.wahl_pruefen({"moe_schichten": "viele"})["moe_schichten"] is None


@pytest.mark.parametrize("wert", [None, "nein", 5, [], ["kv_cache"]])
def test_was_kein_satz_von_werten_ist_kommt_leer_zurueck(wert):
    assert wahl.wahl_pruefen(wert) == {}


def test_fremde_schluessel_kommen_nicht_durch():
    geprueft = wahl.wahl_pruefen({"kv_cache": "q8_0", "eingeschmuggelt": "x"})
    assert "eingeschmuggelt" not in geprueft


def test_die_vorgabe_ist_das_was_die_maschine_ohnehin_tut():
    """A stored default must not turn into a flag on the command line."""
    assert wahl.VORGABE["kv_cache"] == KV_VORGABE
    assert wahl.VORGABE["flash_attention"] == FA_VORGABE
    assert wahl.VORGABE["faeden"] is None


def test_zweimal_pruefen_aendert_nichts_mehr():
    einmal = wahl.wahl_pruefen({"kv_cache": "q4_0", "faeden": 6})
    assert wahl.wahl_pruefen(einmal) == einmal


# --- The running server answers first -------------------------------------


def test_der_lauf_traegt_die_hebel_mit_sich(tmp_path):
    """Otherwise nothing can say what the server is actually holding."""
    import stat

    from app.feineinstellungen import Feineinstellungen
    from app.modellrunner import Modellrunner

    (tmp_path / "klein.gguf").write_bytes(b"x" * 2000)
    programm = tmp_path / "llama-server"
    programm.write_text("#!/bin/sh\nsleep 30\n")
    programm.chmod(programm.stat().st_mode | stat.S_IEXEC)

    runner = Modellrunner(tmp_path, str(programm))
    fein = Feineinstellungen.aus_daten({"kv_cache": "q4_0", "moe_auf_cpu": True})
    lauf = runner.starten("klein.gguf", port=18121, fein=fein)
    try:
        assert lauf.fein is not None
        assert lauf.fein.kv_cache == "q4_0"
        assert lauf.fein.moe_auf_cpu is True
        assert runner.lauf().fein.kv_cache == "q4_0"
    finally:
        runner.stoppen()
