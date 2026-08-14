"""The advanced section's levers, and the command line they turn into."""

from __future__ import annotations

import pytest

from app.feineinstellungen import (
    FA_VORGABE,
    KV_VORGABE,
    MAX_FAEDEN,
    Feineinstellungen,
    flags,
)


def test_vorgaben_sagen_nichts():
    """A command with nothing set looks as it did before the section existed."""
    assert flags(Feineinstellungen()) == []
    assert flags(None) == []


def test_kv_cache_setzt_beide_haelften():
    zeile = flags(Feineinstellungen(kv_cache="q8_0"))
    assert zeile == ["--cache-type-k", "q8_0", "--cache-type-v", "q8_0"]


def test_kv_cache_vorgabe_bleibt_stumm():
    assert flags(Feineinstellungen(kv_cache=KV_VORGABE)) == []


def test_flash_attention_nur_wenn_abweichend():
    assert flags(Feineinstellungen(flash_attention=FA_VORGABE)) == []
    assert flags(Feineinstellungen(flash_attention="on")) == ["--flash-attn", "on"]
    assert flags(Feineinstellungen(flash_attention="off")) == ["--flash-attn", "off"]


def test_faeden():
    assert flags(Feineinstellungen(faeden=8)) == ["--threads", "8"]
    assert flags(Feineinstellungen(faeden=None)) == []


def test_moe_ohne_zahl_nimmt_alles():
    assert flags(Feineinstellungen(moe_auf_cpu=True)) == ["--cpu-moe"]


def test_moe_mit_zahl_nimmt_die_ersten_schichten():
    zeile = flags(Feineinstellungen(moe_auf_cpu=True, moe_schichten=12))
    assert zeile == ["--n-cpu-moe", "12"]


def test_moe_zahl_ohne_schalter_bleibt_stumm():
    assert flags(Feineinstellungen(moe_schichten=12)) == []


def test_festnageln_nutzt_die_nicht_veraltete_form():
    """`--mlock` is deprecated in the shipped build; this is its replacement."""
    assert flags(Feineinstellungen(festnageln=True)) == ["--load-mode", "mmap+mlock"]


def test_alles_zusammen_bleibt_lesbar():
    zeile = flags(Feineinstellungen(
        kv_cache="q4_0", flash_attention="on", faeden=6,
        moe_auf_cpu=True, moe_schichten=4, festnageln=True,
    ))
    assert zeile == [
        "--cache-type-k", "q4_0", "--cache-type-v", "q4_0",
        "--flash-attn", "on",
        "--threads", "6",
        "--n-cpu-moe", "4",
        "--load-mode", "mmap+mlock",
    ]


# --- What arrives from the window ------------------------------------------


def test_unbekannter_cache_faellt_auf_die_vorgabe():
    """A name that is not a name must never reach the command line."""
    e = Feineinstellungen.aus_daten({"kv_cache": "q1_unfug"})
    assert e.kv_cache == KV_VORGABE
    assert flags(e) == []


def test_unbekannte_flash_wahl_faellt_zurueck():
    assert Feineinstellungen.aus_daten({"flash_attention": "vielleicht"}).flash_attention == FA_VORGABE


@pytest.mark.parametrize("roh,erwartet", [(0, None), ("", None), (None, None), (-3, 1), (99999, MAX_FAEDEN)])
def test_faeden_werden_in_den_bereich_geholt(roh, erwartet):
    assert Feineinstellungen.aus_daten({"faeden": roh}).faeden == erwartet


def test_kaputte_zahlen_werden_zu_nichts():
    e = Feineinstellungen.aus_daten({"faeden": "acht", "moe_schichten": "viele"})
    assert e.faeden is None
    assert e.moe_schichten is None


def test_leere_daten_sind_die_vorgaben():
    assert Feineinstellungen.aus_daten(None).als_daten() == Feineinstellungen().als_daten()


def test_hin_und_zurueck():
    e = Feineinstellungen(kv_cache="q8_0", flash_attention="on", faeden=4,
                          moe_auf_cpu=True, moe_schichten=2, festnageln=True)
    assert Feineinstellungen.aus_daten(e.als_daten()).als_daten() == e.als_daten()
