"""The memory tool: what it writes, and what it refuses.

The interesting half is what it CANNOT do. A tool that can hand over whole
file contents can also wipe the memory in one call, and a rule that slips in
without a yes sits in every later request — that is the difference between a
memory and a permanent prompt injection.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tools import memory
from app.tools.registry import WerkzeugRegistry, WerkzeugVerboten


# --- Writing the text, without a disk ----------------------------------------


def test_ein_faktum_landet_unter_seiner_ueberschrift():
    neu = memory.eintragen("", "Arbeitet an einem festen Schreibtisch.", memory.FAKTUM)
    assert "## Facts" in neu
    assert "- Arbeitet an einem festen Schreibtisch." in neu
    assert "## Rules" not in neu


def test_eine_regel_landet_unter_ihrer():
    neu = memory.eintragen("", "Kommentare auf Englisch.", memory.REGEL)
    assert neu.startswith("## Rules")
    assert "- Kommentare auf Englisch." in neu


def test_bestehendes_bleibt_stehen():
    alt = "## Rules\n- Erste Regel.\n\n## Facts\n- Erstes Faktum."
    neu = memory.eintragen(alt, "Zweites Faktum.", memory.FAKTUM)
    assert "- Erste Regel." in neu
    assert "- Erstes Faktum." in neu
    assert "- Zweites Faktum." in neu


def test_dasselbe_zweimal_bleibt_einmal():
    alt = "## Facts\n- Arbeitet am Schreibtisch."
    assert memory.eintragen(alt, "Arbeitet am Schreibtisch.", memory.FAKTUM).count("Arbeitet am Schreibtisch.") == 1


def test_ersetzen_tauscht_statt_anzuhaengen():
    """The case that decides whether the memory gets smarter or only fuller."""
    alt = "## Rules\n- Kommentare auf Deutsch."
    neu = memory.eintragen(
        alt, "Kommentare auf Englisch.", memory.REGEL, ersetzt="Kommentare auf Deutsch."
    )
    assert "Deutsch" not in neu
    assert "- Kommentare auf Englisch." in neu


def test_ersetzen_findet_den_eintrag_auch_unter_der_anderen_ueberschrift():
    """A sentence can change from being knowledge to being an instruction."""
    alt = "## Facts\n- Mag kurze Berichte."
    neu = memory.eintragen(
        alt, "Berichte kurz halten.", memory.REGEL, ersetzt="Mag kurze Berichte."
    )
    assert "Mag kurze Berichte." not in neu
    assert neu.startswith("## Rules")


def test_ein_unbekannter_ersetzt_wert_loescht_nichts():
    alt = "## Facts\n- Erstes Faktum."
    neu = memory.eintragen(alt, "Zweites.", memory.FAKTUM, ersetzt="Gibt es nicht.")
    assert "- Erstes Faktum." in neu
    assert "- Zweites." in neu


# --- Rules ask, facts do not -------------------------------------------------


def test_nichts_davon_fragt_nach():
    """One prompt in the whole program, and it is the shell reaching outside
    the shared folders. A prompt that comes ten times a session gets clicked
    away without reading, and then it protects nothing — what protects the
    memory instead is that it is visible and can be deleted in a click."""
    for art in ("rule", "fact", None):
        argumente = {"text": "x"} | ({"kind": art} if art else {})
        assert memory.braucht_bestaetigung(argumente) is False


# --- What it refuses ---------------------------------------------------------


def test_ohne_text_wird_nichts_geschrieben(tmp_path):
    pfad = tmp_path / "memory.md"
    with pytest.raises(memory.MemoryVerboten):
        asyncio.run(memory.ausfuehren({"text": "  ", "kind": "fact"}, pfad))
    assert not pfad.exists()


def test_ein_ganzes_dokument_wird_abgewiesen(tmp_path):
    pfad = tmp_path / "memory.md"
    lang = "x" * (memory.MAX_LAENGE + 1)
    with pytest.raises(memory.MemoryVerboten):
        asyncio.run(memory.ausfuehren({"text": lang, "kind": "fact"}, pfad))
    assert not pfad.exists()


def test_es_gibt_keinen_weg_die_datei_zu_leeren(tmp_path):
    """No parameter hands over whole content and none deletes. Clearing the
    memory is the user's move, in the settings window."""
    felder = set(memory.werkzeug_beschreibung().schema["properties"])
    assert felder == {"text", "kind", "replaces"}


# --- The way through the registry --------------------------------------------


def test_die_registry_bietet_es_an_und_fuehrt_es_aus(tmp_path):
    pfad = tmp_path / "memory.md"
    registry = WerkzeugRegistry([], memory_pfad=pfad)

    namen = [w["function"]["name"] for w in registry.als_openai_werkzeuge()]
    assert namen == [memory.WERKZEUG_NAME]

    antwort = asyncio.run(
        registry.ausfuehren(memory.WERKZEUG_NAME, {"text": "Heißt Prüfstein.", "kind": "fact"})
    )
    assert antwort == "Saved."
    assert "- Heißt Prüfstein." in pfad.read_text()


def test_ohne_pfad_gibt_es_das_werkzeug_nicht(tmp_path):
    registry = WerkzeugRegistry([])
    assert registry.als_openai_werkzeuge() == []
    with pytest.raises(WerkzeugVerboten):
        asyncio.run(registry.ausfuehren(memory.WERKZEUG_NAME, {"text": "x", "kind": "fact"}))


def test_abgeschaltet_wird_es_weder_angeboten_noch_ausgefuehrt(tmp_path):
    registry = WerkzeugRegistry([], memory_pfad=tmp_path / "memory.md")
    registry.abgeschaltet = {memory.WERKZEUG_NAME}
    assert registry.als_openai_werkzeuge() == []
    with pytest.raises(WerkzeugVerboten):
        asyncio.run(registry.ausfuehren(memory.WERKZEUG_NAME, {"text": "x", "kind": "fact"}))


def test_die_registry_haelt_das_gedaechtnis_ebenfalls_frei(tmp_path):
    registry = WerkzeugRegistry([], memory_pfad=tmp_path / "memory.md")
    for argumente in ({"text": "x", "kind": "rule"}, {"text": "x", "kind": "fact"}):
        assert registry.braucht_bestaetigung(memory.WERKZEUG_NAME, argumente) is False
        assert registry.bestaetigungsgrund(memory.WERKZEUG_NAME, argumente) is None
