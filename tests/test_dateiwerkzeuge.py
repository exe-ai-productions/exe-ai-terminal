"""The built-in file tools: read_file, write_file, edit_file, list_dir.

What matters here is the boundary and the refusals, not the happy path:

* inside a shared folder nothing asks, outside it the confirmation appears,
  and without any shared folder the tools stay shut,
* edit_file refuses both the passage it cannot find and the one it finds
  twice — a silent guess would change the wrong line,
* read_file refuses a binary file instead of handing back replacement
  characters,
* and the listings stop before they fill the whole context.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tools import (
    datei_aendern,
    datei_lesen,
    datei_schreiben,
    dateiwerkzeuge,
    grenzen,
    ordner_lesen,
)


def lauf(coro):
    return asyncio.run(coro)


@pytest.fixture()
def ordner(tmp_path):
    (tmp_path / "notizen").mkdir()
    (tmp_path / "notizen" / "liste.md").write_text("eins\nzwei\ndrei\n", encoding="utf-8")
    return [str(tmp_path)]


# --- The boundary ----------------------------------------------------------


@pytest.mark.parametrize("modul", dateiwerkzeuge.MODULE)
def test_ohne_freigabe_bleibt_alles_zu(modul):
    with pytest.raises(grenzen.GrenzeVerletzt):
        lauf(modul.ausfuehren({"path": "irgendwas.txt", "content": "x", "old_text": "a", "new_text": "b"}, []))


@pytest.mark.parametrize("modul", dateiwerkzeuge.MODULE)
def test_innerhalb_fragt_nichts(modul, ordner):
    assert modul.braucht_bestaetigung({"path": "notizen/liste.md"}, ordner) is False


@pytest.mark.parametrize("modul", dateiwerkzeuge.MODULE)
def test_ausserhalb_fragt_nach(modul, ordner):
    assert modul.braucht_bestaetigung({"path": "/etc/hosts"}, ordner) is True
    assert modul.aussenpfad({"path": "../draussen.txt"}, ordner) is not None


def test_ohne_freigabe_wird_nicht_gefragt(ordner):
    """No folder means the tool does not run at all — there is nothing to
    confirm either."""
    assert datei_lesen.braucht_bestaetigung({"path": "/etc/hosts"}, []) is False


# --- read_file -------------------------------------------------------------


def test_lesen_gibt_die_kopfzeile_mit(ordner):
    text = lauf(datei_lesen.ausfuehren({"path": "notizen/liste.md"}, ordner))
    assert text.startswith("lines 1–3 of 3")
    assert "zwei" in text


def test_lesen_mit_ausschnitt(ordner):
    text = lauf(datei_lesen.ausfuehren({"path": "notizen/liste.md", "offset": 2, "limit": 1}, ordner))
    assert text.splitlines() == ["lines 2–2 of 3", "zwei"]


def test_lesen_kappt_lange_dateien(ordner, tmp_path):
    (tmp_path / "lang.txt").write_text(("x" * 100 + "\n") * 500, encoding="utf-8")
    text = lauf(datei_lesen.ausfuehren({"path": "lang.txt"}, ordner))
    assert "continue with offset" in text
    assert len(text) < datei_lesen.MAX_ZEICHEN + 500


def test_lesen_lehnt_binaerdateien_ab(ordner, tmp_path):
    (tmp_path / "bild.bin").write_bytes(b"\x89PNG\x00\x01\x02")
    with pytest.raises(grenzen.GrenzeVerletzt) as fehler:
        lauf(datei_lesen.ausfuehren({"path": "bild.bin"}, ordner))
    assert "binary" in str(fehler.value)


def test_lesen_verweist_bei_ordnern_weiter(ordner):
    with pytest.raises(grenzen.GrenzeVerletzt) as fehler:
        lauf(datei_lesen.ausfuehren({"path": "notizen"}, ordner))
    assert "list_dir" in str(fehler.value)


# --- write_file ------------------------------------------------------------


def test_schreiben_legt_elternordner_an(ordner, tmp_path):
    antwort = lauf(
        datei_schreiben.ausfuehren({"path": "neu/tief/datei.txt", "content": "hallo\n"}, ordner)
    )
    assert (tmp_path / "neu" / "tief" / "datei.txt").read_text(encoding="utf-8") == "hallo\n"
    assert antwort.startswith("Created")


def test_schreiben_sagt_wenn_es_ueberschreibt(ordner):
    lauf(datei_schreiben.ausfuehren({"path": "a.txt", "content": "eins"}, ordner))
    antwort = lauf(datei_schreiben.ausfuehren({"path": "a.txt", "content": "zwei"}, ordner))
    assert antwort.startswith("Overwrote")


# --- edit_file -------------------------------------------------------------


def test_aendern_trifft_genau_einmal(ordner, tmp_path):
    antwort = lauf(
        datei_aendern.ausfuehren(
            {"path": "notizen/liste.md", "old_text": "zwei", "new_text": "ZWEI"}, ordner
        )
    )
    assert "line 2" in antwort
    assert (tmp_path / "notizen" / "liste.md").read_text(encoding="utf-8") == "eins\nZWEI\ndrei\n"


def test_aendern_ohne_treffer(ordner):
    with pytest.raises(grenzen.GrenzeVerletzt) as fehler:
        lauf(
            datei_aendern.ausfuehren(
                {"path": "notizen/liste.md", "old_text": "vier", "new_text": "x"}, ordner
            )
        )
    assert "not found" in str(fehler.value)


def test_aendern_bei_mehreren_treffern(ordner, tmp_path):
    (tmp_path / "doppelt.txt").write_text("a\na\n", encoding="utf-8")
    with pytest.raises(grenzen.GrenzeVerletzt) as fehler:
        lauf(datei_aendern.ausfuehren({"path": "doppelt.txt", "old_text": "a", "new_text": "b"}, ordner))
    assert "2 times" in str(fehler.value)
    assert (tmp_path / "doppelt.txt").read_text(encoding="utf-8") == "a\na\n"


# --- list_dir --------------------------------------------------------------


def test_ordner_lesen_nimmt_den_ersten_freigegebenen(ordner):
    text = lauf(ordner_lesen.ausfuehren({}, ordner))
    assert "notizen/" in text


def test_ordner_lesen_zeigt_verstecktes_und_groessen(ordner, tmp_path):
    (tmp_path / ".versteckt").write_text("x", encoding="utf-8")
    text = lauf(ordner_lesen.ausfuehren({}, ordner))
    assert ".versteckt" in text
    assert "1 B" in text


def test_ordner_lesen_geht_in_die_tiefe(ordner):
    flach = lauf(ordner_lesen.ausfuehren({}, ordner))
    tief = lauf(ordner_lesen.ausfuehren({"depth": 2}, ordner))
    assert "liste.md" not in flach
    assert "liste.md" in tief


def test_ordner_lesen_kappt_lange_listen(ordner, tmp_path):
    for nummer in range(ordner_lesen.MAX_EINTRAEGE + 20):
        (tmp_path / f"datei-{nummer:04}.txt").write_text("x", encoding="utf-8")
    text = lauf(ordner_lesen.ausfuehren({}, ordner))
    assert "stopped at" in text
