"""A drawing job as an entry in the chat's little history."""

from __future__ import annotations

from app import bildlauf
from app.bildlauf import MAX_ZEICHEN, kurzform
from app.tools.hintergrund import ABGEBROCHEN, ART_BEFEHL, ART_BILD, FEHLER, FERTIG, laeufe


def test_kurzform_laesst_kurze_prompts_in_ruhe():
    assert kurzform("ein rotes Fahrrad") == "ein rotes Fahrrad"


def test_kurzform_macht_eine_zeile_daraus():
    assert kurzform("  ein  rotes\nFahrrad  ") == "ein rotes Fahrrad"


def test_kurzform_kuerzt_an_der_wortgrenze():
    lang = " ".join(["Fahrrad"] * 40)
    kurz = kurzform(lang)
    assert len(kurz) <= MAX_ZEICHEN + 1
    assert kurz.endswith("…")
    # Cut between words, not through one.
    assert not kurz[:-1].endswith("Fahrra")


def test_ohne_chat_kein_eintrag():
    assert bildlauf.beginnen(None, "egal") is None
    # And closing that non-entry is allowed and does nothing.
    bildlauf.beenden(None)


def test_lauf_erscheint_und_endet_fertig():
    lauf = bildlauf.beginnen("chat-bild-1", "ein rotes Fahrrad im Regen")
    assert lauf is not None
    assert lauf.art == ART_BILD
    assert lauf.zustand == "laeuft"
    assert laeufe.laeufe("chat-bild-1")[-1].befehl == "ein rotes Fahrrad im Regen"

    bildlauf.beenden(lauf)
    assert lauf.zustand == FERTIG
    assert lauf.dauer_sekunden is not None and lauf.dauer_sekunden >= 0
    laeufe.vergessen("chat-bild-1")


def test_gescheiterter_lauf_ist_rot_abgebrochener_nicht():
    a = bildlauf.beginnen("chat-bild-2", "kaputt")
    bildlauf.beenden(a, gescheitert=True)
    assert a.zustand == FEHLER

    b = bildlauf.beginnen("chat-bild-2", "gestoppt")
    bildlauf.beenden(b, abgebrochen=True)
    assert b.zustand == ABGEBROCHEN
    laeufe.vergessen("chat-bild-2")


def test_befehlslaeufe_bleiben_befehle():
    """The registry learned a word, not a second behaviour."""
    lauf = laeufe.anlegen("chat-bild-3", "ls -la")
    assert lauf.art == ART_BEFEHL
    laeufe.beenden(lauf, code=0)
    assert lauf.zustand == FERTIG
    assert lauf.dauer_sekunden is not None
    laeufe.vergessen("chat-bild-3")


def test_zuschauer_erfahren_art_und_dauer():
    """What the terminal module draws has to arrive over the stream."""
    gesehen = []
    laeufe._zuschauer.setdefault("chat-bild-4", set())
    import asyncio

    schlange = asyncio.Queue()
    laeufe._zuschauer["chat-bild-4"].add(schlange)
    try:
        lauf = bildlauf.beginnen("chat-bild-4", "ein Bild")
        bildlauf.beenden(lauf)
        while not schlange.empty():
            gesehen.append(schlange.get_nowait())
    finally:
        laeufe._zuschauer["chat-bild-4"].discard(schlange)
        laeufe.vergessen("chat-bild-4")

    start = next(e for e in gesehen if e["typ"] == "lauf_start")
    ende = next(e for e in gesehen if e["typ"] == "lauf_ende")
    assert start["art"] == ART_BILD
    assert ende["dauer_sekunden"] is not None
